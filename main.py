from fastapi import FastAPI, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Category, ReviewHistory, AccessLog, Base
from database import SessionLocal, engine
from celery import Celery
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from models import Base

# Create tables if they don't exist
def create_tables():
    Base.metadata.create_all(bind=engine)

create_tables()

load_dotenv()

app = FastAPI()

# Celery configuration
celery_app = Celery('tasks', broker=os.getenv('REDIS_URL'))

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@celery_app.task
def log_access(text):
    db = SessionLocal()
    access_log = AccessLog(text=text)
    db.add(access_log)
    db.commit()
    db.close()

# Pydantic models for request bodies
class CategoryCreate(BaseModel):
    name: str
    description: str

class ReviewCreate(BaseModel):
    text: str
    stars: int
    review_id: str
    tone: Optional[str] = None
    sentiment: Optional[str] = None
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

@app.get("/")
async def root():
    return {"message": "Welcome to the Reviews API!"}

@app.post("/categories/", response_model=CategoryCreate)
async def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    db_category = Category(name=category.name, description=category.description)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@app.get("/categories/", response_model=List[CategoryCreate])
async def get_categories(db: Session = Depends(get_db)):
    categories = db.query(Category).all()
    return categories

@app.post("/reviews/", response_model=ReviewResponse)
async def create_review(review: ReviewCreate, db: Session = Depends(get_db)):
    # Check if the category exists
    category = db.query(Category).filter(Category.id == review.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    db_review = ReviewHistory(
        text=review.text,
        stars=review.stars,
        review_id=review.review_id,
        tone=review.tone,
        sentiment=review.sentiment,
        category_id=review.category_id
    )
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return db_review

@app.get("/reviews/", response_model=List[ReviewResponse])
async def get_reviews(category_id: Optional[int] = None, db: Session = Depends(get_db)):
    if category_id:
        reviews = db.query(ReviewHistory).filter(ReviewHistory.category_id == category_id).all()
    else:
        reviews = db.query(ReviewHistory).all()
    return reviews

@app.get("/reviews/trends", response_model=List[TrendResponse])
async def get_reviews_trends(db: Session = Depends(get_db)):
    # Query to get the top 5 categories based on average stars
    subquery = db.query(
        ReviewHistory.review_id,
        func.max(ReviewHistory.created_at).label('latest_created_at')
    ).group_by(ReviewHistory.review_id).subquery()

    latest_reviews = db.query(ReviewHistory).join(
        subquery,
        (ReviewHistory.review_id == subquery.c.review_id) &
        (ReviewHistory.created_at == subquery.c.latest_created_at)
    ).subquery()

    trends = db.query(
        Category.id,
        Category.name,
        Category.description,
        func.avg(latest_reviews.c.stars).label('average_stars'),
        func.count(latest_reviews.c.id).label('total_reviews')
    ).join(latest_reviews, Category.id == latest_reviews.c.category_id).group_by(Category.id).order_by(func.avg(latest_reviews.c.stars).desc()).limit(5).all()

    # Log access asynchronously
    log_access.delay("GET /reviews/trends")

    return [{
        "id": trend.id,
        "name": trend.name,
        "description": trend.description,
        "average_stars": trend.average_stars,
        "total_reviews": trend.total_reviews
    } for trend in trends]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)