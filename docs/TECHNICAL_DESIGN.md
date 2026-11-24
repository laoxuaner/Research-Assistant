# 研知：面向计算机专业学生的技术方案

本文依据当前仓库实现说明架构、算法与工程取舍。标为“后续建议”的内容尚未实现；本文只增加讲解，不修改业务代码。

## 1. 系统定位与约束

这是本地单用户的科研资料系统，由论文知识库、带证据检索问答、确定性实验分析、可复现报告四个子域组成。输入是文本PDF及CSV/XLSX；输出是可定位原文、保存的分析结果与导出文件。默认仅监听127.0.0.1。

主要质量属性：可追溯性、离线可用性、结果可复现、失败可解释、安装简单。当前不以高并发、多租户、超大规模语料或自动Agent执行为目标。

## 2. 架构：模块化单体与按能力分离

~~~mermaid
flowchart TD
    UI[React 浏览器工作台] --> API[FastAPI HTTP接口]
    API --> Paper[论文解析与检索模块]
    API --> Research[证据问答模块]
    API --> Stats[统计模块]
    API --> Export[报告与导出模块]
    Paper --> DB[(SQLite与FTS5)]
    Research --> DB
    Stats --> DB
    Export --> DB
    Paper --> Disk[原始文件与代码快照]
    Export --> Disk
    Research -.配置并启用后.-> Model[Chat与Embedding适配器]
~~~

生产环境一个Uvicorn应用同时提供API和frontend/dist。开发时5173的Vite通过/api代理到8000后台；浏览器代码使用相对地址。逻辑前后端分离不要求两个生产进程。

主要模块：
- main.py：应用工厂、生命周期、中间件、路由与静态资源。
- models/db/migrations/schemas/deps：关系模型、会话、迁移、输入约束、项目范围。
- api_core.py / api_experiments.py：HTTP入口与部分业务编排。
- papers.py / parse_pdf.py：任务、切块、FTS、独立解析进程。
- research.py / providers.py：检索融合、证据组织、模型协议和校验。
- stats_engine.py：无数据库/HTTP/模型依赖的表格处理和计算核心，但仍依赖pandas、SciPy、Pydantic等库。
- exports.py：已保存结果到报告、PNG与复现包。
- frontend/src：页面、共享组件、请求工具、数值显示和样式。

这是模块化单体，未完整实现DDD、独立Repository层或微服务拆分。接口层仍直接操作ORM，复杂功能将来可以进一步抽出服务层。

技术选型：
| 层 | 当前选择 | 收益 | 代价 |
| --- | --- | --- | --- |
| UI | React、TypeScript、Vite、Tailwind与自定义CSS | 组件化、静态类型、开发构建方便 | 本地状态/异步请求需要管理 |
| API | FastAPI、Pydantic | 参数校验、依赖注入、OpenAPI | async声明不自动消除同步阻塞 |
| 存储 | SQLite、SQLAlchemy | 无独立数据库服务、关系约束、事务 | 写入并发受限 |
| 检索 | FTS5 BM25；可选NumPy向量 | 无独立搜索服务 | 大规模向量检索受内存/线性扫描限制 |
| PDF | pypdf、PDF.js | 提取与阅读分工 | 复杂排版与扫描件不保证正确提取 |
| 分析 | pandas、NumPy、SciPy | 成熟数值能力、固定算法 | 研究设计仍需人工确认 |
| 导出 | Matplotlib及文件模板 | 无模型也能生成真实结果 | 图文排版与跨环境数值一致性仍有边界 |

## 3. 数据模型与不变量

