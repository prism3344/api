from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select
from database import get_session
from models import Project, Task, Notification, User
from schemas import ProjectCreate, ProjectRead, TaskCreate, TaskRead
from auth import get_current_user, require_role
from deps import pagination_params
import csv, os, uuid
from typing import List

router = APIRouter(prefix="", tags=["projects","tasks","files","export","ws"])

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# in-memory websocket manager (very simple)
class WSManager:
    def __init__(self):
        self.active: dict[int, List[WebSocket]] = {}

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(user_id, []).append(ws)

    def disconnect(self, user_id: int, ws: WebSocket):
        sockets = self.active.get(user_id, [])
        if ws in sockets:
            sockets.remove(ws)

    async def push(self, user_id: int, message: str):
        import asyncio
        sockets = self.active.get(user_id, [])
        for s in list(sockets):
            try:
                await s.send_json({"message": message})
            except Exception:
                try:
                    await s.close()
                except:
                    pass
                self.disconnect(user_id, s)

ws_manager = WSManager()

# ----------------- PROJECTS -----------------
@router.post("/projects", response_model=ProjectRead, dependencies=[Depends(get_current_user)], status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_session), current=Depends(get_current_user)):
    project = Project(name=payload.name, description=payload.description, owner_id=current.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@router.get("/projects", response_model=List[ProjectRead], dependencies=[Depends(get_current_user)])
def list_projects(limit_offset: dict = Depends(pagination_params), q: str = None, db: Session = Depends(get_session)):
    limit = limit_offset["limit"]; offset = limit_offset["offset"]
    stmt = select(Project).where(Project.is_deleted == False)
    if q:
        stmt = stmt.where(Project.name.contains(q) | Project.description.contains(q))
    stmt = stmt.offset(offset).limit(limit)
    projs = db.exec(stmt).all()
    # eager load tasks for response (simple)
    for p in projs:
        p.tasks = db.exec(select(Task).where(Task.project_id == p.id, Task.is_deleted == False)).all()
    return projs

@router.get("/projects/{project_id}", response_model=ProjectRead, dependencies=[Depends(get_current_user)])
def get_project(project_id: int, db: Session = Depends(get_session)):
    p = db.exec(select(Project).where(Project.id == project_id, Project.is_deleted == False)).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    p.tasks = db.exec(select(Task).where(Task.project_id == p.id, Task.is_deleted == False)).all()
    return p

@router.delete("/projects/{project_id}", status_code=204, dependencies=[Depends(require_role("manager"))])
def soft_delete_project(project_id: int, db: Session = Depends(get_session), current=Depends(get_current_user)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    p.is_deleted = True
    db.add(p)
    db.commit()
    return

# ----------------- TASKS -----------------
@router.post("/projects/{project_id}/tasks", response_model=TaskRead, status_code=201, dependencies=[Depends(get_current_user)])
def add_task_to_project(project_id: int, payload: TaskCreate, db: Session = Depends(get_session), current=Depends(get_current_user)):
    project = db.get(Project, project_id)
    if not project or project.is_deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    # create task, notify owner in background
    task = Task(title=payload.title, description=payload.description, completed=payload.completed, project_id=project_id)
    db.add(task)
    db.commit()
    db.refresh(task)
    # notification
    note = Notification(user_id=project.owner_id, message=f"New task '{task.title}' in project '{project.name}'")
    db.add(note)
    db.commit()
    # push ws in background (non-blocking)
    import asyncio
    try:
        asyncio.create_task(ws_manager.push(project.owner_id, f"New task added: {task.title}"))
    except RuntimeError:
        # if not running in event loop (test sync), skip
        pass
    return task

@router.put("/tasks/{task_id}", response_model=TaskRead, dependencies=[Depends(get_current_user)])
def update_task(task_id: int, payload: TaskCreate, db: Session = Depends(get_session), current=Depends(get_current_user)):
    t = db.get(Task, task_id)
    if not t or t.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    # optimistic locking: require client to provide version in payload? here we require exact match via header trick (simpler: trust payload.title as update)
    t.title = payload.title
    t.description = payload.description
    t.completed = payload.completed or False
    t.version += 1
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

@router.delete("/tasks/{task_id}", status_code=204, dependencies=[Depends(get_current_user)])
def delete_task(task_id: int, db: Session = Depends(get_session), current=Depends(get_current_user)):
    t = db.get(Task, task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    t.is_deleted = True
    db.add(t)
    db.commit()
    return

# ----------------- BULK import -----------------
@router.post("/projects/{project_id}/tasks/bulk", dependencies=[Depends(require_role("manager"))])
def bulk_import_tasks(project_id: int, rows: List[TaskCreate], db: Session = Depends(get_session)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    created = []
    for r in rows:
        t = Task(title=r.title, description=r.description, completed=r.completed, project_id=project_id)
        db.add(t)
        created.append(t)
    db.commit()
    for t in created:
        db.refresh(t)
    return {"created": len(created), "tasks": [t.id for t in created]}

# ----------------- FILE UPLOAD -----------------
@router.post("/projects/{project_id}/upload")
def upload_file(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_session), current=Depends(get_current_user)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    fname = f"{uuid.uuid4().hex}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, fname)
    with open(path, "wb") as f:
        f.write(file.file.read())
    return {"filename": fname, "path": path}

# ----------------- EXPORT (background) -----------------
def _export_projects_csv(path: str, db: Session):
    stmt = select(Project).where(Project.is_deleted == False)
    projs = db.exec(stmt).all()
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["id","name","desc","owner_id","created_at"])
        for p in projs:
            writer.writerow([p.id, p.name, p.description or "", p.owner_id, p.created_at])

@router.post("/export/projects")
def export_projects(background: BackgroundTasks, db: Session = Depends(get_session), current=Depends(require_role("manager"))):
    out = f"./exports/projects_{uuid.uuid4().hex}.csv"
    # schedule export
    background.add_task(_export_projects_csv, out, db)
    return {"export_path": out}

# ----------------- WEBSOCKET -----------------
@router.websocket("/ws/{user_id}")
async def ws_endpoint(websocket: WebSocket, user_id: int):
    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            _ = await websocket.receive_text()  # echo or ignore
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, websocket)
