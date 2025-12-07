from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


# ============================================================
# USER
# ============================================================

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, nullable=False)
    email: str = Field(index=True, unique=True, nullable=False)
    hashed_password: str
    role: str = Field(default="user", index=True)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # --- RELACJE ---
    projects: List["Project"] = Relationship(back_populates="owner")
    notifications: List["Notification"] = Relationship(back_populates="user")


# ============================================================
# PROJECT
# ============================================================

class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_deleted: bool = Field(default=False)

    # optimistic locking
    version: int = Field(default=1, nullable=False)

    # --- RELACJE ---
    owner: Optional[User] = Relationship(back_populates="projects")
    tasks: List["Task"] = Relationship(back_populates="project")


# ============================================================
# TASK
# ============================================================

class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    completed: bool = Field(default=False)
    project_id: Optional[int] = Field(default=None, foreign_key="project.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_deleted: bool = Field(default=False)

    version: int = Field(default=1, nullable=False)

    # --- RELACJE ---
    project: Optional[Project] = Relationship(back_populates="tasks")


# ============================================================
# NOTIFICATION
# ============================================================

class Notification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    message: str
    seen: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # --- RELACJE ---
    user: Optional[User] = Relationship(back_populates="notifications")