~~~mermaid
erDiagram
    Project ||--o{ Paper : contains
    Paper ||--o{ PaperPage : pages
    Paper ||--o{ Chunk : chunks
    Chunk ||--o{ Embedding : vectors
    Project ||--o{ Conversation : conversations
    Conversation ||--o{ Message : messages
    Message ||--o{ Citation : cites
    Project ||--o{ Experiment : experiments
    Experiment ||--o{ DatasetVersion : versions
    DatasetVersion ||--o{ AnalysisRun : analyses
    AnalysisRun ||--o{ Report : reports
    Project ||--o{ Job : tasks
~~~

此图是主要关系示意，未画出全部冗余project_id、Note及Preference。重要约束：
1. Paper(project_id, sha256)唯一：同项目按内容去重，改文件名不绕过。
2. PaperPage(paper_id,page_number)唯一：实际PDF页码，而非印刷页码。
3. Embedding(chunk_id,fingerprint)唯一：同片段可区分不同配置来源。
4. AnalysisRun.dataset_id固定：后续上传或清洗不覆盖旧分析。
5. Report保存context和markdown：报告是生成时快照。
6. 所有项目资源入口校验project_id；检索也限定所选论文、年份与标签。
7. 表关联使用CASCADE/SET NULL/RESTRICT；JSON中的关联ID另由业务校验。

PaperPage保留整页，Chunk保留切块和页内字符偏移，FTS保留分词后的检索表示，Embedding保留模型向量。这些是为不同访问模式建立的派生表示，不应把FTS的tokens作为最终引用原文。

原PDF、表格和统计代码快照存磁盘，结构化元数据存SQLite。JSON字段适合配置、结果和快照；经常按条件查询且要求关系约束的数据更适合普通列或关系表。

## 4. HTTP契约、依赖注入与事务

JSON API统一/api前缀；上传用multipart，下载返回文件字节。典型接口：
| 操作 | 接口 |
| --- | --- |
| 建项目 | POST /api/projects |
| 上传PDF | POST /api/projects/{p}/papers |
| 检索 | POST /api/projects/{p}/search |
| 提问 | POST /api/projects/{p}/ask |
| 导入数据 | POST /api/projects/{p}/experiments/{e}/datasets |
| 保存分析 | POST /api/projects/{p}/experiments/{e}/analyses |
| 创建报告 | POST /api/projects/{p}/reports |

校验分层：前端用于交互提示；Pydantic检查类型、范围与组合配置；deps检查资源归属；统计引擎检查样本和设计适用性；SQLite约束维护关系不变量。TypeScript类型本身不提供服务器响应的运行时校验。

create_app把数据库、配置与Provider放进app.state。测试可以替换Provider或临时数据目录，属于轻量依赖注入；Protocol定义generate/embed契约，不要求继承某个运行时基类。

Session上下文正常commit，异常rollback。Depends(session,scope='function')使事务收尾在成功响应发送前完成，避免先告诉前端成功、随后才提交失败。

SQLite启用foreign_keys、WAL、busy_timeout。WAL允许读写更好地并行，但不会让SQLite变成多写者数据库。

文件系统不加入SQLite事务。当前上传先写文件再写记录，删除也涉及unlink，崩溃可能留下孤儿文件或缺失文件。FTS删除触发器属于数据库同一事务，文件不属于。后续建议：临时文件、明确提交阶段、补偿删除及定期一致性扫描。

ask在新对话flush后调用模型，可能在网络等待期间保持写事务，是后续值得优先缩短的事务边界。

## 5. PDF处理流水线与任务状态机

~~~mermaid
sequenceDiagram
    participant UI as 浏览器
    participant API as API
    participant DB as SQLite
    participant Task as 进程内后台任务
    participant PDF as PDF解析子进程
    UI->>API: multipart上传
    API->>API: 大小/文件头/后缀/SHA256检查
    API->>DB: Paper与queued Job
    API->>DB: commit
    API-->>UI: 已接收及任务信息
    API->>Task: BackgroundTasks执行
    Task->>DB: running
    Task->>PDF: 提取逐页文字，设置超时
    PDF-->>Task: 页面JSON或错误
    Task->>DB: Page/Chunk/FTS及最终状态
~~~

PDF解析采用独立Python进程，通过stdout返回JSON。这样父任务可以设置timeout，失败不会直接在HTTP请求中持续解析。它不是权限沙箱，也没有OS级内存限额。

默认限制：单文件30MB、PDF300页、解析60秒；每批最多20文件、总100MB。子解析器还限制页内容流和提取文字量。阈值是资源边界，不代表所有复杂文件都可在限额内安全快速解析。

Job状态：queued→running→completed或failed；启动时遗留queued/running→interrupted。重试创建新Job，旧记录留存。论文另有needs_ocr状态；当前全文可读字符不足30时不建立索引，混合扫描页没有自动OCR。

逐页切块1200字符、重叠160字符，步长1040，保持页边界。偏移针对提取后的页面文字，不是PDF二进制字节。

BackgroundTasks是进程内执行机制；Job只是持久化状态记录。没有durable broker、lease、原子抢占或自动重投，因此不能声称exactly-once或重启自动续跑。当前按单Uvicorn进程运行。

## 6. 检索：倒排索引、BM25、语义向量与RRF

### 6.1 关键词检索
原文与query都经过同一tokenize：小写、jieba、停用词、字符检查与长度限制，再交给FTS5 unicode61。查询词去重、最多35个，当前采用OR匹配。

FTS5是倒排检索。BM25综合词项稀有程度、频率饱和与文档长度，对命中片段排序。SQLite的bm25值越小越靠前，应用转换符号用于返回；分数不应解释为置信概率。

project_id/paper_id在FTS定义中UNINDEXED。它们用于SQL逻辑范围约束，不是每个项目拥有一个物理独立倒排索引。

当前分词会过滤单字符、标点及部分常见词，对公式、缩写和专有名词可能召回不足；这些应该通过检索评测改进，不能只看演示问题命中就认为检索质量充分。

### 6.2 可选向量检索
每个片段调用EmbeddingProvider，保存model、dimension、version和fingerprint。指纹按服务地址+模型名+v1计算；查询向量维度也要检查。相同模型名背后的服务升级不能完全自动识别。

余弦相似度：
cos(q,v) = dot(q,v) / (norm(q) * norm(v))

当前加载范围内全部匹配指纹的向量，用NumPy逐条算分，默认相似度阈值0.35。若范围中有N片段、维度d，核心计算约O(Nd)，排序约O(NlogN)，物化内存约O(Nd)。没有ANN、HNSW、FAISS或向量数据库。

### 6.3 融合
关键词前30和语义前30按RRF融合：
RRF(chunk) = sum(1 / (60 + rank_i(chunk)))
rank从1开始，不在某一路列表就没有该路贡献。

实际核心代码：
~~~python
for values in [lexical,[c for _,c in semantic[:30]]]:
    for rank,item in enumerate(values):
        cid=item["chunk_id"]
        merged[cid]=item
        scores[cid]=scores.get(cid,0)+1/(60+rank+1)
~~~

RRF融合排名，避免直接相加不同量纲的BM25和余弦分数。当前两路等权，没有cross-encoder重排。模型缺失、向量未建或服务失败时回退关键词并给提示。

## 7. RAG：约束生成输入与验证输出

当前链路：范围校验→混合或关键词召回→上下文字符预算→问题+证据JSON→ChatProvider→结构检查与引用校验→保存Message/Citation。

默认上下文预算18000字符，主要限制摘录字符总量，不是精确token预算或完整请求字符上限；输出上限默认1800token。长论文阅读卡按片段顺序截断，未做全篇分层摘要，可能遗漏后半段。

模型回答用claims列表，kind分reported/inference/suggestion。每条已报告/推断结论需要引用。validate_citations核对chunk_id、paper_id、整数页码与quote是否为本次证据的原文子串。引用真实性检查不等于语义蕴含验证。

当前模型调用是一次完整JSON响应，没有SSE流式。Conversation保存历史，但生成payload只包含当前问题与本次证据，不自动注入全部历史上下文。

Provider是Chat Completions兼容和Embeddings兼容适配器，使用JSON模式加手工结构校验，并不是所有服务都支持的严格JSON Schema保证。聊天与向量独立地址/模型/密钥。请求45秒超时，默认重试1次、上限2次；这是每次请求的超时，不是总工作流deadline。

论文内容作为不可信数据，放入evidence，系统规则禁止其改变任务。模型没有工具执行权限；建议经校验并由用户确认后才能调用固定分析功能。但提示与引用校验不是对提示注入或模型误解的完全证明。

## 8. 数据版本、清洗与确定性统计

读取表格时先保留字符串，保护001等ID和NA/NULL字面标签，之后只对指定数值指标转换。质量概况记录缺失、非数值、重复、IQR异常点与预览前50行。异常点默认只标记。

清洗仅白名单支持指定列缺失行排除和完全重复行排除；每步记录受影响行数，并生成新DatasetVersion。原件不覆盖。分析清洗版本时，从原始文件按原工作表和规则链重放，当前CSV是审计导出；文件指纹不匹配则拒绝继续。

analyze(DataFrame,AnalysisConfig)→标准JSON结果。处理顺序：
1. 校验列和保留字段，复制输入表；
2. 限定两组，记录排除；
3. 按明确策略处理无效指标；
4. 用完整选定输入检查ID，避免排除缺失后掩盖重复单位；
5. 配对时检查组内唯一与两组ID集合一致，并按ID连接；
6. 描述统计；
7. 适用才做推断，否则保留描述及原因；
8. 返回结果、原始有效点、警告、排除及配置。

描述统计为n/mean/median/样本std/min/max。次要数值指标只描述，不批量检验。

独立两组Welch：
delta = mean(B) - mean(A)
SE = sqrt(s_A^2/n_A + s_B^2/n_B)
t = delta / SE
df = (s_A^2/n_A + s_B^2/n_B)^2 /
     [(s_A^2/n_A)^2/(n_A-1) + (s_B^2/n_B)^2/(n_B-1)]
95% CI = delta ± t_0.975,df * SE

配对设计按ID得到d_i=B_i−A_i，再以mean(d)、s_d/sqrt(n)、df=n−1计算。p方向与B−A统一，CI始终双侧。基准均值0不算相对变化。

数值稳定性：均值、std及检验中先按尺度缩放，减小平方溢出/下溢；尾概率使用sf；非有限值不能作为JSON中的NaN/Infinity输出。这不是任意精度算术，仍受IEEE浮点与库实现约束。

不支持复杂重复测量、聚类、多组、多重比较、协变量调整和功效分析。单位、独立性和检验适用性不能仅由数据列判断。

## 9. 前端状态、PDF与结果呈现

App管理项目/导航/全局入口，页面使用局部hooks与api.ts fetch封装，无Redux或统一server-state缓存。

实验页用请求序号和实验ID避免旧请求覆盖新选择；配置变化使confirmed失效。PDF读取与canvas渲染有cancelled标记、destroy/cancel收尾。不是所有页面请求都统一支持AbortController，因此不能声称全站竞态已完全解决。

PDF.js worker、cmaps和标准字体本地打包。按页canvas渲染，点击Citation时使用paper_id/page_number，而不是解析模型回答中的页码文字。

图表基于已保存result.points；前端展示交互图，后台Matplotlib导出PNG。数据源一致不代表像素、分箱、所有视觉细节完全相同。数值格式化保留非零极小量；分箱明确最后边界，避免最大值丢失。报告Markdown禁用原始HTML并限制报告图片来源。

async/await与CPU并行应区分：Provider是同步httpx；同步接口由框架安排工作线程，上传async接口中的pandas解析等仍可能阻塞事件循环。后续应按负载把同步I/O或CPU任务移到适当线程/进程。

## 10. 复现、测试与安全边界

AnalysisRun记录原始/版本哈希、规则链、配置、有效样本、排除、依赖、平台、应用版本、统计源码哈希，并保存统计源码快照。Report绑定保存结果，模型不重算数字。

ZIP包含original、stats_engine.py、reproduce.py、config、provenance、saved_result、summary、report与PNG。复现脚本核对原件/代码哈希→读取原始sheet→重放清洗→计算→递归容差比对已存结果。它重算统计与审计，不重新绘全部图。比较使用assert，因此应普通python运行，不用-O。

哈希证明内容一致，不证明科研真实性或作者身份；这不是数字签名或完整OS/容器快照。复现数值采用容差，不承诺不同硬件环境逐比特相同。

测试分为统计纯函数、模型协议桩、API集成、导出子进程复现、真实浏览器闭环和单独干净venv复现。验收文档记录61个后台测试、10个前端测试及构建/干净复现通过；真实外部模型调用未验证。本文是读码讲解，没有重跑上述测试。

安全按本地单用户设计：127.0.0.1、Host/Origin/CORS约束、随机存储名、文件限制、项目范围、后端密钥、参数化SQL、Markdown限制、模型不执行代码、CSV公式转义。它没有登录、多租户RBAC、公网部署防护或数据加密，不能直接当多人公网服务部署。

## 11. 按实际瓶颈演进：以下均为后续建议

| 阶段 | 可以改进 | 应先观察的证据 |
| --- | --- | --- |
| 维护性 | API编排抽服务；减少大组件；补类型化结果协议 | 变更冲突、重复逻辑、类型漂移 |
| 本地可靠性 | 缩短网络等待事务；文件补偿/孤儿扫描；迁移新增版本 | DB锁等待、崩溃恢复与一致性测试 |
| 任务增长 | durable worker、原子领取、lease、并发限制、取消 | 排队时延、进程资源、重复执行 |
| 资料增长 | 分页、虚拟列表、向量缓存/ANN、检索评测集 | p95查询延迟、内存、Recall@k与引用正确率 |
| 团队使用 | PostgreSQL、认证授权、对象存储、审计与配额 | 明确多人需求与威胁模型 |
| 更强科研功能 | OCR、表格/公式提取、复杂统计、结构化复现环境 | 数据类型和实验设计的真实需要 |

不要先为不存在的吞吐量拆微服务。当前最有教学价值的三件事是：范围约束贯穿访问链；数值计算与语言生成分离；数据版本、配置、代码与结果共同构成可追溯分析。

源码入口：[逐文件解读](code-guide/README.md)、[完整源码阅读器](code-guide/code-reader.html)、[验收记录](ACCEPTANCE.md)。
