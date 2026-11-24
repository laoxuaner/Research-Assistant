# 测试、启动脚本、示例与教学工具的全部解读

[返回目录](README.md) · [完整源码](ALL_SOURCE.md)

测试是对程序行为提出可执行的要求。基本结构是准备已知数据 → 调用真实函数或接口 → assert/expect 验证结果。测试通过不是科学结论正确的证明；测试桩也不是外部模型调用。

本章展示所有 Python 测试的顶层函数/类代码，并逐项说明。嵌套 helper 包含在父函数原文中。参数化案例数多于 test_ 函数数量。当前讲解工作没有重新运行整套应用测试；实际历史验收见 ../ACCEPTANCE.md。

## backend/tests/test_api.py

[打开完整源文件](E:/agent/backend/tests/test_api.py)

主要导入：pytest 提供 fixture、parametrize、raises、approx；TestClient 在进程内调用 FastAPI；pandas 构造已知表；monkeypatch 暂时替换外部依赖；subprocess 用于真的执行复现脚本。各文件只引入自己所需项。

### client（L18–22）

pytest fixture 使用 tmp_path 作为独立数据目录，关闭模型，进入 TestClient 上下文触发应用的启动/收尾。yield 后资源释放，避免测试写入你的真实 data。

[实际代码：backend/tests/test_api.py，L18–L22](E:/agent/backend/tests/test_api.py:18)

```python
def client(tmp_path):
    settings=Settings(_env_file=None,data_dir=str(tmp_path),ai_chat_model="",embedding_model="")
    app=create_app(settings=settings)
    with TestClient(app) as c:
        yield c
```


### project（L24–27）

向创建项目接口发送已知输入，先断言201，再返回 ID；后续测试都通过真实 API 建立前置资料。

[实际代码：backend/tests/test_api.py，L24–L27](E:/agent/backend/tests/test_api.py:24)

```python
def project(c,name="测试项目"):
    response=c.post("/api/projects",json={"name":name,"question":"检索增强方法得分"})
    assert response.status_code==201,response.text
    return response.json()["id"]
```


### upload（L29–33）

从 samples 打开真实 PDF，以 multipart 上传，断言创建成功并返回论文 ID；不是把预制解析结果直接塞到数据库。

[实际代码：backend/tests/test_api.py，L29–L33](E:/agent/backend/tests/test_api.py:29)

```python
def upload(c,pid,name="demo_paper_zh.pdf"):
    with (ROOT/"samples"/name).open("rb") as f:
        r=c.post(f"/api/projects/{pid}/papers",files=[("files",(name,f,"application/pdf"))])
    assert r.status_code==201,r.text
    return r.json()["papers"][0]["id"]
```


### experiment（L35–38）

通过真实实验创建接口建立记录，返回实验 ID。

[实际代码：backend/tests/test_api.py，L35–L38](E:/agent/backend/tests/test_api.py:35)

```python
def experiment(c,pid):
    r=c.post(f"/api/projects/{pid}/experiments",json={"name":"独立实验"})
    assert r.status_code==201,r.text
    return r.json()["id"]
```


### dataset（L40–45）

上传指定 CSV/XLSX；可选 sheet 以表单字段发送；返回服务器建立的固定数据版本。

[实际代码：backend/tests/test_api.py，L40–L45](E:/agent/backend/tests/test_api.py:40)

```python
def dataset(c,pid,eid,name="independent.csv",sheet=None):
    with (ROOT/"samples"/name).open("rb") as f:
        r=c.post(f"/api/projects/{pid}/experiments/{eid}/datasets",
            files={"file":(name,f)},data={"sheet":sheet} if sheet else {})
    assert r.status_code==201,r.text
    return r.json()
```


### config（L47–50）

集中构造已确认的独立样本配置，**kwargs 覆盖个别字段来验证边界。

[实际代码：backend/tests/test_api.py，L47–L50](E:/agent/backend/tests/test_api.py:47)

```python
def config(**kwargs):
    return {"group_column":"group","metric_column":"score","group_a":"A","group_b":"B",
        "design":"independent","sample_id_column":"sample_id","experimental_unit":"独立样本",
        "missing_policy":"error","alternative":"two-sided","unit":"分","direction":"higher","confirmed":True,**kwargs}
```


### run（L52–55）

发送某个数据版本和配置到 analyses 接口，断言201并取保存结果。

[实际代码：backend/tests/test_api.py，L52–L55](E:/agent/backend/tests/test_api.py:52)

```python
def run(c,pid,eid,ds,cfg=None):
    r=c.post(f"/api/projects/{pid}/experiments/{eid}/analyses",json={"dataset_id":ds["id"],"config":cfg or config()})
    assert r.status_code==201,r.text
    return r.json()
```


### test_empty_workspace_project_lifecycle_settings_no_secrets（L57–66）

验证新工作区为空、首页统计真实为0、项目可归档改名、设置默认不启用 AI，并且设置响应不含 key 字段。这只是响应字段检查，不是任意日志系统的形式化审计。

[实际代码：backend/tests/test_api.py，L57–L66](E:/agent/backend/tests/test_api.py:57)

```python
def test_empty_workspace_project_lifecycle_settings_no_secrets(client):
    assert client.get("/api/health").json()["status"]=="ok"
    assert client.get("/api/projects").json()==[]
    pid=project(client)
    overview=client.get(f"/api/projects/{pid}/overview").json()
    assert [overview[k] for k in ("paper_count","experiment_count","report_count","pending_jobs")]==[0,0,0,0]
    assert client.patch(f"/api/projects/{pid}",json={"archived":True,"name":"归档项目"}).json()["archived"]
    values=client.get("/api/settings").json()
    assert not values["chat_configured"] and not values["ai_enabled"]
    assert not any("key" in k for k in values)
```


### test_real_pdf_parse_search_dedupe_delete_and_scope（L68–88）

完成真实 PDF 解析→检索第2页→项目B不可访问项目A→换名重复文件仍去重→删除后FTS无残留。直接查 chunks_fts 数量补充验证索引清理。

[实际代码：backend/tests/test_api.py，L68–L88](E:/agent/backend/tests/test_api.py:68)

```python
def test_real_pdf_parse_search_dedupe_delete_and_scope(client):
    a,b=project(client,"项目A"),project(client,"项目B")
    paper=upload(client,a)
    details=client.get(f"/api/projects/{a}/papers/{paper}").json()
    assert details["status"]=="completed"
    assert details["page_count"]==2
    assert "每组包含 5 个独立样本" in details["pages"][0]["text"]
    results=client.post(f"/api/projects/{a}/search",json={"query":"均值差"}).json()["results"]
    assert results and any(x["page_number"]==2 for x in results)
    assert all(x["paper_id"]==paper and x["quote"] for x in results)
    assert client.post(f"/api/projects/{b}/search",json={"query":"均值差"}).json()["results"]==[]
    assert client.get(f"/api/projects/{b}/papers/{paper}/file").status_code==404
    assert client.post(f"/api/projects/{b}/search",json={"query":"均值差","paper_ids":[paper]}).status_code==404
    with (ROOT/"samples"/"demo_paper_zh.pdf").open("rb") as f:
        again=client.post(f"/api/projects/{a}/papers",files={"files":("renamed.pdf",f)}).json()
    assert again["duplicates"]==["renamed.pdf"]
    assert len(client.get(f"/api/projects/{a}/papers").json())==1
    assert client.delete(f"/api/projects/{a}/papers/{paper}").status_code==200
    assert client.post(f"/api/projects/{a}/search",json={"query":"均值差"}).json()["results"]==[]
    with client.app.state.database.session() as db:
        assert db.execute(text("SELECT count(*) FROM chunks_fts")).scalar()==0
```


### test_metadata_filters_and_notes（L90–96）

给论文设置年份、标签、阅读状态和笔记，分别用正确/错误过滤条件搜索，再将year显式清空。验证过滤与元数据更新。

[实际代码：backend/tests/test_api.py，L90–L96](E:/agent/backend/tests/test_api.py:90)

```python
def test_metadata_filters_and_notes(client):
    pid=project(client);paper=upload(client,pid)
    assert client.patch(f"/api/projects/{pid}/papers/{paper}",json={"tags":["方法"],"year":2024,"notes":"保留证据","reading_status":"read"}).status_code==200
    assert client.post(f"/api/projects/{pid}/search",json={"query":"样本","year":2023}).json()["results"]==[]
    assert client.post(f"/api/projects/{pid}/search",json={"query":"样本","year":2024,"tags":["方法"]}).json()["results"]
    assert client.post(f"/api/projects/{pid}/search",json={"query":"样本","tags":["其他"]}).json()["results"]==[]
    assert client.patch(f"/api/projects/{pid}/papers/{paper}",json={"year":None}).json()["year"] is None
```


### test_offline_evidence_no_fabricated_answer_and_no_evidence（L98–106）

离线问答有证据时必须明确未配置模型；无关问题返回 no_evidence 且没有引用。对话列表应保存用户和助手两条消息。

[实际代码：backend/tests/test_api.py，L98–L106](E:/agent/backend/tests/test_api.py:98)

```python
def test_offline_evidence_no_fabricated_answer_and_no_evidence(client):
    pid=project(client);upload(client,pid)
    r=client.post(f"/api/projects/{pid}/ask",json={"question":"均值差"}).json()
    assert r["mode"]=="offline" and r["citations"]
    assert "未配置" in r["answer"]
    r=client.post(f"/api/projects/{pid}/ask",json={"question":"Europa orbital eccentricity"}).json()
    assert r["mode"]=="no_evidence" and r["citations"]==[]
    stored=client.get(f"/api/projects/{pid}/conversations").json()
    assert len(stored)==2 and all(len(c["messages"])==2 for c in stored)
```


### GroundedChat（L108–113）

聊天测试桩：检查 system 中有不可信资料规则，再从本次 evidence 取一个真实引用构造响应。它验证协议，不调用互联网模型。

[实际代码：backend/tests/test_api.py，L108–L113](E:/agent/backend/tests/test_api.py:108)

```python
class GroundedChat:
    def generate(self,system,payload):
        assert "不可信" in system and "不能" in system
        evidence=payload["evidence"][0]
        return {"claims":[{"kind":"reported","text":"测试材料包含此证据。","citations":[{
            **{k:evidence[k] for k in ("paper_id","chunk_id","page_number")},"quote":evidence["quote"][:40]}]}]}
```


### ForgedChat（L115–117）

故意返回不存在的论文、片段、页码和引文，用来检验后端会拒绝编造引用。

[实际代码：backend/tests/test_api.py，L115–L117](E:/agent/backend/tests/test_api.py:115)

```python
class ForgedChat:
    def generate(self,system,payload):
        return {"claims":[{"kind":"reported","text":"编造发现","citations":[{"chunk_id":"bogus","paper_id":"bogus","page_number":99,"quote":"fake"}]}]}
```


### enable_chat（L119–123）

只在测试应用内设置本地兼容地址和测试模型，并替换 provider 对象，再通过设置接口启用。test-stub 不是交付给用户的真实模型名。

[实际代码：backend/tests/test_api.py，L119–L123](E:/agent/backend/tests/test_api.py:119)

```python
def enable_chat(client,provider):
    client.app.state.settings.ai_base_url="http://127.0.0.1:11434/v1"
    client.app.state.settings.ai_chat_model="test-stub"
    client.app.state.chat_provider=provider
    assert client.patch("/api/settings",json={"ai_enabled":True}).status_code==200
```


### test_model_contract_valid_and_forged_citations（L125–132）

先用合法测试桩确认 ai 模式保留引用，再用伪造测试桩确认编造的文字和引用被丢弃。

[实际代码：backend/tests/test_api.py，L125–L132](E:/agent/backend/tests/test_api.py:125)

```python
def test_model_contract_valid_and_forged_citations(client):
    pid=project(client);upload(client,pid)
    enable_chat(client,GroundedChat())
    result=client.post(f"/api/projects/{pid}/ask",json={"question":"均值差"}).json()
    assert result["mode"]=="ai" and result["citations"]
    enable_chat(client,ForgedChat())
    result=client.post(f"/api/projects/{pid}/ask",json={"question":"均值差"}).json()
    assert result["mode"]=="no_evidence" and not result["citations"] and "编造发现" not in result["answer"]
```


### test_ocr_corrupt_retry_and_invalid_upload（L134–145）

扫描 PDF 应 needs_ocr 且不可被文字检索；损坏 PDF 应 failed，重试后仍失败；伪装扩展名且没有 PDF 头的上传应400。

[实际代码：backend/tests/test_api.py，L134–L145](E:/agent/backend/tests/test_api.py:134)

```python
def test_ocr_corrupt_retry_and_invalid_upload(client):
    pid=project(client)
    paper=upload(client,pid,"scanned_demo.pdf")
    details=client.get(f"/api/projects/{pid}/papers/{paper}").json()
    assert details["status"]=="needs_ocr" and "OCR" in details["error"]
    assert client.post(f"/api/projects/{pid}/search",json={"query":"扫描"}).json()["results"]==[]
    broken=upload(client,pid,"corrupt_demo.pdf")
    assert client.get(f"/api/projects/{pid}/papers/{broken}").json()["status"]=="failed"
    assert client.post(f"/api/projects/{pid}/papers/{broken}/retry").status_code==200
    assert client.get(f"/api/projects/{pid}/papers/{broken}").json()["status"]=="failed"
    bad=client.post(f"/api/projects/{pid}/papers",files={"files":("../../fake.pdf",b"not PDF")})
    assert bad.status_code==400
```


### test_persist_restart_and_interrupted_job（L147–161）

在同一临时目录先写 running 论文/Job，关应用后重新创建，验证项目仍在、任务变 interrupted，迁移版本记录不重复。写入 running 状态是模拟中断，不是故意杀真实服务。

[实际代码：backend/tests/test_api.py，L147–L161](E:/agent/backend/tests/test_api.py:147)

```python
def test_persist_restart_and_interrupted_job(tmp_path):
    app=create_app(data_dir=tmp_path)
    with TestClient(app) as c:
        pid=project(c)
        with app.state.database.session() as db:
            paper=Paper(project_id=pid,title="中断",filename="x.pdf",storage_path=str(tmp_path/"x.pdf"),sha256="dummy",status="running")
            db.add(paper);db.flush()
            paper_id=paper.id
            db.add(Job(project_id=pid,resource_id=paper.id,kind="parse",status="running"))
    app2=create_app(data_dir=tmp_path)
    with TestClient(app2) as c:
        assert c.get("/api/projects").json()[0]["id"]==pid
        assert c.get(f"/api/projects/{pid}/papers/{paper_id}").json()["status"]=="interrupted"
        with app2.state.database.session() as db:
            assert db.execute(text("SELECT count(*) FROM schema_migrations")).scalar()==1
```


### test_timeout_is_explicit（L163–172）

monkeypatch 把 subprocess.run 替换为抛 TimeoutExpired 的 timeout 函数，直接运行解析任务，检查用户能看到超时原因。只模拟超时，不让测试真的等待一分钟。

