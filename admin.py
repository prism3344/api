from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from database import get_session
from models import User, Project, Task
from auth import require_role

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/stats", dependencies=[Depends(require_role("admin"))])
def stats(db: Session = Depends(get_session)):
    total_users = db.exec(select(User)).count()
    total_projects = db.exec(select(Project)).count()
    total_tasks = db.exec(select(Task)).count()
    return {"users": total_users, "projects": total_projects, "tasks": total_tasks}
