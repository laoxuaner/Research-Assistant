"""Public demonstrations must use isolated synthetic data and remain read-only."""
import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from app.config import ROOT, Settings
from app.main import create_app
from app.models import AnalysisRun, Conversation, Job, Message, Paper, Project, Report

PUBLIC_URL = "https://research-demo.example"


def demo_settings(directory, **values):
    return Settings(_env_file=None, data_dir=str(directory), deployment_mode="demo",
                    demo_public_url=PUBLIC_URL, **values)


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    directory = tmp_path_factory.mktemp("online-demo")
    settings = demo_settings(directory, ai_api_key="never-send-this-demo-placeholder",
                             ai_chat_model="must-not-call", embedding_model="must-not-call")
    app = create_app(settings=settings)
    with TestClient(app, base_url=PUBLIC_URL) as client:
        yield client


@pytest.mark.parametrize("public_url", ["", "http://research-demo.example",
    "https://*.example", "https://user:password@example.com", "https://example.com/a",
    "https://example.com?token=example", "https://example.com#section",
    "https://example.com:99999", "https://bad host.example"])
def test_demo_requires_exact_https_origin(tmp_path, public_url):
    with pytest.raises(ValidationError, match="DEMO_PUBLIC_URL"):
        Settings(_env_file=None, data_dir=str(tmp_path), deployment_mode="demo",
                 demo_public_url=public_url)


def test_demo_refuses_local_and_preexisting_data_directories(tmp_path):
    with pytest.raises(ValidationError, match="独立 DATA_DIR"):
        demo_settings(ROOT / "data")
    (tmp_path / "research.db").write_bytes(b"existing private database placeholder")
    with pytest.raises(ValueError, match="已有资料目录"):
        create_app(settings=demo_settings(tmp_path))
    assert (tmp_path / "research.db").read_bytes() == b"existing private database placeholder"


def test_demo_seeds_real_readable_papers_saved_analysis_and_report(demo):
    assert demo.get("/api/health").status_code == 200
    settings = demo.get("/api/settings").json()
    assert settings["deployment_mode"] == "demo" and settings["read_only"] is True
    assert not settings["chat_configured"] and not settings["embedding_configured"]
    assert not settings["ai_enabled"]
    assert "never-send" not in str(settings)
    projects = demo.get("/api/projects").json()
    assert len(projects) == 1
    pid = projects[0]["id"]
    assert "示例" in projects[0]["name"]
    papers = demo.get(f"/api/projects/{pid}/papers").json()
    assert len(papers) == 2 and all(p["status"] == "completed" for p in papers)
    assert demo.get(f"/api/projects/{pid}/papers/{papers[0]['id']}/file").content.startswith(b"%PDF-")
    experiments = demo.get(f"/api/projects/{pid}/experiments").json()
    detail = demo.get(f"/api/projects/{pid}/experiments/{experiments[0]['id']}").json()
    assert len(detail["analyses"]) == 1
    comparison = detail["analyses"][0]["result"]["comparison"]
    assert comparison["difference"] == pytest.approx(2)
    reports = demo.get(f"/api/projects/{pid}/reports").json()
    assert len(reports) == 1 and "DEMO" in reports[0]["title"]
    download = demo.get(f"/api/projects/{pid}/reports/{reports[0]['id']}/download?format=zip")
    assert download.status_code == 200
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        assert {"report.md", "summary.csv", "reproduce.py", "plot.png"} <= set(archive.namelist())


