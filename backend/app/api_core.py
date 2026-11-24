import hashlib
from pathlib import Path
from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session
from .db import serialize
from .models import Project, Paper, PaperPage, Job, Experiment, Report, Preference, Conversation, Message, Citation, Chunk, Embedding, Note, uid
from .schemas import ProjectInput, ProjectPatch, PaperPatch, SearchInput, AskInput, CompareInput, SettingsInput, NoteInput
from .deps import session, project, scoped, paper_ids
from .papers import parse_job
from .providers import configured, ProviderError
from . import research

router=APIRouter(prefix="/api")

@router.get("/health")
def health(): return {"status":"ok","app":"研知 · Research Workbench","version":"1.0.0"}

@router.get("/settings")
def settings(request:Request,db:Session=Depends(session, scope="function")):
    s=request.app.state.settings
    return {"chat_configured":configured(s.ai_base_url,s.ai_chat_model,s.ai_api_key),
        "embedding_configured":configured(s.embedding_base_url or s.ai_base_url,s.embedding_model,s.embedding_api_key),
        "ai_enabled":research.enabled(db),"chat_model":s.ai_chat_model,
        "embedding_model":s.embedding_model,"chat_base_url":s.ai_base_url,
        "embedding_base_url":s.embedding_base_url or s.ai_base_url,
        "limits":{"max_upload_mb":s.max_upload_mb,"max_pdf_pages":s.max_pdf_pages,
            "parse_timeout_seconds":s.parse_timeout_seconds,"max_dataset_rows":s.max_dataset_rows,
            "max_dataset_columns":s.max_dataset_columns}}

@router.patch("/settings")
def update_settings(body:SettingsInput,request:Request,db:Session=Depends(session, scope="function")):
    row=db.get(Preference,"ai_enabled")
    if not row: db.add(Preference(key="ai_enabled",value=body.ai_enabled))
    else: row.value=body.ai_enabled
    db.commit()
    return settings(request,db)

@router.get("/projects")
def projects(db:Session=Depends(session, scope="function")):
    return [serialize(p) for p in db.scalars(select(Project).order_by(Project.created_at.desc()))]

@router.post("/projects",status_code=201)
def create_project(body:ProjectInput,db:Session=Depends(session, scope="function")):
    row=Project(**body.model_dump());db.add(row);db.flush()
    return serialize(row)

@router.patch("/projects/{project_id}")
def update_project(project_id:str,body:ProjectPatch,db:Session=Depends(session, scope="function")):
    row=project(db,project_id)
    for key,value in body.model_dump(exclude_unset=True).items():
        if value is not None: setattr(row,key,value)
    db.flush();return serialize(row)

@router.get("/projects/{project_id}/overview")
def overview(project_id:str,db:Session=Depends(session, scope="function")):
    project(db,project_id)
    def count(cls): return db.scalar(select(func.count()).select_from(cls).where(cls.project_id==project_id)) or 0
    return {"paper_count":count(Paper),"experiment_count":count(Experiment),"report_count":count(Report),
        "pending_jobs":db.scalar(select(func.count()).select_from(Job).where(Job.project_id==project_id,Job.status.in_(["queued","running"]))) or 0,
        "recent_experiments":[serialize(x) for x in db.scalars(select(Experiment).where(Experiment.project_id==project_id).order_by(Experiment.created_at.desc()).limit(5))],
        "recent_reports":[serialize(x,["context"]) for x in db.scalars(select(Report).where(Report.project_id==project_id).order_by(Report.created_at.desc()).limit(5))]}

@router.get("/projects/{project_id}/papers")
def list_papers(project_id:str,db:Session=Depends(session, scope="function")):
    project(db,project_id)
    return [serialize(p) for p in db.scalars(select(Paper).where(Paper.project_id==project_id).order_by(Paper.created_at.desc()))]

def store_paper(db,settings,project_id,filename,content):
    filename=filename.replace("\\","/").split("/")[-1][:240]
    if Path(filename).suffix.lower()!=".pdf" or not content.startswith(b"%PDF-"):
        raise HTTPException(400,"请上传有效的 PDF 文件")
    digest=hashlib.sha256(content).hexdigest()
    old=db.scalar(select(Paper).where(Paper.project_id==project_id,Paper.sha256==digest))
    if old: return old,None
    directory=settings.directory()/"papers";directory.mkdir(parents=True,exist_ok=True)
    path=directory/(uid()+".pdf")
    path.write_bytes(content)
    paper=Paper(project_id=project_id,title=Path(filename).stem,filename=filename,
        storage_path=str(path),sha256=digest,size_bytes=len(content))
    db.add(paper);db.flush()
    job=Job(project_id=project_id,resource_id=paper.id,kind="parse")
    db.add(job);db.flush()
    return paper,job

