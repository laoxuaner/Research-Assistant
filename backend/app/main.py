from contextlib import asynccontextmanager
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import ValidationError
from .config import Settings, ROOT
from .db import Database
from .papers import recover_jobs
from .providers import CompatibleChatProvider, CompatibleEmbeddingProvider, ProviderError
from .api_core import router as core_router
from .api_experiments import router as experiment_router

def create_app(data_dir=None, settings=None):
    settings=settings or Settings()
    if data_dir: settings.data_dir=str(data_dir)
    from .online_demo import prepare_demo_directory, seed_online_demo, settings_router, demo_router, readonly_post, demo_host, READ_ONLY_NOTICE
    is_demo=settings.deployment_mode=="demo"
    if is_demo:
        settings.validate_demo()
        prepare_demo_directory(settings)
    database=Database(settings.directory())

    @asynccontextmanager
    async def lifespan(app):
        database.migrate()
        recover_jobs(database)
        if is_demo:
            await seed_online_demo(app)
        yield
        database.engine.dispose()

    app=FastAPI(title="研知 · 科研论文知识库与实验分析助手",version="1.0.0",lifespan=lifespan)
    app.state.settings=settings
    app.state.database=database
    app.state.chat_provider=CompatibleChatProvider(settings)
    app.state.embedding_provider=CompatibleEmbeddingProvider(settings)
    origins=([settings.demo_public_url] if is_demo else
        ["http://127.0.0.1:5173","http://localhost:5173","http://127.0.0.1:8000","http://localhost:8000"])
    app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=(["GET","POST"] if is_demo else ["GET","POST","PATCH","DELETE"]),allow_headers=["Content-Type"])
    allowed_hosts=([demo_host(settings),"127.0.0.1","localhost","[::1]"] if is_demo else
        ["127.0.0.1","localhost","testserver","[::1]"])
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=allowed_hosts)

    @app.middleware("http")
    async def local_origin(request:Request,call_next):
        if request.method in ("POST","PATCH","PUT","DELETE") and request.headers.get("origin") and request.headers["origin"] not in origins:
            return JSONResponse({"detail":"仅允许演示站点的同源请求" if is_demo else "仅允许本地工作台发起修改请求"},status_code=403)
        if is_demo and request.method not in ("GET","HEAD","OPTIONS"):
            if request.method!="POST" or not readonly_post(request.url.path):
                return JSONResponse({"detail":READ_ONLY_NOTICE},status_code=403)
        response=await call_next(request)
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="no-referrer"
        return response

    @app.exception_handler(ProviderError)
    async def provider_error(request,exc): return JSONResponse({"detail":str(exc)},status_code=502)
    @app.exception_handler(ValidationError)
    async def validation_error(request,exc): return JSONResponse({"detail":"输入配置无效："+str(exc)[:400]},status_code=422)
    @app.exception_handler(ValueError)
    async def value_error(request,exc): return JSONResponse({"detail":str(exc)[:500]},status_code=400)

    app.include_router(settings_router)
    if is_demo:
        app.include_router(demo_router)
    app.include_router(core_router)
    app.include_router(experiment_router)
    from .demo import router as demo_router
    app.include_router(demo_router)
    dist=ROOT/"frontend"/"dist"
    @app.get("/{path:path}",include_in_schema=False)
    def frontend(path:str):
        if path.startswith("api/") or path=="api": raise HTTPException(404,"API 不存在")
        target=(dist/path).resolve()
        if not target.is_relative_to(dist.resolve()): raise HTTPException(404)
        if target.is_file(): return FileResponse(target)
        if Path(path).suffix: raise HTTPException(404,"静态资源不存在")
        if (dist/"index.html").exists(): return FileResponse(dist/"index.html")
        return JSONResponse({"message":"前端尚未构建，请在 frontend 执行 npm run build","api_docs":"/docs"})
    return app

app=create_app(settings=Settings(_env_file=None) if os.getenv("DEPLOYMENT_MODE")=="demo" else None)
