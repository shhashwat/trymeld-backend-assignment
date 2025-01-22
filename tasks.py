from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery('tasks', broker=os.getenv('REDIS_URL'))

@celery_app.task
def log_access(text):
    from models import AccessLog
    from database import SessionLocal

    db = SessionLocal()
    access_log = AccessLog(text=text)
    db.add(access_log)
    db.commit()
    db.close()