[实际代码：backend/tests/test_api.py，L163–L172](E:/agent/backend/tests/test_api.py:163)

```python
def test_timeout_is_explicit(client,monkeypatch,tmp_path):
    pid=project(client)
    with client.app.state.database.session() as db:
        p=Paper(project_id=pid,title="timeout",filename="x.pdf",storage_path=str(tmp_path/"x.pdf"),sha256="timeout")
        db.add(p);db.flush()
        job=Job(project_id=pid,resource_id=p.id,kind="parse");db.add(job);db.flush();jid=job.id;paper_id=p.id
    def timeout(*args,**kwargs): raise subprocess.TimeoutExpired("parser",1)
    monkeypatch.setattr("app.papers.subprocess.run",timeout)
    parse_job(client.app.state.database,client.app.state.settings,jid)
    assert "超过时限" in client.get(f"/api/projects/{pid}/papers/{paper_id}").json()["error"]
```


### test_analysis_report_and_all_exports（L174–195）

通过 API 上传数据、保存分析和报告，核对差值2及已知p值；下载ZIP和各单文件格式，确认箱线图PNG头，并验证另一个项目不可读取分析或报告。

[实际代码：backend/tests/test_api.py，L174–L195](E:/agent/backend/tests/test_api.py:174)

```python
def test_analysis_report_and_all_exports(client,tmp_path):
    pid=project(client);eid=experiment(client,pid);ds=dataset(client,pid,eid)
    analysis=run(client,pid,eid,ds)
    assert analysis["result"]["comparison"]["difference"]==2
    assert analysis["result"]["comparison"]["pvalue"]==pytest.approx(0.08051623795726257)
    r=client.post(f"/api/projects/{pid}/reports",json={"analysis_id":analysis["id"]})
    assert r.status_code==201,r.text
    report=r.json()
    assert "2" in report["markdown"]
    prefix=f"/api/projects/{pid}/reports/{report['id']}/download"
    zipped=client.get(prefix+"?format=zip")
    assert zipped.status_code==200
    with zipfile.ZipFile(io.BytesIO(zipped.content)) as archive:
        assert {"report.md","summary.csv","plot.png","reproduce.py","analysis_config.json","provenance.json","requirements.txt"}<=set(archive.namelist())
        archive.extractall(tmp_path/"export")
    for fmt in ("md","csv","png","py","json"):
        response=client.get(prefix+"?format="+fmt)
        assert response.status_code==200 and len(response.content)>20
    assert client.get(f"/api/projects/{pid}/analyses/{analysis['id']}/plot.png?kind=box").content.startswith(b"\x89PNG")
    second=project(client,"另一个")
    assert client.get(f"/api/projects/{second}/analyses/{analysis['id']}").status_code==404
    assert client.get(f"/api/projects/{second}/reports/{report['id']}/download").status_code==404
```


### test_sheet_preview_is_read_only_and_version_bound（L197–204）

导入 Independent 工作表后预览 Paired，确认固定版本的sheet仍为 Independent，随后分析差值仍为2。预览不等于重新导入。

[实际代码：backend/tests/test_api.py，L197–L204](E:/agent/backend/tests/test_api.py:197)

```python
def test_sheet_preview_is_read_only_and_version_bound(client):
    pid=project(client);eid=experiment(client,pid);ds=dataset(client,pid,eid,"experiments.xlsx","Independent")
    other=client.get(f"/api/projects/{pid}/datasets/{ds['id']}/preview?sheet=Paired")
    assert other.status_code==200
    current=client.get(f"/api/projects/{pid}/experiments/{eid}").json()["datasets"][0]
    assert current["sheet"]=="Independent"
    analysis=run(client,pid,eid,ds)
    assert analysis["result"]["comparison"]["difference"]==2
```


### test_cleaning_is_new_version_and_hash_tampering_detected（L206–219）

清洗应生成不同ID、parent_id 指向原版本并保留原文件指纹；随后故意改原文件，分析应409而非偷偷使用变化后的内容。

[实际代码：backend/tests/test_api.py，L206–L219](E:/agent/backend/tests/test_api.py:206)

```python
def test_cleaning_is_new_version_and_hash_tampering_detected(client):
    pid=project(client);eid=experiment(client,pid);ds=dataset(client,pid,eid,"missing_values.csv")
    r=client.post(f"/api/projects/{pid}/experiments/{eid}/datasets/{ds['id']}/clean",json={"drop_missing_columns":["score"]})
    assert r.status_code==201,r.text
    clean=r.json()
    assert clean["parent_id"]==ds["id"] and clean["id"]!=ds["id"]
    assert clean["original_sha256"]==ds["original_sha256"]
    assert clean["row_count"]<ds["row_count"]
    with client.app.state.database.session() as db:
        from app.models import DatasetVersion
        row=db.get(DatasetVersion,ds["id"])
        Path(row.storage_path).write_text("tampered",encoding="utf-8")
    r=client.post(f"/api/projects/{pid}/experiments/{eid}/analyses",json={"dataset_id":ds["id"],"config":config(missing_policy="drop")})
    assert r.status_code==409
```


### test_no_confirmation_and_unsafe_origin_rejected（L221–225）

confirmed=False 的推断配置应422；非白名单 Origin 发起创建项目应403。二者分别检查分析确认与浏览器来源。

[实际代码：backend/tests/test_api.py，L221–L225](E:/agent/backend/tests/test_api.py:221)

```python
def test_no_confirmation_and_unsafe_origin_rejected(client):
    pid=project(client);eid=experiment(client,pid);ds=dataset(client,pid,eid)
    r=client.post(f"/api/projects/{pid}/experiments/{eid}/analyses",json={"dataset_id":ds["id"],"config":config(confirmed=False)})
    assert r.status_code==422
    assert client.post("/api/projects",json={"name":"外部"},headers={"Origin":"https://untrusted.example"}).status_code==403
```


### test_demo_explicit_idempotent_real_data（L227–235）

空工作区不会自行出现示例；调用示例导入后有2篇论文和1个实验，再调用返回同一项目，验证显式导入与幂等。

[实际代码：backend/tests/test_api.py，L227–L235](E:/agent/backend/tests/test_api.py:227)

```python
def test_demo_explicit_idempotent_real_data(client):
    assert client.get("/api/projects").json()==[]
    r=client.post("/api/demo")
    assert r.status_code==200,r.text
    pid=r.json()["project_id"]
    assert client.post("/api/demo").json()["project_id"]==pid
    assert len(client.get(f"/api/projects/{pid}/papers").json())==2
    overview=client.get(f"/api/projects/{pid}/overview").json()
    assert overview["paper_count"]==2 and overview["experiment_count"]==1
```


### NullClaimsChat（L238–239）

返回结构不合约的 claims=None 和 fields=None，专用于模拟模型输出格式错误。

[实际代码：backend/tests/test_api.py，L238–L239](E:/agent/backend/tests/test_api.py:238)

```python
class NullClaimsChat:
    def generate(self,system,payload): return {"claims":None,"fields":None}
```


### test_malformed_model_output_is_actionable_not_server_crash（L241–245）

不合约问答和阅读卡应返回可解释的502，避免出现没有解释的服务器崩溃。

[实际代码：backend/tests/test_api.py，L241–L245](E:/agent/backend/tests/test_api.py:241)

```python
def test_malformed_model_output_is_actionable_not_server_crash(client):
    pid=project(client);paper=upload(client,pid)
    enable_chat(client,NullClaimsChat())
    assert client.post(f"/api/projects/{pid}/ask",json={"question":"均值差"}).status_code==502
    assert client.post(f"/api/projects/{pid}/papers/{paper}/reading-card").status_code==502
```


### FixedEmbedding（L247–249）

返回固定、非零、有限的测试向量。dimension 可变，让测试模拟服务返回维度变化；不代表真实语义召回质量。

[实际代码：backend/tests/test_api.py，L247–L249](E:/agent/backend/tests/test_api.py:247)

```python
class FixedEmbedding:
    dimension=2
    def embed(self,values): return [[1.0]+[0.0]*(self.dimension-1) for _ in values]
```


### test_hybrid_scope_selected_paper_and_dimension_change（L251–275）

为A项目建向量索引，语义查询也必须限定选定论文；B项目不能看到A的近邻。之后把维度改3验证关键词回退警告，再改模型名验证 needs_rebuild。

[实际代码：backend/tests/test_api.py，L251–L275](E:/agent/backend/tests/test_api.py:251)

```python
def test_hybrid_scope_selected_paper_and_dimension_change(client):
    a,b=project(client,"A"),project(client,"B")
    first=upload(client,a)
    second=upload(client,a,"demo_paper_en.pdf")
    upload(client,b,"demo_paper_en.pdf")
    settings=client.app.state.settings
    settings.embedding_base_url="http://127.0.0.1:11434/v1"
    settings.embedding_model="test-embedding"
    provider=FixedEmbedding()
    client.app.state.embedding_provider=provider
    client.patch("/api/settings",json={"ai_enabled":True})
    assert client.post(f"/api/projects/{a}/embeddings/rebuild").status_code==200
    status=client.get(f"/api/projects/{a}/embedding-status").json()
    assert status["indexed_chunks"]==status["total_chunks"]>0
    result=client.post(f"/api/projects/{a}/search",json={"query":"未知语义问题","paper_ids":[first]}).json()
    assert result["mode"]=="hybrid" and result["results"]
    assert all(x["paper_id"]==first for x in result["results"])
    # B has no vectors until explicitly indexed and must never see A's nearest neighbours.
    result=client.post(f"/api/projects/{b}/search",json={"query":"未知语义问题"}).json()
    assert result["results"]==[]
    provider.dimension=3
    result=client.post(f"/api/projects/{a}/search",json={"query":"均值差"}).json()
    assert result["results"] and any("维度" in warning for warning in result["warnings"])
    settings.embedding_model="new-model"
    assert client.get(f"/api/projects/{a}/embedding-status").json()["needs_rebuild"]
```


### test_cleaned_xlsx_export_retains_original_sheet_and_code（L277–290）

对XLSX生成清洗版本并保存分析，再导出ZIP；包内仍是原始xlsx，保留原工作表名和分析代码指纹。

[实际代码：backend/tests/test_api.py，L277–L290](E:/agent/backend/tests/test_api.py:277)

```python
def test_cleaned_xlsx_export_retains_original_sheet_and_code(client,tmp_path):
    pid=project(client);eid=experiment(client,pid);ds=dataset(client,pid,eid,"experiments.xlsx","Independent")
    r=client.post(f"/api/projects/{pid}/experiments/{eid}/datasets/{ds['id']}/clean",json={"drop_duplicate_rows":True})
    assert r.status_code==201,r.text
    analysis=run(client,pid,eid,r.json())
    report=client.post(f"/api/projects/{pid}/reports",json={"analysis_id":analysis["id"]})
    assert report.status_code==201,report.text
    zipped=client.get(f"/api/projects/{pid}/reports/{report.json()['id']}/download?format=zip")
    assert zipped.status_code==200
    with zipfile.ZipFile(io.BytesIO(zipped.content)) as archive:
        assert "original/data.xlsx" in archive.namelist()
        manifest=json.loads(archive.read("provenance.json"))
        assert manifest["sheet"]=="Independent"
        assert manifest["stats_engine_sha256"]==analysis["provenance"]["analysis_code_sha256"]
```


### test_failed_database_commit_never_returns_success（L293–308）

用 SQLAlchemy commit 事件中的 fail_commit 在提交时只失败一次；API 必须返回400，且项目列表仍为空。finally 移除事件，防止污染其他测试。

[实际代码：backend/tests/test_api.py，L293–L308](E:/agent/backend/tests/test_api.py:293)

```python
def test_failed_database_commit_never_returns_success(client):
    from sqlalchemy import event
    engine=client.app.state.database.engine
    armed=[True]
    def fail_commit(connection):
        if armed[0]:
            armed[0]=False
            raise ValueError("测试：存储提交失败")
    event.listen(engine,"commit",fail_commit)
    try:
        response=client.post("/api/projects",json={"name":"不能虚报已保存"})
        assert response.status_code==400
        assert "存储提交失败" in response.json()["detail"]
    finally:
        event.remove(engine,"commit",fail_commit)
    assert client.get("/api/projects").json()==[]
```


## backend/tests/test_stats.py

[打开完整源文件](E:/agent/backend/tests/test_stats.py)

主要导入：pytest 提供 fixture、parametrize、raises、approx；TestClient 在进程内调用 FastAPI；pandas 构造已知表；monkeypatch 暂时替换外部依赖；subprocess 用于真的执行复现脚本。各文件只引入自己所需项。

### independent_config（L11–18）

生成统计测试使用的 AnalysisConfig，默认独立单位id、指标value、双侧检验和已确认；changes允许测试改变一项条件。

[实际代码：backend/tests/test_stats.py，L11–L18](E:/agent/backend/tests/test_stats.py:11)

```python
def independent_config(**changes):
    values = dict(
        group_column="group", metric_column="value", group_a="A", group_b="B",
        design="independent", experimental_unit="one subject", sample_id_column="id",
        missing_policy="error", alternative="two-sided", confirmed=True, unit="ms",
    )
    values.update(changes)
    return AnalysisConfig(**values)
```


### small_data（L21–26）

提供A=[1,2,3,4,5]、B=[2,4,6,8,10]的已知小数据。它与 samples/independent.csv 的B组不同，因此本模块差值是3，不是教学示例的2。

[实际代码：backend/tests/test_stats.py，L21–L26](E:/agent/backend/tests/test_stats.py:21)

```python
def small_data():
    return pd.DataFrame({
        "id": [f"A{i}" for i in range(5)] + [f"B{i}" for i in range(5)],
        "group": ["A"] * 5 + ["B"] * 5,
        "value": [1, 2, 3, 4, 5, 2, 4, 6, 8, 10],
    })
```


### test_welch_known_reference_and_b_minus_a（L29–44）

手算均值、方差、自由度和t统计量，并与固定参考p值比较；最后 JSON allow_nan=False 确认结果没有非法NaN/Infinity。

[实际代码：backend/tests/test_stats.py，L29–L44](E:/agent/backend/tests/test_stats.py:29)

```python
def test_welch_known_reference_and_b_minus_a():
    result = analyze(small_data(), independent_config())
    a, b = result["summary"]
    assert a["n"] == b["n"] == 5
    assert a["mean"] == 3
    assert a["std"] == pytest.approx(math.sqrt(2.5))
    assert b["mean"] == 6
    cmp = result["comparison"]
    assert cmp["status"] == "completed"
    assert cmp["difference"] == 3
    assert cmp["relative_change_percent"] == 100
    assert cmp["df"] == pytest.approx(100 / 17)
    assert cmp["statistic"] == pytest.approx(3 / math.sqrt(2.5))
    assert cmp["pvalue"] == pytest.approx(0.10753119493062728, rel=1e-12)
    assert cmp["ci_low"] < 0 < cmp["ci_high"]
    json.dumps(result, allow_nan=False)
```


