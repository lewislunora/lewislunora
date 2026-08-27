from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta, date
from pydantic import BaseModel, EmailStr
from typing import Optional
from jose import jwt, JWTError
import bcrypt as _bcrypt
import secrets

from .config import JWT_SECRET, JWT_ALGORITHM, STUDENT_TOKEN_EXPIRE_DAYS, ADMIN_TOKEN_EXPIRE_HOURS, ADMIN_KEY
from .database import get_db, Student, Task, TaskSubmission, Reward, Transaction, Redemption, Parent

router = APIRouter(prefix="/api/student")
security = HTTPBearer(auto_error=False)
admin_security = HTTPBearer(auto_error=False)

AUTO_APPROVE_CATEGORIES = ["看廣告", "答題"]


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    age: int
    parent_email: Optional[str] = None
    parent_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class ConsentRequest(BaseModel):
    student_email: str
    parent_token: Optional[str] = None


class TaskSubmitRequest(BaseModel):
    proof_text: Optional[str] = None


class RedeemRequest(BaseModel):
    quantity: int = 1


class AdminLoginRequest(BaseModel):
    admin_key: str


class TaskCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    points_reward: int
    category: str
    icon: Optional[str] = None
    daily_limit: Optional[int] = None
    expires_at: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    points_reward: Optional[int] = None
    category: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None
    daily_limit: Optional[int] = None
    expires_at: Optional[str] = None


class RewardCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    points_required: int
    stock: int = -1
    image_url: Optional[str] = None
    category: str


class RewardUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    points_required: Optional[int] = None
    stock: Optional[int] = None
    image_url: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


