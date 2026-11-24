# 验收记录与复查步骤

日期：2026-10-28（Asia/Shanghai）。所有数据均为合成测试材料，不代表真实科研发现。

## 自动化与环境

验收环境：Windows、Python 3.12.14、Node.js 24.14.1、npm 11.11.0。

| 检查 | 本次结果 |
| --- | --- |
| 主虚拟环境依赖一致性 | `.venv/Scripts/python.exe -m pip check`：No broken requirements found |
| PowerShell 脚本 | common/setup/start/dev/test 全部通过 PowerShell AST 语法解析 |
| Python 辅助脚本 | generate_samples.py / verify_reproduction.py 通过 py_compile |
| 运行时探测 | 本机 py.exe 无已安装 Python 时容错；成功定位 bundled Python、系统 Node/npm |
| PDF 样例 | 2 个中英文 PDF 各 2 页；中文已知事实逐页提取断言通过，TrueType 字体子集已嵌入 |
| PDF 排版 | Poppler 渲染中英 4 页与扫描 1 页，逐页视觉检查无重叠、截断或缺字 |
| 扫描样例 | pypdf 提取无文本，作为 OCR 路径材料 |
| XLSX 样例 | 4 个工作表、表头、独立数据 10 行已读取验证 |
| 样例可重复生成 | 连续生成两次，全部 SHA-256 清单相同 |
| 实际 HTTP 服务 | GET /api/health 返回 ok；GET /api/settings 模型未配置且未启用 |
| 后端全部测试 | 61 passed，39.31s；包含存储提交失败不虚报成功的回归测试 |
| 前端生产构建 | TypeScript 与 Vite 生产构建通过；PDF.js 字体资源已本地打包 |
| Playwright 浏览器流程 | 10 passed，29.7s：7 项数值函数 + 3 项真实 Chromium 工作流 |
| 全新 venv 导出复现 | 通过；不继承系统包，仅安装导出 requirements，清空 PYTHONPATH 后成功 |
| 真实外部模型 | 未运行，缺少用户 API Key；不算通过 |

## 干净环境复现

使用 TestClient 创建隔离应用数据库，避免依赖正在运行的服务。脚本只导入合成数据，不会读取个人项目。

```powershell
.\.venv\Scripts\python.exe scripts/verify_reproduction.py
.\.venv\Scripts\python.exe -m venv tmp/repro-venv
.\tmp\repro-venv\Scripts\python.exe -m pip install -r tmp/repro-clean/requirements.txt
Push-Location tmp/repro-clean
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = ''
    & ../repro-venv/Scripts/python.exe reproduce.py
} finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
```

请使用全新目录；若示例路径已有上次验收数据，使用脚本 `--app-data tmp/repro-app-2 --output tmp/repro-clean-2` 及相应新 venv，不要混用上次包的配置。全新 venv 必须为 `include-system-site-packages = false`，只安装 ZIP 中的 requirements.txt，不能依赖主项目路径。

本次在 tmp/repro-venv 中实际运行成功，include-system-site-packages=false，安装前只有 pip。仅安装导出 requirements.txt 后，清空 PYTHONPATH，在解压目录运行 reproduce.py 得到：

```text
REPRODUCTION PASSED: input hash, analysis source, cleaning chain and saved results match.
```

该检查证明包内数据、代码、配置与保存的统计结果一致；不等于验证研究假设或论文结论。

## 验收矩阵

| 用户验收项 | 自动化证据 | 手动复查 |
| --- | --- | --- |
| 建项目、传论文、检索、打开引用页 | test_api 的真实 PDF 流程；浏览器用例 | 建立项目，上传 demo_paper_zh.pdf，搜“独立样本”，点证据跳转 PDF 第 1 页 |
| 模型回答与无证据不伪造 | test_providers 线协议；test_api 的有效/伪造引用测试桩 | 未配置时明确显示真实片段；配置真实模型后核对引用原文 |
| 项目隔离 | test_api 的 scope 测试 | 新建项目 B，不导入论文，不能搜到 A 的片段 |
| PDF 去重与删除索引 | test_api 的 dedupe/delete | 重复上传相同 PDF，不增加论文；删除后搜索不再命中 |
| OCR、损坏、中断、重试 | test_api 的 OCR/corrupt/retry、restart/interrupted、timeout | 上传 scanned_demo.pdf、corrupt_demo.pdf，检查不同状态和错误 |
| 已知统计参考 | test_stats 中 Welch、单侧、严格配对 | independent.csv：A 均值 3、B 均值 5、差 2、p≈0.0805162379573 |
| 缺失、无效、重复 ID、样本不足 | test_stats 多个边界和审计测试 | missing_values.csv 默认不推断；duplicate_pairs.csv 不产生虚假 p 值 |
| 导出与界面一致 | test_exports 与 test_api 全格式下载 | 比对 summary.csv、报告与图表中的 n/均值/区间 |
| 独立复现 | 原始链/XLSX/历史代码快照测试 + 干净 venv 实测 | 解压 ZIP，安装包内依赖，执行 reproduce.py |
| 重启与离线 | test_api 的 persist/restart 和 offline | 重启，已有论文/数据/报告仍存在；无 Key 可完成统计和导出 |