### test_single_sided_pvalue_is_for_b_minus_a_and_ci_stays_two_sided（L47–54）

同一数据检验 greater/less/two-sided，验证方向始终是 B−A，单侧p与双侧p的关系正确，而95%CI始终保持双侧。

[实际代码：backend/tests/test_stats.py，L47–L54](E:/agent/backend/tests/test_stats.py:47)

```python
def test_single_sided_pvalue_is_for_b_minus_a_and_ci_stays_two_sided():
    greater = analyze(small_data(), independent_config(alternative="greater"))["comparison"]
    less = analyze(small_data(), independent_config(alternative="less"))["comparison"]
    two = analyze(small_data(), independent_config())["comparison"]
    assert greater["pvalue"] == pytest.approx(two["pvalue"] / 2)
    assert less["pvalue"] == pytest.approx(1 - greater["pvalue"])
    assert greater["ci_low"] == two["ci_low"] == less["ci_low"]
    assert greater["ci_high"] == two["ci_high"] == less["ci_high"]
```


### test_strict_pairing_matches_by_id_not_row_order（L57–74）

故意打乱B组配对ID行顺序，按ID匹配后核对差值、df、t和闭式参考p值；证明不是直接按行相减。

[实际代码：backend/tests/test_stats.py，L57–L74](E:/agent/backend/tests/test_stats.py:57)

```python
def test_strict_pairing_matches_by_id_not_row_order():
    data = pd.DataFrame({
        "pair": [1, 2, 3, 4, 5, 5, 3, 1, 4, 2],
        "group": ["A"] * 5 + ["B"] * 5,
        "value": [10, 10, 10, 10, 10, 15, 13, 11, 14, 12],
    })
    config = independent_config(design="paired", sample_id_column=None, pair_column="pair")
    result = analyze(data, config)
    cmp = result["comparison"]
    assert cmp["status"] == "completed"
    assert cmp["difference"] == pytest.approx(3)
    assert cmp["df"] == 4
    assert cmp["statistic"] == pytest.approx(math.sqrt(18))
    # Closed-form two-sided tail for t with 4 degrees of freedom.
    s = math.sqrt(9 / 11)
    assert cmp["pvalue"] == pytest.approx(1 - 1.5 * s + .5 * s**3, abs=1e-13)
    assert cmp["ci_low"] == pytest.approx(3 - 1.9632431614775607)
    assert cmp["ci_high"] == pytest.approx(3 + 1.9632431614775607)
```


### test_inference_requires_explicit_design_confirmation（L81–83）

parametrize 分别测试未确认、空实验单位、无样本ID和同组选两次，创建配置应抛 ValueError。一个测试定义会展开成多个案例。

[实际代码：backend/tests/test_stats.py，L81–L83](E:/agent/backend/tests/test_stats.py:81)

```python
def test_inference_requires_explicit_design_confirmation(change):
    with pytest.raises(ValueError):
        independent_config(**change)
```


### test_duplicate_independent_units_retains_description_without_test（L86–93）

让一个ID跨组重复，描述均值仍返回，但 comparison=unsupported 且p为None，原因包含重复。

[实际代码：backend/tests/test_stats.py，L86–L93](E:/agent/backend/tests/test_stats.py:86)

```python
def test_duplicate_independent_units_retains_description_without_test():
    data = small_data()
    data.loc[5, "id"] = data.loc[0, "id"]
    result = analyze(data, independent_config())
    assert result["summary"][0]["mean"] == 3
    assert result["comparison"]["status"] == "unsupported"
    assert result["comparison"]["pvalue"] is None
    assert "重复" in result["comparison"]["reason"]
```


### test_duplicate_unit_not_hidden_by_metric_exclusion（L96–101）

重复ID所在记录的指标同时缺失，也不能通过排除指标记录掩盖重复实验单位。ID检查必须先于指标排除。

[实际代码：backend/tests/test_stats.py，L96–L101](E:/agent/backend/tests/test_stats.py:96)

```python
def test_duplicate_unit_not_hidden_by_metric_exclusion():
    data = small_data()
    data.loc[1, "id"] = data.loc[0, "id"]
    data.loc[1, "value"] = np.nan
    result = analyze(data, independent_config(missing_policy="drop"))
    assert result["comparison"]["status"] == "unsupported"
```


### test_duplicate_or_unmatched_pairs_are_not_silently_deleted（L108–113）

参数化重复配对或两组配对集合不同的情况：禁止推断，但原始点仍保留。

[实际代码：backend/tests/test_stats.py，L108–L113](E:/agent/backend/tests/test_stats.py:108)

```python
def test_duplicate_or_unmatched_pairs_are_not_silently_deleted(pair_values):
    data = pd.DataFrame({"group": ["A"] * 3 + ["B"] * 3,
                         "pair": pair_values, "value": [1, 2, 3, 3, 4, 6]})
    result = analyze(data, independent_config(design="paired", sample_id_column=None, pair_column="pair"))
    assert result["comparison"]["status"] == "unsupported"
    assert len(result["points"]) == 6
```


### test_pairwise_metric_exclusion_removes_whole_pair_with_audit（L116–126）

一个配对中一侧指标缺失，明确drop时要移除整对，记录两侧行号，确保剩余两组样本数仍相等。

[实际代码：backend/tests/test_stats.py，L116–L126](E:/agent/backend/tests/test_stats.py:116)

```python
def test_pairwise_metric_exclusion_removes_whole_pair_with_audit():
    data = pd.DataFrame({
        "group": ["A"] * 3 + ["B"] * 3,
        "pair": [1, 2, 3, 1, 2, 3],
        "value": [1, None, 3, 3, 5, 6],
    })
    result = analyze(data, independent_config(design="paired", sample_id_column=None, pair_column="pair", missing_policy="drop"))
    assert [s["n"] for s in result["summary"]] == [2, 2]
    assert result["comparison"]["difference"] == 2.5
    assert {e["row"] for e in result["exclusions"]} == {3, 6}
    assert result["comparison"]["status"] == "completed"
```


### test_missing_invalid_and_infinite_values_are_explicit（L129–138）

把两个值改成字符串和无穷大；默认策略抛错，显式drop后样本数与排除计数正确且结果可严格JSON序列化。

[实际代码：backend/tests/test_stats.py，L129–L138](E:/agent/backend/tests/test_stats.py:129)

```python
def test_missing_invalid_and_infinite_values_are_explicit():
    data = small_data().astype({"value": object})
    data.loc[0, "value"] = "invalid"
    data.loc[1, "value"] = float("inf")
    with pytest.raises(ValueError, match="非数值"):
        analyze(data, independent_config())
    result = analyze(data, independent_config(missing_policy="drop"))
    assert [s["n"] for s in result["summary"]] == [3, 5]
    assert len(result["exclusions"]) == 2
    json.dumps(result, allow_nan=False)
```


### test_empty_group_zero_baseline_and_constant_values_are_safe（L141–151）

A常量0时相对变化为None，不产生无解释的无穷大或p值；每组只剩1个观测时应给样本不足原因。

[实际代码：backend/tests/test_stats.py，L141–L151](E:/agent/backend/tests/test_stats.py:141)

```python
def test_empty_group_zero_baseline_and_constant_values_are_safe():
    data = small_data()
    data.loc[:4, "value"] = 0
    result = analyze(data, independent_config())
    assert result["comparison"]["relative_change_percent"] is None
    assert result["comparison"]["status"] == "unsupported"
    assert result["comparison"]["pvalue"] is None
    json.dumps(result, allow_nan=False)
    result = analyze(small_data().iloc[[0, 5]], independent_config())
    assert result["comparison"]["status"] == "unsupported"
    assert "不足" in result["comparison"]["reason"]
```


### test_paired_constant_differences_do_not_emit_fake_significance（L154–159）

每对差值完全相同，差值方差为0；程序明确unsupported，避免把数值退化误报成极强显著性。

[实际代码：backend/tests/test_stats.py，L154–L159](E:/agent/backend/tests/test_stats.py:154)

```python
def test_paired_constant_differences_do_not_emit_fake_significance():
    data = pd.DataFrame({"group": ["A", "A", "B", "B"], "pair": [1, 2, 1, 2], "value": [1, 2, 3, 4]})
    result = analyze(data, independent_config(design="paired", pair_column="pair", sample_id_column=None))
    assert result["comparison"]["status"] == "unsupported"
    assert result["comparison"]["pvalue"] is None
    json.dumps(result, allow_nan=False)
```


### test_profile_marks_outliers_and_preserves_input（L162–173）

检查缺失、非数值和IQR异常值计数；异常值未自动删除，原DataFrame内容也不被质量概况函数修改。

[实际代码：backend/tests/test_stats.py，L162–L173](E:/agent/backend/tests/test_stats.py:162)

```python
def test_profile_marks_outliers_and_preserves_input():
    data = pd.DataFrame({"value": [1, 1, 1, 1, 100, None, "oops"], "group": ["A"] * 7})
    before = data.copy(deep=True)
    profile = profile_dataframe(data)
    quality = profile["quality"]["columns"][0]
    assert quality["missing"] == 1
    assert quality["non_numeric"] == 1
    assert quality["outlier_count"] == 1
    assert profile["quality"]["outliers_removed"] is False
    assert profile["row_count"] == 7
    pd.testing.assert_frame_equal(before, data)
    json.dumps(profile, allow_nan=False)
```


### test_whitelisted_transforms_audit_and_do_not_mutate_source（L176–184）

按明确规则去缺失及完全重复行，检查受影响行数且原表不变；未知 eval 规则必须拒绝。

[实际代码：backend/tests/test_stats.py，L176–L184](E:/agent/backend/tests/test_stats.py:176)

```python
def test_whitelisted_transforms_audit_and_do_not_mutate_source():
    data = pd.DataFrame({"x": [1, None, 2, 2, ""]})
    cleaned, audit = apply_transforms(data, {"steps": [{"drop_missing_columns": ["x"], "drop_duplicate_rows": True}]})
    assert cleaned["x"].tolist() == [1, 2]
    assert len(data) == 5
    assert audit[0]["dropped_missing_rows"] == 2
    assert audit[0]["dropped_duplicate_rows"] == 1
    with pytest.raises(ValueError):
        apply_transforms(data, {"steps": [{"eval": "1+1"}]})
```


### test_csv_and_xlsx_sheet_selection_and_profile（L187–201）

写临时CSV和两工作表XLSX，再读回指定sheet，确认行数与sheet清单；不存在的sheet应明确报错。

[实际代码：backend/tests/test_stats.py，L187–L201](E:/agent/backend/tests/test_stats.py:187)

```python
def test_csv_and_xlsx_sheet_selection_and_profile(tmp_path):
    csv = tmp_path / "sample.csv"
    small_data().to_csv(csv, index=False, encoding="utf-8-sig")
    frame, sheets = read_dataset(csv)
    assert sheets == []
    assert len(frame) == 10
    xlsx = tmp_path / "sample.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        small_data().to_excel(writer, sheet_name="实验", index=False)
        small_data().head(3).to_excel(writer, sheet_name="子集", index=False)
    selected, sheets = read_dataset(xlsx, sheet="子集")
    assert sheets == ["实验", "子集"]
    assert len(selected) == 3
    with pytest.raises(ValueError, match="工作表不存在"):
        read_dataset(xlsx, sheet="missing")
```


### test_read_dataset_preserves_identifiers_precision_and_literal_na（L203–209）

读取时保留001编号、NA/NULL字面标签和高精度数值字符串，避免 pandas 默认推断悄悄改变数据。

[实际代码：backend/tests/test_stats.py，L203–L209](E:/agent/backend/tests/test_stats.py:203)

```python
def test_read_dataset_preserves_identifiers_precision_and_literal_na(tmp_path):
    source = tmp_path / "labels.csv"
    source.write_text("id,group,value\n001,NA,1.0000000000000002\n1,NULL,2.35\n", encoding="utf-8")
    loaded, _ = read_dataset(source)
    assert loaded["id"].tolist() == ["001", "1"]
    assert loaded["group"].tolist() == ["NA", "NULL"]
    assert loaded["value"].tolist() == ["1.0000000000000002", "2.35"]
```


### test_paired_repeated_subjects_are_rejected_even_with_unique_trial_pairs（L212–221）

即使每次试验pair ID唯一，同一实验单位在组内重复也不能当成独立配对；应拒绝推断并解释重复单位。

[实际代码：backend/tests/test_stats.py，L212–L221](E:/agent/backend/tests/test_stats.py:212)

```python
def test_paired_repeated_subjects_are_rejected_even_with_unique_trial_pairs():
    data = pd.DataFrame({
        "group": ["A"] * 3 + ["B"] * 3,
        "pair": [1, 2, 3, 1, 2, 3],
        "id": ["same-subject", "same-subject", "another", "same-subject", "same-subject", "another"],
        "value": [1, 2, 3, 3, 5, 7],
    })
    result = analyze(data, independent_config(design="paired", pair_column="pair"))
    assert result["comparison"]["status"] == "unsupported"
    assert "重复实验单位" in result["comparison"]["reason"]
```


### test_welch_is_scale_invariant_without_underflow_or_overflow（L224–233）

把数值缩放至1e−160与1e160，t和p应相同，差值按比例变化；验证数值稳定性而非只测试普通量级。

[实际代码：backend/tests/test_stats.py，L224–L233](E:/agent/backend/tests/test_stats.py:224)

```python
def test_welch_is_scale_invariant_without_underflow_or_overflow(scale):
    data = small_data()
    data["value"] = data["value"] * scale
    result = analyze(data, independent_config())
    cmp = result["comparison"]
    assert cmp["status"] == "completed"
    assert cmp["pvalue"] == pytest.approx(0.10753119493062728)
    assert cmp["statistic"] == pytest.approx(3 / math.sqrt(2.5))
    assert cmp["difference"] / scale == pytest.approx(3)
    json.dumps(result, allow_nan=False)
```


### test_paired_exact_constant_differences_remain_unsupported_after_scaling（L236–240）

原始配对差值恒定时仍应拒绝，不能由浮点缩放误差制造出看似非零方差。

[实际代码：backend/tests/test_stats.py，L236–L240](E:/agent/backend/tests/test_stats.py:236)

```python
def test_paired_exact_constant_differences_remain_unsupported_after_scaling():
    data = pd.DataFrame({"group": ["A", "A", "B", "B"], "pair": [1, 2, 1, 2], "value": [10, 11, 12, 13]})
    result = analyze(data, independent_config(design="paired", pair_column="pair", sample_id_column=None))
    assert result["comparison"]["status"] == "unsupported"
    assert result["comparison"]["pvalue"] is None
```


### test_internal_column_conflicts_are_rejected_without_mutating_input（L243–249）

对每个内部保留列名做参数化输入，必须拒绝且不覆盖原始列。

[实际代码：backend/tests/test_stats.py，L243–L249](E:/agent/backend/tests/test_stats.py:243)

