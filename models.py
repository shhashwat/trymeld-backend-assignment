from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Category(Base):
    __tablename__ = 'category'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True)
    description = Column(String)
    reviews = relationship('ReviewHistory', back_populates='category')

class ReviewHistory(Base):
    __tablename__ = 'review_history'
    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(String, nullable=True)
    stars = Column(Integer)
    review_id = Column(String(255))
    tone = Column(String(255), nullable=True)
    sentiment = Column(String(255), nullable=True)
    category_id = Column(Integer, ForeignKey('category.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    category = relationship('Category', back_populates='reviews')

class AccessLog(Base):
    __tablename__ = 'access_log'
    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(String)