@router.post("/projects/{project_id}/papers",status_code=201)
async def upload_papers(project_id:str,request:Request,background_tasks:BackgroundTasks,files:list[UploadFile]=File(...),db:Session=Depends(session, scope="function")):
    project(db,project_id)
    if len(files)>20: raise HTTPException(400,"每批最多上传 20 个文件")
    s=request.app.state.settings
    prepared=[]
    for file in files:
        value=await file.read(s.max_upload_mb*1024*1024+1)
        await file.close()
        if len(value)>s.max_upload_mb*1024*1024: raise HTTPException(413,"文件超过大小限制")
        if Path(file.filename or "").suffix.lower()!=".pdf" or not value.startswith(b"%PDF-"): raise HTTPException(400,"请上传有效的 PDF 文件")
        prepared.append((file.filename or "paper.pdf",value))
    if sum(len(v) for _,v in prepared)>100*1024*1024: raise HTTPException(413,"本批文件总大小超过 100 MB")
    result,duplicates=[],[]
    for filename,content in prepared:
        paper,job=store_paper(db,s,project_id,filename,content)
        result.append(serialize(paper))
        if job:
            background_tasks.add_task(parse_job,request.app.state.database,s,job.id)
        else: duplicates.append(filename)
    db.commit()
    return {"papers":result,"duplicates":duplicates}

@router.get("/projects/{project_id}/papers/{paper_id}")
def get_paper(project_id:str,paper_id:str,db:Session=Depends(session, scope="function")):
    row=scoped(db,Paper,paper_id,project_id)
    return {**serialize(row),
        "pages":[serialize(x,["paper_id"]) for x in db.scalars(select(PaperPage).where(PaperPage.paper_id==paper_id).order_by(PaperPage.page_number))],
        "jobs":[serialize(x) for x in db.scalars(select(Job).where(Job.project_id==project_id,Job.resource_id==paper_id).order_by(Job.created_at.desc()))]}

@router.patch("/projects/{project_id}/papers/{paper_id}")
def update_paper(project_id:str,paper_id:str,body:PaperPatch,db:Session=Depends(session, scope="function")):
    row=scoped(db,Paper,paper_id,project_id)
    for key,value in body.model_dump(exclude_unset=True).items():
        if value is not None or key=="year": setattr(row,key,value)
    if body.notes is not None:
        note=db.scalar(select(Note).where(Note.project_id==project_id,Note.paper_id==paper_id))
        if note: note.content=body.notes
        else: db.add(Note(project_id=project_id,paper_id=paper_id,content=body.notes))
    db.flush();return serialize(row)

@router.delete("/projects/{project_id}/papers/{paper_id}")
def remove_paper(project_id:str,paper_id:str,db:Session=Depends(session, scope="function")):
    row=scoped(db,Paper,paper_id,project_id)
    path=Path(row.storage_path)
    if row.status=="running": raise HTTPException(409,"论文正在解析，请完成后删除")
    db.execute(delete(Job).where(Job.project_id==project_id,Job.resource_id==paper_id))
    db.delete(row);db.flush()
    path.unlink(missing_ok=True)
    return {"deleted":True}

@router.get("/projects/{project_id}/papers/{paper_id}/file")
def paper_file(project_id:str,paper_id:str,db:Session=Depends(session, scope="function")):
    row=scoped(db,Paper,paper_id,project_id)
    if not Path(row.storage_path).exists(): raise HTTPException(404,"原始文件缺失")
    return FileResponse(row.storage_path,media_type="application/pdf",filename=row.filename,content_disposition_type="inline")

@router.post("/projects/{project_id}/papers/{paper_id}/retry")
def retry_paper(project_id:str,paper_id:str,request:Request,background_tasks:BackgroundTasks,db:Session=Depends(session, scope="function")):
    row=scoped(db,Paper,paper_id,project_id)
    if row.status not in ("failed","interrupted","needs_ocr"): raise HTTPException(409,"当前状态无需重试")
    row.status,row.error="queued",None
    job=Job(project_id=project_id,resource_id=paper_id,kind="parse");db.add(job);db.flush()
    payload=serialize(job);db.commit()
    background_tasks.add_task(parse_job,request.app.state.database,request.app.state.settings,job.id)
    return payload

@router.get("/projects/{project_id}/jobs")
def jobs(project_id:str,db:Session=Depends(session, scope="function")):
    project(db,project_id)
    return [serialize(j) for j in db.scalars(select(Job).where(Job.project_id==project_id).order_by(Job.created_at.desc()).limit(100))]