```python
def test_internal_column_conflicts_are_rejected_without_mutating_input(column):
    data = small_data()
    data[column] = "original"
    before = data.copy(deep=True)
    with pytest.raises(ValueError, match="内部保留"):
        analyze(data, independent_config())
    pd.testing.assert_frame_equal(before, data)
```


## backend/tests/test_providers.py

[打开完整源文件](E:/agent/backend/tests/test_providers.py)

主要导入：pytest 提供 fixture、parametrize、raises、approx；TestClient 在进程内调用 FastAPI；pandas 构造已知表；monkeypatch 暂时替换外部依赖；subprocess 用于真的执行复现脚本。各文件只引入自己所需项。

### test_compatible_chat_and_embedding_wire_contract（L9–27）

httpx.MockTransport 拦截请求，检查模型名、输出参数、独立密钥与没有tools字段；故意打乱embedding响应index，适配器必须按index重排。

[实际代码：backend/tests/test_providers.py，L9–L27](E:/agent/backend/tests/test_providers.py:9)

```python
def test_compatible_chat_and_embedding_wire_contract(monkeypatch):
    requests=[]
    real=httpx.Client
    def handle(request):
        import json
        body=json.loads(request.content)
        requests.append((str(request.url),body,request.headers.get("authorization")))
        if request.url.path.endswith("chat/completions"):
            return httpx.Response(200,json={"choices":[{"message":{"content":'{"claims":[]}'}}]})
        return httpx.Response(200,json={"data":[{"index":1,"embedding":[0,1]},{"index":0,"embedding":[1,0]}]})
    monkeypatch.setattr(httpx,"Client",lambda **kwargs:real(transport=httpx.MockTransport(handle),**kwargs))
    settings=Settings(_env_file=None,ai_chat_model="test-model",ai_api_key="test-secret",embedding_model="embed-model",embedding_api_key="separate-secret")
    assert CompatibleChatProvider(settings).generate("rules",{"question":"hi"})=={"claims":[]}
    assert CompatibleEmbeddingProvider(settings).embed(["a","b"])==[[1.0,0.0],[0.0,1.0]]
    assert requests[0][1]["model"]=="test-model"
    assert requests[0][1]["max_completion_tokens"]==1800
    assert requests[0][2]=="Bearer test-secret"
    assert requests[1][2]=="Bearer separate-secret"
    assert "tools" not in requests[0][1]
```


### test_provider_errors_sanitized_and_finite_retries（L29–39）

模拟HTTP429且响应含敏感正文，默认一次重试总共2次；对外错误只带状态和可读说明，不泄露响应正文。

[实际代码：backend/tests/test_providers.py，L29–L39](E:/agent/backend/tests/test_providers.py:29)

```python
def test_provider_errors_sanitized_and_finite_retries(monkeypatch):
    calls=[]
    real=httpx.Client
    def handle(request):
        calls.append(request)
        return httpx.Response(429,text="sensitive response including some secret")
    monkeypatch.setattr(httpx,"Client",lambda **kwargs:real(transport=httpx.MockTransport(handle),**kwargs))
    settings=Settings(_env_file=None,ai_retries=1)
    with pytest.raises(ProviderError,match="HTTP 429") as error:
        request_json("https://example.com/v1","secret","chat/completions",{},settings)
    assert len(calls)==2 and "sensitive" not in str(error.value)
```


### test_nonfinite_vectors_and_nonobject_chat_rejected（L41–51）

实际代码先测试全零向量被拒绝，再测试聊天内容是JSON数组而非对象被拒绝。测试名提到nonfinite，但本例没有直接构造NaN向量，不能夸大覆盖。

[实际代码：backend/tests/test_providers.py，L41–L51](E:/agent/backend/tests/test_providers.py:41)

```python
def test_nonfinite_vectors_and_nonobject_chat_rejected(monkeypatch):
    real=httpx.Client
    mode=["vectors"]
    def handle(request):
        if mode[0]=="vectors": return httpx.Response(200,json={"data":[{"index":0,"embedding":[0,0]}]})
        return httpx.Response(200,json={"choices":[{"message":{"content":"[]"}}]})
    monkeypatch.setattr(httpx,"Client",lambda **kwargs:real(transport=httpx.MockTransport(handle),**kwargs))
    s=Settings(_env_file=None)
    with pytest.raises(ProviderError): CompatibleEmbeddingProvider(s).embed(["a"])
    mode[0]="chat"
    with pytest.raises(ProviderError): CompatibleChatProvider(s).generate("rules",{})
```


### test_reference_quote_page_and_bool_validation（L53–59）

合法原文子串可引用；布尔值True不能冒充页码1；错误页码、伪造摘录和别的论文ID都无效。

[实际代码：backend/tests/test_providers.py，L53–L59](E:/agent/backend/tests/test_providers.py:53)

```python
def test_reference_quote_page_and_bool_validation():
    source={"paper_id":"paper","chunk_id":"chunk","page_number":1,"quote":"This is original evidence.","title":"Test"}
    assert validate_citations([{**source,"quote":"original evidence"}],[source])
    assert not validate_citations([{**source,"page_number":True}],[source])
    assert not validate_citations([{**source,"page_number":2}],[source])
    assert not validate_citations([{**source,"quote":"fabricated evidence"}],[source])
    assert not validate_citations([{**source,"paper_id":"other-project"}],[source])
```


### test_provider_local_configuration（L61–64）

localhost/127.0.0.1的本地服务可无密钥，外部服务缺密钥不可被视为已配置。

[实际代码：backend/tests/test_providers.py，L61–L64](E:/agent/backend/tests/test_providers.py:61)

```python
def test_provider_local_configuration():
    assert configured("http://127.0.0.1:11434/v1","local","")
    assert not configured("https://api.openai.com/v1","remote","")
    assert not configured("http://example.org/v1","remote","")
```


## backend/tests/test_exports.py

[打开完整源文件](E:/agent/backend/tests/test_exports.py)

主要导入：pytest 提供 fixture、parametrize、raises、approx；TestClient 在进程内调用 FastAPI；pandas 构造已知表；monkeypatch 暂时替换外部依赖；subprocess 用于真的执行复现脚本。各文件只引入自己所需项。

### fixture_context（L16–35）

把已保存分析、项目问题、实验设计、数据版本和一条合成证据组合成报告上下文，允许覆盖数据字段验证导出边界。

[实际代码：backend/tests/test_exports.py，L16–L35](E:/agent/backend/tests/test_exports.py:16)

```python
def fixture_context(frame, **dataset_changes):
    config = AnalysisConfig(
        group_column="group", metric_column="value", group_a="A", group_b="B",
        design="independent", sample_id_column="id", experimental_unit="subject",
        confirmed=True, missing_policy="drop", unit="ms",
    )
    result = analyze(frame, config)
    dataset = {
        "id": "version-1", "filename": "experiment.csv", "sha256": "version-hash",
        "sheet": None, "transform": {"steps": []},
    }
    dataset.update(dataset_changes)
    return {
        "project": {"name": "测试项目", "question": "对比两组响应", "hypothesis": "B 组响应存在差异"},
        "experiment": {"name": "测试实验", "hypothesis": "示例假设", "conditions": "相同测量协议"},
        "dataset": dataset,
        "analysis": {"id": "analysis-1", "config": config.model_dump(), "result": result},
        "citations": [{"paper_id": "paper-1", "chunk_id": "chunk-1", "title": "测试材料", "page_number": 2, "quote": "This is synthetic test evidence."}],
        "report_title": "测试报告", "versions": {"code_version": "test"},
    }
```


### frame（L38–42）

导出测试的六行已知小表，三行A、三行B。

[实际代码：backend/tests/test_exports.py，L38–L42](E:/agent/backend/tests/test_exports.py:38)

```python
def frame():
    return pd.DataFrame({
        "id": ["a1", "a2", "a3", "b1", "b2", "b3"],
        "group": ["A"] * 3 + ["B"] * 3, "value": [1, 2, 3, 3, 5, 6],
    })
```


### test_plot_is_valid_png_with_real_data（L46–50）

对 points/box/hist 参数化，检查PNG签名与合理长度。它证明有实际图片输出，不等于逐像素验证全部图形语义。

[实际代码：backend/tests/test_exports.py，L46–L50](E:/agent/backend/tests/test_exports.py:46)

```python
def test_plot_is_valid_png_with_real_data(kind):
    context = fixture_context(frame())
    image = render_plot(context["analysis"]["result"], kind)
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(image) > 10000
```


### test_report_uses_saved_numbers_and_evidence（L53–63）

核对报告标题、原文页码、摘录、chunk ID、具体统计表行和局限说明，确保数字从已保存结果进入模板。

[实际代码：backend/tests/test_exports.py，L53–L63](E:/agent/backend/tests/test_exports.py:53)

```python
def test_report_uses_saved_numbers_and_evidence():
    context = fixture_context(frame())
    markdown = build_markdown(context)
    assert "# 测试报告" in markdown
    assert "测试材料，PDF 第 2 页" in markdown
    assert "This is synthetic test evidence." in markdown
    assert "chunk-1" in markdown
    assert "| A | 3 | 2 | 2 | 1 | 1 | 3 |" in markdown
    assert "统计显著性不能直接解释为实际价值" in markdown
    assert "95% 双侧" in markdown
    assert "original/" in markdown
```


### test_unsupported_design_report_has_no_fake_pvalue（L66–73）

使A组为常量，报告应说明unsupported和原因，不能凭空写出p值。

[实际代码：backend/tests/test_exports.py，L66–L73](E:/agent/backend/tests/test_exports.py:66)

```python
def test_unsupported_design_report_has_no_fake_pvalue():
    source = frame()
    source.loc[0:2, "value"] = 0
    context = fixture_context(source)
    markdown = build_markdown(context)
    assert "unsupported" in markdown
    assert "常量" in markdown
    assert "p 值：" not in markdown
```


### write_bundle（L76–80）

把 build_export 返回的相对路径→字节字典写进临时目录，为真正运行复现脚本准备文件。

[实际代码：backend/tests/test_exports.py，L76–L80](E:/agent/backend/tests/test_exports.py:76)

```python
def write_bundle(files, folder):
    for relative, payload in files.items():
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
```


### run_reproduction（L83–90）

从环境中移除PYTHONPATH/PYTHONHOME，以当前解释器运行包内reproduce.py并捕获输出。这属于脱离项目导入路径的验证，并不等于新建了全新依赖环境。

[实际代码：backend/tests/test_exports.py，L83–L90](E:/agent/backend/tests/test_exports.py:83)

```python
def run_reproduction(folder):
    isolated_environment = dict(os.environ)
    isolated_environment.pop("PYTHONPATH", None)
    isolated_environment.pop("PYTHONHOME", None)
    return subprocess.run(
        [sys.executable, str(folder / "reproduce.py")], cwd=str(folder),
        env=isolated_environment, capture_output=True, text=True, timeout=90,
    )
```


### test_self_contained_export_replays_original_cleaning_chain（L93–131）

原始表含重复及缺失，分两步清洗；导出后运行复现脚本，结果及清洗审计必须完全相同。再篡改包内原始数据，复现应失败。

[实际代码：backend/tests/test_exports.py，L93–L131](E:/agent/backend/tests/test_exports.py:93)

```python
def test_self_contained_export_replays_original_cleaning_chain(tmp_path):
    original_frame = pd.concat([frame(), frame().iloc[[0]], pd.DataFrame({"id": ["bad"], "group": ["A"], "value": [None]})], ignore_index=True)
    original = tmp_path / "source.csv"
    original_frame.to_csv(original, index=False)
    transform = {"steps": [
        {"drop_duplicate_rows": True},
        {"drop_missing_columns": ["value"]},
    ], "sheet": None}
    parsed, _ = read_dataset(original)
    cleaned, audit = apply_transforms(parsed, transform)
    assert len(cleaned) == 6
    assert len(audit) == 2
    context = fixture_context(cleaned, transform=transform)
    files = build_export(context, original)
    required = {
        "original/data.csv", "report.md", "summary.csv", "plot.png", "box.png",
        "histogram.png", "reproduce.py", "stats_engine.py", "analysis_config.json",
        "saved_result.json", "provenance.json", "requirements.txt",
    }
    assert required <= set(files)
    assert files["original/data.csv"] == original.read_bytes()
    manifest = json.loads(files["provenance.json"])
    assert manifest["effective_rows"] == 6
    assert manifest["transform"] == transform
    assert all("==" in line for line in files["requirements.txt"].decode().splitlines())
    extracted = tmp_path / "isolated"
    extracted.mkdir()
    write_bundle(files, extracted)
    completed = run_reproduction(extracted)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "REPRODUCTION PASSED" in completed.stdout
    assert json.loads((extracted / "reproduced_result.json").read_text(encoding="utf-8")) == context["analysis"]["result"]
    restored_audit = json.loads((extracted / "reproduced_cleaning_audit.json").read_text(encoding="utf-8"))
    assert restored_audit == audit
    # A changed input must never silently produce a successful reproduction.
    (extracted / "original" / "data.csv").write_text("changed", encoding="utf-8")
    changed = run_reproduction(extracted)
    assert changed.returncode != 0
    assert "Original data hash does not match" in changed.stderr
```


### test_xlsx_selected_sheet_reproduces（L134–146）

工作簿有无关表和目标中文表，导出后脚本必须选原目标sheet复现。

[实际代码：backend/tests/test_exports.py，L134–L146](E:/agent/backend/tests/test_exports.py:134)

```python
def test_xlsx_selected_sheet_reproduces(tmp_path):
    original = tmp_path / "source.xlsx"
    with pd.ExcelWriter(original, engine="openpyxl") as book:
        pd.DataFrame({"unused": [1]}).to_excel(book, sheet_name="ignore", index=False)
        frame().to_excel(book, sheet_name="实验", index=False)
    source, _ = read_dataset(original, sheet="实验")
    context = fixture_context(source, filename="测试.xlsx", sheet="实验", transform={"steps": [], "sheet": "实验"})
    files = build_export(context, original)
    extracted = tmp_path / "xlsx_reproduction"
    extracted.mkdir()
    write_bundle(files, extracted)
    completed = run_reproduction(extracted)
    assert completed.returncode == 0, completed.stderr + completed.stdout
```


### test_export_rejects_original_hash_mismatch（L149–154）

保存的原始哈希与实际文件不一致时，build_export 拒绝创建看似可信的包。

[实际代码：backend/tests/test_exports.py，L149–L154](E:/agent/backend/tests/test_exports.py:149)

```python
def test_export_rejects_original_hash_mismatch(tmp_path):
    original = tmp_path / "source.csv"
    frame().to_csv(original, index=False)
    context = fixture_context(frame(), original_sha256="tampered")
    with pytest.raises(ValueError, match="哈希"):
        build_export(context, original)
```


### test_csv_summary_uses_same_saved_numbers_and_escapes_formulas（L157–169）

组名以=开头时，CSV单元格前加单引号防止Excel当公式；统计数值仍与保存结果一致。

[实际代码：backend/tests/test_exports.py，L157–L169](E:/agent/backend/tests/test_exports.py:157)

