from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

from backend.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    profile = relationship("Profile", back_populates="user", uselist=False)

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    key = Column(String, default="individual")
    label = Column(String, default="Individual")
    persona = Column(String, default="")
    currency = Column(String, default="₹")
    
    # We store these as JSON to easily adapt to the frontend's dynamic structure
    metrics = Column(JSON, default=[])
    goal = Column(JSON, default={})
    decisionTypes = Column(JSON, default=[])
    
    user = relationship("User", back_populates="profile")
    alerts = relationship("Alert", back_populates="profile")
    history = relationship("DecisionHistory", back_populates="profile")
    audit_traces = relationship("AuditTrace", back_populates="profile")

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"))
    level = Column(String) # 'warn', 'info'
    text = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    profile = relationship("Profile", back_populates="alerts")

class DecisionHistory(Base):
    __tablename__ = "decision_history"
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"))
    title = Column(String)
    date_str = Column(String)
    outcome = Column(String)
    tag = Column(String) # 'good', 'warn'
    
    profile = relationship("Profile", back_populates="history")

class AuditTrace(Base):
    __tablename__ = "audit_traces"
    id = Column(String, primary_key=True) # UUID for request_id
    profile_id = Column(Integer, ForeignKey("profiles.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    query = Column(String)
    response = Column(JSON)
    reasoning_trace = Column(JSON)
    sources = Column(JSON)
    
    profile = relationship("Profile", back_populates="audit_traces")

class MarketData(Base):
    __tablename__ = "market_data"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    asset_type = Column(String) # 'stock', 'forex', 'mutual_fund'
    price = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

class NewsItem(Base):
    __tablename__ = "news_items"
    id = Column(Integer, primary_key=True, index=True)
    headline = Column(String)
    summary = Column(String)
    sentiment = Column(String) # 'positive', 'neutral', 'negative'
    category = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class EconomicIndicator(Base):
    __tablename__ = "economic_indicators"
    id = Column(Integer, primary_key=True, index=True)
    indicator_name = Column(String, index=True)
    value = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