def create_student_token(student_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(days=STUDENT_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(student_id), "email": email, "role": "student", "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_admin_token() -> str:
    expire = datetime.utcnow() + timedelta(hours=ADMIN_TOKEN_EXPIRE_HOURS)
    payload = {"sub": "admin", "role": "admin", "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_student(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Student:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登入")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("role") != "student":
            raise HTTPException(status_code=401, detail="無效的 Token")
        student_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="無效的 Token")
    student = db.query(Student).filter(Student.id == student_id, Student.is_active == True).first()
    if student is None:
        raise HTTPException(status_code=401, detail="學生不存在或已被停用")
    return student


async def get_admin(
    credentials: HTTPAuthorizationCredentials = Depends(admin_security),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登入")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="需要管理員權限")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="無效的 Token")


def get_today_start():
    return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def get_week_start():
    today = datetime.utcnow()
    return (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


# ============ AUTH ENDPOINTS ============


@router.post("/auth/register", status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(Student).filter(Student.email == body.email.strip().lower()).first():
        raise HTTPException(status_code=400, detail="此 Email 已經註冊過")

    password_hash = _bcrypt.hashpw(body.password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
    parent_token = secrets.token_urlsafe(32)

    student = Student(
        name=body.name.strip(),
        email=body.email.strip().lower(),
        password_hash=password_hash,
        age=body.age,
        parent_email=body.parent_email.strip().lower() if body.parent_email else None,
        parent_name=body.parent_name.strip() if body.parent_name else None,
        parent_consent=False,
        parent_token=parent_token,
        points_balance=0,
        total_earned=0,
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    # TODO: Send notification to parent_email with parent_token for consent
    # In production, send email to parent_email with a link like:
    # /api/student/auth/parent/consent?student_email={student.email}&parent_token={parent_token}

    token = create_student_token(student.id, student.email)
    return {
        "token": token,
        "student": {
            "id": student.id,
            "name": student.name,
            "email": student.email,
            "points_balance": student.points_balance,
            "total_earned": student.total_earned,
            "parent_consent": student.parent_consent,
        },
    }


@router.post("/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.email == body.email.strip().lower(), Student.is_active == True).first()
    if not student or not _bcrypt.checkpw(body.password.encode("utf-8"), student.password_hash.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Email 或密碼錯誤")

    token = create_student_token(student.id, student.email)
    return {
        "token": token,
        "student": {
            "id": student.id,
            "name": student.name,
            "email": student.email,
            "points_balance": student.points_balance,
            "total_earned": student.total_earned,
        },
    }


@router.post("/auth/parent/consent")
def parent_consent(body: ConsentRequest, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.email == body.student_email.strip().lower()).first()
    if not student:
        raise HTTPException(status_code=404, detail="學生不存在")

    if body.parent_token and body.parent_token != student.parent_token:
        raise HTTPException(status_code=403, detail="家長驗證碼錯誤")

    if student.parent_consent:
        return {"status": "ok", "message": "家長同意已經確認"}

    student.parent_consent = True
    db.commit()
    return {"status": "ok", "message": "家長同意已確認"}


@router.get("/auth/me")
def get_me(student: Student = Depends(get_current_student)):
    return {
        "id": student.id,
        "name": student.name,
        "email": student.email,
        "age": student.age,
        "parent_email": student.parent_email,
        "parent_consent": student.parent_consent,
        "points_balance": student.points_balance,
        "total_earned": student.total_earned,
        "created_at": student.created_at.isoformat() if student.created_at else None,
    }


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/change-password")
def change_password(
    body: ChangePasswordRequest,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    if not _bcrypt.checkpw(body.current_password.encode("utf-8"), student.password_hash.encode("utf-8")):
        raise HTTPException(status_code=400, detail="目前密碼不正確")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密碼至少 6 碼")
    student.password_hash = _bcrypt.hashpw(body.new_password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
    db.commit()
    return {"ok": True}


# ============ STUDENT ENDPOINTS ============


@router.get("/tasks")
def list_tasks(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    tasks = db.query(Task).filter(
        Task.is_active == True,
        (Task.expires_at == None) | (Task.expires_at > now),
    ).all()

    result = []
    for task in tasks:
        daily_count = 0
        if task.daily_limit:
            today_start = get_today_start()
            daily_count = db.query(TaskSubmission).filter(
                TaskSubmission.task_id == task.id,
                TaskSubmission.student_id == student.id,
                TaskSubmission.created_at >= today_start,
            ).count()

        result.append({
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "points_reward": task.points_reward,
            "category": task.category,
            "icon": task.icon or "📋",
            "daily_limit": task.daily_limit,
            "daily_remaining": max(0, (task.daily_limit or 999) - daily_count),
            "expires_at": task.expires_at.isoformat() if task.expires_at else None,
        })
    return {"items": result}


@router.post("/tasks/{task_id}/submit")
def submit_task(
    task_id: int,
    body: TaskSubmitRequest,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id, Task.is_active == True).first()
    if not task:
        raise HTTPException(status_code=404, detail="任務不存在")

    if task.expires_at and task.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="此任務已過期")

    if task.daily_limit:
        today_start = get_today_start()
        daily_count = db.query(TaskSubmission).filter(
            TaskSubmission.task_id == task.id,
            TaskSubmission.student_id == student.id,
            TaskSubmission.created_at >= today_start,
        ).count()
        if daily_count >= task.daily_limit:
            raise HTTPException(status_code=400, detail=f"今日已達到此任務上限 ({task.daily_limit} 次)")

    submission = TaskSubmission(
        student_id=student.id,
        task_id=task.id,
        status="pending",
        proof_text=body.proof_text,
        points_awarded=0,
    )

    auto_approved = task.category in AUTO_APPROVE_CATEGORIES
    if auto_approved:
        submission.status = "approved"
        submission.points_awarded = task.points_reward
        submission.reviewed_at = datetime.utcnow()

        student.points_balance += task.points_reward
        student.total_earned += task.points_reward

        txn = Transaction(
            student_id=student.id,
            type="earn",
            amount=task.points_reward,
            description=f"完成任務：{task.title}",
            reference_type="task",
            reference_id=task.id,
        )
        db.add(txn)

    db.add(submission)
    db.commit()
    db.refresh(submission)

    return {
        "id": submission.id,
        "status": submission.status,
        "points_awarded": submission.points_awarded,
        "auto_approved": auto_approved,
        "new_balance": student.points_balance,
    }


@router.get("/points")
def get_points(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    total_spent = db.query(func.abs(func.sum(Transaction.amount))).filter(
        Transaction.student_id == student.id,
        Transaction.type == "spend",
    ).scalar() or 0

    return {
        "balance": student.points_balance,
        "total_earned": student.total_earned,
        "total_spent": total_spent,
    }


@router.get("/transactions")
def list_transactions(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    txns = db.query(Transaction).filter(
        Transaction.student_id == student.id,
    ).order_by(desc(Transaction.created_at)).limit(50).all()

    return {
        "items": [
            {
                "id": t.id,
                "type": t.type,
                "amount": t.amount,
                "description": t.description,
                "reference_type": t.reference_type,
                "reference_id": t.reference_id,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in txns
        ]
    }


@router.get("/rewards")
def list_rewards(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    rewards = db.query(Reward).filter(Reward.is_active == True).all()
    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "points_required": r.points_required,
                "stock": r.stock,
                "in_stock": r.stock == -1 or r.stock > 0,
                "image_url": r.image_url,
                "category": r.category,
            }
            for r in rewards
        ]
    }


@router.post("/rewards/{reward_id}/redeem")
def redeem_reward(
    reward_id: int,
    body: RedeemRequest,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    reward = db.query(Reward).filter(Reward.id == reward_id, Reward.is_active == True).first()
    if not reward:
        raise HTTPException(status_code=404, detail="獎勵不存在")

    if not student.parent_consent:
        raise HTTPException(status_code=403, detail="需要家長同意才能兌換獎勵")

    total_cost = reward.points_required * body.quantity

    if student.points_balance < total_cost:
        raise HTTPException(status_code=400, detail=f"點數不足，需要 {total_cost} 點，目前 {student.points_balance} 點")

    if reward.stock != -1 and reward.stock < body.quantity:
        raise HTTPException(status_code=400, detail="庫存不足")

    if reward.stock != -1:
        reward.stock -= body.quantity

    student.points_balance -= total_cost

    redemption = Redemption(
        student_id=student.id,
        reward_id=reward.id,
        points_spent=total_cost,
        status="pending",
    )
    db.add(redemption)

    txn = Transaction(
        student_id=student.id,
        type="spend",
        amount=-total_cost,
        description=f"兌換：{reward.name} x{body.quantity}",
        reference_type="reward",
        reference_id=reward.id,
    )
    db.add(txn)

    db.commit()
    db.refresh(redemption)

    return {
        "id": redemption.id,
        "reward_name": reward.name,
        "points_spent": total_cost,
        "new_balance": student.points_balance,
        "status": redemption.status,
    }


@router.get("/redemptions")
def list_redemptions(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    items = db.query(Redemption).filter(
        Redemption.student_id == student.id,
    ).order_by(desc(Redemption.created_at)).all()

    return {
        "items": [
            {
                "id": r.id,
                "reward_name": r.reward.name if r.reward else "未知",
                "points_spent": r.points_spent,
                "status": r.status,
                "fulfillment_note": r.fulfillment_note,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "fulfilled_at": r.fulfilled_at.isoformat() if r.fulfilled_at else None,
            }
            for r in items
        ]
    }


@router.get("/stats")
def get_stats(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    week_start = get_week_start()
    tasks_this_week = db.query(TaskSubmission).filter(
        TaskSubmission.student_id == student.id,
        TaskSubmission.status == "approved",
        TaskSubmission.created_at >= week_start,
    ).count()

    approved_submissions = db.query(TaskSubmission).filter(
        TaskSubmission.student_id == student.id,
        TaskSubmission.status == "approved",
    ).order_by(desc(TaskSubmission.created_at)).all()

    streak = 0
    if approved_submissions:
        dates = sorted(set(s.created_at.date() for s in approved_submissions), reverse=True)
        check_date = date.today()
        for d in dates:
            if d == check_date:
                streak += 1
                check_date -= timedelta(days=1)
            elif d < check_date:
                break

    rank = db.query(func.count(Student.id)).filter(
        Student.total_earned > student.total_earned,
        Student.is_active == True,
    ).scalar() or 0
    rank += 1

    return {
        "tasks_this_week": tasks_this_week,
        "streak": streak,
        "rank": rank,
        "total_students": db.query(func.count(Student.id)).filter(Student.is_active == True).scalar() or 1,
        "points_balance": student.points_balance,
        "total_earned": student.total_earned,
    }


# ============ ADMIN ENDPOINTS ============


@router.post("/admin/login")
def admin_login(body: AdminLoginRequest):
    if body.admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="管理員金鑰錯誤")
    token = create_admin_token()
    return {"token": token, "role": "admin"}


@router.get("/admin/tasks")
def admin_list_tasks(admin: dict = Depends(get_admin), db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(desc(Task.created_at)).all()
    return {
        "items": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "points_reward": t.points_reward,
                "category": t.category,
                "icon": t.icon,
                "is_active": t.is_active,
                "daily_limit": t.daily_limit,
                "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tasks
        ]
    }


@router.post("/admin/tasks", status_code=201)
def admin_create_task(body: TaskCreateRequest, admin: dict = Depends(get_admin), db: Session = Depends(get_db)):
    expires_at = None
    if body.expires_at:
        try:
            expires_at = datetime.fromisoformat(body.expires_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式錯誤，請使用 ISO 格式")

    task = Task(
        title=body.title,
        description=body.description,
        points_reward=body.points_reward,
        category=body.category,
        icon=body.icon,
        daily_limit=body.daily_limit,
        expires_at=expires_at,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {
        "id": task.id,
        "title": task.title,
        "points_reward": task.points_reward,
        "category": task.category,
        "is_active": task.is_active,
    }


@router.put("/admin/tasks/{task_id}")
def admin_update_task(
    task_id: int,
    body: TaskUpdateRequest,
    admin: dict = Depends(get_admin),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任務不存在")

    if body.title is not None:
        task.title = body.title
    if body.description is not None:
        task.description = body.description
    if body.points_reward is not None:
        task.points_reward = body.points_reward
    if body.category is not None:
        task.category = body.category
    if body.icon is not None:
        task.icon = body.icon
    if body.is_active is not None:
        task.is_active = body.is_active
    if body.daily_limit is not None:
        task.daily_limit = body.daily_limit
    if body.expires_at is not None:
        try:
            task.expires_at = datetime.fromisoformat(body.expires_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式錯誤")

    db.commit()
    return {"status": "ok", "id": task.id}


@router.delete("/admin/tasks/{task_id}")
def admin_delete_task(task_id: int, admin: dict = Depends(get_admin), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任務不存在")
    task.is_active = False
    db.commit()
    return {"status": "deleted", "id": task_id}


@router.get("/admin/rewards")
def admin_list_rewards(admin: dict = Depends(get_admin), db: Session = Depends(get_db)):
    rewards = db.query(Reward).order_by(desc(Reward.created_at)).all()
    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "points_required": r.points_required,
                "stock": r.stock,
                "image_url": r.image_url,
                "category": r.category,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rewards
        ]
    }


@router.post("/admin/rewards", status_code=201)
def admin_create_reward(body: RewardCreateRequest, admin: dict = Depends(get_admin), db: Session = Depends(get_db)):
    reward = Reward(
        name=body.name,
        description=body.description,
        points_required=body.points_required,
        stock=body.stock,
        image_url=body.image_url,
        category=body.category,
    )
    db.add(reward)
    db.commit()
    db.refresh(reward)
    return {
        "id": reward.id,
        "name": reward.name,
        "points_required": reward.points_required,
        "category": reward.category,
    }


@router.put("/admin/rewards/{reward_id}")
def admin_update_reward(
    reward_id: int,
    body: RewardUpdateRequest,
    admin: dict = Depends(get_admin),
    db: Session = Depends(get_db),
):
    reward = db.query(Reward).filter(Reward.id == reward_id).first()
    if not reward:
        raise HTTPException(status_code=404, detail="獎勵不存在")

    if body.name is not None:
        reward.name = body.name
    if body.description is not None:
        reward.description = body.description
    if body.points_required is not None:
        reward.points_required = body.points_required
    if body.stock is not None:
        reward.stock = body.stock
    if body.image_url is not None:
        reward.image_url = body.image_url
    if body.category is not None:
        reward.category = body.category
    if body.is_active is not None:
        reward.is_active = body.is_active

    db.commit()
    return {"status": "ok", "id": reward.id}


@router.delete("/admin/rewards/{reward_id}")
def admin_delete_reward(reward_id: int, admin: dict = Depends(get_admin), db: Session = Depends(get_db)):
    reward = db.query(Reward).filter(Reward.id == reward_id).first()
    if not reward:
        raise HTTPException(status_code=404, detail="獎勵不存在")
    reward.is_active = False
    db.commit()
    return {"status": "deleted", "id": reward_id}


@router.get("/admin/submissions")
def admin_list_submissions(
    status_filter: Optional[str] = None,
    admin: dict = Depends(get_admin),
    db: Session = Depends(get_db),
):
    query = db.query(TaskSubmission)
    if status_filter:
        query = query.filter(TaskSubmission.status == status_filter)
    query = query.order_by(desc(TaskSubmission.created_at))
    submissions = query.all()

    return {
        "items": [
            {
                "id": s.id,
                "student_name": s.student.name if s.student else "未知",
                "student_email": s.student.email if s.student else "未知",
                "task_title": s.task.title if s.task else "未知",
                "task_category": s.task.category if s.task else "未知",
                "status": s.status,
                "proof_text": s.proof_text,
                "points_awarded": s.points_awarded,
                "points_reward": s.task.points_reward if s.task else 0,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
            }
            for s in submissions
        ]
    }


@router.post("/admin/submissions/{submission_id}/approve")
def admin_approve_submission(
    submission_id: int,
    admin: dict = Depends(get_admin),
    db: Session = Depends(get_db),
):
    submission = db.query(TaskSubmission).filter(TaskSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="提交記錄不存在")
    if submission.status != "pending":
        raise HTTPException(status_code=400, detail=f"此提交已處理（狀態：{submission.status}）")

    task = submission.task
    student = submission.student

    points = task.points_reward if task else 0
    submission.status = "approved"
    submission.points_awarded = points
    submission.reviewed_at = datetime.utcnow()

    if student:
        student.points_balance += points
        student.total_earned += points

    txn = Transaction(
        student_id=submission.student_id,
        type="earn",
        amount=points,
        description=f"任務審核通過：{task.title if task else '未知'}",
        reference_type="task",
        reference_id=submission.task_id,
    )
    db.add(txn)
    db.commit()

    return {
        "status": "approved",
        "points_awarded": points,
        "student_balance": student.points_balance if student else None,
    }


@router.post("/admin/submissions/{submission_id}/reject")
def admin_reject_submission(
    submission_id: int,
    admin: dict = Depends(get_admin),
    db: Session = Depends(get_db),
):
    submission = db.query(TaskSubmission).filter(TaskSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="提交記錄不存在")
    if submission.status != "pending":
        raise HTTPException(status_code=400, detail=f"此提交已處理（狀態：{submission.status}）")

    submission.status = "rejected"
    submission.reviewed_at = datetime.utcnow()
    db.commit()

    return {"status": "rejected", "id": submission_id}


@router.get("/admin/students")
def admin_list_students(admin: dict = Depends(get_admin), db: Session = Depends(get_db)):
    students = db.query(Student).order_by(desc(Student.total_earned)).all()
    return {
        "items": [
            {
                "id": s.id,
                "name": s.name,
                "email": s.email,
                "age": s.age,
                "parent_email": s.parent_email,
                "parent_consent": s.parent_consent,
                "points_balance": s.points_balance,
                "total_earned": s.total_earned,
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in students
        ]
    }


@router.get("/admin/redemptions")
def admin_list_redemptions(
    status_filter: Optional[str] = None,
    admin: dict = Depends(get_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Redemption)
    if status_filter:
        query = query.filter(Redemption.status == status_filter)
    query = query.order_by(desc(Redemption.created_at))
    items = query.all()

    return {
        "items": [
            {
                "id": r.id,
                "student_name": r.student.name if r.student else "未知",
                "student_email": r.student.email if r.student else "未知",
                "reward_name": r.reward.name if r.reward else "未知",
                "points_spent": r.points_spent,
                "status": r.status,
                "fulfillment_note": r.fulfillment_note,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "fulfilled_at": r.fulfilled_at.isoformat() if r.fulfilled_at else None,
            }
            for r in items
        ]
    }


@router.post("/admin/redemptions/{redemption_id}/fulfill")
def admin_fulfill_redemption(
    redemption_id: int,
    body: dict = Body(default={}),
    admin: dict = Depends(get_admin),
    db: Session = Depends(get_db),
):
    redemption = db.query(Redemption).filter(Redemption.id == redemption_id).first()
    if not redemption:
        raise HTTPException(status_code=404, detail="兌換記錄不存在")
    if redemption.status != "pending":
        raise HTTPException(status_code=400, detail=f"此兌換已處理（狀態：{redemption.status}）")

    redemption.status = "fulfilled"
    redemption.fulfilled_at = datetime.utcnow()
    redemption.fulfillment_note = body.get("note", "")
    db.commit()

    return {"status": "fulfilled", "id": redemption_id}


@router.get("/admin/stats")
def admin_stats(admin: dict = Depends(get_admin), db: Session = Depends(get_db)):
    total_students = db.query(func.count(Student.id)).filter(Student.is_active == True).scalar() or 0
    total_points_earned = db.query(func.sum(Student.total_earned)).filter(Student.is_active == True).scalar() or 0
    total_points_balance = db.query(func.sum(Student.points_balance)).filter(Student.is_active == True).scalar() or 0
    total_tasks = db.query(func.count(Task.id)).filter(Task.is_active == True).scalar() or 0
    total_rewards = db.query(func.count(Reward.id)).filter(Reward.is_active == True).scalar() or 0
    total_submissions = db.query(func.count(TaskSubmission.id)).scalar() or 0
    pending_submissions = db.query(func.count(TaskSubmission.id)).filter(
        TaskSubmission.status == "pending"
    ).scalar() or 0
    total_redemptions = db.query(func.count(Redemption.id)).scalar() or 0
    pending_redemptions = db.query(func.count(Redemption.id)).filter(
        Redemption.status == "pending"
    ).scalar() or 0

    today_start = get_today_start()
    active_today = db.query(func.count(func.distinct(TaskSubmission.student_id))).filter(
        TaskSubmission.created_at >= today_start,
    ).scalar() or 0

    return {
        "total_students": total_students,
        "total_points_earned": total_points_earned,
        "total_points_balance": total_points_balance,
        "total_tasks": total_tasks,
        "total_rewards": total_rewards,
        "total_submissions": total_submissions,
        "pending_submissions": pending_submissions,
        "total_redemptions": total_redemptions,
        "pending_redemptions": pending_redemptions,
        "active_today": active_today,
    }
