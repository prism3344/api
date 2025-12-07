from fastapi import Depends, Query
from database import get_session
from sqlmodel import Session

def pagination_params(limit: int = Query(10, gt=0, le=100), offset: int = Query(0, ge=0)):
    return {"limit": limit, "offset": offset}