### 精确参考值

`samples/expected_results.json` 记录完整值。独立样本的样本标准差均为 sqrt(2.5)，Welch 自由度 8，差值 B-A 的双侧 95% CI 为 [-0.3060041352, 4.3060041352]。

配对样本共有 5 对，差值为 [1,2,1,3,2]，均值差 1.8，t≈4.8107023544，df=4，双侧 p≈0.0085809187，95% CI≈[0.7611493663,2.8388506337]。

无证据问题示例：“火星大气压的测量值是多少？”、“Europa orbital eccentricity value?”。这些问题不应产生论文中没有的指标或引用。不同检索模式可能召回词面相关片段，模型必须核对内容；后端引用校验仅验证来源字段与原文，不能证明语义结论。

## 尚需用户配置与已知限制

真实外部聊天/Embedding 服务尚未调用。需要用户填写 .env、重启、在设置启用，再验证服务模型名称、JSON 模式兼容性、请求超时和实际引用质量。测试桩验证的是接口契约和错误处理，不是模型科学准确性。

第一版只覆盖文本 PDF、CSV/XLSX、个人规模本地单用户、一个主要指标的两组推断。OCR、复杂表格/公式抽取、多组检验、重复测量模型、自动实验、团队权限等不在范围。分析单位、独立性与适用性需要研究者确认。

## 最终验证说明

- Python 命令：`.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`，61 项全部通过。一个 Starlette TestClient 对 httpx 的弃用提示不影响运行。
- 前端命令：`npm.cmd run build` 与 `npm.cmd run test:e2e`。生产构建和 10 项前端测试通过；隔离服务使用 8001/5173 与 tmp/e2e-*，不修改个人数据库。
- 首次使用系统旧 Edge 时测试框架不兼容，最终改用 Playwright 官方下载且版本匹配的 Chromium，完整流程已通过。
- 浏览器实际完成建项目、上传中英文 PDF、检索“均值差”、打开 PDF 第 2 页、离线问答、无证据回答、文献对比、上传 CSV、确认 Welch 配置、核对差值 2 / 每组 n=5 / p≈0.080516、切换图表、生成排版报告并下载真实 ZIP。
- 该流程收集的网络请求没有外部 CDN/字体请求；未配置聊天/向量服务，没有真实外部模型调用。
- 保存先提交数据库再返回成功；快速切换实验防止旧读取覆盖新记录；非零极小量用科学计数法；直方图不丢最大值。
- 最终预览见 [workbench-preview.png](workbench-preview.png)。

## 2026-11-24 在线演示补充验收

公开演示使用独立数据目录和合成材料，不读取本机 `.env`，关闭聊天及向量服务。精确校验公开 HTTPS Host/Origin；后端拒绝上传、修改、删除和新建分析，离线问答仅返回检索证据，不保存访客会话。默认本机工作台仍支持完整写入流程。

- 后端：原 API 17 项、新增公开演示 31 项、统计/模型适配/导出 44 项，共 **92 项通过**。覆盖独立目录保护、只读 API、精确域名、离线证据、重启幂等和报告导出。
- 前端：`npm.cmd run build` 通过。数值与原有工作流 **10 项通过**；只读演示 **1 项通过**，包含停滞 PDF 下载时关闭并确认 AbortSignal、重新打开及完整渲染第 2 页。
- 真实公网：通过实际 Cloudflare Quick Tunnel 地址执行 `playwright.public.config.ts`，**1 项通过**；未拦截或伪造 API。核对 HTTPS 页面、只读设置、拒绝写入、PDF 实际完成渲染、离线引用、保存统计、三张报告图与 ZIP 下载，浏览器 `pageerror` 为空。
- 修复首次公网检查暴露的 PDF Worker 提前终止错误；复测通过。PDF 下载有 45 秒超时并可取消，初始化/渲染收尾后统一销毁资源；测试等待真实渲染完成标记，不以 Canvas 默认尺寸判断成功。
- Windows 临时演示脚本：语法解析、实际启动、状态查询、重复启动、停止及重启均通过。以进程 ID、启动时间、可执行路径和参数核验身份后，仅停止演示进程；保留本机资料和演示目录。
- `cloudflared` 使用官方 2026.10.7 Windows amd64 便携版，SHA-256 与该版本官方发布页面一致。程序与会话记录位于忽略的 `tmp/`，未提交到 Git。
- Docker/Render 配置已做 YAML 和启动参数检查，**本机没有 Docker，未运行镜像构建或 Render 发布**。本次按用户选择使用临时链接；电脑关机、休眠、断网或停止隧道后不可访问，重建时地址改变。

公网测试命令（替换为启动脚本实际输出的 URL）：

```powershell
$env:PUBLIC_DEMO_URL = 'https://your-current-url.trycloudflare.com'
Push-Location frontend
npx.cmd playwright test --config=playwright.public.config.ts
Pop-Location
```

真实模型服务仍未配置，本次公网演示不包含外部模型调用验收。