def test_demo_search_and_ask_return_evidence_without_persisting_visitors(demo):
    pid = demo.get("/api/projects").json()[0]["id"]
    response = demo.post(f"/api/projects/{pid}/search", json={"query": "均值差"},
                         headers={"Origin": PUBLIC_URL})
    assert response.status_code == 200 and response.json()["results"]

    class NeverCallModel:
        def generate(self, *args):
            raise AssertionError("public demo must not call a model")
        def embed(self, *args):
            raise AssertionError("public demo must not call embeddings")

    demo.app.state.chat_provider = demo.app.state.embedding_provider = NeverCallModel()
    response = demo.post(f"/api/projects/{pid}/ask", json={"question": "均值差"})
    assert response.status_code == 200
    answer = response.json()
    assert answer["mode"] == "offline" and answer["citations"]
    assert answer["conversation_id"] is None
    assert demo.post(f"/api/projects/{pid}/ask", json={"question": "Europa orbit"}).json()["mode"] == "no_evidence"
    with demo.app.state.database.session() as db:
        assert db.scalar(select(func.count()).select_from(Conversation)) == 0
        assert db.scalar(select(func.count()).select_from(Message)) == 0
    assert demo.post(f"/api/projects/{pid}/search", json={"query": "均值差", "paper_ids": ["wrong-project"]}).status_code == 404


@pytest.mark.parametrize("method,path", [
    ("POST", "/api/projects"), ("PATCH", "/api/projects/example"),
    ("POST", "/api/demo"), ("PATCH", "/api/settings"),
    ("POST", "/api/projects/example/papers"),
    ("DELETE", "/api/projects/example/papers/paper"),
    ("POST", "/api/projects/example/papers/paper/retry"),
    ("POST", "/api/projects/example/experiments"),
    ("POST", "/api/projects/example/experiments/exp/datasets"),
    ("POST", "/api/projects/example/experiments/exp/datasets/ds/clean"),
    ("POST", "/api/projects/example/experiments/exp/analyses"),
    ("POST", "/api/projects/example/experiments/exp/suggest"),
    ("POST", "/api/projects/example/reports"),
    ("POST", "/api/projects/example/embeddings/rebuild"),
    ("PUT", "/api/projects/example/search"),
    ("TRACE", "/api/projects/example/search"),
])
def test_demo_rejects_mutations_even_without_origin(demo, method, path):
    response = demo.request(method, path, json={})
    assert response.status_code == 403
    assert "只读" in response.json()["detail"]


def test_demo_rejects_foreign_hosts_and_origins_and_supports_exact_cors(demo):
    pid = demo.get("/api/projects").json()[0]["id"]
    assert demo.get("/api/projects", headers={"Host": "evil.example"}).status_code == 400
    assert demo.post(f"/api/projects/{pid}/search", json={"query": "均值差"},
                     headers={"Origin": "https://evil.example"}).status_code == 403
    assert demo.get("/api/health", headers={"Host": "127.0.0.1:8010"}).status_code == 200
    preflight = demo.options(f"/api/projects/{pid}/search", headers={
        "Origin": PUBLIC_URL, "Access-Control-Request-Method": "POST"})
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == PUBLIC_URL
    forbidden = demo.options("/api/projects", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert forbidden.status_code == 400
    assert demo.post("/api/projects", json={"name": "still forbidden"},
                     headers={"Origin": PUBLIC_URL}).status_code == 403


def test_demo_restart_reuses_seed_and_recovers_interrupted_parse(tmp_path):
    settings = demo_settings(tmp_path)
    app = create_app(settings=settings)
    with TestClient(app, base_url=PUBLIC_URL):
        with app.state.database.session() as db:
            paper = db.scalar(select(Paper))
            paper.status = "running"
            db.add(Job(project_id=paper.project_id, resource_id=paper.id,
                       kind="parse", status="running"))
    restarted = create_app(settings=settings)
    with TestClient(restarted, base_url=PUBLIC_URL):
        with restarted.state.database.session() as db:
            assert db.scalar(select(func.count()).select_from(Project)) == 1
            assert db.scalar(select(func.count()).select_from(AnalysisRun)) == 1
            assert db.scalar(select(func.count()).select_from(Report)) == 1
            assert all(p.status == "completed" for p in db.scalars(select(Paper)))


def test_default_local_mode_still_supports_project_creation(tmp_path):
    app = create_app(settings=Settings(_env_file=None, data_dir=str(tmp_path)))
    with TestClient(app) as client:
        values = client.get("/api/settings").json()
        assert values["deployment_mode"] == "local" and values["read_only"] is False
        assert client.post("/api/projects", json={"name": "本机可编辑"}).status_code == 201
