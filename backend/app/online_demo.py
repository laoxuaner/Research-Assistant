"""Read-only public presentation of synthetic data, separate from local user data."""
import re
from urllib.parse import urlsplit

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import research
from .api_core import settings as core_settings
from .deps import paper_ids, project, session
from .models import AnalysisRun, Job, Paper, Preference, Report
from .schemas import AskInput, ReportInput

READ_ONLY_NOTICE = "公开演示为只读模式：仅使用合成测试资料，上传、修改、分析保存及模型配置请下载后在本机使用。"
_READ_POST = re.compile(r"^/api/projects/[^/]+/(?:search|ask|compare|papers/[^/]+/reading-card)$")
_MARKER_NAME = ".public-demo-data"
_MARKER_CONTENT = "research-assistant-public-demo-v1\n"

settings_router = APIRouter(prefix="/api")
demo_router = APIRouter(prefix="/api")


def readonly_post(path):
    return bool(_READ_POST.fullmatch(path))


def demo_host(settings):
    return urlsplit(settings.demo_public_url).hostname


def prepare_demo_directory(settings):
    """Refuse to publish any preexisting directory not created for public demos."""
    directory = settings.directory()
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / _MARKER_NAME
    if marker.exists():
        if not marker.is_file() or marker.read_text(encoding="utf-8") != _MARKER_CONTENT:
            raise ValueError("公开演示数据目录标记无效，请使用新的独立 DATA_DIR")
    else:
        if any(directory.iterdir()):
            raise ValueError("公开演示拒绝使用已有资料目录，请使用新的空 DATA_DIR")
        marker.write_text(_MARKER_CONTENT, encoding="utf-8")


@settings_router.get("/settings", name="deployment_settings")
def deployment_settings(request: Request, db: Session = Depends(session, scope="function")):
    values = core_settings(request, db)
    is_demo = request.app.state.settings.deployment_mode == "demo"
    return {**values, "deployment_mode": request.app.state.settings.deployment_mode,
            "read_only": is_demo, "demo_notice": READ_ONLY_NOTICE if is_demo else ""}


@demo_router.post("/projects/{project_id}/ask", name="demo_ask")
def demo_ask(project_id: str, body: AskInput, request: Request,
             db: Session = Depends(session, scope="function")):
    project(db, project_id)
    paper_ids(db, project_id, body.paper_ids)
    result = research.answer(db, project_id, body, request.app.state.settings,
                             request.app.state.chat_provider, request.app.state.embedding_provider)
    # Show actual evidence without keeping visitors' questions in a shared history.
    return {**result, "conversation_id": None}


async def seed_online_demo(app):
    """Seed once, finish/recover PDF jobs before accepting public requests."""
    from .demo import import_demo
    from .api_experiments import create_report
    from .papers import parse_job

    request = Request({"type": "http", "app": app, "headers": []})
    tasks = BackgroundTasks()
    database, settings = app.state.database, app.state.settings
    with database.session() as db:
        imported = import_demo(request, tasks, db)
    await tasks()

    retries = BackgroundTasks()
    with database.session() as db:
        project_id = imported["project_id"]
        papers = list(db.scalars(select(Paper).where(Paper.project_id == project_id)))
        if len(papers) != 2:
            raise ValueError("公开演示样例论文不完整，请检查 samples 测试材料")
        for paper in papers:
            if paper.status != "completed":
                paper.status, paper.error = "queued", None
                job = Job(project_id=project_id, resource_id=paper.id, kind="parse")
                db.add(job)
                db.flush()
                retries.add_task(parse_job, database, settings, job.id)
        preference = db.get(Preference, "ai_enabled")
        if preference:
            preference.value = False
        else:
            db.add(Preference(key="ai_enabled", value=False))
    await retries()

    with database.session() as db:
        papers = list(db.scalars(select(Paper).where(Paper.project_id == project_id)))
        if any(paper.status != "completed" for paper in papers):
            raise ValueError("公开演示样例 PDF 解析失败，请检查服务日志和测试材料")
        existing = db.scalar(select(Report).where(Report.project_id == project_id))
        if not existing:
            run = db.scalar(select(AnalysisRun).where(AnalysisRun.project_id == project_id))
            if not run:
                raise ValueError("公开演示缺少示例分析结果")
            create_report(project_id, ReportInput(analysis_id=run.id,
                          title="DEMO · 合成测试数据研究报告"), request, db)
