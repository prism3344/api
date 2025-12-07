from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from database import get_session
from models import User
import os
from datetime import datetime, timedelta

SECRET_KEY = os.getenv("SECRET_KEY", "very_secret_key_for_dev")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

def verify_password(plain, hashed):
    return pwd_ctx.verify(plain, hashed)

def get_password_hash(password):
    return pwd_ctx.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_session)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token",
                                          headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.exec(select(User).where((User.username == sub) | (User.email == sub))).first()
    if not user:
        raise credentials_exception
    return user

def require_role(role: str):
    def _checker(user: User = Depends(get_current_user)):
        roles = {"user": 0, "manager": 1, "admin": 2}
        if roles.get(user.role, 0) < roles.get(role, 0):
            raise HTTPException(status_code=403, detail="Insufficient privileges")
        return user
    return _checker
