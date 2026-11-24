from contextlib import asynccontextmanager
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
    database=Database(settings.directory())

    @asynccontextmanager
    async def lifespan(app):
        database.migrate()
        recover_jobs(database)
        yield
        database.engine.dispose()

    app=FastAPI(title="研知 · 科研论文知识库与实验分析助手",version="1.0.0",lifespan=lifespan)
    app.state.settings=settings
    app.state.database=database
    app.state.chat_provider=CompatibleChatProvider(settings)
    app.state.embedding_provider=CompatibleEmbeddingProvider(settings)
    origins=["http://127.0.0.1:5173","http://localhost:5173","http://127.0.0.1:8000","http://localhost:8000"]
    app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=["GET","POST","PATCH","DELETE"],allow_headers=["Content-Type"])
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=["127.0.0.1","localhost","testserver","[::1]"])

    @app.middleware("http")
    async def local_origin(request:Request,call_next):
        if request.method in ("POST","PATCH","PUT","DELETE") and request.headers.get("origin") and request.headers["origin"] not in origins:
            return JSONResponse({"detail":"仅允许本地工作台发起修改请求"},status_code=403)
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

app=create_app()