```python
def test_csv_summary_uses_same_saved_numbers_and_escapes_formulas(tmp_path):
    source = frame()
    source["group"] = source["group"].replace("A", "=SUM(1,2)")
    config = AnalysisConfig(group_column="group", metric_column="value", group_a="=SUM(1,2)", group_b="B")
    result = analyze(source, config)
    original = tmp_path / "source.csv"
    source.to_csv(original, index=False)
    context = fixture_context(frame())
    context["analysis"] = {"id": "a", "config": config.model_dump(), "result": result}
    files = build_export(context, original)
    rows = list(csv.DictReader(io.StringIO(files["summary.csv"].decode("utf-8-sig"))))
    assert rows[0]["group"] == "'=SUM(1,2)"
    assert float(rows[0]["mean"]) == result["summary"][0]["mean"]
```


### test_cleaned_xlsx_export_keeps_original_extension_and_literal_ids（L171–194）

XLSX清洗到CSV后仍带原xlsx，并保留原sheet、001编号及数字精度，运行复现得到相同结果。

[实际代码：backend/tests/test_exports.py，L171–L194](E:/agent/backend/tests/test_exports.py:171)

```python
def test_cleaned_xlsx_export_keeps_original_extension_and_literal_ids(tmp_path):
    source = tmp_path / "untouched.xlsx"
    original_frame = pd.DataFrame({
        "id": ["001", "002", "003", "004", "005", "006", "bad"],
        "group": ["A"] * 3 + ["B"] * 3 + ["A"],
        "value": [1.0000000000000002, 2.25, 3.1, 3.5, 5.7, 6.8, None],
    })
    original_frame.to_excel(source, sheet_name="原始", index=False)
    original, _ = read_dataset(source, sheet="原始")
    transform = {"sheet": "原始", "steps": [{"drop_missing_columns": ["value"]}]}
    cleaned, _ = apply_transforms(original, transform)
    persisted = tmp_path / "cleaned.csv"
    cleaned.to_csv(persisted, index=False, encoding="utf-8-sig")
    reloaded, _ = read_dataset(persisted)
    pd.testing.assert_frame_equal(cleaned, reloaded)
    context = fixture_context(cleaned, filename="original-cleaned.csv", sheet=None, transform=transform)
    files = build_export(context, source)
    assert "original/data.xlsx" in files
    assert "original/data.csv" not in files
    destination = tmp_path / "original_xlsx_reproduction"
    destination.mkdir()
    write_bundle(files, destination)
    completed = run_reproduction(destination)
    assert completed.returncode == 0, completed.stderr + completed.stdout
```


### test_saved_engine_and_versions_are_exported_instead_of_current_runtime（L197–218）

模拟历史统计代码与旧依赖版本，导出必须使用分析时快照；代码指纹不同则拒绝。这里old-version只验证文本选择，没有尝试安装该虚构版本。

[实际代码：backend/tests/test_exports.py，L197–L218](E:/agent/backend/tests/test_exports.py:197)

```python
def test_saved_engine_and_versions_are_exported_instead_of_current_runtime(tmp_path):
    import hashlib
    source = tmp_path / "raw.csv"
    frame().to_csv(source, index=False)
    context = fixture_context(frame())
    engine_source = (Path(__file__).resolve().parents[1] / "app" / "stats_engine.py").read_text(encoding="utf-8")
    engine_source += "\n# historical snapshot\n"
    digest = hashlib.sha256(engine_source.encode("utf-8")).hexdigest()
    context["analysis_engine_source"] = engine_source
    context["analysis"]["provenance"] = {
        "analysis_code_sha256": digest, "app_version": "old-app",
        "versions": {"numpy": "old-version"},
    }
    files = build_export(context, source)
    assert files["stats_engine.py"].decode("utf-8") == engine_source
    assert "numpy==old-version\n" in files["requirements.txt"].decode("ascii")
    provenance = json.loads(files["provenance.json"])
    assert provenance["stats_engine_sha256"] == digest
    assert provenance["code_version"] == "old-app"
    context["analysis"]["provenance"]["analysis_code_sha256"] = "different"
    with pytest.raises(ValueError, match="代码"):
        build_export(context, source)
```


## frontend/tests/numeric.spec.ts：数值显示与分箱

全部7个测试依次验证：非零小数/p值不显示成0；普通数值、001字符串、空值的格式；浮点最后边界不丢最大值；内部边界只归一个箱且最后边界闭合；10万点不使用超长数组展开参数；极大/极小有限值仍正确入箱；常量/空值/非有限值/非法箱数有明确结果。

formatNumber/makeHistogram 是纯函数，所以这些 Playwright test 文件中的数值测试不需要 page。expect(...).toBe 是严格相等，toEqual 比结构，toThrow 检查异常。

[实际代码：frontend/tests/numeric.spec.ts，L1–L107](E:/agent/frontend/tests/numeric.spec.ts:1)

```typescript
import { test, expect } from "@playwright/test";
import { formatNumber, makeHistogram } from "../src/numeric";

test("nonzero small measurements and p values retain their magnitude", () => {
  for (const value of [
    0.00003,
    0.000001,
    -0.000001,
    1e-160,
    1e-300,
    Number.MIN_VALUE,
  ]) {
    const displayed = formatNumber(value);
    expect(displayed).not.toBe("0");
    expect(displayed).not.toBe("-0");
    expect(displayed).toContain("e");
    expect(Math.sign(Number(displayed))).toBe(Math.sign(value));
  }
  expect(formatNumber(0.00003)).toBe("3e-5");
  expect(formatNumber(0.0001)).toBe("0.0001");
  expect(formatNumber(1e160)).toBe("1e+160");
});

test("ordinary numbers and identifier strings keep readable formatting", () => {
  expect(formatNumber(1234.56789)).toBe("1,234.5679");
  expect(formatNumber(1.23)).toBe("1.23");
  expect(formatNumber(0)).toBe("0");
  expect(formatNumber(-0)).toBe("0");
  expect(formatNumber("001")).toBe("001");
  expect(formatNumber(null)).toBe("—");
  expect(formatNumber(undefined)).toBe("—");
  expect(formatNumber(Infinity)).toBe("—");
  expect(formatNumber(NaN)).toBe("—");
});

test("floating last-edge rounding cannot drop the maximum observation", () => {
  const values = [0.1, 0.3, 0.5, 0.7, 0.9, 1.1];
  const histogram = makeHistogram(values, 3);
  expect(histogram.total).toBe(values.length);
  expect(histogram.bins.reduce((sum, bin) => sum + bin.count, 0)).toBe(
    values.length,
  );
  expect(histogram.bins.at(-1)?.hi).toBe(1.1);
  expect(histogram.binIndices.at(-1)).toBe(2);
  expect(histogram.bins.at(-1)?.count).toBe(2);
  expect(histogram.binIndices.every((index) => index >= 0 && index < 3)).toBe(
    true,
  );
});

test("interior boundaries have one assignment and final boundary is inclusive", () => {
  const histogram = makeHistogram([0, 1, 2, 3, 4], 4);
  expect(histogram.binIndices).toEqual([0, 1, 2, 3, 3]);
  expect(histogram.bins.map((bin) => bin.count)).toEqual([1, 1, 1, 2]);
});

test("100000 observations do not use array spread arguments", () => {
  const values = Array.from({ length: 100000 }, (_, index) => index / 1000);
  const histogram = makeHistogram(values, 12);
  expect(histogram.min).toBe(0);
  expect(histogram.max).toBe(99.999);
  expect(histogram.total).toBe(100000);
  expect(histogram.bins.reduce((sum, bin) => sum + bin.count, 0)).toBe(100000);
  expect(histogram.binIndices.at(-1)).toBe(11);
});

test("extreme finite numbers and subnormal ranges remain assigned", () => {
  for (const values of [
    [-1e308, -5e307, 0, 5e307, 1e308],
    [0, Number.MIN_VALUE, 2 * Number.MIN_VALUE],
  ]) {
    const histogram = makeHistogram(values, 4);
    expect(histogram.bins.reduce((sum, bin) => sum + bin.count, 0)).toBe(
      values.length,
    );
    expect(
      histogram.bins.every(
        (bin) => Number.isFinite(bin.lo) && Number.isFinite(bin.hi),
      ),
    ).toBe(true);
    expect(
      histogram.binIndices.every(
        (index) => Number.isInteger(index) && index >= 0 && index < 4,
      ),
    ).toBe(true);
  }
});

test("constant, empty and invalid values are explicit", () => {
  const constant = makeHistogram([7, 7, 7], 3);
  expect(constant.bins).toHaveLength(1);
  expect(constant.bins[0].count).toBe(3);
  expect(constant.binIndices).toEqual([0, 0, 0]);
  expect(makeHistogram([], 3)).toEqual({
    min: null,
    max: null,
    total: 0,
    bins: [],
    binIndices: [],
  });
  const mixed = makeHistogram([0, NaN, Infinity, -Infinity, 1], 3);
  expect(mixed.total).toBe(2);
  expect(mixed.binIndices).toEqual([0, -1, -1, -1, 2]);
  for (const count of [0, -1, 1.5, NaN, 1001]) {
    expect(() => makeHistogram([1], count)).toThrow(RangeError);
  }
});
```


## frontend/tests/workbench.spec.ts：真实浏览器操作

createProject（L8–21）通过可访问标签填写对话框，保存并等待它消失；nav（L22–24）按导航按钮名切换。getByRole/getByLabel 依赖用户能读到的名称，比抓易变CSS位置更接近实际操作。

[实际代码：frontend/tests/workbench.spec.ts，L1–L24](E:/agent/frontend/tests/workbench.spec.ts:1)

```typescript
import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFile, mkdir, copyFile } from "node:fs/promises";
const root = fileURLToPath(new URL("../..", import.meta.url));
const sample = (name: string) => path.join(root, "samples", name);

async function createProject(page: Page, name: string) {
  await page.getByRole("button", { name: "新建项目", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "创建科研项目" });
  await dialog.getByLabel("项目名称", { exact: true }).fill(name);
  await dialog
    .getByLabel("研究问题", { exact: true })
    .fill("均值差与独立样本实验");
  await dialog
    .getByLabel("研究假设", { exact: true })
    .fill("B 组得分可能高于 A 组；用于测试流程。");
  await dialog.getByRole("button", { name: "保存项目", exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByLabel("当前科研项目")).toContainText(name);
}
async function nav(page: Page, name: string) {
  await page.getByRole("button", { name, exact: true }).click();
}
```


第一个测试（L25–168）从建项目、传双语PDF、检索第2页、打开canvas，到离线问答、无证据问题、文献对比、上传CSV、确认设计、核对统计值、切换图表、报告图片与ZIP下载。它记录外部网络请求和pageerror，最后应为空；还保存实际验收截图。

page.waitForResponse 在点击前建立等待，避免请求太快而漏监听。expect.poll 等 PDF canvas 或报告图片确实加载，不把对话框出现等同于内容渲染成功。

[实际代码：frontend/tests/workbench.spec.ts，L25–L168](E:/agent/frontend/tests/workbench.spec.ts:25)

```typescript
test("complete offline research workflow with original PDF and reproducible export", async ({
  page,
}, info) => {
  const external: string[] = [];
  const pageErrors: string[] = [];
  page.on("pageerror", (e) => pageErrors.push(e.message));
  page.on("request", (r) => {
    if (
      /^https?:/.test(r.url()) &&
      !["localhost", "127.0.0.1"].includes(new URL(r.url()).hostname)
    )
      external.push(r.url());
  });
  await page.goto("/");
  await createProject(page, "浏览器验收 · 科研闭环");
  await nav(page, "论文知识库");
  await page
    .getByLabel("上传 PDF", { exact: true })
    .setInputFiles([sample("demo_paper_zh.pdf"), sample("demo_paper_en.pdf")]);
  await expect(page.getByText("已就绪", { exact: true })).toHaveCount(2);
  await page.getByLabel("论文检索词").fill("均值差");
  await page.getByRole("button", { name: "检索原文", exact: true }).click();
  await expect(page.locator(".search-hit")).not.toHaveCount(0);
  await page.getByRole("button", { name: "查看证据 1", exact: true }).click();
  await expect(page.locator(".evidence")).toContainText("PDF 第 2 页");
  await page
    .getByRole("button", { name: "打开原文对应页", exact: true })
    .click();
  const reader = page.getByRole("dialog");
  await expect(reader.getByLabel("PDF 页码")).toHaveValue("2");
  await expect
    .poll(() =>
      reader
        .locator("canvas")
        .evaluate((el) => (el as HTMLCanvasElement).width),
    )
    .toBeGreaterThan(100);
  await expect(reader.getByText(/PDF 预览失败/)).toHaveCount(0);
  await reader.getByRole("button", { name: "关闭", exact: true }).click();

  await nav(page, "科研问答");
  await page
    .getByRole("textbox", { name: "研究问题", exact: true })
    .fill("均值差");
  await page.getByRole("button", { name: "发送问题", exact: true }).click();
  await expect(
    page.getByText("原文检索 · 非 AI 总结", { exact: true }),
  ).not.toHaveCount(0);
  await expect(
    page.locator(".chat-message.assistant .citation-button"),
  ).not.toHaveCount(0);
  await page
    .getByRole("textbox", { name: "研究问题", exact: true })
    .fill("Europa orbital eccentricity");
  await page.getByRole("button", { name: "发送问题", exact: true }).click();
  await expect(page.getByText(/当前资料不足以支持该结论/)).toBeVisible();

  await nav(page, "文献对比");
  await page.locator(".select-paper input").nth(0).check();
  await page.locator(".select-paper input").nth(1).check();
  await page.getByRole("button", { name: "生成对比表", exact: true }).click();
  await expect(page.locator(".comparison-column")).toHaveCount(2);
  await expect(page.locator(".comparison-grid")).toContainText(
    "未配置或未启用模型",
  );

  await nav(page, "实验分析");
  await page.getByRole("button", { name: "新建实验", exact: true }).click();
  const form = page.getByRole("dialog", { name: "创建实验记录" });
  await form.getByLabel("实验名称", { exact: true }).fill("浏览器实验");
  await form
    .getByLabel("研究假设", { exact: true })
    .fill("人工构造数据，用于验证 B-A=2。");
  await form.getByRole("button", { name: "创建实验", exact: true }).click();
  await expect(form).toBeHidden();
  await page
    .getByLabel("实验数据文件")
    .setInputFiles(sample("independent.csv"));
  await page.getByRole("button", { name: "导入为新版本", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "明确分析设计" }),
  ).toBeVisible();
  await page.getByLabel("分组列", { exact: true }).selectOption("group");
  await page.getByLabel("主要指标列", { exact: true }).selectOption("score");
  await page.getByLabel("指标单位", { exact: true }).fill("分");
  await page.getByLabel("基准组 A", { exact: true }).fill("A");
  await page.getByLabel("比较组 B", { exact: true }).fill("B");
  await page
    .getByLabel("分析设计", { exact: true })
    .selectOption("independent");
  await page.getByRole("textbox", { name: /^实验单位/ }).fill("独立实验样本");
  await page
    .getByLabel("实验单位 / 样本 ID 列", { exact: true })
    .selectOption("sample_id");
  await expect(
    page.getByRole("button", { name: "运行并保存分析", exact: true }),
  ).toBeDisabled();
  await page.getByRole("checkbox", { name: /我已核对数据版本/ }).check();
  const computed = page.waitForResponse(
    (r) => r.url().endsWith("/analyses") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "运行并保存分析", exact: true })
    .click();
  const saved = await (await computed).json();
  expect(saved.result.comparison.difference).toBe(2);
  expect(saved.result.comparison.pvalue).toBeCloseTo(0.08051623795726257, 12);
  expect(saved.result.summary.map((x: { n: number }) => x.n)).toEqual([5, 5]);
  await expect(page.locator(".result-stats .number").nth(0)).toHaveText("2");
  await page.getByRole("button", { name: "箱线图", exact: true }).click();
  await expect(
    page.getByRole("img", { name: "score (分) 箱线图" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "分布图", exact: true }).click();
  await expect(page.locator(".recharts-bar")).toHaveCount(2);
  await page.getByRole("button", { name: "生成研究报告", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "本次实验结果", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".rendered-report img")).toHaveCount(3);
  await expect
    .poll(() =>
      page
        .locator(".rendered-report img")
        .first()
        .evaluate((el) => (el as HTMLImageElement).naturalWidth),
    )
    .toBeGreaterThan(100);
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "完整复现包", exact: true }).click();
  const file = await download;
  const archive = info.outputPath("research-report.zip");
  await file.saveAs(archive);
  expect((await readFile(archive)).subarray(0, 2).toString()).toBe("PK");
  await nav(page, "实验分析");
  await page.getByRole("button", { name: /分析结果/ }).click();
  await mkdir(path.join(root, "docs"), { recursive: true });
  await page.screenshot({
    path: path.join(root, "docs", "workbench-preview.png"),
    fullPage: true,
  });
  expect(external).toEqual([]);
  expect(pageErrors).toEqual([]);
});
```


