from fastapi import FastAPI, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, exc
from models import Category, ReviewHistory, AccessLog, Base
from database import SessionLocal, engine
from celery import Celery
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
import logging
import anthropic
from anthropic import Anthropic, APIError

# Load environment variables
load_dotenv()

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize FastAPI
app = FastAPI()

# Configure Celery properly
celery_app = Celery(
    'main',
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL")
)
celery_app.conf.update(
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    imports=['main']
)

# Database setup
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models
class CategoryCreate(BaseModel):
    name: str
    description: str

class ReviewCreate(BaseModel):
    text: str
    stars: int
    review_id: str
    category_id: int

class ReviewResponse(BaseModel):
    id: int
    text: str
    stars: int
    review_id: str
    created_at: datetime
    tone: Optional[str] = None
    sentiment: Optional[str] = None
    category_id: int

class TrendResponse(BaseModel):
    id: int
    name: str
    description: str
    average_stars: float
    total_reviews: int

# Celery tasks
@celery_app.task
def compute_tone_sentiment(review_id: int):
    db = SessionLocal()
    try:
        review = db.query(ReviewHistory).filter(ReviewHistory.id == review_id).first()
        if not review:
            logger.error(f"Review {review_id} not found")
            return

        # Analyze sentiment and tone using Claude
        prompt = f"""Analyze this product review (rated {review.stars}/10 stars):
        Review text: "{review.text}"
        
        Return JSON with:
        - "tone": main emotional tone (e.g., positive, negative, neutral)
        - "sentiment": overall sentiment (positive, negative, neutral)"""

        response = client.completions.create(
            model="claude-2",  # Use the latest Claude model
            prompt=prompt,
            max_tokens_to_sample=300,
            temperature=0.7,
        )

        # Parse the response
        content = response.completion.strip()
        content = content.replace('```json', '').replace('```', '').strip()
        result = json.loads(content)
        
        review.tone = result.get("tone", "neutral").lower()
        review.sentiment = result.get("sentiment", "neutral").lower()

        db.commit()
        db.refresh(review)
        logger.info(f"Processed review {review_id}: tone={review.tone}, sentiment={review.sentiment}")

    except json.JSONDecodeError as e:
        logger.error(f"JSON Error (Review {review_id}): {content}")
    except APIError as e:
        logger.error(f"Anthropic API error processing review {review_id}: {str(e)}")
        db.rollback()
    except Exception as e:
        logger.error(f"Error processing review {review_id}: {str(e)}")
        db.rollback()
    finally:
        db.close()
        
# API Endpoints
@app.post("/categories/", response_model=CategoryCreate, status_code=status.HTTP_201_CREATED)
async def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    try:
        existing = db.query(Category).filter(func.lower(Category.name) == func.lower(category.name)).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category with this name already exists"
            )

        db_category = Category(**category.dict())
        db.add(db_category)
        db.commit()
        db.refresh(db_category)
        return db_category
    except exc.IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category with this name already exists"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating category: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating category"
        )

@app.get("/categories/", response_model=List[CategoryCreate])
async def get_categories(db: Session = Depends(get_db)):
    return db.query(Category).all()

@app.post("/reviews/reprocess")
async def reprocess_reviews(db: Session = Depends(get_db)):
    try:
        reviews = db.query(ReviewHistory).filter(
            (ReviewHistory.tone == None) | 
            (ReviewHistory.sentiment == None)
        ).all()
        
        for review in reviews:
            compute_tone_sentiment.delay(review.id)
            
        return {"message": f"Queued {len(reviews)} reviews for reprocessing"}
    except Exception as e:
        logger.error(f"Reprocessing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Reprocessing failed")

@app.post("/reviews/", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(review: ReviewCreate, db: Session = Depends(get_db)):
    try:
        if not db.query(Category).filter(Category.id == review.category_id).first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )

        db_review = ReviewHistory(
            **review.dict(exclude={'tone', 'sentiment'}),
            tone=None,
            sentiment=None
        )
        db.add(db_review)
        db.commit()
        db.refresh(db_review)

        compute_tone_sentiment.delay(db_review.id)
        return db_review
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating review: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating review"
        )

@app.get("/reviews/", response_model=List[ReviewResponse])
async def get_reviews(
    category_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(ReviewHistory)
        if category_id is not None:
            query = query.filter(ReviewHistory.category_id == category_id)
        
        reviews = query.order_by(ReviewHistory.created_at.desc()).all()
        
        log_text = f"GET /reviews/?category_id={category_id}" if category_id else "GET /reviews/"
        log_access.delay(log_text)
        
        return reviews
    except Exception as e:
        logger.error(f"Error fetching reviews: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching reviews"
        )

@app.get("/reviews/trends", response_model=List[TrendResponse])
async def get_reviews_trends(db: Session = Depends(get_db)):
    try:
        subquery = (
            db.query(
                ReviewHistory.review_id,
                func.max(ReviewHistory.created_at).label('latest_created_at')
            )
            .group_by(ReviewHistory.review_id)
            .subquery()
        )

        latest_reviews = (
            db.query(ReviewHistory)
            .join(
                subquery,
                (ReviewHistory.review_id == subquery.c.review_id) &
                (ReviewHistory.created_at == subquery.c.latest_created_at)
            )
            .subquery()
        )

        trends = (
            db.query(
                Category.id,
                Category.name,
                Category.description,
                func.avg(latest_reviews.c.stars).label('average_stars'),
                func.count(latest_reviews.c.id).label('total_reviews')
            )
            .join(latest_reviews, Category.id == latest_reviews.c.category_id)
            .group_by(Category.id)
            .order_by(func.avg(latest_reviews.c.stars).desc())
            .limit(5)
            .all()
        )

        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "average_stars": round(t.average_stars, 2),
                "total_reviews": t.total_reviews
            }
            for t in trends
        ]
    except Exception as e:
        logger.error(f"Error fetching trends: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching trends"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
