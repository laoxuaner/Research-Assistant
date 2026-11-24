"""Explicitly imported synthetic examples, never mixed with a real user's initial workspace."""
import shutil
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.orm import Session
from .config import ROOT
from .db import serialize
from .deps import session
from .models import Project, Paper, Experiment, DatasetVersion, AnalysisRun, Preference, uid
from .api_core import store_paper
from .api_experiments import versions, hash_file
from .papers import parse_job
from .stats_engine import read_dataset, profile_dataframe, analyze, AnalysisConfig

router=APIRouter(prefix="/api")

@router.post("/demo")
def import_demo(request:Request,background_tasks:BackgroundTasks,db:Session=Depends(session, scope="function")):
    pref=db.get(Preference,"demo_project_id")
    if pref and db.get(Project,pref.value): return {"project_id":pref.value,"reused":True}
    samples=ROOT/"samples"
    if not (samples/"independent.csv").exists():
        from fastapi import HTTPException
        raise HTTPException(400,"示例材料缺失，请先运行 scripts/generate_samples.py")
    settings=request.app.state.settings
    p=Project(name="示例 · 检索增强方法评估",question="检索增强方法如何影响实验得分？",
        hypothesis="在明确的实验条件下，B 组得分可能高于 A 组。",
        tags=["演示","测试材料"],notes="本项目全部文件和数值为人工构造的演示数据，不代表真实科研发现。")
    db.add(p);db.flush()
    ids=[]
    for name in ("demo_paper_zh.pdf","demo_paper_en.pdf"):
        if not (samples/name).exists(): continue
        paper,job=store_paper(db,settings,p.id,name,(samples/name).read_bytes())
        paper.tags=["演示","测试材料"]
        ids.append(paper.id)
        if job: background_tasks.add_task(parse_job,request.app.state.database,settings,job.id)
    exp=Experiment(project_id=p.id,name="示例 · 两组独立实验",hypothesis=p.hypothesis,paper_ids=ids,
        conditions="人工构造，每组 5 个独立实验单位。",parameters="metric=score; group=A/B",notes="用于验证统计流程，不代表真实实验。")
    db.add(exp);db.flush()
    directory=settings.directory()/"datasets";directory.mkdir(parents=True,exist_ok=True)
    path=directory/(uid()+".csv");shutil.copyfile(samples/"independent.csv",path)
    frame,sheets=read_dataset(path)
    ds=DatasetVersion(project_id=p.id,experiment_id=exp.id,filename="independent.csv",
        storage_path=str(path),original_path=str(path),sha256=hash_file(path),original_sha256=hash_file(path),
        sheet=None,sheets=sheets,transform={"steps":[],"sheet":None,"original_filename":"independent.csv"},**profile_dataframe(frame))
    db.add(ds);db.flush()
    cfg=AnalysisConfig(group_column="group",metric_column="score",group_a="A",group_b="B",
        design="independent",sample_id_column="sample_id",experimental_unit="独立样本",
        missing_policy="error",alternative="two-sided",unit="分",direction="higher",confirmed=True)
    from pathlib import Path
    import hashlib
    engine_bytes=(Path(__file__).parent/"stats_engine.py").read_bytes()
    engine_sha=hashlib.sha256(engine_bytes).hexdigest()
    engine_dir=settings.directory()/"engines"
    engine_dir.mkdir(parents=True,exist_ok=True)
    (engine_dir/(engine_sha+".py")).write_bytes(engine_bytes)
    run=AnalysisRun(project_id=p.id,experiment_id=exp.id,dataset_id=ds.id,config=cfg.model_dump(),
        result=analyze(frame,cfg),provenance={"dataset_sha256":ds.sha256,"original_sha256":ds.original_sha256,
            "transform":ds.transform,"versions":versions(),"app_version":"1.0.0",
            "analysis_code_sha256":engine_sha,
            "random_seed":None})
    db.add(run)
    if pref: pref.value=p.id
    else: db.add(Preference(key="demo_project_id",value=p.id))
    db.flush()
    result={"project_id":p.id,"reused":False}
    db.commit()
    return result
