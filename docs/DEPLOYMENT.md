# 在线演示部署

在线演示使用真实 FastAPI 后端、构建后的 React 前端与 SQLite。预置论文、实验和报告均为合成测试材料。公开演示为只读模式：可以阅读 PDF、检索证据、查看保存的统计与下载报告；上传、删除、修改配置和新建分析等写操作关闭。离线问答展示真实检索片段，不伪装成模型总结。

公开演示不读取本机 `.env`，不使用个人 `data/`，模型调用被关闭。完整的个人科研工作台继续通过根目录 README 的本地启动方式使用。

## 临时演示链接（本机保持开机）

本项目可以通过 Cloudflare Quick Tunnel 将独立的只读演示服务映射到临时 HTTPS 地址，不需要 Cloudflare 账号或自己的域名。链接在隧道停止后失效，每次创建会产生不同地址；适合面试或短时间分享，不承诺持续在线。[Quick Tunnels 官方说明](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

先按 README 完成依赖安装和前端构建，再使用官方 `cloudflared` 程序运行：

```powershell
.\scripts\demo-online.ps1 -Cloudflared 'C:\tools\cloudflared.exe'
```

`C:\tools\cloudflared.exe` 是示例文件位置，需要替换成实际下载路径。程序下载入口见 [Cloudflare 官方下载说明](https://developers.cloudflare.com/tunnel/downloads/)。

启动脚本会输出本次生成的 `https://…trycloudflare.com` 地址，并在后台保持独立演示服务与隧道进程运行。启动命令成功退出后，演示仍然在线。演示结束时执行以下专用停止脚本，它只管理该演示的进程，不会停止日常本地工作台：

```powershell
.\scripts\stop-demo-online.ps1
```

电脑关机、休眠或网络断开时，临时链接也无法访问。下次重新启动会生成新的地址。

临时服务仅监听 `127.0.0.1`，经隧道转发；演示 Host 与 Origin 使用本次生成的准确 HTTPS 地址。不要把原来的个人科研服务端口直接交给隧道。

## 启动参数与检查

`scripts/start_demo.py` 是只读演示入口。其参数来自环境变量：

| 环境变量 | 作用 |
| --- | --- |
| `PUBLIC_URL` | 演示的准确 HTTPS 来源，优先采用 |
| `RENDER_EXTERNAL_URL` | Render 自动注入的 HTTPS 来源，未设置 `PUBLIC_URL` 时采用 |
| `DEMO_PUBLIC_URL` | 其他启动器可提供的 HTTPS 来源，作为最后候选 |
| `DEMO_DATA_DIR` | 独立演示数据目录，默认位于系统临时目录 |
| `PORT` | HTTP 监听端口，默认 `10000` |
| `DEMO_BIND_HOST` | 默认 `0.0.0.0` 供容器使用，临时演示指定 `127.0.0.1` |

启动脚本忽略继承的个人 `DATA_DIR`，只使用独立的 `DEMO_DATA_DIR`；拒绝将演示目录设置为项目根目录或个人 `data/`。它不读取 `.env`，并清空模型地址、名称和密钥。

以下命令仅验证参数，不启动服务、不建立数据库：

```powershell
$env:PUBLIC_URL = 'https://demo.example.com'
$env:DEMO_DATA_DIR = Join-Path $PWD 'tmp\online-demo-check'
$env:DEMO_BIND_HOST = '127.0.0.1'
$env:PORT = '8010'
.\.venv\Scripts\python.exe scripts\start_demo.py --check
```

`demo.example.com` 是参数示例，不是已经部署的地址。实际启动需要准确的 HTTPS 来源，不允许账号、密码、路径、查询或片段；缺少来源时拒绝启动。运行时使用一个 Uvicorn worker，`WEB_CONCURRENCY` 不会把它变成多进程。

## 可选：部署到 Render（电脑关机后仍可访问）

仓库提供 `Dockerfile`、`.dockerignore` 与 `render.yaml`。Render 可从 GitHub 仓库构建镜像，由同一个 FastAPI 服务提供页面与 API。[Render Docker 文档](https://render.com/docs/docker)

1. 注册并登录 [Render](https://dashboard.render.com/)，连接有权访问本仓库的 GitHub 账号。
2. 打开 [部署入口](https://render.com/deploy?repo=https://github.com/laoxuaner/Research-Assistant)，或选择 **New → Blueprint**，再选中 `laoxuaner/Research-Assistant`。
3. 选择 `main` 分支和根目录的 `render.yaml`。默认服务名为 `research-assistant-demo`，如名称不可用可更改。
4. 确认实例方案为 **Free**。本配置不创建付费数据库、持久盘或其他服务，不需要填写模型密钥。
5. 等待构建、启动和健康检查通过。实际地址以 Render 控制台显示的 `https://…onrender.com` 为准；仅有配置文件不代表已经部署成功。

配置采用 `runtime: docker`、`plan: free`、`healthCheckPath: /api/health` 和一个实例。`main` 分支新提交会触发重新构建。[Blueprint 配置参考](https://render.com/docs/blueprint-spec)

Render 自动注入 `RENDER_EXTERNAL_URL`，不需要手工填写自己的推测地址。服务使用平台的 `PORT`，默认 `10000`。[默认环境变量](https://render.com/docs/environment-variables)

### 免费方案的限制

免费实例空闲时会休眠，再访问需要等待冷启动。其本地文件系统是临时的，重启、部署或休眠后会丢失运行时 SQLite 和文件；启动时会重新建立合成演示数据。免费实例不提供持久盘，另有计算时长、流量和构建额度。它适合演示，不保证持续在线或保存个人研究资料。

具体限制及可能的超额计费以 [Render 免费方案文档](https://render.com/docs/free) 和账号账单设置为准。创建服务时保持 Free，不要为了运行示例自动升级付费方案。

### 手动创建 Render Web Service 时的配置

| 配置 | 值 |
| --- | --- |
| Repository | `https://github.com/laoxuaner/Research-Assistant` |
| Branch | `main` |
| Language / Runtime | Docker |
| Dockerfile Path | `./Dockerfile` |
| Docker Build Context | `.` |
| Docker Command | 留空，采用镜像启动命令 |
| Instance Type | Free |
| Health Check Path | `/api/health` |
| `DEMO_DATA_DIR` | `/tmp/research-assistant-demo` |
| `PORT` | `10000` |

Docker 镜像仅复制应用、前端构建与合成材料，使用非 root 用户，包含中文导出所需的 Noto CJK 字体，并限制数值计算线程数量。环境中无需任何模型密钥。

## 部署后的核对

1. `/api/health` 返回 `status: ok`。
2. 页面显示“公开只读演示”，包含合成项目和预置分析。
3. 能打开 PDF、检索原文证据、查看保存的统计并下载示例报告。
4. 上传、编辑、删除和新建分析被禁用，直接调用相关 API 也返回只读提示。
5. `/api/settings` 返回 `deployment_mode: demo`、`read_only: true`，聊天与向量模型未配置。

实际公网服务是否可用，应以启动结果和以上访问核对为准。没有运行 Docker 构建时，不能把脚本或 YAML 检查表述为镜像已经构建成功。
