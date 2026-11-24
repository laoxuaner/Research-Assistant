# 启动、配置、数据库与输入校验

[总目录](README.md) · [前一章](00-start-here.md) · [完整源码阅读器](code-reader.html)

本章把后台最基础的六个文件和空包入口全部拆开讲。行号按当前源码；代码段为实际原文。

## 1. backend/app/__init__.py：为什么是空文件

它把 app 目录标记为 Python 包。当前没有初始化逻辑。导入 app.main 时，业务组装在 main.py，不需要把代码塞进这个空文件。

## 2. config.py：集中读取后台设置

[实际代码：backend/app/config.py，L1–L31](E:/agent/backend/app/config.py:1)

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", env_file_encoding="utf-8")
    data_dir: str = str(ROOT / "data")
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_chat_model: str = ""
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_min_similarity: float = 0.35
    embedding_model: str = ""
    ai_json_mode: bool = True
    ai_token_parameter: str = 'max_completion_tokens'
    ai_timeout_seconds: float = 45
    ai_max_output_tokens: int = 1800
    ai_context_chars: int = 18000
    ai_retries: int = 1
    max_upload_mb: int = 30
    max_pdf_pages: int = 300
    parse_timeout_seconds: int = 60
    max_dataset_rows: int = 100000
    max_dataset_columns: int = 200
    max_xlsx_uncompressed_mb: int = 150

    def directory(self) -> Path:
        path = Path(self.data_dir)
        return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
```


第 1–4 行：Path 用于处理路径；ROOT 指向项目根目录。__file__ 是当前文件位置，resolve 取得规范绝对路径，parents[2] 从 backend/app/config.py 向上找到项目根。

第 6–7 行：Settings 继承 BaseSettings，字段默认值可以被环境变量和根目录 .env 覆盖。extra='ignore' 忽略配置文件中未声明的项；这里的 .env 是后台配置，不能与前端输入表单混为一谈。

| 字段组 | 作用与当前默认 |
| --- | --- |
| data_dir | 用户数据目录，默认 ROOT/data |
| ai_base_url / ai_api_key / ai_chat_model | 聊天服务地址、密钥与模型，密钥和模型默认空 |
| embedding_base_url / embedding_api_key / embedding_model | 向量服务独立配置，密钥不隐式复制聊天密钥 |
| embedding_min_similarity | 语义相似度下限 0.35，不是结论正确率 |
| ai_json_mode / ai_token_parameter | 兼容接口的 JSON 模式与输出长度参数名 |
| ai_timeout_seconds / ai_retries | 请求超时 45 秒；重试默认 1，provider 内部另有上限 |
| ai_context_chars / ai_max_output_tokens | 发送上下文字符量与输出 token 上限 |
| max_upload_mb / max_pdf_pages / parse_timeout_seconds | 单文件、PDF 页数与解析时限 |
| max_dataset_rows / max_dataset_columns / max_xlsx_uncompressed_mb | 表格行列数及 XLSX 解压大小限制 |

directory()（L29–31）把相对 DATA_DIR 解释为相对于项目根目录，而不是相对于运行命令时的目录。返回 Path 对象，调用者继续拼接 papers、datasets 等路径。

## 3. db.py：连接数据库以及提交/回滚

[实际代码：backend/app/db.py，L1–L33](E:/agent/backend/app/db.py:1)

```python
from contextlib import contextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from .models import Base

