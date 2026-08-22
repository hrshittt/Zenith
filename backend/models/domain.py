from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, JSON, Text, UniqueConstraint
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
    chat_sessions = relationship("ChatSession", back_populates="profile")
    startup_profile = relationship("StartupProfile", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    startup_snapshots = relationship("StartupMetricSnapshot", back_populates="profile", cascade="all, delete-orphan")
    startup_transactions = relationship("StartupTransaction", back_populates="profile", cascade="all, delete-orphan")
    startup_decisions = relationship("StartupDecisionLog", back_populates="profile", cascade="all, delete-orphan")
    startup_weekly_reports = relationship("StartupWeeklyReport", cascade="all, delete-orphan")

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

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(String, primary_key=True) # UUID
    profile_id = Column(Integer, ForeignKey("profiles.id"))
    title = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    profile = relationship("Profile", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", order_by="ChatMessage.created_at", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"))
    role = Column(String) # 'user' or 'twin'
    content = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


# ---------------------------------------------------------------------------
# Startup journey — kept fully separate from the Individual profile's
# metrics/goal/decisionTypes JSON blobs above. All financial fields are
# nullable: onboarding never fabricates a value the founder didn't provide.
# ---------------------------------------------------------------------------

class StartupProfile(Base):
    __tablename__ = "startup_profiles"
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), unique=True, index=True)

    # Founder
    founder_name = Column(String)
    founder_email = Column(String)
    founder_mobile = Column(String)
    preferred_language = Column(String)

    # Company
    company_name = Column(String)
    industry = Column(String)
    business_model = Column(String)
    founded_year = Column(Integer)
    stage = Column(String)
    location = Column(String)
    website = Column(String)
    headcount = Column(Integer)  # current headcount — also Team > Current Headcount

    # Revenue
    is_pre_revenue = Column(Boolean, default=False)
    monthly_revenue = Column(Float)
    revenue_streams = Column(JSON, default=[])
    revenue_growth_pct_input = Column(Float)  # founder-estimated MoM growth %, used until real history exists
    paying_customers = Column(Integer)

    # Expenses
    fixed_costs = Column(Float)
    variable_costs = Column(Float)

    # Cash
    current_cash = Column(Float)
    monthly_burn_input = Column(Float)  # fallback gross burn if fixed/variable costs weren't itemized

    # Debt
    business_loans_debt = Column(Float)

    # Funding
    total_funding = Column(Float)
    last_round = Column(String)
    currently_fundraising = Column(Boolean, default=False)
    fundraising_target = Column(Float)

    # Team
    planned_hires = Column(Integer)
    cost_per_hire = Column(Float)  # fully-loaded monthly cost per hire

    # Goals — list of {type, label, target_value, target_unit, target_date}
    goals = Column(JSON, default=[])

    # Current financial decision the founder is weighing at onboarding time
    current_decision = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="startup_profile")


class StartupMetricSnapshot(Base):
    __tablename__ = "startup_metric_snapshots"
    __table_args__ = (UniqueConstraint("profile_id", "snapshot_date", name="uq_startup_snapshot_profile_date"),)
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), index=True)
    snapshot_date = Column(Date, index=True)
    cash = Column(Float)
    gross_burn = Column(Float)
    net_burn = Column(Float)
    revenue = Column(Float)
    runway_months = Column(Float)
    financial_health_score = Column(Float)
    raw = Column(JSON, default={})  # full computed metric bundle, for report reuse
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("Profile", back_populates="startup_snapshots")


class StartupTransaction(Base):
    """Hisaab ledger — money in / money out, categorized."""
    __tablename__ = "startup_transactions"
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), index=True)
    type = Column(String)  # 'in' | 'out'
    category = Column(String)
    amount = Column(Float)
    description = Column(String)
    txn_date = Column(Date, default=lambda: datetime.utcnow().date())
    source = Column(String, default="manual")  # 'manual' | 'auto' (Gmail, later)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="startup_transactions")


class StartupDecisionLog(Base):
    """Recent Decisions — every onboarded/simulated startup decision, with its computed outcome."""
    __tablename__ = "startup_decision_log"
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), index=True)
    title = Column(String)
    decision_type = Column(String)
    scenario_text = Column(String)
    result_summary = Column(JSON, default={})
    tag = Column(String)  # 'good' | 'warn' | 'neutral'
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("Profile", back_populates="startup_decisions")


class StartupWeeklyReport(Base):
    """A saved snapshot of a Mon-Sun weekly spend + suggestions report. One row
    per (profile, week_start) — idempotent, generated on-demand and cached here
    so past weeks' reports stay stable even as new transactions get logged."""
    __tablename__ = "startup_weekly_reports"
    __table_args__ = (UniqueConstraint("profile_id", "week_start", name="uq_weekly_report_profile_week"),)
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), index=True)
    week_start = Column(Date, index=True)  # Monday
    week_end = Column(Date)                # Sunday
    currency = Column(String, default="₹")
    category_spend = Column(JSON, default={})
    flags = Column(JSON, default=[])
    suggestions = Column(JSON, default=[])
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("Profile")