第二个测试（L170–189）新项目上传扫描/损坏PDF，核对 OCR/失败状态以及无检索命中。第三个测试（L191–209）改成390像素宽，展开导航、查看无模型设置，检查页面没有横向溢出。

[实际代码：frontend/tests/workbench.spec.ts，L170–L209](E:/agent/frontend/tests/workbench.spec.ts:170)

```typescript
test("project switching isolates documents and displays OCR/failure states", async ({
  page,
}) => {
  await page.goto("/");
  await createProject(page, "浏览器验收 · 隔离与失败");
  await nav(page, "论文知识库");
  await expect(
    page.getByText("建立你的第一份文献证据", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("上传 PDF", { exact: true })
    .setInputFiles([sample("scanned_demo.pdf"), sample("corrupt_demo.pdf")]);
  await expect(page.getByText("需要 OCR", { exact: true })).toBeVisible();
  await expect(page.getByText("处理失败", { exact: true })).toBeVisible();
  await page.getByLabel("论文检索词").fill("均值差");
  await page.getByRole("button", { name: "检索原文", exact: true }).click();
  await expect(
    page.getByText("没有找到匹配的原文", { exact: true }),
  ).toBeVisible();
});

test("mobile navigation stays within viewport and opens settings without a model", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "打开导航", exact: true }).click();
  await nav(page, "模型与设置");
  await expect(
    page.getByRole("heading", { name: "外部 AI 模型", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "同意并启用 AI", exact: true }),
  ).toBeDisabled();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
});
```

## frontend/playwright.config.ts：隔离测试服务

[实际代码：frontend/playwright.config.ts，L1–L48](E:/agent/frontend/playwright.config.ts:1)

```typescript
import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("..", import.meta.url));
const python = path.join(root, ".venv", "Scripts", "python.exe");
export default defineConfig({
  testDir: "./tests",
  timeout: 90000,
  expect: { timeout: 15000 },
  workers: 1,
  fullyParallel: false,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    actionTimeout: 15000,
    browserName: "chromium",
    channel: process.env.PW_BROWSER_CHANNEL || undefined,
    headless: true,
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        '"' +
        python +
        '" -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8001',
      url: "http://127.0.0.1:8001/api/health",
      timeout: 40000,
      reuseExistingServer: false,
      env: {
        DATA_DIR: path.join(root, "tmp", "e2e-" + Date.now()),
        AI_CHAT_MODEL: "",
        AI_API_KEY: "",
        EMBEDDING_MODEL: "",
        EMBEDDING_API_KEY: "",
      },
    },
    {
      command: "npm.cmd run dev -- --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      timeout: 40000,
      reuseExistingServer: false,
      env: { WORKBENCH_API_URL: "http://127.0.0.1:8001" },
    },
  ],
});
```


workers=1/fullyParallel=false 防止共享浏览器流程同时改数据。webServer 启临时8001后端与5173前端，DATA_DIR 放 tmp/e2e-时间戳，清空模型变量；WORKBENCH_API_URL让Vite代理指向测试后端。reuseExistingServer=false 避免测试误用日常8000服务。失败保留截图和trace。

## PowerShell 共同语法

param 声明参数；[switch] 是存在/不存在的开关；. 文件路径是 dot-sourcing，把公共函数加载到当前脚本；& 是调用程序；@参数数组 是展开参数，避免拼接成一条危险命令。Push-Location/Pop-Location 临时切换目录并在 finally 恢复。

### scripts/common.ps1

[实际代码：scripts/common.ps1，L1–L65](E:/agent/scripts/common.ps1:1)

```powershell
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:WorkbenchRoot = Split-Path -Parent $PSScriptRoot

function Assert-NativeExit {
    param([string]$Action)
    if ($LASTEXITCODE -ne 0) { throw "$Action failed (exit $LASTEXITCODE)." }
}

function Find-WorkbenchPython {
    param([string]$Python = '')
    if ($Python) {
        $resolved = Get-Command -Name $Python -CommandType Application -ErrorAction Stop | Select-Object -First 1
        return [pscustomobject]@{ Path = $resolved.Source; Prefix = @() }
    }
    $pyLauncher = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pyLauncher) {
        try {
            & $pyLauncher.Source -3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' *> $null
            if ($LASTEXITCODE -eq 0) { return [pscustomobject]@{ Path = $pyLauncher.Source; Prefix = @('-3') } }
        } catch { # An installed launcher may have no installed Python runtime.
        }
    }
    foreach ($name in @('python.exe', 'python3.exe')) {
        $candidate = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($candidate -and $candidate.Source -notlike '*WindowsApps*') {
            try {
                & $candidate.Source -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' *> $null
                if ($LASTEXITCODE -eq 0) { return [pscustomobject]@{ Path = $candidate.Source; Prefix = @() } }
            } catch { # Continue to the bundled runtime.
            }
        }
    }
    $bundled = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $bundled) {
        return [pscustomobject]@{ Path = $bundled; Prefix = @() }
    }
    throw 'Python 3.12+ not found. Install CPython, or pass -Python "C:\path with spaces\python.exe".'
}

function Find-WorkbenchNode {
    param([string]$Node = '')
    if ($Node) { return (Get-Command $Node -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source }
    $candidate = Get-Command node.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($candidate) { return $candidate.Source }
    $bundled = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    throw 'Node.js 20+ not found. Install Node.js, or pass -Node "C:\path\node.exe".'
}

function Find-WorkbenchNpm {
    param([string]$Npm = '')
    if ($Npm) { return (Get-Command $Npm -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source }
    $candidate = Get-Command npm.cmd -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($candidate) { return $candidate.Source }
    throw 'npm.cmd not found. Install Node.js with npm, or pass -Npm "C:\path\npm.cmd".'
}

function Get-WorkbenchVenvPython {
    $pythonExe = Join-Path $script:WorkbenchRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        throw 'Virtual environment missing. Run .\scripts\setup.ps1 first.'
    }
    return $pythonExe
}
```


| 函数/段落 | 完整作用 |
| --- | --- |
| 开头 L1–3 | 严格模式、遇错误停止、确定项目根；不改系统HOME等变量 |
| Assert-NativeExit L5–8 | 外部进程退出码不是0就抛错。PowerShell错误策略不会自动把每个程序非零退出变成异常，所以需要这一层 |
| Find-WorkbenchPython L10–39 | 优先显式路径，再py -3，再PATH中的python，再bundled runtime；前两种自动探测用小命令验证≥3.12，跳过WindowsApps占位程序 |
| Find-WorkbenchNode L41–49 | 显式路径、PATH、bundled runtime；setup另行检查主版本≥20 |
| Find-WorkbenchNpm L51–57 | 显式路径或PATH中的npm.cmd，找不到给清楚提示 |
| Get-WorkbenchVenvPython L59–65 | 要求项目.venv解释器存在，否则提示先setup |

### scripts/setup.ps1

[实际代码：scripts/setup.ps1，L1–L43](E:/agent/scripts/setup.ps1:1)

```powershell
[CmdletBinding()]
param(
    [string]$Python = '',
    [string]$Node = '',
    [string]$Npm = '',
    [switch]$SkipSamples
)
. (Join-Path $PSScriptRoot 'common.ps1')
Push-Location $script:WorkbenchRoot
try {
    $venv = Join-Path $script:WorkbenchRoot '.venv'
    if (-not (Test-Path -LiteralPath (Join-Path $venv 'Scripts/python.exe'))) {
        $runtime = Find-WorkbenchPython -Python $Python
        $runtimeArgs = @($runtime.Prefix) + @('-m', 'venv', $venv)
        & $runtime.Path @runtimeArgs
        Assert-NativeExit 'Create Python virtual environment'
    }
    $venvPython = Get-WorkbenchVenvPython
    & $venvPython -c 'import sys; assert sys.version_info >= (3, 12), "Python 3.12+ required"'
    Assert-NativeExit 'Check Python version'
    $nodeExe = Find-WorkbenchNode -Node $Node
    $npmExe = Find-WorkbenchNpm -Npm $Npm
    $env:PATH = (Split-Path -Parent $nodeExe) + [IO.Path]::PathSeparator + $env:PATH
    & $nodeExe -e 'if(Number(process.versions.node.split(".")[0])<20)process.exit(1)'
    Assert-NativeExit 'Check Node.js version'
    & $venvPython -m pip install -r requirements.lock.txt
    Assert-NativeExit 'Install locked backend dependencies'
    if (-not (Test-Path -LiteralPath '.env')) {
        Copy-Item -LiteralPath '.env.example' -Destination '.env'
    }
    Push-Location (Join-Path $script:WorkbenchRoot 'frontend')
    try {
        & $npmExe ci
        Assert-NativeExit 'Install locked frontend dependencies'
        & $npmExe run build
        Assert-NativeExit 'Build frontend'
    } finally { Pop-Location }
    if (-not $SkipSamples) {
        & $venvPython scripts/generate_samples.py
        Assert-NativeExit 'Generate DEMO fixtures'
    }
    Write-Host 'Setup complete. Run .\scripts\start.ps1 and open http://127.0.0.1:8000'
} finally { Pop-Location }
```


L1–8 接收工具路径及SkipSamples并加载公共函数；L11–20 缺失才建虚拟环境，再检查Python版本；L21–28 定位Node/npm、只调整当前进程PATH、检查Node并安装Python锁定依赖；L29–31 仅缺失时复制.env；L32–39 npm ci按锁文件安装并构建；L40–42 可选生成示例。finally 总会恢复目录。安装会访问软件源，脚本不是完全离线安装器。

### scripts/start.ps1

[实际代码：scripts/start.ps1，L1–L13](E:/agent/scripts/start.ps1:1)

```powershell
[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'common.ps1')
Push-Location $script:WorkbenchRoot
try {
    $pythonExe = Get-WorkbenchVenvPython
    if (-not (Test-Path -LiteralPath 'frontend/dist/index.html')) {
        throw 'Frontend build missing. Run .\scripts\setup.ps1 or npm run build in frontend.'
    }
    Write-Host "Research workbench: http://127.0.0.1:8000 ; Ctrl+C to stop."
    & $pythonExe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
    Assert-NativeExit 'Run application'
} finally { Pop-Location }
```


只检查已有虚拟环境和前端构建，启动 Uvicorn。app.main:app 表示从 app/main.py 取 app 对象；--app-dir backend 设置导入根；--host 127.0.0.1 限本机；--port 8000 指定端口。它不会每次重新安装依赖。

### scripts/dev.ps1

[实际代码：scripts/dev.ps1，L1–L33](E:/agent/scripts/dev.ps1:1)

```powershell
[CmdletBinding()]
param([string]$Node = '')
. (Join-Path $PSScriptRoot 'common.ps1')
Push-Location $script:WorkbenchRoot
$backendProcess = $null
$frontendProcess = $null
try {
    $pythonExe = Get-WorkbenchVenvPython
    $nodeExe = Find-WorkbenchNode -Node $Node
    $viteFile = Join-Path $script:WorkbenchRoot 'frontend/node_modules/vite/bin/vite.js'
    if (-not (Test-Path -LiteralPath $viteFile)) { throw 'Frontend dependencies missing. Run setup.ps1 first.' }
    $logDir = Join-Path $script:WorkbenchRoot 'data/dev-logs'
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $backendArgs = @('-m','uvicorn','app.main:app','--app-dir','backend','--host','127.0.0.1','--port','8000','--reload')
    $backendProcess = Start-Process -FilePath $pythonExe -ArgumentList $backendArgs -WorkingDirectory $script:WorkbenchRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'backend.stdout.log') -RedirectStandardError (Join-Path $logDir 'backend.stderr.log')
    $frontendArgs = @(('"' + $viteFile + '"'), '--host','127.0.0.1','--port','5173','--strictPort')
    $frontendProcess = Start-Process -FilePath $nodeExe -ArgumentList $frontendArgs -WorkingDirectory (Join-Path $script:WorkbenchRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'frontend.stdout.log') -RedirectStandardError (Join-Path $logDir 'frontend.stderr.log')
    Write-Host 'Development UI: http://127.0.0.1:5173 ; API: http://127.0.0.1:8000'
    Write-Host "Logs: $logDir ; Ctrl+C stops the processes started by this script."
    while (-not $backendProcess.HasExited -and -not $frontendProcess.HasExited) {
        Start-Sleep -Seconds 1
        $backendProcess.Refresh()
        $frontendProcess.Refresh()
    }
    throw "A development server stopped. Inspect $logDir."
} finally {
    foreach ($process in @($backendProcess, $frontendProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
        }
    }
    Pop-Location
}
```


用于修改源码时的开发环境。--reload 重载后端；Vite提供前端热更新。Start-Process -WindowStyle Hidden启动两个自有进程并保存进程对象，日志落data/dev-logs；循环监测退出；finally 只按记录的PID清理本脚本启动的进程树，不粗暴结束全部python/node。

### scripts/test.ps1

