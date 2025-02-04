# Review Management API with FastAPI and Celery

This project is a **FastAPI-based REST API** designed to manage product reviews, analyze their sentiment and tone, and provide trend analysis. It uses **Celery** for asynchronous task processing and integrates with an **LLM (Claude by Anthropic)** for sentiment and tone analysis.

---

## Features

- **Review Management**:
  - Create and retrieve product reviews.
  - Analyze reviews for sentiment (`positive`, `negative`, `neutral`) and tone (`positive`, `negative`, `neutral`).
- **Category Management**:
  - Create and retrieve categories for organizing reviews.
- **Trend Analysis**:
  - Get trends based on average review ratings and total reviews per category.
- **Asynchronous Processing**:
  - Use **Celery** for background processing of sentiment and tone analysis.
- **LLM Integration**:
  - Leverage **Claude by Anthropic** (or another LLM) for advanced sentiment and tone analysis.

---

## Technologies Used

- **Backend**: FastAPI
- **Task Queue**: Celery
- **Database**: SQLAlchemy (SQLite by default, but can be configured for other databases)
- **Caching/Message Broker**: Redis (for Celery)
- **Environment Management**: Python-dotenv
- **LLM**: Claude by Anthropic (or OpenAI, etc.)

---

## Prerequisites

Before running the project, ensure you have the following installed:

- Python 3.8+
- Redis (for Celery)
- An API key from [Anthropic](https://www.anthropic.com/) (for Claude) or another LLM provider.

---

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/review-management-api.git
cd review-management-api
```

### 2. Set Up a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables
Create a `.env` file in the root directory and add the following variables:
```env
# LLM API Key (e.g., Anthropic or OpenAI)
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Redis URL (for Celery)
REDIS_URL=redis://localhost:6379/0

# Database URL (SQLite by default)
DATABASE_URL=sqlite:///./reviews.db
```

### 5. Initialize the Database
Run the following command to create the database tables:
```bash
python -c "from database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### 6. Start Redis
Ensure Redis is running locally. You can install and start Redis using:
```bash
# On macOS (using Homebrew)
brew install redis
brew services start redis

# On Linux
sudo apt-get install redis-server
sudo service redis-server start
```

### 7. Run the Application
Start the FastAPI server and Celery worker:
```bash
# Start FastAPI
uvicorn main:app --reload

# Start Celery Worker (in a separate terminal)
celery -A main.celery_app worker --loglevel=info
```

---

## API Endpoints

### Categories
- **Create a Category**:
  - `POST /categories/`
  - Request Body:
    ```json
    {
      "name": "Electronics",
      "description": "Reviews for electronic products"
    }
    ```

- **Get All Categories**:
  - `GET /categories/`

### Reviews
- **Create a Review**:
  - `POST /reviews/`
  - Request Body:
    ```json
    {
      "text": "This product is amazing!",
      "stars": 9,
      "review_id": "12345",
      "category_id": 1
    }
    ```

- **Get All Reviews**:
  - `GET /reviews/`
  - Optional Query Parameter: `category_id` (filter reviews by category)
  - Pagination: 15 reviews per page.

- **Reprocess Reviews**:
  - `POST /reviews/reprocess`
  - Reprocesses all reviews with missing sentiment or tone analysis.

### Trends
- **Get Review Trends**:
  - `GET /reviews/trends`
  - Returns top 5 categories based on average review ratings.

---

## Example Usage

### Create a Category
```bash
curl -X POST "http://127.0.0.1:8000/categories/" \
-H "Content-Type: application/json" \
-d '{"name": "Electronics", "description": "Reviews for electronic products"}'
```

### Create a Review
```bash
curl -X POST "http://127.0.0.1:8000/reviews/" \
-H "Content-Type: application/json" \
-d '{"text": "This product is amazing!", "stars": 9, "review_id": "12345", "category_id": 1}'
```

### Get Review Trends
```bash
curl -X GET "http://127.0.0.1:8000/reviews/trends"
```

### Get Reviews by Category
```bash
curl -X GET "http://127.0.0.1:8000/reviews/?category_id=1"
```

---

## Project Structure

```
review-management-api/
├── main.py                  # FastAPI application and endpoints
├── celery_tasks.py          # Celery tasks for background processing
├── models.py                # SQLAlchemy models for database
├── database.py              # Database setup and session management
├── schemas.py               # Pydantic models for request/response validation
├── requirements.txt         # Project dependencies
├── .env                     # Environment variables
├── README.md                # Project documentation
└── tests/                   # Unit and integration tests (optional)
```

---

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) for the web framework.
- [Anthropic](https://www.anthropic.com/) for the Claude AI model.
- [Celery](https://docs.celeryproject.org/) for background task processing.

---

## Contact

For questions or feedback, feel free to reach out:
- **Shashwat Singh**
- **Email**: sshashwatssingh@gmail.com
- **GitHub**: [shhashwat](https://github.com/shhashwat)

---

Enjoy using the Review Management API! 🚀
