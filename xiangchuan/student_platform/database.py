from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta
import secrets

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    age = Column(Integer, nullable=False)
    parent_email = Column(String(200), nullable=True)
    parent_name = Column(String(100), nullable=True)
    parent_consent = Column(Boolean, default=False)
    parent_token = Column(String(100), nullable=True)
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=True)
    points_balance = Column(Integer, default=0)
    total_earned = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    parent = relationship("Parent", back_populates="children")
    submissions = relationship("TaskSubmission", back_populates="student", foreign_keys="TaskSubmission.student_id")
    transactions = relationship("Transaction", back_populates="student")
    redemptions = relationship("Redemption", back_populates="student")


class Parent(Base):
    __tablename__ = "parents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    phone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    children = relationship("Student", back_populates="parent")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    points_reward = Column(Integer, nullable=False)
    category = Column(String(50), nullable=False)
    icon = Column(String(10), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    daily_limit = Column(Integer, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    submissions = relationship("TaskSubmission", back_populates="task")


class TaskSubmission(Base):
    __tablename__ = "task_submissions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    status = Column(String(20), default="pending")
    proof_text = Column(Text, nullable=True)
    reviewer_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    points_awarded = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)

    student = relationship("Student", back_populates="submissions", foreign_keys=[student_id])
    task = relationship("Task", back_populates="submissions")


class Reward(Base):
    __tablename__ = "rewards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    points_required = Column(Integer, nullable=False)
    stock = Column(Integer, default=-1)
    image_url = Column(String(500), nullable=True)
    category = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    redemptions = relationship("Redemption", back_populates="reward")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    type = Column(String(20), nullable=False)
    amount = Column(Integer, nullable=False)
    description = Column(String(500), nullable=True)
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="transactions")


class Redemption(Base):
    __tablename__ = "redemptions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    reward_id = Column(Integer, ForeignKey("rewards.id"), nullable=False)
    points_spent = Column(Integer, nullable=False)
    status = Column(String(20), default="pending")
    fulfillment_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    fulfilled_at = Column(DateTime, nullable=True)

    student = relationship("Student", back_populates="redemptions")
    reward = relationship("Reward", back_populates="redemptions")


SEED_TASKS = [
    {"title": "看廣告賺點數", "description": "觀看一則廣告影片，完成後即可獲得點數", "points_reward": 5, "category": "看廣告", "icon": "📺"},
    {"title": "寫 100 字心得", "description": "閱讀指定文章並撰寫至少 100 字心得", "points_reward": 20, "category": "寫心得", "icon": "✍️"},
    {"title": "答對 5 題測驗", "description": "完成一組 5 題的知識測驗並全部答對", "points_reward": 15, "category": "答題", "icon": "🧠"},
    {"title": "上傳創作作品", "description": "上傳你的原創作品（圖文/影音/程式），審核通過後獲得點數", "points_reward": 30, "category": "創作內容", "icon": "🎨"},
    {"title": "每日簽到", "description": "每天來平台簽到，輕鬆領取點數", "points_reward": 3, "category": "其他", "icon": "✅"},
    {"title": "推薦好友", "description": "成功邀請一位好友註冊並完成任一任務", "points_reward": 50, "category": "其他", "icon": "👫"},
]

SEED_REWARDS = [
    {"name": "Line 貼圖", "description": "任選一款 Line 貼圖（價值 NT$60）", "points_required": 60, "stock": -1, "category": "虛擬商品"},
    {"name": "超商 $50 禮券", "description": "7-11 / 全家 $50 元禮券", "points_required": 200, "stock": 50, "category": "超商禮券"},
    {"name": "誠品 $100 禮券", "description": "誠品書店 $100 元禮券", "points_required": 300, "stock": 30, "category": "超商禮券"},
    {"name": "Spotify Premium 月卡", "description": "Spotify Premium 一個月訂閱", "points_required": 500, "stock": 20, "category": "點數卡"},
    {"name": "Nintendo eShop $300 點數", "description": "Nintendo eShop 儲值金 $300", "points_required": 800, "stock": 10, "category": "點數卡"},
]


def init_db():
    Base.metadata.create_all(bind=engine)
    _seed_data()


def _seed_data():
    session = SessionLocal()
    try:
        if session.query(Task).count() == 0:
            for t in SEED_TASKS:
                task = Task(**t)
                session.add(task)

        if session.query(Reward).count() == 0:
            for r in SEED_REWARDS:
                reward = Reward(**r)
                session.add(reward)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class StudentDatabase:
    @staticmethod
    def init_db():
        init_db()

    @staticmethod
    def get_session():
        return SessionLocal()