@router.post("/projects/{project_id}/search")
def search(project_id:str,body:SearchInput,request:Request,db:Session=Depends(session, scope="function")):
    project(db,project_id);paper_ids(db,project_id,body.paper_ids)
    return research.search(db,project_id,body,request.app.state.settings,request.app.state.embedding_provider)

@router.post("/projects/{project_id}/ask")
def ask(project_id:str,body:AskInput,request:Request,db:Session=Depends(session, scope="function")):
    project(db,project_id);paper_ids(db,project_id,body.paper_ids)
    conversation=scoped(db,Conversation,body.conversation_id,project_id) if body.conversation_id else Conversation(project_id=project_id,title=body.question[:100])
    db.add(conversation);db.flush()
    result=research.answer(db,project_id,body,request.app.state.settings,request.app.state.chat_provider,request.app.state.embedding_provider)
    db.add(Message(conversation_id=conversation.id,role="user",content=body.question,mode=result["mode"]))
    message=Message(conversation_id=conversation.id,role="assistant",content=result["answer"],mode=result["mode"],citations=result["citations"])
    db.add(message);db.flush()
    for cite in result["citations"]:
        db.add(Citation(message_id=message.id,**{key:cite[key] for key in ("paper_id","chunk_id","page_number","quote","title")}))
    return {**result,"conversation_id":conversation.id}

@router.get("/projects/{project_id}/conversations")
def conversations(project_id:str,db:Session=Depends(session, scope="function")):
    project(db,project_id)
    rows=[]
    for c in db.scalars(select(Conversation).where(Conversation.project_id==project_id).order_by(Conversation.created_at.desc()).limit(50)):
        messages=[]
        for m in db.scalars(select(Message).where(Message.conversation_id==c.id).order_by(Message.created_at)):
            data=serialize(m)
            for cite in data.get("citations",[]):
                if not db.get(Chunk,cite.get("chunk_id")): cite["unavailable"]=True
            messages.append(data)
        rows.append({**serialize(c),"messages":messages})
    return rows

@router.post("/projects/{project_id}/papers/{paper_id}/reading-card")
def reading_card(project_id:str,paper_id:str,request:Request,db:Session=Depends(session, scope="function")):
    scoped(db,Paper,paper_id,project_id)
    return research.reading_card(db,project_id,paper_id,request.app.state.settings,request.app.state.chat_provider)

@router.post("/projects/{project_id}/compare")
def compare(project_id:str,body:CompareInput,request:Request,db:Session=Depends(session, scope="function")):
    project(db,project_id);paper_ids(db,project_id,body.paper_ids)
    rows=[];modes=[];warnings=[]
    for pid in body.paper_ids:
        paper=db.get(Paper,pid)
        card=research.reading_card(db,project_id,pid,request.app.state.settings,request.app.state.chat_provider)
        rows.append({"paper_id":pid,"title":paper.title,"fields":card["fields"]})
        modes.append(card["mode"]);warnings.extend(card["warnings"])
    warnings.append("不同数据集、单位、评价协议的结果不直接排序或宣称优劣。")
    return {"mode":"ai" if all(m=="ai" for m in modes) else "offline","rows":rows,"warnings":list(dict.fromkeys(warnings))}

@router.get("/projects/{project_id}/embedding-status")
def embedding_status(project_id:str,request:Request,db:Session=Depends(session, scope="function")):
    project(db,project_id)
    total=db.scalar(select(func.count()).select_from(Chunk).where(Chunk.project_id==project_id))
    current=db.scalar(select(func.count()).select_from(Embedding).where(Embedding.project_id==project_id,Embedding.fingerprint==research.fingerprint(request.app.state.settings)))
    return {"total_chunks":total,"indexed_chunks":current,"needs_rebuild":total>current,"model":request.app.state.settings.embedding_model}

@router.post("/projects/{project_id}/embeddings/rebuild")
def rebuild(project_id:str,request:Request,background_tasks:BackgroundTasks,db:Session=Depends(session, scope="function")):
    project(db,project_id)
    if not research.embedding_ready(request.app.state.settings,db): raise HTTPException(400,"未配置或未启用向量模型")
    active=db.scalar(select(Job).where(Job.project_id==project_id,Job.kind=="embedding",Job.status.in_(["queued","running"])))
    if active: raise HTTPException(409,"向量索引任务正在运行")
    job=Job(project_id=project_id,kind="embedding");db.add(job);db.flush()
    value=serialize(job);db.commit()
    background_tasks.add_task(research.rebuild_embeddings,request.app.state.database,request.app.state.settings,job.id,request.app.state.embedding_provider)
    return value