[实际代码：scripts/test.ps1，L1–L25](E:/agent/scripts/test.ps1:1)

```powershell
[CmdletBinding()]
param([switch]$E2E, [switch]$InstallBrowsers, [string]$Node = '', [string]$Npm = '')
. (Join-Path $PSScriptRoot 'common.ps1')
Push-Location $script:WorkbenchRoot
try {
    $pythonExe = Get-WorkbenchVenvPython
    & $pythonExe -m pytest backend/tests -q -p no:cacheprovider
    Assert-NativeExit 'Backend tests'
    $nodeExe = Find-WorkbenchNode -Node $Node
    $npmExe = Find-WorkbenchNpm -Npm $Npm
    $env:PATH = (Split-Path -Parent $nodeExe) + [IO.Path]::PathSeparator + $env:PATH
    Push-Location (Join-Path $script:WorkbenchRoot 'frontend')
    try {
        & $npmExe run build
        Assert-NativeExit 'Frontend production build'
        if ($E2E) {
            if ($InstallBrowsers) {
                & $nodeExe node_modules/@playwright/test/cli.js install chromium
                Assert-NativeExit 'Install Playwright Chromium'
            }
            & $npmExe run test:e2e
            Assert-NativeExit 'Browser tests'
        }
    } finally { Pop-Location }
} finally { Pop-Location }
```


先pytest再前端build，每步检查退出码。只有-E2E才执行浏览器测试；-InstallBrowsers只在该分支下载Chromium。构建通过检查类型和打包，不等于页面交互全部已验收。

## scripts/generate_samples.py：样例来自哪里

模块开头定义 ROOT、OUT、HEADER，以及独立组、配对组、缺失/非数值/极值、重复pair和不完整pair的数据。PAIRED按同一P编号建立两组记录；这些都是人工构造材料。

[实际代码：scripts/generate_samples.py，L1–L53](E:/agent/scripts/generate_samples.py:1)

```python
"""Create deterministic DEMO / test fixtures. Run from any working directory.

Requires reportlab, openpyxl, Pillow, scipy and pypdf (in requirements.lock.txt).
The contents are synthetic test material, not published research.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import math
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.table import Table, TableStyleInfo
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table as PdfTable, TableStyle
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader
from scipy import stats

rl_config.invariant = 1
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "samples"
OUT.mkdir(exist_ok=True)

HEADER = ["sample_id", "group", "score", "pair_id"]
INDEPENDENT = [[f"A{i}", "A", i, ""] for i in range(1, 6)] + [
    [f"B{i}", "B", i + 2, ""] for i in range(1, 6)]
PAIRED = []
for i, (a, b) in enumerate(zip([10, 12, 14, 16, 18], [11, 14, 15, 19, 20]), 1):
    PAIRED.extend([[f"A{i}", "A", a, f"P{i}"], [f"B{i}", "B", b, f"P{i}"]])
MISSING = [
    ["A1", "A", 1, ""], ["A2", "A", "", ""], ["A3", "A", "bad", ""],
    ["A4", "A", 4, ""], ["B1", "B", 3, ""], ["B2", "B", 5, ""],
    ["B3", "B", "", ""], ["B4", "B", 100, ""],
]
DUPLICATE_PAIRS = PAIRED + [["A_duplicate", "A", 10, "P1"]]
UNMATCHED_PAIRS = PAIRED[:-1]
```


write_csv（L55–59）：utf-8-sig方便Excel识别中文；newline=''交给csv库管理换行；先写表头再写数据。

[实际代码：scripts/generate_samples.py，L55–L59](E:/agent/scripts/generate_samples.py:55)

```python
def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADER)
        writer.writerows(rows)
```


make_paper（L61–121）：注册中文字体，优先用户指定或系统可嵌入字体；设置标题/正文样式；逐页拼接段落和表格；嵌套footer（L110–116）画页脚和实际页码；SimpleDocTemplate.build生成可提取文字的PDF。invariant固定容易变化的生成元信息，便于重复生成一致材料。

[实际代码：scripts/generate_samples.py，L61–L121](E:/agent/scripts/generate_samples.py:61)

```python
def make_paper(name, lang, sections):
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    font = "STSong-Light" if lang == "zh" else "Helvetica"
    if lang == "zh":
        candidates = [os.getenv("DEMO_CJK_FONT", ""), "C:/Windows/Fonts/simsun.ttc",
                      "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"]
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                try:
                    pdfmetrics.registerFont(TTFont("DemoCJK", candidate, subfontIndex=0))
                    font = "DemoCJK"
                    break
                except Exception:
                    continue
    styles = {
        "label": ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=9,
                                textColor=colors.HexColor("#A15C16"), spaceAfter=16),
        "title": ParagraphStyle("title", fontName=font, fontSize=21, leading=31,
                                textColor=colors.HexColor("#102A43"), spaceAfter=16,
                                wordWrap="CJK"),
        "heading": ParagraphStyle("heading", fontName=font, fontSize=13, leading=21,
                                  spaceBefore=20, spaceAfter=10, textColor=colors.HexColor("#126C67")),
        "body": ParagraphStyle("body", fontName=font, fontSize=11, leading=20,
                               spaceAfter=14, wordWrap="CJK", alignment=TA_LEFT),
    }
    story = []
    for idx, section in enumerate(sections):
        if idx:
            story.append(PageBreak())
        story.append(Paragraph("DEMO / SYNTHETIC TEST MATERIAL", styles["label"]))
        story.append(Paragraph(section["title"], styles["title"]))
        for heading, body in section["paragraphs"]:
            story.append(Paragraph(heading, styles["heading"]))
            story.append(Paragraph(body, styles["body"]))
        story.append(Spacer(1, 18))
        if "table" in section:
            rows = [[Paragraph(str(c), styles["body"]) for c in row] for row in section["table"]]
            table = PdfTable(rows, colWidths=[145, 145, 145])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF3F3")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#BCCCDC")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E2EC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(table)
    def footer(c, doc):
        c.setStrokeColor(colors.HexColor("#D9E2EC"))
        c.line(64, 54, A4[0] - 64, 54)
        c.setFillColor(colors.HexColor("#52606D"))
        c.setFont("Helvetica", 9)
        c.drawString(64, 37, "DEMO - not published research")
        c.drawRightString(A4[0] - 64, 37, f"PDF page {doc.page}")
    doc = SimpleDocTemplate(str(OUT / name), pagesize=A4, leftMargin=64,
                            rightMargin=64, topMargin=58, bottomMargin=78,
                            title=("测试材料：检索与证据" if lang == "zh" else "DEMO retrieval study"),
                            author="DEMO fixture generator")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
```


make_scanned（L123–141）：Pillow把字画到PNG，再把图放进PDF；没有PDF文字层，专门测试needs_ocr。make_workbook（L143–187）：建立四张表，冻结表头、格式化并加入表格；固定文档时间，重打包ZIP条目顺序/时间，降低每次生成时哈希无意义变化。

[实际代码：scripts/generate_samples.py，L123–L187](E:/agent/scripts/generate_samples.py:123)

```python
def make_scanned():
    image = Image.new("RGB", (1240, 1754), "#FFFFFF")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    font = ImageFont.truetype(str(font_path), 32) if font_path.exists() else ImageFont.load_default()
    small = ImageFont.truetype(str(font_path), 23) if font_path.exists() else font
    draw.rectangle((95, 110, 1145, 1580), outline="#CDD7E0", width=3)
    for y, line in enumerate(["DEMO / SCANNED TEST MATERIAL", "Raster image only; no selectable text.",
                              "Expected application status: needs OCR.",
                              "This file is synthetic, not a real paper."]):
        draw.text((145, 190 + y * 95), line, fill="#18344B", font=font if y == 0 else small)
    draw.text((145, 1480), "PDF page 1 - DEMO", fill="#52606D", font=small)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    c = canvas.Canvas(str(OUT / "scanned_demo.pdf"), pagesize=A4, invariant=1)
    c.setTitle("DEMO scanned-only test fixture")
    c.drawImage(ImageReader(buf), 0, 0, width=A4[0], height=A4[1])
    c.save()

def make_workbook():
    workbook = Workbook()
    workbook.remove(workbook.active)
    for index, (name, rows) in enumerate([
        ("Independent", INDEPENDENT), ("Paired", PAIRED),
        ("MissingValues", MISSING), ("DuplicatePairs", DUPLICATE_PAIRS),
    ], 1):
        sheet = workbook.create_sheet(name)
        sheet.append(HEADER)
        for row in rows:
            sheet.append(row)
        sheet.freeze_panes = "A2"
        sheet.sheet_view.showGridLines = False
        for cell in sheet[1]:
            cell.fill = PatternFill("solid", fgColor="18344B")
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(vertical="center")
        sheet.row_dimensions[1].height = 28
        for column in "ABCD":
            sheet.column_dimensions[column].width = 20
        sheet.auto_filter.ref = sheet.dimensions
        table = Table(displayName=f"DemoData{index}", ref=sheet.dimensions)
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        sheet.add_table(table)
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.print_options.horizontalCentered = True
        sheet.print_title_rows = "1:1"
    workbook.properties.title = "DEMO synthetic experiment fixtures"
    workbook.properties.description = "Synthetic test data, not scientific results. See expected_results.json."
    workbook.properties.created = datetime(2026, 1, 1)
    workbook.properties.modified = datetime(2026, 1, 1)
    output = OUT / "experiments.xlsx"
    workbook.save(output)
    source = io.BytesIO(output.read_bytes())
    canonical = io.BytesIO()
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(canonical, "w", zipfile.ZIP_DEFLATED) as target:
        for name in sorted(original.namelist()):
            content = original.read(name)
            if name == "docProps/core.xml":
                content = re.sub(rb"(<dcterms:modified[^>]*>).*?(</dcterms:modified>)",
                                 rb"\g<1>2026-01-01T00:00:00Z\g<2>", content)
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, content)
    output.write_bytes(canonical.getvalue())
```


expected_results（L189–238）：用已知数组和SciPy生成参考值、问题/页码、边界预期及文件哈希。它是测试材料说明；test_stats还使用手工推导的参考值，以免只把同一次调用结果与自身比较。

[实际代码：scripts/generate_samples.py，L189–L238](E:/agent/scripts/generate_samples.py:189)

```python
def expected_results():
    a, b = [1, 2, 3, 4, 5], [3, 4, 5, 6, 7]
    pa, pb = [10, 12, 14, 16, 18], [11, 14, 15, 19, 20]
    independent = stats.ttest_ind(b, a, equal_var=False)
    paired = stats.ttest_rel(pb, pa)
    ici, pci = independent.confidence_interval(), paired.confidence_interval()
    data = {
        "notice": "DEMO / 测试材料；所有论文与数据均为合成样例，不代表真实科研发现。",
        "difference_definition": "B - A; relative change = (B-A) / abs(A) * 100",
        "common_config": {"group_column": "group", "metric_column": "score",
                          "group_a": "A", "group_b": "B", "experimental_unit": "subject",
                          "sample_id_column": "sample_id", "missing_policy": "error",
                          "alternative": "two-sided", "unit": "points",
                          "direction": "higher", "confirmed": True},
        "independent": {
            "file": "independent.csv", "design": "independent", "n_a": 5, "n_b": 5,
            "mean_a": 3, "mean_b": 5, "std_a": math.sqrt(2.5), "std_b": math.sqrt(2.5),
            "difference": 2, "relative_change_percent": 200 / 3,
            "statistic": float(independent.statistic), "df": float(independent.df),
            "pvalue": float(independent.pvalue), "ci_low": float(ici.low), "ci_high": float(ici.high),
            "reference": "Manual means / sample variance and scipy.stats.ttest_ind(B,A,equal_var=False).",
        },
        "paired": {
            "file": "paired.csv", "design": "paired", "pair_column": "pair_id", "pairs": 5,
            "mean_a": 14, "mean_b": 15.8, "difference": 1.8,
            "statistic": float(paired.statistic), "df": float(paired.df),
            "pvalue": float(paired.pvalue), "ci_low": float(pci.low), "ci_high": float(pci.high),
            "reference": "Paired differences [1,2,1,3,2]; scipy.stats.ttest_rel(B,A).",
        },
        "edge_cases": {
            "missing_values.csv": "8 rows: score has 2 missing and 1 nonnumeric value; error policy must block inference; explicit drop leaves A n=2, B n=3. Outliers remain unless user explicitly cleans.",
            "duplicate_pairs.csv": "Repeated pair P1 in group A: paired inference must be refused.",
            "unmatched_pairs.csv": "P5 missing in group B: must report unmatched pair; do not silently pair by row.",
            "scanned_demo.pdf": "One image-only page, extraction has no text: paper needs OCR.",
            "corrupt_demo.pdf": "Intentionally invalid PDF: parser must record failure.",
        },
        "evidence_questions": [
            {"question": "示例实验每组有多少个独立样本？", "file": "demo_paper_zh.pdf", "page": 1, "contains": "每组包含 5 个独立样本"},
            {"question": "示例实验的均值差是多少？", "file": "demo_paper_zh.pdf", "page": 2, "contains": "均值差 B-A 为 2 分"},
            {"question": "What metric and sample size were used?", "file": "demo_paper_en.pdf", "page": 1, "contains": "Recall@5"},
            {"question": "What are the limitations?", "file": "demo_paper_en.pdf", "page": 2, "contains": "synthetic"},
        ],
        "no_evidence_questions": [
            "火星大气压的测量值是多少？", "Europa orbital eccentricity value?"
        ],
        "workbook_sheets": ["Independent", "Paired", "MissingValues", "DuplicatePairs"],
    }
    files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != "expected_results.json" and not p.name.endswith(".md"))
    data["sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (OUT / "expected_results.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
```


main（L240–282）：生成两篇明确标记的中英文DEMO论文、纯图扫描PDF、故意损坏PDF、五份CSV及XLSX；最后用pypdf验证页数、关键句与扫描件空文字。__main__判断使直接执行才运行main，import时不生成整套材料。

[实际代码：scripts/generate_samples.py，L240–L285](E:/agent/scripts/generate_samples.py:240)

