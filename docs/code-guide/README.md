# 研知：完整源码图解与逐文件解读

适合先阅读过使用指南、准备开始学习代码的读者。讲解按实际源码编写，节选处明确标注；完整原代码在附录中展示。

本阅读器与源码附录保留初版交付快照。2026-11-24 新增的在线演示、公开访问限制和 PDF 清理改动，请以仓库当前源码及[部署说明](../DEPLOYMENT.md)为准；附录中的文件指纹对应快照版本。

本次收录 60 个文件，共 16,737 行；其中自有代码与配置 52 个文件、11,498 行，另外包含依赖锁文件和文本测试材料。

## 阅读入口

- [离线源码阅读器](code-reader.html)：用浏览器打开，可切换文件、按文件名或源码内容筛选、跳到函数/行号、复制完整代码。无需启动服务或联网。
- [完整源码合订本](ALL_SOURCE.md)：所有收录文件的完整文本。
- [覆盖清单与源码指纹](manifest.json)：文件、行数、函数/类型定位和 SHA-256。

## 按学习顺序阅读

1. [先读：语法、目录与完整调用路线](00-start-here.md)
2. [启动、配置、数据库与输入校验](01-core-database.md)
3. [论文、检索、AI 与引用](02-papers-ai.md)
4. [全部前端、组件、状态与样式](03-frontend.md)
5. [数据版本、统计与报告复现](04-statistics-exports.md)
6. [全部测试、启动脚本与示例生成](05-tests-scripts.md)

建议每次只读一个章节：先看它解决的问题，再看代码，最后顺着函数调用找到下一层。文档只补充讲解，不改变应用行为。

## 范围说明

项目自有源码、测试、脚本、配置及文本测试材料；排除第三方依赖、PDF.js字体/字符表、缓存、构建产物、真实.env与用户data。
依赖锁文件解释整体作用并保留全文，不逐条讲解第三方软件包内部实现。已有 README 与验收文档是说明材料，原始 PDF/XLSX 是二进制样例，均可在项目目录查看。
源码附录是生成时快照。以后修改应用后，运行构建脚本即可刷新；讲解中的行号也应随之复核。

## 所有文件与完整代码

| 文件 | 类别 | 行数 | 完整代码 |
| --- | --- | ---: | --- |
| .env.example | 配置 | 24 | [展开](source/01.md) |
| .gitignore | 配置 | 12 | [展开](source/02.md) |
| backend/app/__init__.py | 后端 | 0 | [展开](source/03.md) |
| backend/app/api_core.py | 后端 | 224 | [展开](source/04.md) |
| backend/app/api_experiments.py | 后端 | 245 | [展开](source/05.md) |
| backend/app/config.py | 后端 | 31 | [展开](source/06.md) |
| backend/app/db.py | 后端 | 33 | [展开](source/07.md) |
| backend/app/demo.py | 后端 | 67 | [展开](source/08.md) |
| backend/app/deps.py | 后端 | 23 | [展开](source/09.md) |
| backend/app/exports.py | 后端 | 353 | [展开](source/10.md) |
| backend/app/main.py | 后端 | 68 | [展开](source/11.md) |
| backend/app/migrations.py | 后端 | 13 | [展开](source/12.md) |
| backend/app/models.py | 后端 | 157 | [展开](source/13.md) |
| backend/app/papers.py | 后端 | 119 | [展开](source/14.md) |
| backend/app/parse_pdf.py | 后端 | 29 | [展开](source/15.md) |
| backend/app/providers.py | 后端 | 76 | [展开](source/16.md) |
| backend/app/research.py | 后端 | 184 | [展开](source/17.md) |
| backend/app/schemas.py | 后端 | 76 | [展开](source/18.md) |
| backend/app/stats_engine.py | 后端 | 386 | [展开](source/19.md) |
| backend/tests/test_api.py | 测试 | 308 | [展开](source/20.md) |
| backend/tests/test_exports.py | 测试 | 218 | [展开](source/21.md) |
| backend/tests/test_providers.py | 测试 | 64 | [展开](source/22.md) |
| backend/tests/test_stats.py | 测试 | 249 | [展开](source/23.md) |
| docs/code-guide/build_code_book.py | 教学工具 | 247 | [展开](source/24.md) |
| docs/guide-example-statistics.py | 教学工具 | 131 | [展开](source/25.md) |
| frontend/copy-pdf-assets.mjs | 配置 | 10 | [展开](source/26.md) |
| frontend/index.html | 配置 | 13 | [展开](source/27.md) |
| frontend/package-lock.json | 依赖锁文件 | 5031 | [展开](source/28.md) |
| frontend/package.json | 配置 | 37 | [展开](source/29.md) |
| frontend/playwright.config.ts | 配置 | 48 | [展开](source/30.md) |
| frontend/postcss.config.js | 配置 | 1 | [展开](source/31.md) |
| frontend/src/App.tsx | 前端 | 2043 | [展开](source/32.md) |
| frontend/src/Experiments.tsx | 前端 | 1489 | [展开](source/33.md) |
| frontend/src/api.ts | 前端 | 186 | [展开](source/34.md) |
| frontend/src/components.tsx | 前端 | 653 | [展开](source/35.md) |
| frontend/src/main.tsx | 前端 | 9 | [展开](source/36.md) |
| frontend/src/numeric.ts | 前端 | 112 | [展开](source/37.md) |
| frontend/src/styles.css | 前端 | 2665 | [展开](source/38.md) |
| frontend/src/vite-env.d.ts | 前端 | 1 | [展开](source/39.md) |
| frontend/tailwind.config.js | 配置 | 5 | [展开](source/40.md) |
| frontend/tests/numeric.spec.ts | 测试 | 107 | [展开](source/41.md) |
| frontend/tests/workbench.spec.ts | 测试 | 209 | [展开](source/42.md) |
| frontend/tsconfig.json | 配置 | 17 | [展开](source/43.md) |
| frontend/vite.config.ts | 配置 | 11 | [展开](source/44.md) |
| pyproject.toml | 配置 | 10 | [展开](source/45.md) |
| requirements.lock.txt | 依赖锁文件 | 50 | [展开](source/46.md) |
| requirements.txt | 配置 | 2 | [展开](source/47.md) |
| samples/duplicate_pairs.csv | 测试数据 | 12 | [展开](source/48.md) |
| samples/expected_results.json | 测试数据 | 105 | [展开](source/49.md) |
| samples/independent.csv | 测试数据 | 11 | [展开](source/50.md) |
| samples/missing_values.csv | 测试数据 | 9 | [展开](source/51.md) |
| samples/paired.csv | 测试数据 | 11 | [展开](source/52.md) |
| samples/unmatched_pairs.csv | 测试数据 | 10 | [展开](source/53.md) |
| scripts/common.ps1 | 脚本 | 65 | [展开](source/54.md) |
| scripts/dev.ps1 | 脚本 | 33 | [展开](source/55.md) |
| scripts/generate_samples.py | 脚本 | 285 | [展开](source/56.md) |
| scripts/setup.ps1 | 脚本 | 43 | [展开](source/57.md) |
| scripts/start.ps1 | 脚本 | 13 | [展开](source/58.md) |
| scripts/test.ps1 | 脚本 | 25 | [展开](source/59.md) |
| scripts/verify_reproduction.py | 脚本 | 69 | [展开](source/60.md) |
