# 从哪里开始读代码

[返回总目录](README.md) · [完整源码](ALL_SOURCE.md) · [可搜索源码阅读器](code-reader.html)

这套材料覆盖项目自己编写的源码、测试、脚本和配置。依赖目录 node_modules、Python .venv、PDF.js 字体/字符表属于第三方依赖；dist、缓存、真实用户数据也不属于手写业务代码。完整收录清单见 manifest.json。

阅读方法：先知道一段代码要完成什么，再看输入、处理、输出，最后看异常时做什么。不要一开始背语法或试着从 styles.css 第一行一直读到最后一行。

## 一、目录是程序的分工表

| 目录/文件 | 负责的事情 | 应该怎样读 |
| --- | --- | --- |
| scripts/start.ps1 | 启动本地服务 | 看最后实际执行的命令 |
| backend/app/main.py | 组装后台应用 | 找 create_app、启动收尾、路由注册 |
| config.py / db.py / models.py / schemas.py / deps.py | 配置、存储结构、输入检查和项目范围 | 先区别数据库模型与输入模型 |
| api_core.py | 项目、论文、问答和设置的 API 入口 | 看路由地址、输入和调用的业务函数 |
| papers.py / parse_pdf.py | 解析任务、切块、分词和文字提取 | 理解原 PDF 怎样变成可检索片段 |
| research.py / providers.py | 检索、模型请求、引用校验 | 理解离线与有模型两条分支 |
| api_experiments.py / stats_engine.py | 实验接口与确定性统计计算 | 接口保存版本，统计引擎只做计算 |
| exports.py | 报告、图表和复现包 | 找已保存结果、原文件、代码快照的来源 |
| frontend/src | 浏览器页面 | 从 main.tsx → App.tsx → 子组件 → api.ts 读 |
| backend/tests / frontend/tests | 验证已有行为 | 看准备数据、执行动作、assert/expect |
| scripts/generate_samples.py / samples | 合成教学与测试材料 | 不是真实论文或科研发现 |
| requirements.lock.txt / frontend/package-lock.json | 固定第三方依赖版本 | 理解整体作用，无需背每一项 |

## 二、先学会看这几个符号

| 代码 | 初学者解释 |
| --- | --- |
| Python 的 import | 从别的文件或库中引入工具 |
| def name(...): | 定义一个可以被调用的函数，括号是输入 |
| class Name | 定义一种对象或数据结构 |
| return | 把结果交给调用者 |
| if / for | 按条件选择，或对一组内容逐个处理 |
| with | 进入一个有开始和收尾工作的上下文，例如数据库事务 |
| try / except | 尝试执行；失败后进入错误处理 |
| yield | 先把控制权交出去，稍后再回来收尾，数据库会话就是这样使用 |
| @router.post(...) | 装饰器：把下面的函数登记为某个 HTTP 接口 |
| TypeScript 的 type | 给数据形状做静态说明，不是运行时检查 |
| const | 声明一个变量绑定 |
| async / await | 等待异步工作完成，例如请求后端；不等于自动开一个计算线程 |
| useState | React 保存会影响页面的状态 |
| useEffect | React 在渲染后与网络、事件或 PDF 渲染等外部系统同步 |
| JSX 的 <Button> | 描述页面应该显示的组件 |
| assert / expect | 测试中声明应该满足的条件，不满足就失败 |

Python 的缩进属于语法。JS/TS 使用大括号组织代码；TSX 在 TypeScript 中加入页面结构。CSS 的选择器指定要影响哪些元素，冒号后的值决定颜色、间距和布局。

## 三、先跟完一次创建项目

完整路线：ProjectModal 表单 → api() → HTTP POST /api/projects → ProjectInput 校验 → create_project → SQLAlchemy 会话 → SQLite → JSON 返回 → 前端更新列表。

后端这一段很短，但贯穿了全项目最常用的写法：

[实际代码：backend/app/api_core.py，L44–L47](E:/agent/backend/app/api_core.py:44)

```python
@router.post("/projects",status_code=201)
def create_project(body:ProjectInput,db:Session=Depends(session, scope="function")):
    row=Project(**body.model_dump());db.add(row);db.flush()
    return serialize(row)
```


body 是通过校验的输入对象。body.model_dump() 把它变成字典；** 把字典字段展开成 Project 的构造参数。db.add 让会话管理这个新对象；db.flush 发送待执行的 SQL，并取得默认生成的 id，但最终持久化仍由事务提交完成。serialize 把对象转成能返回给网页的数据。

Depends(session, scope='function') 表示 FastAPI 注入数据库会话，并在接口函数结束、成功响应发送之前收尾事务。否则可能发生网页已经看到成功、数据库提交却失败的问题。test_failed_database_commit_never_returns_success 专门覆盖这个场景。

HTTP 201 表示创建成功；400 表示业务输入有问题；404 表示资源不存在或不在当前范围；422 表示结构/配置校验失败；502 用于模型服务或模型响应格式错误。HTTP 状态不等于统计结论。

## 四、再跟一次论文上传

网页选文件 → multipart 上传 → store_paper 检查 PDF、算 SHA-256 → 保存随机服务器文件名 → 写 Paper 和 Job → 后台 parse_job → 子进程 parse_pdf → PaperPage / Chunk / FTS 索引 → 状态 completed 或 needs_ocr / failed。

SHA-256 是文件内容的指纹，换文件名不会改变它。同一项目用它识别重复 PDF。Job 是保存到数据库的任务记录；它不等于拥有复杂调度器的独立任务队列。

## 五、再跟一次实验分析

网页填写 AnalysisConfig → 后端确认配置 → verify_dataset 检查文件哈希 → 从原始文件重放已记录的清洗 → analyze 计算 → 保存 AnalysisRun 的结果、配置、依赖版本和代码快照 → 网页显示结果 → 创建 Report → build_export 生成复现包。

数据层 DatasetVersion、结果层 AnalysisRun、报告层 Report 各自保存信息。它们分别回答：用哪份数据、按什么方法算出了什么、当时怎样整理成报告。

## 六、源码里的几个重要边界

1. 提示模型遵守规则与校验引用是降低错误的措施，不是对所有结论的数学证明。
2. 前端类型和按钮禁用提升使用体验；真正接收请求时，后端仍要独立校验。
3. 数据库事务保护数据库写入；文件系统写入不是同一个事务。论文上传、删除等失败边界请看对应章节，不能泛称所有文件操作都有数据库级原子性。
4. 默认 CORS、Origin 与 Host 检查是本地使用约束，不是完整的多人认证系统。
5. 测试中的 fake provider 只验证程序行为，不表示已经调用真实外部模型。

下一章：[启动、配置、数据库与输入校验](01-core-database.md)。