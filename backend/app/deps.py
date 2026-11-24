from fastapi import Request, HTTPException
from sqlalchemy import select
from .models import Project, Paper

def session(request: Request):
    with request.app.state.database.session() as db:
        yield db

def project(db, project_id):
    row = db.get(Project,project_id)
    if not row: raise HTTPException(404,"科研项目不存在")
    return row

def scoped(db, cls, resource_id, project_id):
    project(db,project_id)
    row = db.get(cls,resource_id)
    if not row or row.project_id != project_id: raise HTTPException(404,"资源不存在或不属于当前项目")
    return row

def paper_ids(db, project_id, ids):
    if not ids: return
    found=set(db.scalars(select(Paper.id).where(Paper.project_id==project_id,Paper.id.in_(ids))))
    if found != set(ids): raise HTTPException(404,"所选论文不属于当前项目或已删除")
