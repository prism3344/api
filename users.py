from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from auth import get_password_hash, create_access_token, verify_password
from database import get_session
from models import User
from schemas import UserCreate, UserRead, Token

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/register", response_model=UserRead, status_code=201)
def register(user: UserCreate, db: Session = Depends(get_session)):
    exists = db.exec(select(User).where((User.username == user.username) | (User.email == user.email))).first()
    if exists:
        raise HTTPException(status_code=400, detail="User exists")
    hashed = get_password_hash(user.password)
    u = User(username=user.username, email=user.email, hashed_password=hashed)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

@router.post("/token", response_model=Token)
def token(form_data: UserCreate, db: Session = Depends(get_session)):  # simple - accepts username/password JSON for demo
    user = db.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    tok = create_access_token({"sub": user.username})
    return {"access_token": tok}