class Database:
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine("sqlite:///" + str(directory / "research.db"), connect_args={"check_same_thread": False, "timeout": 30})
        @event.listens_for(self.engine, "connect")
        def configure(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    def migrate(self):
        from .migrations import migrate
        migrate(self.engine)

    @contextmanager
    def session(self):
        with self.Session() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

def serialize(row, exclude=()):
    hidden = {"storage_path", "original_path", "vector"} | set(exclude)
    return {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name not in hidden}
```


Database.__init__（L7–15）先建立目录，再创建 SQLite engine。engine 可以理解成获取数据库连接的工厂，不是一条业务记录。check_same_thread=False 允许 FastAPI 工作方式跨线程使用连接；它不表示任意并发写入没有限制。

嵌套 configure（L11–14）在每次新连接时打开外键检查、WAL 日志模式与 30 秒忙等待。WAL 改善本地读写并行，但第一版仍按单进程单用户使用。

sessionmaker 创建会话工厂；expire_on_commit=False 避免提交后立刻让对象属性失效。migrate()（L17–19）把迁移工作转交 migrations.py。

session()（L22–29）有三步：yield db 把会话交给业务代码；正常结束就 commit；异常就 rollback 并继续抛出。with self.Session() 在退出时关闭会话。rollback 回滚数据库写入，不会自动撤销已经写到磁盘的文件。

serialize()（L31–33）遍历数据库字段形成字典，默认隐藏服务器存储路径和向量内容，另外允许调用者指定排除项。它不是对任意对象的万能序列化器，只用于这里的 SQLAlchemy 表对象。

## 4. migrations.py：只在需要时建立表与索引

[实际代码：backend/app/migrations.py，L1–L13](E:/agent/backend/app/migrations.py:1)

```python
"""Versioned, repeatable local SQLite migrations. Add new versions; never edit applied migrations."""
from sqlalchemy import text
from .models import Base

def migrate(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)"))
        versions = set(conn.execute(text("SELECT version FROM schema_migrations")).scalars())
        if 1 not in versions:
            Base.metadata.create_all(conn)
            conn.execute(text("CREATE VIRTUAL TABLE chunks_fts USING fts5(chunk_id UNINDEXED, project_id UNINDEXED, paper_id UNINDEXED, tokens, tokenize='unicode61')"))
            conn.execute(text("CREATE TRIGGER chunks_fts_delete AFTER DELETE ON chunks BEGIN DELETE FROM chunks_fts WHERE chunk_id=old.id; END"))
            conn.execute(text("INSERT INTO schema_migrations(version) VALUES (1)"))
```


migrate(engine) 在一个 engine.begin 事务中工作。先建立版本记录表，再查已执行版本。如果版本 1 已存在，就跳过这一版；否则建立模型表、FTS5 虚拟表、删除触发器，再记版本。

chunks_fts 中 tokens 是可搜索内容；chunk_id、project_id、paper_id 使用 UNINDEXED，保存关联信息但不建立词项索引。查询还会显式限定项目。删除 chunks 后触发器同步删除 FTS 记录，避免删掉论文后仍检索到旧文本。

当前只有初始迁移版本 1。将来改变数据库结构，需要新增迁移版本，不能仅修改 models.py 就声称老数据库自动升级。

## 5. models.py：数据库中每种记录的形状

[实际代码：backend/app/models.py，L1–L22](E:/agent/backend/app/models.py:1)

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()
def uid(): return uuid.uuid4().hex
def now(): return datetime.now(timezone.utc).isoformat()

class Entity:
    id = Column(String, primary_key=True, default=uid)
    created_at = Column(String, default=now, nullable=False)

class Project(Entity, Base):
    __tablename__ = "projects"
    name = Column(String(200), nullable=False)
    question = Column(Text, default="")
    hypothesis = Column(Text, default="")
    tags = Column(JSON, default=list)
    notes = Column(Text, default="")
    archived = Column(Boolean, default=False)
    updated_at = Column(String, default=now, onupdate=now)
```


Base 是 SQLAlchemy 声明模型的基础。uid() 生成 UUID 十六进制字符串；now() 生成带 UTC 时区的 ISO 时间。Entity 混入公共 id 与 created_at，后面的大部分实体继承它。

Column 描述表的一列：String/Text 保存文字，Integer/Float 保存数字，Boolean 保存真/假，JSON 保存列表或字典。primary_key 是主键；ForeignKey 是指向另一张表的关联；nullable=False 表示不能为空；default 是未提供值时的默认；index=True 是为查询建立普通索引。

注意 default=list / dict 传的是工厂函数，每个新记录生成自己的容器，不共享同一个可变列表。

[实际代码：backend/app/models.py，L24–L70](E:/agent/backend/app/models.py:24)

```python
class Paper(Entity, Base):
    __tablename__ = "papers"
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(Text, default="")
    authors = Column(Text, default="")
    year = Column(Integer, nullable=True)
    doi = Column(Text, default="")
    tags = Column(JSON, default=list)
    reading_status = Column(String, default="unread")
    notes = Column(Text, default="")
    filename = Column(Text, nullable=False)
    storage_path = Column(Text, nullable=False)
    sha256 = Column(String, nullable=False)
    size_bytes = Column(Integer, default=0)
    page_count = Column(Integer, default=0)
    status = Column(String, default="queued")
    error = Column(Text, nullable=True)
    parser_version = Column(String, default="pypdf-v1")
    __table_args__ = (UniqueConstraint("project_id", "sha256"),)

class PaperPage(Entity, Base):
    __tablename__ = "paper_pages"
    paper_id = Column(String, ForeignKey("papers.id", ondelete="CASCADE"), index=True, nullable=False)
    page_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("paper_id", "page_number"),)

class Chunk(Entity, Base):
    __tablename__ = "chunks"
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    paper_id = Column(String, ForeignKey("papers.id", ondelete="CASCADE"), index=True, nullable=False)
    page_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    start_offset = Column(Integer, nullable=False)
    end_offset = Column(Integer, nullable=False)
    parser_version = Column(String, default="pypdf-v1")

class Embedding(Entity, Base):
    __tablename__ = "embeddings"
    chunk_id = Column(String, ForeignKey("chunks.id", ondelete="CASCADE"), index=True, nullable=False)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    model = Column(Text, nullable=False)
    fingerprint = Column(Text, nullable=False)
    dimension = Column(Integer, nullable=False)
    version = Column(String, default="v1")
    vector = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("chunk_id", "fingerprint"),)
```


| 模型 | 字段与关联逐项说明 |
| --- | --- |
| Project（L14–22） | name 名称；question 问题；hypothesis 假设；tags 标签；notes 备注；archived 归档标记；updated_at 更新时自动改时间 |
| Paper（L24–42） | project_id 所属项目；title/authors/year/doi/tags 元信息；reading_status 阅读状态；notes 备注；filename 原文件显示名；storage_path 服务器随机存储路径；sha256 内容指纹；size_bytes 大小；page_count 页数；status/error 解析状态与原因；parser_version 解析规则版本 |
| PaperPage（L44–49） | paper_id 所属论文；page_number 实际 PDF 页码；text 整页原文。论文+页码唯一 |
| Chunk（L51–59） | project_id/paper_id 限定资料范围；page_number 引用位置；text 片段；start_offset/end_offset 页内文字偏移；parser_version 记录提取规则 |
| Embedding（L61–70） | chunk_id 对应片段；project_id 范围；model 模型名；fingerprint 服务与模型指纹；dimension 维度；version 记录格式版本；vector 数值列表。片段+指纹唯一 |

Paper 的 UniqueConstraint(project_id, sha256) 把去重限定在同一项目，不是所有项目共享同一条论文。程序层先查重，数据库约束提供最后一层约束。

[实际代码：backend/app/models.py，L72–L108](E:/agent/backend/app/models.py:72)

```python
class Note(Entity, Base):
    __tablename__ = "notes"
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    paper_id = Column(String, ForeignKey("papers.id", ondelete="CASCADE"), nullable=True)
    content = Column(Text, default="")

class Conversation(Entity, Base):
    __tablename__ = "conversations"
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(Text, default="")

class Message(Entity, Base):
    __tablename__ = "messages"
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, default="")
    mode = Column(String, default="offline")
    citations = Column(JSON, default=list)

class Citation(Entity, Base):
    __tablename__ = "citations"
    message_id = Column(String, ForeignKey("messages.id", ondelete="CASCADE"), index=True, nullable=False)
    paper_id = Column(String, ForeignKey("papers.id", ondelete="SET NULL"), nullable=True)
    chunk_id = Column(String, ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True)
    page_number = Column(Integer)
    quote = Column(Text)
    title = Column(Text)

class Experiment(Entity, Base):
    __tablename__ = "experiments"
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(Text, nullable=False)
    hypothesis = Column(Text, default="")
    paper_ids = Column(JSON, default=list)
    conditions = Column(Text, default="")
    parameters = Column(Text, default="")
    notes = Column(Text, default="")
```


| 模型 | 字段与关联逐项说明 |
| --- | --- |
| Note（L72–76） | project_id 所属项目；可选 paper_id；content 笔记正文。独立笔记实体与 Paper.notes 元数据备注是两种保存位置 |
| Conversation（L78–81） | project_id、title 组织一次对话记录 |
| Message（L83–89） | conversation_id 所属对话；role 用户或助手；content 正文；mode 离线/AI/资料不足；citations 保存 JSON 引用快照 |
| Citation（L91–98） | message_id 关联消息；paper_id/chunk_id 关联出处；page_number/quote/title 保存引用信息。删除论文时两个外键可置空，历史文字仍是快照 |
| Experiment（L100–108） | project_id、name、hypothesis；paper_ids 为关联论文 ID 列表；conditions、parameters、notes 记录实验背景 |

Message.citations 是便于读取的 JSON，Citation 表是结构化引用记录。它们的维护逻辑在 api_core.py。paper_ids JSON 列表不是数据库外键，是否属于当前项目由 deps.paper_ids 校验。

[实际代码：backend/app/models.py，L110–L157](E:/agent/backend/app/models.py:110)

```python
class DatasetVersion(Entity, Base):
    __tablename__ = "dataset_versions"
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    experiment_id = Column(String, ForeignKey("experiments.id", ondelete="CASCADE"), index=True, nullable=False)
    parent_id = Column(String, ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True)
    filename = Column(Text, nullable=False)
    storage_path = Column(Text, nullable=False)
    original_path = Column(Text, nullable=False)
    sha256 = Column(String, nullable=False)
    original_sha256 = Column(String, nullable=False)
    sheet = Column(String, nullable=True)
    sheets = Column(JSON, default=list)
    columns = Column(JSON, default=list)
    row_count = Column(Integer, default=0)
    preview = Column(JSON, default=list)
    quality = Column(JSON, default=dict)
    transform = Column(JSON, default=dict)

class AnalysisRun(Entity, Base):
    __tablename__ = "analysis_runs"
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    experiment_id = Column(String, ForeignKey("experiments.id", ondelete="CASCADE"), index=True, nullable=False)
    dataset_id = Column(String, ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False)
    config = Column(JSON, nullable=False)
    result = Column(JSON, nullable=False)
    provenance = Column(JSON, default=dict)

class Report(Entity, Base):
    __tablename__ = "reports"
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    analysis_id = Column(String, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False)
    markdown = Column(Text, nullable=False)
    context = Column(JSON, default=dict)

class Job(Entity, Base):
    __tablename__ = "jobs"
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    resource_id = Column(String, nullable=True)
    kind = Column(String, nullable=False)
    status = Column(String, default="queued", index=True)
    error = Column(Text, nullable=True)
    updated_at = Column(String, default=now, onupdate=now)

class Preference(Base):
    __tablename__ = "preferences"
    key = Column(String, primary_key=True)
    value = Column(JSON, nullable=False)
```


| 模型 | 字段与关联逐项说明 |
| --- | --- |
| DatasetVersion（L110–126） | project_id/experiment_id 归属；parent_id 指向上一清洗版本；filename 显示名；storage_path 当前版本文件；original_path 原件；sha256/original_sha256 两份指纹；sheet/sheets 工作表；columns/row_count/preview/quality 预览；transform 已确认清洗规则 |
| AnalysisRun（L128–135） | 项目、实验、dataset_id 确定数据版本；config 保存分析参数；result 保存数值和图数据；provenance 保存代码/依赖等来源信息 |
| Report（L137–143） | project_id、analysis_id；title、markdown 报告正文；context 保存生成时上下文，保持历史一致 |
| Job（L145–152） | project_id、resource_id 关联资料；kind 类型；status/error 持久化状态；updated_at 最近变化时间 |
| Preference（L154–157） | key/value 键值设置，当前 AI 启用开关存这里；它不继承 Entity，key 自身就是主键 |

ondelete='CASCADE' 表示删上级时连带删子记录；SET NULL 保留记录但清空关联；RESTRICT 阻止删除仍被分析使用的数据版本。这些只有连接真正启用 foreign_keys 时才生效，所以 db.py 的 PRAGMA 很关键。

## 6. schemas.py：进入后台前先检查输入

[实际代码：backend/app/schemas.py，L1–L49](E:/agent/backend/app/schemas.py:1)

```python
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class ProjectInput(Input):
    name: str = Field(min_length=1,max_length=200)
    question: str = Field(default="",max_length=10000)
    hypothesis: str = Field(default="",max_length=10000)
    tags: list[str] = Field(default_factory=list,max_length=30)
    notes: str = Field(default="",max_length=30000)
    archived: bool = False

class ProjectPatch(Input):
    name: str | None = Field(default=None,min_length=1,max_length=200)
    question: str | None = Field(default=None,max_length=10000)
    hypothesis: str | None = Field(default=None,max_length=10000)
    tags: list[str] | None = Field(default=None,max_length=30)
    notes: str | None = Field(default=None,max_length=30000)
    archived: bool | None = None

class PaperPatch(Input):
    title: str | None = Field(default=None,min_length=1,max_length=500)
    authors: str | None = Field(default=None,max_length=2000)
    year: int | None = Field(default=None,ge=1000,le=2200)
    doi: str | None = Field(default=None,max_length=300)
    tags: list[str] | None = Field(default=None,max_length=30)
    reading_status: Literal["unread","reading","read"] | None = None
    notes: str | None = Field(default=None,max_length=50000)

class SearchInput(Input):
    query: str = Field(min_length=1,max_length=2000)
    paper_ids: list[str] = Field(default_factory=list,max_length=100)
    year: int | None = None
    tags: list[str] = Field(default_factory=list,max_length=30)
    limit: int = Field(default=8,ge=1,le=30)

class AskInput(Input):
    question: str = Field(min_length=1,max_length=2000)
    paper_ids: list[str] = Field(default_factory=list,max_length=100)
    conversation_id: str | None = None

class CompareInput(Input):
    paper_ids: list[str] = Field(min_length=2,max_length=5)
    @model_validator(mode="after")
    def unique(self):
        if len(set(self.paper_ids))!=len(self.paper_ids): raise ValueError("请选择不同论文")
        return self
```


Input 是输入模型共同基类：extra='forbid' 拒绝未声明字段，str_strip_whitespace=True 去除首尾空格。Field 的 min_length/max_length/ge/le 限制字符串、列表或数值范围。

| 输入模型 | 每个字段的作用和约束 |
| --- | --- |
| ProjectInput（L7–13） | name 必填1–200字符；question/hypothesis各≤10000；tags最多30；notes≤30000；archived默认false |
| ProjectPatch（L15–21） | 同类字段均可不传，配合 exclude_unset 只修改明确提供的字段。可选不代表数据库所有列都能写null |
| PaperPatch（L23–30） | title≤500且非空；authors≤2000；year 1000–2200或null；doi≤300；tags≤30；reading_status 只能unread/reading/read；notes≤50000 |
| SearchInput（L32–37） | query 1–2000；paper_ids≤100；可选year与tags≤30；limit默认8且1–30 |
| AskInput（L39–42） | question 1–2000；paper_ids≤100；可选conversation_id，随后仍要校验项目归属 |
| CompareInput（L44–49） | 论文列表长度2–5；unique() 在模型形成后拒绝重复ID |

Literal 表示只接受列出的值；| None 表示可以为空；default_factory=list 表示为每个输入创建独立列表。model_validator(mode='after') 在字段校验后执行跨字段/整体校验。

[实际代码：backend/app/schemas.py，L51–L76](E:/agent/backend/app/schemas.py:51)

```python
class ExperimentInput(Input):
    name: str = Field(min_length=1,max_length=200)
    hypothesis: str = Field(default="",max_length=10000)
    paper_ids: list[str] = Field(default_factory=list,max_length=100)
    conditions: str = Field(default="",max_length=10000)
    parameters: str = Field(default="",max_length=10000)
    notes: str = Field(default="",max_length=30000)

class CleanInput(Input):
    drop_missing_columns: list[str] = Field(default_factory=list,max_length=200)
    drop_duplicate_rows: bool = False

class SuggestInput(Input):
    dataset_id: str
    question: str = Field(default="",max_length=2000)

class ReportInput(Input):
    analysis_id: str
    title: str = Field(default="",max_length=200)

class SettingsInput(Input):
    ai_enabled: bool

class NoteInput(Input):
    content: str = Field(max_length=50000)
    paper_id: str | None = None
```


| 输入模型 | 字段逐项说明 |
| --- | --- |
| ExperimentInput（L51–57） | name 1–200；hypothesis≤10000；paper_ids≤100；conditions/parameters≤10000；notes≤30000 |
| CleanInput（L59–61） | drop_missing_columns 指定哪些列缺失时删行，最多200列；drop_duplicate_rows 决定是否去完全重复行，默认false |
| SuggestInput（L63–65） | dataset_id 选定数据；question 为可选的分析建议问题，≤2000 |
| ReportInput（L67–69） | analysis_id 选择已保存分析；title≤200 |
| SettingsInput（L71–72） | 只能修改 ai_enabled，密钥不通过这个接口保存 |
| NoteInput（L74–76） | content≤50000；paper_id 可选；归属检查由路由继续执行 |

实验统计的 AnalysisConfig 更接近计算引擎，因此定义在 stats_engine.py，本章的 schemas.py 没有重复定义它。

## 7. deps.py：共享会话与项目隔离

[实际代码：backend/app/deps.py，L1–L23](E:/agent/backend/app/deps.py:1)

```python
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
```


session(request) 从 app.state 拿数据库并 yield 会话。project(db,id) 找项目，找不到抛404。scoped(db,cls,id,project_id) 既查记录，又要求其 project_id 等于当前项目；知道别的项目的资源 ID 也不能读出来。paper_ids 把数据库中属于本项目的所选 ID 集合，与用户提交集合比较，缺少任意一个就拒绝。

这几个函数解决资源归属，不是用户登录权限。当前产品是本地单用户。

## 8. main.py：把前面的部件组装起来

[实际代码：backend/app/main.py，L1–L34](E:/agent/backend/app/main.py:1)

```python
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
```


create_app（L15–66）是应用工厂，既用于真实启动，也用于测试指定临时 data_dir。settings 参数允许注入配置。函数里创建数据库和模型适配器，把它们挂在 app.state，让路由通过 request.app.state 使用。

lifespan（L21–25）在 yield 前执行启动工作：迁移、恢复中断任务；yield 后 dispose 关闭数据库连接资源。@asynccontextmanager 把这个异步生成器变成框架能管理的生命周期。

CORSMiddleware 限定允许的浏览器来源；TrustedHostMiddleware 限定 Host。二者检查的对象不同，不能把 Host 当成 Origin。当前允许测试用 testserver，是为了 TestClient。

[实际代码：backend/app/main.py，L36–L68](E:/agent/backend/app/main.py:36)

```python
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
```


local_origin（L37–43）在有 Origin 的修改请求中拒绝未列出的来源，返回403；正常响应加 nosniff 与 no-referrer。没有 Origin 的请求并不会被这段当作外部浏览器请求拒绝，它不是认证或公网防护系统。

provider_error（L46）把模型适配器异常转换成502；validation_error（L48）处理代码中产生的 Pydantic ValidationError；FastAPI 请求体自己的校验也有框架默认处理。value_error（L50）把可解释的业务 ValueError 转换成400，并限制错误文字长度。

include_router 把核心、实验和示例接口注册到同一个应用。frontend（L58–65）是最后的静态文件与单页路由回退：先拒绝未知 api 路径；resolve + is_relative_to 防止走出 dist；存在文件就发送；带扩展名但不存在则404；普通页面路径回退 index.html。

最后 app=create_app() 生成 Uvicorn 要加载的应用对象。import 时创建对象；数据库迁移在真正进入生命周期时执行。

## 9. 根目录配置

- .env.example 只有设置模板与空密钥；真实 .env 不会收录到源码阅读器。环境变量名对应 Settings 字段。
- .gitignore 排除虚拟环境、依赖、构建、真实 .env、data 和 tmp 等运行产物。
- pyproject.toml 声明项目名、版本、Python≥3.12，并配置 pytest 的导入路径和测试目录。
- requirements.txt 通过 -r requirements.lock.txt 引用精确依赖。requirements.lock.txt 固定 Python 包版本；frontend/package-lock.json 固定 npm 依赖解析。锁文件不会自动把第三方源码变成项目自有源码。

下一章：[论文、检索与 AI](02-papers-ai.md)。