```python
def main():
    make_paper("demo_paper_zh.pdf", "zh", [
        {"title": "测试材料：两组实验与证据检索", "paragraphs": [
            ("材料性质", "本文件为 DEMO 合成测试材料，不是已发表论文。作者为演示研究组；无 DOI。仅用于检验 PDF 解析、中文检索、页码引用和实验分析流程。"),
            ("研究问题与方法", "本测试比较条件 A 与条件 B 的演示评分。每组包含 5 个独立样本，实验单位为受试对象，指标为 score，单位为分。数据文件为 independent.csv。"),
            ("数据与实验设置", "A 组观测值为 1、2、3、4、5；B 组观测值为 3、4、5、6、7。每个样本只有一次观测。分析前须明确分组、主要指标和缺失值处理；使用双侧 Welch t 检验。"),
        ], "table": [["项目", "条件 A", "条件 B"], ["独立样本量", "5", "5"], ["观测单位", "受试对象", "受试对象"]]},
        {"title": "测试材料：结果与局限", "paragraphs": [
            ("主要结果", "A 组均值为 3 分，B 组均值为 5 分，均值差 B-A 为 2 分。两组样本标准差均为 1.5811388301 分。双侧 Welch t 检验的自由度为 8，p 值约为 0.080516。"),
            ("结果解释", "差值的 95% 置信区间约为 -0.306004 至 4.306004 分。在本示例中，区间跨过零；不能据此断言条件 B 优于条件 A。统计显著性也不能直接证明实际价值或因果关系。"),
            ("局限与后续验证", "数据是人为构造的极小样例，不代表任何真实人群。未进行功效分析、多中心验证或长期随访。后续应预先确定研究假设与实验设计，再收集真实独立样本。未报告超导材料或临床生存获益信息。"),
        ]},
    ])
    make_paper("demo_paper_en.pdf", "en", [
        {"title": "DEMO paper: evidence retrieval pilot", "paragraphs": [
            ("Synthetic test material", "This document is a fictional two-page fixture, not a published research paper. It has no DOI and no real-world scientific claim."),
            ("Research question and methods", "The pilot evaluates retrieval of relevant documents from a synthetic collection. The evaluation metric is Recall@5. The pilot uses 12 synthetic queries and a manually specified relevance list."),
            ("Dataset and protocol", "The collection contains 40 generated abstracts. System R returns five documents per query. The simulated protocol records retrieval evidence and PDF page numbers. These metrics differ from the score variable in the Chinese DEMO experiment."),
        ], "table": [["Item", "Protocol", "Unit"], ["Queries", "12", "synthetic queries"], ["Metric", "Recall@5", "fraction"]]},
        {"title": "DEMO paper: limitations and evidence", "paragraphs": [
            ("Reported result", "The synthetic pilot reports mean Recall@5 of 0.75. The fixture does not include query-level raw values or confidence intervals. This value must not be ranked against a score measured in points under a different protocol."),
            ("Limitations", "All abstracts, queries and relevance labels are synthetic. No external validation, medical outcome, survival benefit or superconducting transition temperature was measured."),
            ("Suggested validation", "A future real study should publish query-level labels, specify the retrieval protocol in advance, and separate training, tuning and evaluation collections. This is a suggested experiment, not an established conclusion."),
        ]},
    ])
    make_scanned()
    (OUT / "corrupt_demo.pdf").write_bytes(b"%PDF-1.7\nDEMO intentionally corrupted test fixture. No object table or trailer.\n")
    for name, rows in [("independent.csv", INDEPENDENT), ("paired.csv", PAIRED),
                       ("missing_values.csv", MISSING), ("duplicate_pairs.csv", DUPLICATE_PAIRS),
                       ("unmatched_pairs.csv", UNMATCHED_PAIRS)]:
        write_csv(name, rows)
    make_workbook()
    expected_results()
    for name in ["demo_paper_zh.pdf", "demo_paper_en.pdf"]:
        reader = PdfReader(OUT / name)
        assert len(reader.pages) == 2, name
        assert all((p.extract_text() or "").strip() for p in reader.pages), name
    zh = PdfReader(OUT / "demo_paper_zh.pdf")
    assert "每组包含 5 个独立样本" in zh.pages[0].extract_text()
    assert "均值差 B-A 为 2 分" in zh.pages[1].extract_text()
    assert not (PdfReader(OUT / "scanned_demo.pdf").pages[0].extract_text() or "").strip()
    print(f"Generated and text-verified DEMO fixtures in {OUT}")
    print("Independent: B-A=2, p=" + str(stats.ttest_ind([3,4,5,6,7], [1,2,3,4,5], equal_var=False).pvalue))

if __name__ == "__main__":
    main()
```


## scripts/verify_reproduction.py：导出干净验证材料

[实际代码：scripts/verify_reproduction.py，L1–L69](E:/agent/scripts/verify_reproduction.py:1)

```python
"""Export an isolated synthetic API fixture for clean-environment reproduction.

Does not install dependencies or run an external model.
Usage: .venv/Scripts/python.exe scripts/verify_reproduction.py
Then create a clean venv, install the EXPORTED requirements.txt and run reproduce.py.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-data", default="tmp/repro-app")
    parser.add_argument("--output", default="tmp/repro-clean")
    args = parser.parse_args()
    app_data, output = (ROOT / args.app_data).resolve(), (ROOT / args.output).resolve()
    for folder in [app_data, output]:
        if not folder.is_relative_to((ROOT / "tmp").resolve()):
            raise ValueError("Verification directories must be inside this project's tmp directory")
        if folder.exists() and any(folder.iterdir()):
            raise ValueError(f"Use a fresh empty verification directory: {folder}")
    output.mkdir(parents=True, exist_ok=True)
    settings = Settings(ai_chat_model="", ai_api_key="", embedding_model="", embedding_api_key="")
    with TestClient(create_app(data_dir=app_data, settings=settings)) as client:
        demo = client.post("/api/demo")
        demo.raise_for_status()
        project_id = demo.json()["project_id"]
        experiments = client.get(f"/api/projects/{project_id}/experiments")
        experiments.raise_for_status()
        experiment_id = experiments.json()[0]["id"]
        detail = client.get(f"/api/projects/{project_id}/experiments/{experiment_id}")
        detail.raise_for_status()
        analysis = detail.json()["analyses"][0]
        assert analysis["result"]["comparison"]["difference"] == 2
        report = client.post(f"/api/projects/{project_id}/reports",
                             json={"analysis_id": analysis["id"], "title": "DEMO clean reproduction acceptance"})
        report.raise_for_status()
        download = client.get(f"/api/projects/{project_id}/reports/{report.json()['id']}/download?format=zip")
        download.raise_for_status()
        blob = download.content
    archive_path = output.parent / (output.name + ".zip")
    archive_path.write_bytes(blob)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        names = archive.namelist()
        for name in names:
            if not (output / name).resolve().is_relative_to(output):
                raise ValueError("Unexpected unsafe archive entry")
        archive.extractall(output)
    result = {
        "archive": str(archive_path), "archive_sha256": hashlib.sha256(blob).hexdigest(),
        "output": str(output), "app_data": str(app_data), "files": names,
        "analysis_id": analysis["id"], "mean_difference": analysis["result"]["comparison"]["difference"],
        "note": "Export succeeded; dependency installation and reproduce.py execution are separate checks.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
```


main（L22–66）接收app-data/output；resolve并要求都在项目tmp之内，拒绝非空目录；创建关闭模型的临时应用，显式导入DEMO，取已保存分析并核对差值2，再生成报告下载ZIP。解压前逐路径检查仍在output内。最后打印归档哈希与位置。

它只准备材料，没有替你新建虚拟环境或安装导出依赖。真正的干净依赖环境验证，是用另一个新venv安装ZIP内requirements再运行reproduce.py；不能把导出成功直接称作干净环境复现成功。

## docs/guide-example-statistics.py：上一份入门指南中的教学图

[实际代码：docs/guide-example-statistics.py，L1–L131](E:/agent/docs/guide-example-statistics.py:1)

```python
"""Plot the actual teaching dataset using the project's statistics engine.

Run with the project .venv Python. Only the adjacent PNG is written.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.stats_engine import analyze, read_dataset


def main() -> None:
    frame, _ = read_dataset(ROOT / "samples" / "independent.csv")
    result = analyze(frame, {
        "group_column": "group", "metric_column": "score",
        "group_a": "A", "group_b": "B", "design": "independent",
        "experimental_unit": "每个 sample_id 代表一个独立教学样本",
        "sample_id_column": "sample_id", "missing_policy": "error",
        "alternative": "two-sided", "confirmed": True,
    })
    comp = result["comparison"]
    assert comp["status"] == "completed", comp
    summaries = {s["group"]: s for s in result["summary"]}
    assert [summaries[g]["n"] for g in ["A", "B"]] == [5, 5]
    assert np.allclose([summaries[g]["mean"] for g in ["A", "B"]], [3, 5])

    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if not font_path.exists():
        raise FileNotFoundError("本图要求 Windows 微软雅黑：" + str(font_path))
    font = FontProperties(fname=str(font_path))
    bold = FontProperties(fname=str(font_path), weight="bold")
    plt.rcParams.update({"font.family": font.get_name(), "axes.unicode_minus": False})

    ink, muted, grid = "#19332f", "#60746e", "#e4ebe5"
    teal, blue, orange = "#177b70", "#4277b3", "#a66522"
    fig = plt.figure(figsize=(14, 6), dpi=100, facecolor="#f6f8f4")
    fig.text(.045, .925, "看懂实验结果：差值之外，还要看不确定性",
             color=ink, fontproperties=bold, fontsize=22)
    fig.text(.045, .87,
             "独立样本 · Welch t 检验（双侧）  |  数据与计算均来自本项目的示例文件",
             color=muted, fontproperties=font, fontsize=12)

    left = fig.add_axes([.065, .285, .36, .45], facecolor="white")
    right = fig.add_axes([.53, .285, .425, .45], facecolor="white")
    for ax in [left, right]:
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(axis="both", colors=muted, labelsize=11, length=0, pad=9)
        ax.set_axisbelow(True)

    left.set_title("① 先看每一个原始样本", loc="left", pad=21,
                   color=ink, fontproperties=FontProperties(fname=str(font_path), size=16, weight="bold"))
    offsets = np.array([-.075, .04, -.015, .075, -.04])
    for pos, group, color in [(0, "A", teal), (1, "B", blue)]:
        values = np.array([p["value"] for p in result["points"] if p["group"] == group])
        left.scatter(pos + offsets, values, s=95, color=color,
                     edgecolors="white", linewidths=1.6, zorder=4)
        mean = summaries[group]["mean"]
        left.plot([pos-.23, pos+.23], [mean, mean], color=color,
                  linewidth=3, solid_capstyle="round", zorder=3)
        left.text(pos+.26, mean, f"均值 {mean:g}", va="center", color=color,
                  fontsize=12, fontproperties=bold)
    left.set_xlim(-.55, 1.77)
    left.set_ylim(0, 8)
    left.set_xticks([0, 1], ["A 组\nn = 5", "B 组\nn = 5"])
    left.set_yticks([0, 2, 4, 6, 8])
    left.grid(axis="y", color=grid, linewidth=.8)
    left.set_ylabel("示例指标（无单位）", fontproperties=font,
                    color=muted, labelpad=12, fontsize=11)
    left.text(.02, .965, "一个点 = 一个独立样本；短横线 = 该组平均值",
              transform=left.transAxes, va="top", fontsize=10,
              color=muted, fontproperties=font)

    right.set_title("② 再看两组均值差：B − A", loc="left", pad=21,
                    color=ink, fontproperties=FontProperties(fname=str(font_path), size=16, weight="bold"))
    lo, hi, delta = comp["ci_low"], comp["ci_high"], comp["difference"]
    right.set_xlim(-1.2, 5.1)
    right.set_ylim(0, 1)
    right.axvline(0, color=orange, linewidth=1.7,
                  linestyle=(0, (4, 4)), zorder=1)
    right.text(0, .94, "零差值线", ha="center", va="top",
               color=orange, fontproperties=font, fontsize=11)
    y = .55
    right.plot([lo, hi], [y, y], color=teal, linewidth=5,
               solid_capstyle="round", zorder=3)
    right.vlines([lo, hi], y-.055, y+.055, color=teal, linewidth=2, zorder=3)
    right.scatter([delta], [y], color=teal, edgecolors="white",
                  linewidths=2, s=180, zorder=4)
    right.text(delta, y+.14, f"差值估计 = {delta:g}", ha="center",
               color=ink, fontproperties=bold, fontsize=13)
    right.text(lo, y-.105, f"{lo:.3f}", ha="center", va="top", color=muted, fontsize=11)
    right.text(hi, y-.105, f"{hi:.3f}", ha="center", va="top", color=muted, fontsize=11)
    right.text(.5, .19, "线段 = 均值差的 95% 置信区间",
               transform=right.transAxes, ha="center", color=muted,
               fontproperties=font, fontsize=11)
    right.text(.5, .075, f"区间包含 0   ·   p = {comp['pvalue']:.3f}",
               transform=right.transAxes, ha="center", color=orange,
               fontproperties=bold, fontsize=13)
    right.set_xticks([-1, 0, 1, 2, 3, 4, 5])
    right.set_yticks([])
    right.grid(axis="x", color=grid, linewidth=.8)
    right.set_xlabel("均值差（B − A）", fontproperties=font,
                     fontsize=11, color=muted, labelpad=11)

    fig.text(.5, .112,
             "这次观察到 B 组均值高 2，但当前样本还不足以确认总体均值不同。",
             ha="center", color=ink, fontproperties=bold, fontsize=14,
             bbox={"facecolor": "#e9f0e9", "edgecolor": "none",
                   "boxstyle": "round,pad=.7"})
    fig.text(.5, .035,
             "合成教学数据，不代表真实研究。未达到常用的 0.05 显著性阈值，不等于“没有差异”。",
             ha="center", color=muted, fontproperties=font, fontsize=11)
    target = Path(__file__).with_suffix(".png")
    fig.savefig(target, dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(json.dumps({"output": str(target), "summary": result["summary"],
                      "comparison": comp}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```


main读取真实示例CSV→调用项目analyze→先断言结果有效、均值与n符合已知值→加载微软雅黑→绘左图原始点与均值、右图B−A和95%CI→明确标合成数据→保存相邻PNG。它不生成随机点；横向偏移固定只是防遮挡，不改变纵轴观测值。当前脚本未填unit，因此图标无单位；在网页练习填分后界面显示分。

## 本源码阅读器的生成代码

build_code_book.py 是这次讲解新增的文档工具，不参与日常科研计算。collect_paths只读白名单；definitions为Python用AST提取函数/类及行号，为TS/PS用轻量正则提供导航；category分类；main建立逐文件全文、合订本、manifest和离线HTML，并核对文件哈希。正则导航是阅读辅助，不是完整TypeScript语法分析器。

HTML的selectFile用textContent显示源代码，避免把源文件中的HTML片段执行；嵌入JSON的<、>、&被转义，避免源中的结束script文本截断容器。showFiles只做本地字符串过滤；jumpTo定位行；restore从URL片段恢复文件；copy按钮只复制，不执行代码。源码阅读器不发送网络请求，也不会读取真实.env或用户data。

构建命令：.\.venv\Scripts\python.exe docs\code-guide\build_code_book.py。它只刷新文档附录，不刷新人工解释的语义与行号；应用变更后仍需复核讲解。

## 配置、样例与第三方依赖的边界

根目录.env.example/.gitignore/pyproject.toml/requirements.txt作用在01章；前端构建配置在03章；完整锁文件和CSV/expected_results.json全文在源码附录。CSV是已知输入，JSON保存预期；PDF/XLSX二进制内容由本章生成器说明，不把二进制字节当程序源码逐行朗读。

阅读完毕后可以回到[总目录](README.md)，从真实页面动作反向查函数调用。