from fastapi import FastAPI
from database import init_db
import users as users_router, items as items_router, admin as admin_router
import os

app = FastAPI(title="Complex Task Management API")

# create DB + uploads/exports folders
init_db()
os.makedirs("./uploads", exist_ok=True)
os.makedirs("./exports", exist_ok=True)

app.include_router(users_router.router)
app.include_router(items_router.router)
app.include_router(admin_router.router)

@app.get("/")
def root():
    return {"msg": "Complex API up — see /docs"}
