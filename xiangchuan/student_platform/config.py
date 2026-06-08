import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

JWT_SECRET = os.getenv("STUDENT_JWT_SECRET", "student-platform-secret-dev")
JWT_ALGORITHM = "HS256"
STUDENT_TOKEN_EXPIRE_DAYS = 7
ADMIN_TOKEN_EXPIRE_HOURS = 24
ADMIN_KEY = os.getenv("STUDENT_ADMIN_KEY", "admin123456")
DATABASE_URL = os.getenv("STUDENT_DATABASE_URL", "sqlite:///./student_platform.db")
