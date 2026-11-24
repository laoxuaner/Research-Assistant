# 03 · 前端代码逐文件解读：网页如何把操作交给后端

本章面对第一次读 React / TypeScript 的读者。下面的代码块都从当前文件按标注行号直接摘取；注明“摘录”的代码块只展示该段，不把省略部分冒充完整文件。完整逐行源码另见 [源码总览](./ALL_SOURCE.md)。应用代码没有因本章讲解而修改。

**本章范围：15 个文件，共 7,252 行。** 包括 8 个 src 源文件以及 7 个入口、构建配置文件；不把 node_modules、生成的 dist 或第三方 PDF.js 资源算作自己编写的代码。行号对应本次阅读的文件快照。

## 导航

1. [先理解几个基础词](#先理解几个基础词)
2. [启动入口与构建配置](#启动入口与构建配置)
3. [api.ts：前后端共同说什么话](#apits前后端共同说什么话)
4. [numeric.ts：数字怎样正确显示](#numericts数字怎样正确显示)
5. [components.tsx：可以重复使用的界面积木](#componentstsx可以重复使用的界面积木)
6. [App.tsx：项目、论文、问答、报告和设置](#apptsx项目论文问答报告和设置)
7. [Experiments.tsx：导入、确认设计、展示分析](#experimentstsx导入确认设计展示分析)
8. [styles.css：所有样式区域](#stylescss所有样式区域)
9. [把一次点击连成完整调用链](#把一次点击连成完整调用链)
10. [阅读本章时需要记住的边界](#阅读本章时需要记住的边界)

## 先理解几个基础词

| 词 | 可以怎样理解 | 本项目例子 |
|---|---|---|
| HTML | 告诉浏览器页面有哪些元素 | 输入框、按钮、表格 |
| CSS | 告诉浏览器元素怎样排列和着色 | 左侧导航宽度、按钮颜色 |
| JavaScript | 处理点击、请求、数据变化 | 点击上传后提交文件 |
| TypeScript | 在 JavaScript 上增加开发期类型检查 | 约定论文一定有 id、title |
| JSX / TSX | 在代码中写类似 HTML 的界面结构 | return 里面的 div、Reader |
| 组件 | 可以反复使用的一块界面，本质上是函数 | Field、Modal、Reader |
| props | 父组件交给子组件的输入 | projectId、onClose |
| state | React 记住的、变化后需要更新页面的数据 | 当前页码 page、是否 busy |
| hook | 在函数组件中使用 React 能力的函数 | useState、useEffect |
| 回调 | 把“事情发生后要做什么”作为函数传进去 | onSaved、onCite |
| 异步 / Promise | 请求要等一会儿，期间网页仍可响应 | await api(...) |
| JSON | 前后端传递结构化数据的文本格式 | 分析配置对象 |
| FormData | 浏览器上传文件时用的容器 | 把多份 PDF 放入 files |
| API | 前端向后端请求工作的约定入口 | /api/projects/.../papers |
| ref | 跨渲染保留一个值，但更改它不直接刷新界面 | canvas、请求序号 |

读 React 的一个重要顺序是：**props 输入 → state 记录 → 事件修改 state / 发请求 → return 按新 state 画界面。** return 不是执行统计的地方，它主要描述应该显示什么。

~~~mermaid
flowchart TD
    A["index.html：提供 root 容器"] --> B["main.tsx：启动 React"]
    B --> C["App：保存当前项目和页面"]
    C --> D["Library / Chat / Reports 等页面"]
    C --> E["Experiments：实验工作流"]
    D --> F["api.ts：HTTP 请求包装"]
    E --> F
    F --> G["FastAPI 后端：校验、持久化、检索、统计"]
    G --> F
    F --> H["setState：保存返回结果"]
    H --> I["React 重新绘制组件"]
~~~

## 启动入口与构建配置

### 1. frontend/index.html · 13 行

源文件：[index.html](../../frontend/index.html)。

这是浏览器最初取得的 HTML 外壳。第 2 行的 zh-CN 告诉浏览器和辅助阅读工具页面语言；第 4 行 UTF-8 保证中文正常；第 5 行让小屏按设备宽度排版；第 6 行是浏览器界面可采用的主题色；第 7 行是标签页标题。第 10 行的 root 是空容器，稍后 React 把整个应用放进去。第 11 行引入真正入口，type="module" 允许使用 import / export。


**真实代码（完整文件）：frontend/index.html 第 1—13 行**

~~~html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="theme-color" content="#132a2e" />
    <title>研知 · 科研工作台</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
~~~


### 2. frontend/src/main.tsx · 9 行

源文件：[main.tsx](../../frontend/src/main.tsx)。

四个 import 分别取得 React、DOM 渲染器、根组件 App 和全局 CSS。createRoot 找到上面的 root 容器，render 开始显示 App。感叹号是 TypeScript 的“这里确定不是 null”断言，不是页面上的标点。

StrictMode 会在开发环境额外检查组件的副作用清理等问题；它不是用户看到的页面模块。不要把“组件函数被再次调用”误以为资料就一定应该再次写入数据库：真正的写操作放在明确点击触发的事件函数中。


**真实代码（完整文件）：frontend/src/main.tsx 第 1—9 行**

~~~tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
~~~


### 3. frontend/src/vite-env.d.ts · 1 行

源文件：[vite-env.d.ts](../../frontend/src/vite-env.d.ts)。

这是**类型声明引用**，不是运行程序。它让 TypeScript 认识 Vite 提供的类型，例如 PDF worker 导入路径最后的 ?url。d.ts 主要帮助编辑器和编译器理解代码。


**真实代码（完整文件）：frontend/src/vite-env.d.ts 第 1—1 行**

~~~ts
/// <reference types="vite/client" />
~~~


### 4. frontend/package.json · 37 行

源文件：[package.json](../../frontend/package.json)。

第 2—5 行是包名、版本、禁止意外发布到 npm，以及使用 ES module 的约定。第 6—14 行是 npm 命令；第 15—23 行是应用运行依赖，第 24—36 行是开发工具依赖。


**真实代码（完整文件）：frontend/package.json 第 1—37 行**

~~~json
{
  "name": "research-workbench",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc -b && vite build",
    "preview": "vite preview --host 127.0.0.1",
    "test:e2e": "playwright test",
    "predev": "node copy-pdf-assets.mjs",
    "prebuild": "node copy-pdf-assets.mjs",
    "format": "prettier --write src tests *.ts *.js *.mjs *.json index.html"
  },
  "dependencies": {
    "lucide-react": "^0.468.0",
    "pdfjs-dist": "4.10.38",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-markdown": "^10.1.0",
    "recharts": "^2.15.0",
    "remark-gfm": "^4.0.1"
  },
  "devDependencies": {
    "@playwright/test": "^1.50.0",
    "@types/node": "^22.10.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.5.1",
    "prettier": "^3.9.10",
    "tailwindcss": "^3.4.17",
    "typescript": "~5.7.2",
    "vite": "^6.1.0"
  }
}
~~~


命令逐项解释：

| 命令 | 实际做的事 |
|---|---|
| dev | 启动 Vite 开发服务器，监听本机 |
| predev | npm 自动在 dev 前执行，把 PDF 字体等资源复制到 public |
| build | 先 tsc -b 检查 TypeScript，再由 Vite 打包生产文件 |
| prebuild | npm 自动在 build 前执行同样的 PDF 资源准备 |
| preview | 本机预览已打包文件；日常正式启动由 FastAPI 提供 dist |
| test:e2e | 调用 Playwright 测试；测试代码由测试章节讲解 |
| format | Prettier 格式化源文件；它会改文件排版 |

运行依赖的角色：React / react-dom 绘制界面；lucide-react 是图标；pdfjs-dist 阅读 PDF；recharts 画交互图；react-markdown 与 remark-gfm 负责报告排版。开发依赖包含 TypeScript、Vite、Tailwind、PostCSS、自动加 CSS 前缀的 autoprefixer、Playwright 与 Prettier。

package.json 中带 ^ / ~ 的版本是允许范围；实际安装的精确版本由 package-lock.json 固定，通常用 npm ci 按锁文件安装。不要把版本范围当成这次已经安装的精确版本号。

### 5. frontend/vite.config.ts · 11 行

源文件：[vite.config.ts](../../frontend/vite.config.ts)。

defineConfig 提供配置类型提示，react() 让 Vite 处理 React / TSX。开发页面监听 127.0.0.1:5173；网页请求 /api 时，开发代理转发到 WORKBENCH_API_URL 指定的服务，未指定就转发到 127.0.0.1:8000。因此应用代码不用到处写两个端口。生产输出目录是 dist。


**真实代码（完整文件）：frontend/vite.config.ts 第 1—11 行**

~~~ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": process.env.WORKBENCH_API_URL || "http://127.0.0.1:8000" },
  },
  build: { outDir: "dist" },
});
~~~


注意：这里的 proxy 是**开发服务器**的配置。生产启动由后端同时提供 API 和打包后的前端，浏览器使用同一来源。

### 6. frontend/tsconfig.json · 17 行

源文件：[tsconfig.json](../../frontend/tsconfig.json)。


**真实代码（完整文件）：frontend/tsconfig.json 第 1—17 行**

~~~json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "Bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
~~~


| 配置 | 对读代码的影响 |
|---|---|
| target: ES2022 | 以较新的 JavaScript 能力为目标 |
| lib | 认识 ES2022、浏览器 DOM 及可迭代 DOM 类型 |
| module: ESNext | 保留 import / export 模块结构，由打包器处理 |
| moduleResolution: Bundler | 按打包器的方式寻找被导入模块 |
| jsx: react-jsx | 使用现代 React JSX 转换 |
| strict: true | 开启严格类型检查，尽早发现空值、错误类型 |
| noEmit: true | tsc 只检查，真正输出文件交给 Vite |
| skipLibCheck | 跳过第三方声明文件的全面内部检查 |
| isolatedModules | 要求各模块能独立转换 |
| resolveJsonModule | 允许有类型地导入 JSON |
| allowImportingTsExtensions | 允许带 TypeScript 扩展名的导入 |
| useDefineForClassFields | 采用相应的类字段语义；本项目主要写函数组件 |
| include: src | 此配置检查 src 里的源码 |

### 7. Tailwind 与 PostCSS 两个配置

源文件：[tailwind.config.js](../../frontend/tailwind.config.js)、[postcss.config.js](../../frontend/postcss.config.js)。


**真实代码（完整文件）：frontend/tailwind.config.js 第 1—5 行**

~~~js
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
~~~


**真实代码（完整文件）：frontend/postcss.config.js 第 1—1 行**

~~~js
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
~~~


Tailwind 的 content 规定扫描哪些 HTML / TSX 文件来确定要生成的工具类；theme.extend 与 plugins 都为空，表示暂未添加 Tailwind 自定义主题或插件。PostCSS 依次启用 Tailwind 和 autoprefixer。

虽然项目接入 Tailwind，当前界面的大量外观仍由 styles.css 中的语义类名实现，例如 sidebar、card、evidence。不能看见 Tailwind 依赖就假设每个样式都写成工具类。

### 8. frontend/copy-pdf-assets.mjs · 10 行

源文件：[copy-pdf-assets.mjs](../../frontend/copy-pdf-assets.mjs)。


**真实代码（完整文件）：frontend/copy-pdf-assets.mjs 第 1—10 行**

~~~js
import { cp, mkdir } from "node:fs/promises";
await mkdir(new URL("./public/pdfjs/", import.meta.url), { recursive: true });
for (const name of ["cmaps", "standard_fonts"]) {
  await cp(
    new URL("./node_modules/pdfjs-dist/" + name, import.meta.url),
    new URL("./public/pdfjs/" + name, import.meta.url),
    { recursive: true },
  );
}
console.log("Local PDF.js assets ready");
~~~


这个脚本在 Node.js 中执行，输入是安装在 node_modules 的 PDF.js 资源，输出是 public/pdfjs 下的 cmaps 与 standard_fonts。mkdir 的 recursive 允许父目录不存在；cp 的 recursive 复制整个目录。new URL(..., import.meta.url) 以脚本所在位置解析路径，避免从不同工作目录运行时找错地方。

cmap 可以理解为 PDF 字符与文字编码的对应资料；标准字体是阅读某些 PDF 所需的字体数据。本地复制后，阅读器通过本地 URL 获取这些资源，离线时也不依赖字体 CDN。worker 文件则另由 Vite 的 ?url 导入打包。


## api.ts：前后端共同说什么话

源文件：[api.ts](../../frontend/src/api.ts)，186 行。

这个文件包含两类东西：**类型约定**和**真正发请求的函数**。前者在编译后会被移除；后者会在浏览器运行。

### 1. 第 1—147 行：全部数据类型

| 类型及行号 | 输入 / 字段含义 | 谁使用 |
|---|---|---|
| Project，2—10 | id、名称、问题、假设、标签、备注、归档状态 | App、ProjectForm、Overview |
| Paper，11—27 | 论文元信息、解析状态、文件大小、页数，以及可选逐页文本 | Library、Reader、Scope |
| Citation，28—35 | 论文 ID、片段 ID、标题、PDF 页码、原文摘录、可选分数 | 搜索、问答、阅读卡、证据面板 |
| Job，36—43 | 工作类型、持久化状态、错误、资源 ID、创建时间 | 首页任务 |
| Settings，44—53 | 两种模型是否配置、是否启用、模型名、服务地址、资源上限 | 顶栏、问答提示、设置 |
| Dataset，54—67 | 数据版本 ID、原文件名、哈希、父版本、工作表、列、预览、质量和处理记录 | 实验导入与清洗 |
| AnalysisConfig，68—82 | 分组列、主要指标、A/B 组、设计、单位、缺失策略、检验方向、确认状态 | 分析表单 |
| Result，83—109 | 描述统计、比较结果、有效点、警告、排除记录、配置 | 结果卡与图表 |
| Analysis，110—116 | 保存的一次结果与配置，以及绑定的数据版本 ID | 历史分析、报告 |
| Experiment，117—128 | 实验信息，可选的版本列表与分析列表 | 实验主页面 |
| Report，129—135 | 标题、绑定的分析、Markdown、时间 | 报告页面 |
| Message，136—141 | 发言角色、内容、引用、回答模式 | 对话消息 |
| Conversation，142 | 对话 ID、可选标题、消息列表 | 历史对话 |
| ReadingField，143—147 | 阅读卡一个栏目：名称、正文、引用 | 阅读卡和文献对比 |

看看 Citation 为什么能支持“点一下回原文”：


**真实代码（摘录）：frontend/src/api.ts 第 28—35 行**

~~~ts
export type Citation = {
  paper_id: string;
  chunk_id: string;
  title: string;
  page_number: number;
  quote: string;
  score?: number;
};
~~~


paper_id 决定打开哪篇；page_number 决定打开哪页；chunk_id 和 quote 用来核对这条引用来自哪里。score 是可选的检索分数，不是结论正确率。

分析配置中的联合类型，把可选值限制为几个合法字符串。问号表示字段可选，number | null 表示可以是数字或明确的空值：


**真实代码（摘录）：frontend/src/api.ts 第 68—116 行**

~~~ts
export type AnalysisConfig = {
  group_column: string;
  metric_column: string;
  group_a: string;
  group_b: string;
  design: "descriptive" | "independent" | "paired";
  experimental_unit: string;
  missing_policy: "error" | "drop";
  alternative: "two-sided" | "less" | "greater";
  pair_column?: string;
  sample_id_column?: string;
  unit: string;
  direction: "higher" | "lower";
  confirmed: boolean;
};
export type Result = {
  summary: {
    group: string;
    n: number;
    mean: number | null;
    median: number | null;
    std: number | null;
    min: number | null;
    max: number | null;
  }[];
  comparison: {
    difference?: number | null;
    relative_change_percent?: number | null;
    ci_low?: number | null;
    ci_high?: number | null;
    pvalue?: number | null;
    statistic?: number | null;
    df?: number | null;
    method?: string;
    status?: string;
    reason?: string;
  };
  points: { group: string; value: number; pair_id?: string }[];
  warnings: string[];
  exclusions: unknown[];
  config: AnalysisConfig;
};
export type Analysis = {
  id: string;
  result: Result;
  config: AnalysisConfig;
  dataset_id: string;
  created_at: string;
};
~~~


这里把比较结果设为可选 / 可为空，正是为了让“无法运行推断分析”的情况能够解释原因，而不是硬塞一个 NaN 到页面。

**类型检查只帮助开发者提前发现错写。** 浏览器拿到的 JSON 仍需要后端校验；api<Analysis> 并不会自动对每一个返回字段做运行时验证。

### 2. 第 148—157 行：通用显示函数

fmt 只是给 numeric.ts 的 formatNumber 换一个简短名字，各页面显示数字都复用它。date 接受时间字符串，转成中文月、日、时、分；空字符串返回破折号。


**真实代码（摘录）：frontend/src/api.ts 第 148—157 行**

~~~ts
export const fmt = formatNumber;
export const date = (v: string) =>
  v
    ? new Date(v).toLocaleString("zh-CN", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
~~~


new Date 会按浏览器时区显示时间；它不是数据库写入时间的实现。

### 3. 第 158—182 行：api<T> 请求包装器


**真实代码（摘录）：frontend/src/api.ts 第 158—186 行**

~~~ts
export async function api<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api" + path, {
    ...options,
    headers:
      options.body instanceof FormData
        ? options.headers
        : { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = await response.json();
      message =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail || body);
    } catch {}
    throw new Error(message || "请求失败");
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
export const json = (data: unknown): RequestInit => ({
  method: "POST",
  body: JSON.stringify(data),
});
~~~


按执行顺序解释：

1. 调用者传入 path 和可选 RequestInit；泛型 T 表示调用者预期拿到的数据形状。
2. 自动给 path 加 /api。
3. 如果 body 是 FormData，不自行指定 Content-Type。浏览器必须自己填写 multipart boundary，否则文件上传容易损坏。
4. 普通请求使用 application/json。
5. HTTP 不是 2xx 时，优先读取 FastAPI 返回的 detail；把它变成 Error，让页面 catch 并显示。
6. 204 表示成功但没有正文，直接返回 undefined，避免强行 JSON 解析失败。
7. 其余成功响应按 JSON 解析。
8. json(data) 返回 POST 和 JSON 字符串，减少重复代码。PATCH、DELETE 需要调用者明确传 method。

这个包装器没有设置统一 AbortController、请求超时或自动重试；不要把后端模型调用的有限重试误认为每个前端请求都有同样策略。

## numeric.ts：数字怎样正确显示

源文件：[numeric.ts](../../frontend/src/numeric.ts)，112 行。这里不计算 t 检验，它负责**数值展示和图形分箱**。

### 1. formatNumber · 第 2—21 行

输入：任意值，以及默认 4 位的小数精度上限。输出：显示用字符串。


**真实代码（摘录）：frontend/src/numeric.ts 第 2—21 行**

~~~ts
export function formatNumber(value: unknown, digits = 4): string {
  if (value == null) return "—";
  if (typeof value !== "number") return String(value);
  if (!Number.isFinite(value)) return "—";
  if (value === 0) return "0";

  const precision = Number.isFinite(digits)
    ? Math.max(0, Math.min(12, Math.trunc(digits)))
    : 4;
  const magnitude = Math.abs(value);
  // Never turn a nonzero scientific measurement or p value into a displayed zero.
  if (magnitude < 10 ** -precision || magnitude >= 1e9) {
    const [mantissa, exponent] = value
      .toExponential(Math.max(0, precision - 1))
      .split("e");
    const power = Number(exponent);
    return String(Number(mantissa)) + "e" + (power >= 0 ? "+" : "") + power;
  }
  return value.toLocaleString("zh-CN", { maximumFractionDigits: precision });
}
~~~


分支分别处理：

- null / undefined：显示“—”，表示没有值。
- 非数字，例如组名 A：原样转字符串。
- Infinity / NaN：显示“—”，避免把无效数字当成科研结果。
- 真正的 0：显示“0”。
- digits 限定在 0—12，并取整数。
- 太小但不等于零，或绝对值至少十亿：改成科学记数法。
- 其余数字按中文区域格式显示，最多保留指定小数位。

为什么小数要特别处理？例如 0.00000012 如果只保留四位小数，会看成 0。这里用 1.2e-7，保留“它不是零”的事实。科学记数法的 e-7 表示乘以 10 的负 7 次方。

### 2. HistogramBin / Histogram · 第 23—38 行

HistogramBin 保存一个区间：索引、左右边界、频数和显示标签。Histogram 保存整个分布：极值、有效总数、所有箱，以及**每个原数据点落在哪个箱**。binIndices 为 -1 表示非有限数被排除。


**真实代码（摘录）：frontend/src/numeric.ts 第 23—38 行**

~~~ts
export type HistogramBin = {
  index: number;
  lo: number;
  hi: number;
  count: number;
  range: string;
};

export type Histogram = {
  min: number | null;
  max: number | null;
  total: number;
  bins: HistogramBin[];
  /** One entry per original value; -1 marks an excluded nonfinite value. */
  binIndices: number[];
};
~~~


### 3. makeHistogram · 第 40—112 行

输入：数值数组、箱数。输出：上面的 Histogram。

先校验 count 必须是 1—1000 的整数。循环扫描极值和有效数，避免把一个巨大数组展开成 Math.min(...values) 导致参数栈问题。没有有效值时返回空箱和 null 极值。


**真实代码（摘录）：frontend/src/numeric.ts 第 45—76 行**

~~~ts
export function makeHistogram(values: number[], count: number): Histogram {
  if (!Number.isInteger(count) || count < 1 || count > 1000) {
    throw new RangeError(
      "Histogram bin count must be an integer from 1 to 1000.",
    );
  }
  let min = Infinity;
  let max = -Infinity;
  let total = 0;
  for (const value of values) {
    if (!Number.isFinite(value)) continue;
    if (value < min) min = value;
    if (value > max) max = value;
    total++;
  }
  const binIndices = Array<number>(values.length).fill(-1);
  if (!total) return { min: null, max: null, total: 0, bins: [], binIndices };

  const binCount = min === max ? 1 : count;
  const span = max - min;
  const scale = Math.max(Math.abs(min), Math.abs(max)) || 1;
  const scaledMin = min / scale;
  const scaledSpan = max / scale - scaledMin;
  const boundary = (index: number): number => {
    if (index === 0) return min;
    if (index === binCount) return max;
    const fraction = index / binCount;
    // Convex interpolation also works when max - min overflows to Infinity.
    return Number.isFinite(span)
      ? min + span * fraction
      : min * (1 - fraction) + max * fraction;
  };
~~~


min === max 时只生成一个箱；否则生成指定数量的等宽箱。boundary 用插值求边界，在 max−min 溢出成 Infinity 时改用凸组合，尽量保持极端数值可处理。

第 77—87 行为每个箱创建 lo、hi、count=0 和格式化标签。随后按位置为数据分配箱，最后一箱明确接纳最大值，避免浮点误差漏掉最右边的观测：


**真实代码（摘录）：frontend/src/numeric.ts 第 89—112 行**

~~~ts
  for (let position = 0; position < values.length; position++) {
    const value = values[position];
    if (!Number.isFinite(value)) continue;
    let index = 0;
    if (binCount > 1) {
      if (value === max) {
        // Include max even when floating arithmetic puts the last edge just below it.
        index = binCount - 1;
      } else if (value !== min) {
        const fraction =
          Number.isFinite(span) && span > 0
            ? (value - min) / span
            : (value / scale - scaledMin) / scaledSpan;
        index = Math.max(
          0,
          Math.min(binCount - 1, Math.floor(fraction * binCount)),
        );
      }
    }
    bins[index].count++;
    binIndices[position] = index;
  }
  return { min, max, total, bins, binIndices };
}
~~~


内部区间相当于 [左端, 右端)，最后一箱包含最大值。分类依据原始数字算出的索引，不用已经四舍五入的显示标签来判断。返回的 binIndices 让 Experiments.tsx 在同一组公共箱内分别统计 A/B，避免两个组各用不同区间导致误读。

## components.tsx：可以重复使用的界面积木

源文件：[components.tsx](../../frontend/src/components.tsx)，653 行。它被 App.tsx 和 Experiments.tsx 共同调用。

### 1. 导入、worker 与 statusLabel · 第 1—45 行

React 导入中，Children / cloneElement 用于给表单子元素补无障碍属性；Fragment 是不额外产生 DOM 的包装；useId 生成标签 ID；useRef 记住 DOM 或 PDF 对象。lucide-react 提供图标。


**真实代码（摘录）：frontend/src/components.tsx 第 24—45 行**

~~~ts
import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import {
  api,
  json,
  type Paper,
  type Citation,
  type ReadingField,
  fmt,
} from "./api";
pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
export const statusLabel: Record<string, string> = {
  queued: "排队中",
  running: "处理中",
  completed: "已就绪",
  failed: "处理失败",
  interrupted: "已中断",
  needs_ocr: "需要 OCR",
  unread: "未读",
  reading: "阅读中",
  read: "已读",
};
~~~


worker 是浏览器的后台执行线程，PDF 解析交给 PDF.js 的 worker，减轻页面主线程负担。?url 由 Vite 转为打包资源 URL，workerSrc 告诉 PDF.js 去哪里取代码。

statusLabel 是状态翻译表，不是任务状态机本身；真正任务状态保存在后端。阅读状态也复用这张字典。

### 2. Badge、Empty、Spinner、Alert · 第 46—91 行

| 组件 | 输入 | 输出和使用处 |
|---|---|---|
| Badge，46—54 | children、可选 tone | 小标签；用于数量、解析状态、模式 |
| Empty，55—74 | title、说明 children、可选 action | 无资料时的提示与真实操作入口 |
| Spinner，75—82 | 可选 label | 转动图标和说明；不虚构进度百分比 |
| Alert，83—91 | children、可选 tone | 普通、警告、错误提示框 |

它们都是“输入决定显示”的小函数，没有额外业务请求。例如：


**真实代码（摘录）：frontend/src/components.tsx 第 46—54 行**

~~~tsx
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={"badge " + tone}>{children}</span>;
}
~~~


**真实代码（摘录）：frontend/src/components.tsx 第 75—91 行**

~~~tsx
export function Spinner({ label = "正在加载…" }: { label?: string }) {
  return (
    <div className="loading">
      <LoaderCircle className="spin" size={18} />
      {label}
    </div>
  );
}
export function Alert({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <div className={"alert " + tone}>{children}</div>;
}
~~~


children 指组件标签包住的内容，tone 最终变成 CSS 类名。默认参数保证调用时不填也能显示。

### 3. Field 及内部 nameControls · 第 92—133 行

Field 把“字段名称、输入控件、提示文字”统一排好。useId 产生稳定的唯一 ID。nameControls 遍历 children，只对 input / select / textarea 自动补标签关联；已有 aria-label 或 aria-labelledby 的控件保留自己的名称；遇到 Fragment 则递归处理里面的控件。


**真实代码（摘录）：frontend/src/components.tsx 第 101—132 行**

~~~tsx
  const id = useId();
  const nameControls = (nodes: ReactNode): ReactNode =>
    Children.map(nodes, (child) => {
      if (!isValidElement(child)) return child;
      const element = child as ReactElement<{
        children?: ReactNode;
        "aria-label"?: string;
        "aria-labelledby"?: string;
        "aria-describedby"?: string;
      }>;
      if (
        typeof element.type === "string" &&
        ["input", "select", "textarea"].includes(element.type)
      ) {
        if (element.props["aria-label"] || element.props["aria-labelledby"])
          return element;
        return cloneElement(element, {
          "aria-labelledby": id,
          "aria-describedby": hint ? id + "-hint" : undefined,
        });
      }
      return element.type === Fragment
        ? cloneElement(element, {}, nameControls(element.props.children))
        : element;
    });
  return (
    <label className="field">
      <span id={id}>{label}</span>
      {nameControls(children)}
      {hint && <small id={id + "-hint"}>{hint}</small>}
    </label>
  );
~~~


aria-labelledby 指向字段名称，aria-describedby 指向额外提示。这样屏幕阅读器和自动化测试可准确识别“实验单位”，不会把长提示或所有下拉选项都拼成名称。

它目前递归 Fragment，不会递归任意自定义包装组件；若以后把控件包进新的 div / 自定义组件，不能假设自动命名仍然覆盖所有深层子项。

### 4. Modal · 第 134—199 行

输入：标题、内容、关闭回调、是否宽版。输出：遮罩与对话框。

useRef 取得对话框节点。useEffect 做四件事：保存原 body 滚动状态、禁止底页滚动、注册键盘事件、把焦点移入对话框。关闭 / 卸载时恢复滚动并取消监听。


**真实代码（摘录）：frontend/src/components.tsx 第 145—173 行**

~~~tsx
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const list = ref.current?.querySelectorAll<HTMLElement>(
          "button,input,select,textarea,a[href]",
        );
        if (!list?.length) return;
        const first = list[0],
          last = list[list.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    ref.current?.focus();
    return () => {
      document.body.style.overflow = old;
      document.removeEventListener("keydown", key);
    };
  }, [onClose]);
~~~


Escape 关闭；Tab 在首尾控件间循环，以减少焦点跑到底层页面。第 175—198 行的 onMouseDown 只在点击遮罩本身时关闭，点击对话框内容不会误关。role="dialog" 和 aria-modal="true" 告诉辅助技术它是模态框；wide 控制 CSS 宽版。

这是一套基础焦点管理，源码没有完整的“关闭后恢复到原触发按钮”逻辑，也没有过滤所有可能的隐藏 / disabled 焦点候选，不能把它说成完整无障碍框架。

### 5. Citations 与 Evidence · 第 200—252 行

Citations 的输入是一组 Citation 和 onSelect。它遍历数组，每条生成带序号、标题、PDF 页码的按钮；点击把整个引用对象交给父组件。


**真实代码（摘录）：frontend/src/components.tsx 第 207—221 行**

~~~tsx
  return (
    <div className="citations">
      {items.map((c, i) => (
        <button
          key={c.chunk_id + "-" + i}
          className="citation-button"
          title={c.quote}
          onClick={() => onSelect(c)}
        >
          <FileText size={13} />
          {i + 1} · {c.title} <span>p.{c.page_number}</span>
        </button>
      ))}
    </div>
  );
~~~


Evidence 接收当前引用和打开 / 关闭回调，在右侧显示标题、页码、原文 blockquote 和“打开原文对应页”。它本身不去猜页码或重新找证据；引用验证在后端完成。


**真实代码（摘录）：frontend/src/components.tsx 第 232—251 行**

~~~tsx
  return (
    <aside className="evidence">
      <div className="row between">
        <h3>证据原文</h3>
        <button className="icon-button" aria-label="收起证据" onClick={onClose}>
          <X size={17} />
        </button>
      </div>
      <Badge tone="teal">PDF 第 {citation.page_number} 页</Badge>
      <h4>{citation.title}</h4>
      <blockquote>{citation.quote}</blockquote>
      <p className="muted tiny">
        引用标识与原文经过匹配检查。引用存在并不代表结论已经得到充分证明。
      </p>
      <button className="button secondary full" onClick={onOpen}>
        打开原文对应页
        <ArrowUpRight size={15} />
      </button>
    </aside>
  );
~~~


App 收到点击后把引用存为 citation；证据面板调用 onOpen 时，App 再把 paper_id / page_number 存到 reader，Reader 就能跳到原文件对应页。

### 6. Reader 的状态与首次加载 · 第 253—313 行

输入：projectId、paperId、初始页码、关闭 / 保存 / 引用 / 通知回调。输出：宽版阅读弹窗。

| 状态 / ref | 用途 |
|---|---|
| paper | 元信息和逐页文本；也作为编辑中的草稿 |
| page | 当前实际 PDF 页序号 |
| loading / error / pdfError | 分别表示元信息加载、业务错误、PDF 预览错误 |
| tab | text / metadata / card 三个右侧页签 |
| fields | 阅读卡栏目 |
| busy | 保存元信息或请求阅读卡时禁用按钮 |
| canvas | 浏览器绘图画布节点 |
| doc | PDF.js 解析完成的 PDFDocumentProxy |

首次 useEffect 一边 GET 论文详情，一边启动 PDF.js。cancelled 防止已经关闭后再把晚到的成功结果写回；PDF 任务在清理时销毁。


**真实代码（摘录）：frontend/src/components.tsx 第 280—313 行**

~~~tsx
  const url = "/api/projects/" + projectId + "/papers/" + paperId + "/file";
  useEffect(() => {
    let cancelled = false;
    api<Paper>(`/projects/${projectId}/papers/${paperId}`)
      .then((p) => {
        if (!cancelled) setPaper(p);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    const task = pdfjs.getDocument({
      url,
      cMapUrl: "/pdfjs/cmaps/",
      cMapPacked: true,
      standardFontDataUrl: "/pdfjs/standard_fonts/",
      isEvalSupported: false,
    });
    task.promise
      .then((d) => {
        if (cancelled) {
          d.destroy();
          return;
        }
        doc.current = d;
        setPage((p) => Math.min(p, d.numPages));
      })
      .catch((e) => {
        if (!cancelled) setPdfError(String(e.message));
      });
    return () => {
      cancelled = true;
      task.destroy();
      doc.current = null;
    };
  }, [projectId, paperId, url]);
~~~


cMapUrl、standardFontDataUrl 使用前面复制的本地资源；isEvalSupported: false 禁用 PDF.js 的 eval 支持。取到 PDF 后，将页码上界压到真实 numPages。这里 cancelled 防护主要覆盖论文成功写回、PDF 成功 / 错误；元信息 catch / finally 并未都判断 cancelled，不能说所有分支都完全取消。

### 7. Reader 的逐页渲染 effect 和内部 render · 第 314—352 行

paper 或 page 变化就运行这个 effect。PDF 对象尚未准备好时，每隔 150ms 再试；准备好后 getPage(page)，按 1.35 缩放，设置 canvas 像素宽高，再 p.render 绘制。


**真实代码（摘录）：frontend/src/components.tsx 第 314—352 行**

~~~tsx
  useEffect(() => {
    if (!paper || !canvas.current) return;
    let task: pdfjs.RenderTask | undefined;
    let stopped = false;
    async function render() {
      try {
        const d = doc.current;
        if (!d) {
          window.setTimeout(() => {
            if (!stopped) render();
          }, 150);
          return;
        }
        const p = await d.getPage(page);
        if (stopped || !canvas.current) return;
        const viewport = p.getViewport({ scale: 1.35 });
        const c = canvas.current;
        c.height = viewport.height;
        c.width = viewport.width;
        const context = c.getContext("2d");
        if (context) {
          task = p.render({ canvasContext: context, viewport });
          await task.promise;
        }
      } catch (e) {
        if (
          !stopped &&
          e instanceof Error &&
          e.name !== "RenderingCancelledException"
        )
          setPdfError(e.message);
      }
    }
    render();
    return () => {
      stopped = true;
      task?.cancel();
    };
  }, [paper, page]);
~~~


stopped 防止旧页面晚到后继续绘制；切页或关闭时 task.cancel() 停止旧绘制；主动取消导致的 RenderingCancelledException 不作为普通错误显示。ref 用来存 PDF 对象，因为单纯保存大对象不需要触发页面刷新。

### 8. Reader 的 save / readingCard · 第 353—395 行

save 只 PATCH 可编辑元信息：标题、作者、年份、DOI、标签、阅读状态和笔记；不会替换 PDF 原文件或在前端重新切块。保存成功通知父组件 refresh。

readingCard POST /reading-card，保存 fields 并切到 card 页；展示返回 warnings。mode 为 offline 时明确提示“已有原文，不代表 AI 总结”。


**真实代码（摘录）：frontend/src/components.tsx 第 353—395 行**

~~~tsx
  const save = async () => {
    if (!paper) return;
    setBusy(true);
    try {
      await api(`/projects/${projectId}/papers/${paperId}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: paper.title,
          authors: paper.authors,
          year: paper.year,
          doi: paper.doi,
          tags: paper.tags,
          reading_status: paper.reading_status,
          notes: paper.notes,
        }),
      });
      notify("论文信息已保存");
      onSave();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  const readingCard = async () => {
    setBusy(true);
    try {
      const r = await api<{
        fields: ReadingField[];
        mode: string;
        warnings: string[];
      }>(`/projects/${projectId}/papers/${paperId}/reading-card`, json({}));
      setFields(r.fields);
      setTab("card");
      r.warnings?.forEach((w) => notify(w));
      if (r.mode === "offline")
        notify("未配置模型：阅读卡仅展示已有原文，不代表 AI 总结");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
~~~


### 9. Reader 的界面区段 · 第 396—612 行

| 行号 | 页面行为 |
|---|---|
| 396—404 | 弹窗标题；加载、失败、正常三种分支 |
| 405—454 | 上一页、页码输入、下一页、下载原 PDF；输入 clamp 到 1—page_count |
| 455—464 | 显示 canvas，失败则提示可下载原文件阅读 |
| 465—480 | text、metadata、card 页签 |
| 481—488 | 按 page_number 找已保存逐页文本；没有文字明确提示 OCR |
| 489—573 | 全部元信息受控输入；年份空串转 null，标签按中英文逗号切开，最后手动保存 |
| 574—603 | 阅读卡按钮、栏目、引用；点击引用同时 setPage 和 onCite |
| 604—612 | 结束条件分支和弹窗 |

所有输入都有 value 和 onChange。这就是**受控表单**：输入框展示 React state 的值，用户输入再更新 state。没有点保存前，元信息只是当前组件草稿。

### 10. DataTable · 第 613—653 行

输入：行对象数组 rows、列名数组 columns、最多显示行数 max（默认 15）。输出：可横向滚动的表格。


**真实代码（摘录）：frontend/src/components.tsx 第 633—650 行**

~~~tsx
          {rows.slice(0, max).map((r, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c} title={String(r[c] ?? "")}>
                  {r[c] == null ? (
                    <span className="muted">缺失</span>
                  ) : typeof r[c] === "object" ? (
                    JSON.stringify(r[c])
                  ) : (
                    fmt(r[c])
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <p className="muted pad">暂无记录</p>}
~~~


null / undefined 显示“缺失”，对象转 JSON，其他内容用 fmt；单元格 title 保留可悬停查看的原值。只显示 rows.slice(0, max)，因此这是**预览组件**，不是把完整数据全塞进浏览器表格。质量检查与统计计算仍由后端处理全量数据。


## App.tsx：项目、论文、问答、报告和设置

源文件：[App.tsx](../../frontend/src/App.tsx)，2,043 行。它既包含根组件，也包含多数页面组件。文件较长，先按“函数边界”读，暂时不需要把每个 HTML 闭合标签背下来。

### 1. 第 1—85 行：依赖、Page、nav、subtitles

导入的四组东西分别是 Markdown 渲染、React hooks、图标、自己写的 API / 公共组件。Experiments 作为单独文件引入，避免实验页面再塞进本文件。

Page 是合法页面名的联合类型；nav 把页面名、中文名称和图标放在同一个数组里；subtitles 按页面名查说明。这样左侧导航与页面标题可以共用一份定义。


**真实代码（摘录）：frontend/src/App.tsx 第 61—85 行**

~~~ts
type Page =
  | "overview"
  | "papers"
  | "chat"
  | "compare"
  | "experiments"
  | "reports"
  | "settings";
const nav: { id: Page; name: string; icon: typeof BookOpen }[] = [
  { id: "overview", name: "项目概览", icon: LayoutDashboard },
  { id: "papers", name: "论文知识库", icon: BookOpen },
  { id: "chat", name: "科研问答", icon: MessageSquare },
  { id: "compare", name: "文献对比", icon: GitCompareArrows },
  { id: "experiments", name: "实验分析", icon: FlaskConical },
  { id: "reports", name: "研究报告", icon: FileText },
];
const subtitles: Record<Page, string> = {
  overview: "从文献证据到实验发现，让每一步研究都有据可循。",
  papers: "保存原始论文，逐页阅读，让知识成为可以追溯的证据。",
  chat: "围绕研究问题提问，回到原始论文验证每一个结论。",
  compare: "并排梳理研究方法与边界，找到下一步值得验证的问题。",
  experiments: "明确实验设计，再用可复现的计算检验研究假设。",
  reports: "把文献证据、实验结果与分析过程整理为可复现的报告。",
  settings: "管理模型连接与隐私选项，离线功能始终可用。",
};
~~~


这里没有使用 React Router。页面由 state 中的 page 切换；URL 不会自动变成 /papers /chat，刷新页面也不会恢复到刚才的页签。

### 2. App 的全部状态 · 第 86—103 行


**真实代码（摘录）：frontend/src/App.tsx 第 86—103 行**

~~~tsx
export default function App() {
  const [projects, setProjects] = useState<Project[]>([]),
    [pid, setPid] = useState(""),
    [page, setPage] = useState<Page>("overview"),
    [papers, setPapers] = useState<Paper[]>([]),
    [settings, setSettings] = useState<Settings | null>(null),
    [loading, setLoading] = useState(true),
    [loadError, setLoadError] = useState(""),
    [revision, setRevision] = useState(0),
    [projectModal, setProjectModal] = useState(false),
    [edit, setEdit] = useState<Project | null>(null),
    [citation, setCitation] = useState<Citation | null>(null),
    [reader, setReader] = useState<{ paperId: string; page: number } | null>(
      null,
    ),
    [toast, setToast] = useState<{ text: string; error: boolean } | null>(null),
    [mobile, setMobile] = useState(false),
    [demoBusy, setDemoBusy] = useState(false);
~~~


| 状态 | 存什么 |
|---|---|
| projects / pid | 项目列表 / 当前项目 ID |
| page | 当前页面 |
| papers / settings | 当前项目论文 / 后端设置 |
| loading / loadError | 首次加载状态与错误 |
| revision | 刷新计数器；数字增加使依赖它的 effect 重新请求 |
| projectModal / edit | 是否打开项目弹窗 / 编辑哪一项；edit=null 表示新建 |
| citation / reader | 当前证据对象 / 当前打开论文与页码 |
| toast | 临时操作反馈及是否错误 |
| mobile | 是否展开小屏导航 |
| demoBusy | 是否正在导入明确标记的测试材料 |

useState 返回一对值：[当前值，修改函数]。setPid 不直接“改数据库”；它先修改前端当前选择，再由 effect 加载对应资料。

### 3. App 的函数和全部 effect · 第 104—179 行

**notify**（104—106）：稳定的回调，把 text / error 存成 toast。  
**toast effect**（107—111）：提示存在就设 6.5 秒计时器；提示变化 / 组件卸载时 clearTimeout。  
**refresh**（112）：revision 加一，不直接发请求；相关 effect 会被这个依赖变化触发。  
**loadProjects**（113—126）：GET 项目，更新列表，再决定当前项目：保留仍有效的当前项 → 浏览器记住的项 → 第一个未归档项 → 第一项 → 空串。浏览器 localStorage 只记选择 ID，不保存论文原件。


**真实代码（摘录）：frontend/src/App.tsx 第 113—142 行**

~~~tsx
  const loadProjects = useCallback(async () => {
    const list = await api<Project[]>("/projects");
    setProjects(list);
    setPid((current) =>
      list.some((p) => p.id === current)
        ? current
        : list.find((p) => p.id === localStorage.getItem("research-project"))
            ?.id ||
          list.find((p) => !p.archived)?.id ||
          list[0]?.id ||
          "",
    );
    return list;
  }, []);
  useEffect(() => {
    setLoadError("");
    Promise.all([loadProjects(), api<Settings>("/settings").then(setSettings)])
      .catch((e) => setLoadError(e.message))
      .finally(() => setLoading(false));
  }, [loadProjects, revision]);
  useEffect(() => {
    setCitation(null);
    setReader(null);
    if (pid) {
      localStorage.setItem("research-project", pid);
      api<Paper[]>("/projects/" + pid + "/papers")
        .then(setPapers)
        .catch((e) => notify(e.message, true));
    } else setPapers([]);
  }, [pid, revision, notify]);
~~~


第 127—132 行 effect 并行加载项目与设置；Promise.all 表示两项都需要等。catch 保存连接错误，finally 结束首次加载动画。第 133—142 行 effect 随 pid / revision 变化清空证据和阅读器，保存所选 ID，并请求该项目论文。

**论文轮询 effect**（143—152）：仅有 queued / running 论文时启动每 2.5 秒一次的 GET；依赖变化时 clearInterval。已完成后不再持续请求。


**真实代码（摘录）：frontend/src/App.tsx 第 143—179 行**

~~~tsx
  useEffect(() => {
    if (!pid || !papers.some((p) => ["running", "queued"].includes(p.status)))
      return;
    const t = setInterval(() => {
      api<Paper[]>("/projects/" + pid + "/papers")
        .then(setPapers)
        .catch(() => {});
    }, 2500);
    return () => clearInterval(t);
  }, [pid, papers]);
  const project = projects.find((p) => p.id === pid);
  const importDemo = async () => {
    setDemoBusy(true);
    try {
      const r = await api<{ project_id: string }>("/demo", json({}));
      await loadProjects();
      setPid(r.project_id);
      refresh();
      notify("已导入明确标记的测试材料与实验数据");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setDemoBusy(false);
    }
  };
  const navigate = (p: Page) => {
    setPage(p);
    setMobile(false);
  };
  const openCitation = (c: Citation) => setCitation(c);
  const onProjectSaved = async (id: string) => {
    await loadProjects();
    setPid(id);
    refresh();
    setProjectModal(false);
    setEdit(null);
  };
~~~


剩余函数：

| 名称 | 行号 | 输入 → 动作 / 输出 |
|---|---|---|
| project 派生值 | 153 | projects 与 pid → 找到当前对象 |
| importDemo | 154—167 | POST /demo → 重新载入项目、选中新示例、刷新、通知 |
| navigate | 168—171 | Page → 切页并收起小屏导航 |
| openCitation | 172 | Citation → 设置右侧证据 |
| onProjectSaved | 173—179 | 已保存项目 ID → 刷新列表、选中项目、关闭弹窗 |

try / catch / finally 是几乎所有写请求共用的样式：开始 busy → 尝试请求 → 成功更新状态 → 出错展示 → 无论如何恢复按钮。

### 4. App 的 return：整页布局 · 第 180—528 行

| 行号 | 界面区段及数据来源 |
|---|---|
| 181—247 | 固定左侧栏；nav.map 生成按钮，论文徽标使用实际 papers.length |
| 248—250 | 小屏遮罩，点击收起导航 |
| 251—306 | 顶栏：受控项目下拉框、新建入口、AI 状态、设置按钮 |
| 307—333 | 主区标题和项目编辑按钮 |
| 334—341 | 连接失败与“重新连接” |
| 342—413 | 首次加载 / 设置页 / 未选项目欢迎页三种分支 |
| 414—470 | 有项目时按 page 挂载对应页面 |
| 472—475 | 页脚 |
| 477—488 | 右侧 Evidence；打开操作转为 Reader 的 paperId / page |
| 491—501 | ProjectForm，按 edit 决定创建或编辑 |
| 502—512 | Reader，以当前项目和已保存页码打开 PDF |
| 513—525 | 可关闭的全局 toast |

关键的一行是外层的 key：


**真实代码（摘录）：frontend/src/App.tsx 第 413—438 行**

~~~tsx
            ) : (
              <div key={pid}>
                {project.archived && (
                  <Alert>
                    该项目已归档。可在“编辑项目”中恢复，历史资料仍可查看。
                  </Alert>
                )}
                {page === "overview" && (
                  <Overview
                    project={project}
                    revision={revision}
                    onNavigate={navigate}
                    onDemo={importDemo}
                    demoBusy={demoBusy}
                    notify={notify}
                  />
                )}{" "}
                {page === "papers" && (
                  <Library
                    pid={pid}
                    papers={papers}
                    refresh={refresh}
                    notify={notify}
                    onRead={(id, p = 1) => setReader({ paperId: id, page: p })}
                    onCite={openCitation}
                  />
~~~


React 发现 key={pid} 变化，会重新建立这个项目下的子组件，避免把 A 项目的对话、选中文献、实验表单作为 B 项目继续使用。真正的项目资源隔离仍要靠后端每个接口的校验，不能只依赖这个 key。

AI 顶栏显示由 ai_enabled && chat_configured 同时决定；不是模型服务实时健康探针。“已启用”不保证远端此时一定可调用。

### 5. ProjectForm · 第 529—640 行

输入：待编辑 Project 或 null、关闭 / 保存完成 / 通知回调。state 把已有字段复制成草稿；tags 先转成逗号分隔的字符串供人输入。save 阻止浏览器默认刷新，整理 tags，再根据 value 是否存在选择 POST /projects 或 PATCH /projects/{id}。


**真实代码（摘录）：frontend/src/App.tsx 第 540—571 行**

~~~tsx
  const [form, setForm] = useState({
      name: value?.name || "",
      question: value?.question || "",
      hypothesis: value?.hypothesis || "",
      tags: (value?.tags || []).join(", "),
      notes: value?.notes || "",
      archived: value?.archived || false,
    }),
    [busy, setBusy] = useState(false);
  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const data = {
        ...form,
        tags: form.tags
          .split(/[,，]/)
          .map((t) => t.trim())
          .filter(Boolean),
      };
      const p = await api<Project>(
        value ? "/projects/" + value.id : "/projects",
        { method: value ? "PATCH" : "POST", body: JSON.stringify(data) },
      );
      await onSaved(p.id);
      notify(value ? "项目已更新" : "项目已创建");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
~~~


e.preventDefault() 的意思是“这次表单交给 React 处理，不按浏览器默认规则跳转”。...form 是对象展开：复制已有字段；后面写的 tags 会覆盖前面的草稿字符串。

第 573—612 行逐项渲染名称、研究问题、假设、标签、备注；第 613—623 行只在编辑已有项目时显示归档复选框；第 624—637 行是取消 / 保存。下面是一个最典型的受控输入：


**真实代码（摘录）：frontend/src/App.tsx 第 575—584 行**

~~~tsx
        <Field label="项目名称">
          <input
            required
            maxLength={160}
            autoFocus
            value={form.name}
            placeholder="例如：小样本学习中的数据增强策略"
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </Field>
~~~


required 和 maxLength 提供浏览器层的基础约束，后端仍需再验证。value / onChange 使输入与 state 同步；最终 save 才会写数据库。

### 6. Overview · 第 641—890 行

props 提供当前 Project、刷新计数和跳转 / 示例 / 通知回调。

state 中 data 保存论文数、待处理数、实验数、报告数、最近实验和报告；jobs 保存任务列表。reloadOverview 并行请求 /overview 和 /jobs。两个 effect 分别在项目 / revision 变化时加载，以及有排队 / 执行任务时每 2 秒更新。


**真实代码（摘录）：frontend/src/App.tsx 第 656—682 行**

~~~tsx
  const [data, setData] = useState<{
      paper_count: number;
      pending_jobs: number;
      experiment_count: number;
      report_count: number;
      recent_experiments: { id: string; name: string; created_at: string }[];
      recent_reports: Report[];
    } | null>(null),
    [jobs, setJobs] = useState<Job[]>([]);
  const reloadOverview = useCallback(
    () =>
      Promise.all([
        api<typeof data>("/projects/" + project.id + "/overview").then(setData),
        api<Job[]>("/projects/" + project.id + "/jobs").then(setJobs),
      ]).catch((e) => notify(e.message, true)),
    [project.id, notify],
  );
  useEffect(() => {
    void reloadOverview();
  }, [reloadOverview, revision]);
  useEffect(() => {
    if (!jobs.some((j) => ["queued", "running"].includes(j.status))) return;
    const timer = setInterval(() => {
      void reloadOverview();
    }, 2000);
    return () => clearInterval(timer);
  }, [jobs, reloadOverview]);
~~~


JSX 分区：

| 行号 | 展示内容 |
|---|---|
| 685—715 | 项目名称、研究问题、标签与归档状态；装饰轨道由 CSS 绘制 |
| 716—762 | 四个真实统计卡；未拿到值显示“—”，不是假数字 |
| 763—811 | 三个操作入口：论文、问答、实验 |
| 812—846 | 最近实验及时间，或明确空状态 |
| 847—860 | 保存的研究假设，标记待验证 |
| 861—877 | 最多四条失败 / 中断任务与原因 |
| 878—887 | 明确提示“测试材料”的导入按钮 |

源码的 data 类型接收 recent_reports，但当前这一组件没有把最近报告列表渲染出来；它展示报告总数和进入报告页的入口。读代码时应区分“接口里有字段”和“页面真的显示了字段”。

### 7. Library：论文库 · 第 891—1270 行

props：当前项目 ID、论文列表、刷新、通知、打开论文、打开证据。状态分别记录 query / year / tags、选中论文 selected、搜索结果（null 表示还在论文列表）、busy、检索模式、warnings、待删除对象 remove。

全部业务函数：

| 函数 | 行号 | 输入与请求 | 页面变化 |
|---|---|---|---|
| upload | 915—939 | FileList → FormData，POST /papers | 显示接收数和后端判定重复数，触发刷新 |
| search | 940—967 | 查询、选中 ID、年份、标签、limit=20 → POST /search | 保存原文结果、模式与警告 |
| retry | 968—976 | Paper → POST /papers/{id}/retry | 重新入队并刷新 |
| deletePaper | 977—994 | 当前 remove → DELETE /papers/{id} | 清空旧搜索、移除勾选、关闭确认框、刷新 |


**真实代码（摘录）：frontend/src/App.tsx 第 915—939 行**

~~~tsx
  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    const fd = new FormData();
    for (const f of Array.from(files)) fd.append("files", f);
    setBusy(true);
    try {
      const r = await api<{ papers: Paper[]; duplicates: string[] }>(
        "/projects/" + pid + "/papers",
        { method: "POST", body: fd },
      );
      notify(
        "已接收 " +
          r.papers.length +
          " 篇论文" +
          (r.duplicates.length
            ? "，" + r.duplicates.length + " 个重复文件已跳过"
            : ""),
      );
      refresh();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
~~~


**真实代码（摘录）：frontend/src/App.tsx 第 940—967 行**

~~~tsx
  const search = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    try {
      const r = await api<{
        results: Citation[];
        mode: string;
        warnings: string[];
      }>(
        "/projects/" + pid + "/search",
        json({
          query,
          paper_ids: selected,
          year: year ? Number(year) : undefined,
          tags: tags.split(/[,，]/).filter(Boolean),
          limit: 20,
        }),
      );
      setSearchResult(r.results);
      setMode(r.mode);
      setWarnings(r.warnings || []);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
~~~


上传组件支持 multiple，但 PDF 格式 / 大小 / 页数最终由后端检查。上传后清空 file input.value，允许用户再次选择相同文件触发 onChange；不表示绕过去重。哈希去重由后端做。

检索范围里 selected=[] 表示当前项目全部论文。这里的 pid 在请求路径中，paper_ids 在正文中；后端还要验证这些 ID 都属于当前项目。

JSX 分区：

| 行号 | 页面行为 |
|---|---|
| 997—1019 | 上传按钮、数量和 file input |
| 1020—1067 | 搜索表单、年份 / 标签、返回列表 |
| 1068—1106 | 检索警告、模式、命中摘录、页码、证据按钮 / 无结果 |
| 1107—1231 | 论文表格、全选 / 单选、元信息、状态、阅读 / 重试 / 删除 |
| 1232—1242 | 尚无论文时说明格式和 OCR 边界 |
| 1243—1267 | 删除确认；明确会删除文件、文本和索引 |

searchResult 的 null 与 [] 含义不同：null 画论文列表；空数组画“已经检索但没有命中”。这是前端状态设计中很实用的区别。

### 8. Scope：论文范围选择 · 第 1271—1316 行

输入：papers、已选 ID、onChange。使用浏览器原生 details / summary 展开面板；选中时追加 ID，取消时 filter 移除；重置把 selected 变为空数组。


**真实代码（摘录）：frontend/src/App.tsx 第 1293—1313 行**

~~~tsx
          papers.map((p) => (
            <label className="checkbox" key={p.id}>
              <input
                type="checkbox"
                checked={selected.includes(p.id)}
                onChange={(e) =>
                  onChange(
                    e.target.checked
                      ? [...selected, p.id]
                      : selected.filter((id) => id !== p.id),
                  )
                }
              />
              {p.title}
            </label>
          ))
        )}
        <button className="text-button" onClick={() => onChange([])}>
          重置为全部论文
        </button>
      </div>
~~~


它不做网络请求，不决定检索权限，只是把用户选的范围交给 Chat 等父组件。

### 9. Chat：问答与历史 · 第 1317—1531 行

状态：messages 当前消息、question 输入、selected 论文范围、busy、cid 对话 ID、histories 历史列表。load 用 useCallback 包住 GET /conversations；useEffect 在当前项目加载时调用它。

ask 的顺序：阻止默认提交 → trim 问题 → 清空输入 → 立即显示用户消息 → POST /ask → 保存 conversation_id → 追加助手正文、引用、mode → 展示警告 → 刷新历史。失败时把问题放回输入框，便于重试。


**真实代码（摘录）：frontend/src/App.tsx 第 1346—1386 行**

~~~tsx
  const ask = async (e: FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    const q = question.trim();
    setQuestion("");
    setMessages((m) => [...m, { role: "user", content: q, citations: [] }]);
    setBusy(true);
    try {
      const r = await api<{
        answer: string;
        conversation_id: string;
        citations: Citation[];
        mode: string;
        warnings: string[];
      }>(
        "/projects/" + pid + "/ask",
        json({
          question: q,
          paper_ids: selected,
          conversation_id: cid || undefined,
        }),
      );
      setCid(r.conversation_id);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: r.answer,
          citations: r.citations || [],
          mode: r.mode,
        },
      ]);
      r.warnings?.forEach((w) => notify(w));
      load();
    } catch (e) {
      setQuestion(q);
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
~~~


这里“立即显示用户消息”只是前端改善等待感的做法；若请求失败，该条本地消息仍在 messages 中，再重试可能出现重复显示，不应把它当成服务端已经成功保存的证明。

JSX 分区：

| 行号 | 页面行为 |
|---|---|
| 1389—1404 | 按设置显示模型已启用 / 未配置披露 |
| 1406—1420 | 范围选择与新对话；新对话清空当前 messages / cid |
| 1421—1447 | 按 role 显示消息；按 mode 区分 AI、证据不足、非 AI 原文检索；Citations 可点击 |
| 1448—1468 | 初始引导问题，只填输入框，不自动调用 |
| 1469 | 请求中的等待提示 |
| 1471—1501 | 受控问题输入、Ctrl / Cmd + Enter、发送按钮 |
| 1503—1527 | 切换已保存对话；从对象取回 messages |

m.content 放在普通 React p 中显示，是文本，不会作为 HTML 或代码执行。聊天不是流式逐字输出实现，它等后端完整 JSON 返回后一次加入消息。前端在部分按钮 busy 时禁用，但键盘提交函数本身没有额外的 if (busy) 防护；也没有完整的跨历史切换请求取消机制。

### 10. Compare：文献对比 · 第 1532—1666 行

state：selected、rows、busy、warnings、mode。run POST /compare，保存按论文组织的 fields 列表。按钮在少于 2 篇或多于 5 篇时禁用，选满 5 篇后其他未选项禁用。后端仍要验证数量和归属。


**真实代码（摘录）：frontend/src/App.tsx 第 1550—1566 行**

~~~tsx
  const run = async () => {
    setBusy(true);
    try {
      const r = await api<{
        mode: string;
        rows: typeof rows;
        warnings: string[];
      }>("/projects/" + pid + "/compare", json({ paper_ids: selected }));
      setRows(r.rows);
      setWarnings(r.warnings || []);
      setMode(r.mode);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
~~~


第 1590—1627 行是选择卡；第 1628—1633 行提醒不同数据集 / 单位 / 协议不能直接排名；第 1634—1662 行按 rows.length 生成列数，逐字段显示 text 和 Citations。每列最小宽度 270px，内容多时可以横向滚动。这个页面组织对比信息，没有按最高分自动颁出“最佳方法”。

### 11. Reports：报告阅读与下载 · 第 1667—1815 行

state：reports、selected、loading。effect GET 报告列表，尽量保留当前选中项，否则取第一项。没有报告时引导到实验页生成，而不是展示虚构报告。

第 1699—1718 行是左侧列表；第 1719—1766 行展示绑定的分析和下载链接；下载通过普通 a href 向后端取得 MD / CSV / PNG / Python / JSON / ZIP，不在浏览器临时生成科研数字。

**Markdown 安全是本页最重要的实现之一：**


**真实代码（摘录）：frontend/src/App.tsx 第 1770—1809 行**

~~~tsx
          <div className="markdown-report rendered-report">
            <Markdown
              remarkPlugins={[remarkGfm]}
              skipHtml
              components={{
                img: ({ src, alt }) => {
                  const kinds: Record<string, string> = {
                    "plot.png": "points",
                    "box.png": "box",
                    "histogram.png": "hist",
                  };
                  const kind = typeof src === "string" ? kinds[src] : undefined;
                  return kind ? (
                    <img
                      src={
                        "/api/projects/" +
                        pid +
                        "/analyses/" +
                        selected.analysis_id +
                        "/plot.png?kind=" +
                        kind
                      }
                      alt={alt || "实验图表"}
                      loading="lazy"
                    />
                  ) : (
                    <span className="muted">
                      [外部图片未自动加载：{alt || "图片"}]
                    </span>
                  );
                },
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noreferrer">
                    {children}
                  </a>
                ),
              }}
            >
              {selected.markdown}
            </Markdown>
~~~


remarkGfm 支持表格等常用 Markdown；skipHtml 跳过原始 HTML。img 被重写，只接纳报告中三种约定的本地图表名，把它们映射成当前项目、当前分析的后端图表 API；不自动加载其他图片，避免报告正文驱动任意外部图片请求。a 用新标签页和 noreferrer，链接仍需要用户点击。

Markdown 只是排版，selected.markdown 是后端保存的报告文本。这里没有 eval、执行 Python 或把模型生成的文字当程序运行。

### 12. SettingsView：模型开关与索引 · 第 1816—2043 行

state：busy、consent 用户是否勾选知情说明、indexStatus 当前项目向量索引情况。唯一 effect 在 pid 变化时 GET /embedding-status；错误当前被静默忽略，所以状态未出现不应被理解为已确认健康。

toggle PATCH /settings，只修改 ai_enabled；rebuild POST 当前项目 /embeddings/rebuild，提交任务并提示去项目任务看进度：


**真实代码（摘录）：frontend/src/App.tsx 第 1832—1863 行**

~~~tsx
  useEffect(() => {
    if (pid)
      api<Record<string, unknown>>("/projects/" + pid + "/embedding-status")
        .then(setIndexStatus)
        .catch(() => {});
  }, [pid]);
  const toggle = async () => {
    setBusy(true);
    try {
      const s = await api<Settings>("/settings", {
        method: "PATCH",
        body: JSON.stringify({ ai_enabled: !settings?.ai_enabled }),
      });
      onChange(s);
      notify(s.ai_enabled ? "已启用外部模型调用" : "已关闭外部模型调用");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  const rebuild = async () => {
    setBusy(true);
    try {
      await api("/projects/" + pid + "/embeddings/rebuild", json({}));
      notify("已提交向量索引重建，请在项目任务中查看进度");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
~~~


JSX 分区：

| 行号 | 页面行为 |
|---|---|
| 1864—1866 | 设置无法读取时的空状态 |
| 1867—1918 | 展示聊天 / 向量模型名称、服务地址、是否配置 |
| 1919—1938 | 外发范围说明和知情勾选 |
| 1939—1958 | 启停按钮；未同意或两种模型都未配置时不能启用 |
| 1961—2005 | 当前项目向量重建入口、片段总数、已索引数、是否需要重建 |
| 2006—2040 | 后端资源上限：上传大小、页数、解析时限、表格规模 |

前端没有密钥输入框，也没有把密钥保存到 localStorage；密钥在后端 .env / 环境变量中配置。修改 .env 后要重启后端。模型开关与“有没有配置”是两个维度：配置了也要明确启用才会外发。


## Experiments.tsx：导入、确认设计、展示分析

源文件：[Experiments.tsx](../../frontend/src/Experiments.tsx)，1,489 行。

它把“实验记录 → 数据版本 → 用户确认配置 → 后端计算 → 已保存结果 → 报告”串在一起。前端负责填写和展示，t 检验仍由后端统计引擎执行。

### 1. 导入、Props、initialConfig · 第 1—82 行

第 1 行导入公共直方图逻辑；第 2—8 行是 hooks；第 9—24 行图标；第 25—37 行是 Recharts 图形组件；第 38—59 行是 API 类型及公共界面积木。

Props（60—67）接收当前项目、可关联论文、刷新计数、刷新 / 通知回调、跳转报告回调。initialConfig 是首次打开或换数据时使用的空配置：


**真实代码（摘录）：frontend/src/Experiments.tsx 第 68—82 行**

~~~ts
const initialConfig: AnalysisConfig = {
  group_column: "",
  metric_column: "",
  group_a: "",
  group_b: "",
  design: "descriptive",
  experimental_unit: "",
  missing_policy: "error",
  alternative: "two-sided",
  pair_column: "",
  sample_id_column: "",
  unit: "",
  direction: "higher",
  confirmed: false,
};
~~~


默认只做描述统计，缺失策略默认 error，检验方向默认双侧，confirmed=false。分组列、指标、对象、实验单位都留空，避免仅凭列名自动猜测设计。direction="higher" 是指标展示方向，和 alternative="greater" 的单侧检验不是同一个概念。

### 2. Experiments 的全部 state 与 ref · 第 83—114 行

| 状态 | 作用 |
|---|---|
| experiments / eid / detail | 实验列表、选中实验、该实验详情 |
| loading / modal | 列表加载状态、是否打开新建实验弹窗 |
| datasetId / config / analysis | 当前待配置的数据版本、表单草稿、当前查看的已保存分析 |
| file / sheet | 尚待上传的文件与工作表 |
| busy / error | 执行状态和错误说明 |
| clean / cleanColumns / dropDuplicates | 清洗弹窗、需排除缺失行的列、是否删除完全重复行 |
| suggestion | 后端模型建议及说明；独立于正在运行的分析 |
| panel | data 或 result 页签 |
| selectedExperiment ref | 当前实验 ID，供异步回包时检查 |
| detailRequest ref | 最新详情请求序号，防止旧请求覆盖新请求 |

注意 datasetId 与 analysis.dataset_id 不是必须相同：前者是正在配置的版本，后者是历史分析绑定的版本。结果区读取保存的 analysis，不会因为你切换上传文件就偷偷把旧结果改掉。

### 3. loadDetail 与所有 effect：防止“晚到的旧结果” · 第 115—160 行


**真实代码（摘录）：frontend/src/Experiments.tsx 第 112—160 行**

~~~tsx
  const selectedExperiment = useRef("");
  selectedExperiment.current = eid;
  const detailRequest = useRef(0);
  const loadDetail = useCallback(
    async (id: string) => {
      if (!id) return;
      const request = ++detailRequest.current;
      const d = await api<Experiment>(
        "/projects/" + pid + "/experiments/" + id,
      );
      if (
        request !== detailRequest.current ||
        selectedExperiment.current !== id
      )
        return;
      setDetail(d);
      setDatasetId((old) =>
        d.datasets?.some((x) => x.id === old) ? old : d.datasets?.[0]?.id || "",
      );
      setAnalysis(
        (old) =>
          d.analyses?.find((x) => x.id === old?.id) || d.analyses?.[0] || null,
      );
      return d;
    },
    [pid],
  );
  useEffect(() => {
    setLoading(true);
    api<Experiment[]>("/projects/" + pid + "/experiments")
      .then((list) => {
        setExperiments(list);
        setEid((old) =>
          list.some((e) => e.id === old) ? old : list[0]?.id || "",
        );
      })
      .catch((e) => notify(e.message, true))
      .finally(() => setLoading(false));
  }, [pid, revision, notify]);
  useEffect(() => {
    setDetail(null);
    setDatasetId("");
    setAnalysis(null);
    setConfig(initialConfig);
    setError("");
    setFile(null);
    setSheet("");
    if (eid) loadDetail(eid).catch((e) => notify(e.message, true));
  }, [eid, loadDetail, notify]);
~~~


这个竞态例子很好理解：

1. 你点实验 A，发出请求 1。
2. 马上点实验 B，发出请求 2。
3. B 先回来，A 后回来。
4. 没有保护时，页面可能又被 A 覆盖。

源码同时比对 request 序号和 selectedExperiment.current。只有“仍是最新请求，并且仍在查看这项实验”才 setDetail。然后尽量保留仍存在的数据版本 / 分析，否则选列表第一项。

第一个 effect（139—150）按项目 / revision 取实验列表，保留有效 eid。第二个 effect（151—160）随 eid 变化清空旧详情、版本、结果、配置、错误、文件和工作表，再加载详情。

useCallback 的依赖 pid 变化会生成新的 loadDetail，促使相应 effect 重跑；useRef 的 current 变动不触发渲染，适合保存“请求身份”。

### 4. 派生值、update、组名建议 · 第 161—173 行

dataset 从 detail.datasets 中按 datasetId 找到。update 合并字段后总是把 confirmed 设为 false；改配置就必须重新确认：


**真实代码（摘录）：frontend/src/Experiments.tsx 第 161—173 行**

~~~tsx
  const dataset = detail?.datasets?.find((d) => d.id === datasetId);
  const update = (data: Partial<AnalysisConfig>) =>
    setConfig((c) => ({ ...c, ...data, confirmed: false }));
  const groups =
    dataset && config.group_column
      ? [
          ...new Set(
            dataset.preview
              .map((r) => String(r[config.group_column] ?? ""))
              .filter(Boolean),
          ),
        ]
      : [];
~~~


groups 从**预览行**中抽取不重复分组名，只用于 datalist 输入建议。它不是全量分组扫描，因此用户仍能手工输入未在预览里出现的组名；最终存在性由后端检查。不能把候选组列表误认为数据只包含这些组。

### 5. upload、cleanData：原始文件与清洗版本 · 第 174—225 行

upload 输入 file / 可选 sheet，POST /datasets。成功后重新加载详情、选中新版本、清空分析草稿、通知原文件保留。它不会在前端用 FileReader 改写数据。


**真实代码（摘录）：frontend/src/Experiments.tsx 第 174—197 行**

~~~tsx
  const upload = async () => {
    if (!file || !eid) return;
    const fd = new FormData();
    fd.append("file", file);
    if (sheet) fd.append("sheet", sheet);
    setBusy(true);
    setError("");
    try {
      const d = await api<Dataset>(
        "/projects/" + pid + "/experiments/" + eid + "/datasets",
        { method: "POST", body: fd },
      );
      await loadDetail(eid);
      setDatasetId(d.id);
      setSheet(d.sheet || "");
      setConfig(initialConfig);
      notify("数据版本已保存，原始文件保持不变");
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
~~~


cleanData 输入选定版本、cleanColumns / dropDuplicates，POST /datasets/{id}/clean；返回的是新的 Dataset，不覆盖旧版本。成功后选中新版本、关闭清洗弹窗、清空旧配置。


**真实代码（摘录）：frontend/src/Experiments.tsx 第 198—225 行**

~~~tsx
  const cleanData = async () => {
    if (!dataset) return;
    setBusy(true);
    try {
      const d = await api<Dataset>(
        "/projects/" +
          pid +
          "/experiments/" +
          eid +
          "/datasets/" +
          dataset.id +
          "/clean",
        json({
          drop_missing_columns: cleanColumns,
          drop_duplicate_rows: dropDuplicates,
        }),
      );
      await loadDetail(eid);
      setDatasetId(d.id);
      setClean(false);
      setConfig(initialConfig);
      notify("清洗结果已保存为独立版本");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
~~~


清洗请求只包含白名单规则：指定列缺失时排除对应行、删除完全相同重复行。模型不能在这里放一段任意 Python；异常值也没有默认删除选项。

### 6. run、suggest、createReport · 第 226—287 行

run 把**数据版本 ID 与配置**一起送给后端；返回 Analysis 后保存对象，切到结果页，再更新实验详情。分析数字来自后端响应，浏览器没有自己重算 p 值。


**真实代码（摘录）：frontend/src/Experiments.tsx 第 226—244 行**

~~~tsx
  const run = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const a = await api<Analysis>(
        "/projects/" + pid + "/experiments/" + eid + "/analyses",
        json({ dataset_id: datasetId, config }),
      );
      setAnalysis(a);
      setPanel("result");
      await loadDetail(eid);
      notify("统计结果已保存，并绑定当前数据版本");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
~~~


suggest POST /suggest，带 dataset_id 与实验假设 / 默认请求，返回 Partial<AnalysisConfig>、explanation、configured。只是保存 suggestion 并打开建议弹窗，未直接调用 run。

createReport 只在 analysis 存在时 POST /reports，正文绑定 analysis.id 和报告标题。成功刷新后调用 onReports 跳转报告页，不重新读取当前表单代替已保存分析。

### 7. selector：重复列映射控件 · 第 288—307 行

输入：字段中文名称、AnalysisConfig 中一个列字段名、是否必填。输出：Field + select；选项来自 dataset.columns。


**真实代码（摘录）：frontend/src/Experiments.tsx 第 288—307 行**

~~~tsx
  const selector = (
    label: string,
    key: "group_column" | "metric_column" | "sample_id_column" | "pair_column",
    required = false,
  ) => (
    <Field label={label}>
      <select
        value={config[key] || ""}
        required={required}
        onChange={(e) => update({ [key]: e.target.value })}
      >
        <option value="">请选择列</option>
        {dataset?.columns.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
    </Field>
  );
~~~


config[key] 是按变量读取对象字段；{ [key]: value } 是按变量创建字段。这里 key 的联合类型只允许 group_column、metric_column、sample_id_column、pair_column，减少不小心更新错误配置字段的机会。

### 8. Experiments return 的完整功能分区 · 第 308—898 行

| 行号 | 行为和对应状态 |
|---|---|
| 310—335 | 实验数量、新建按钮、加载 / 无实验状态 |
| 338—350 | 实验 tabs；busy 时禁止切换实验 |
| 351—386 | 实验名称、假设、创建时间；展开条件、参数、备注 |
| 387—405 | 数据配置 / 结果两个页签 |
| 408—471 | 文件选择、XLSX 工作表输入、导入新版本 |
| 474—518 | 数据版本下拉框、行列数量、SHA256；换版本清空配置 |
| 519—538 | 质量、预览、清洗版 transform 的 JSON |
| 539—720 | 设计表单与确认；下文逐项拆解 |
| 723—724 | 导入 / 分析错误，保留说明供修改 |
| 727—758 | 已保存分析下拉框和生成报告 |
| 759—779 | AnalysisResult 或尚未分析入口 |
| 782—784 | 实验详情等待状态 |
| 787—800 | 新建实验弹窗；成功添加列表、选中、刷新 |
| 801—854 | 清洗规则弹窗 |
| 855—895 | AI 建议弹窗，导入只填表不执行 |
| 896—898 | 收束返回的 Fragment |

#### 工作表与数据版本

第 435—456 行的 sheet 输入仅在所选文件名以 .xlsx 结束时可用。首次留空由后端使用第一张表。已导入版本有可用 sheet 名称时提供 datalist；它不是在用户刚选文件时就本地解析所有工作表。

第 496—513 行切换 datasetId 只是选择已有版本；换工作表要重新导入生成新版本。SHA256 缩略显示用于确认文件身份，不把整段哈希挤在页面上。

#### 分析表单的每一个字段

| 行号 | 字段 | 为什么需要 |
|---|---|---|
| 558 | 分组列 | 哪一列写 A / B 等对象 |
| 559 | 主要指标列 | 本次推断只针对一个指标 |
| 560—568 | 单位 | 图表与结果数字的意义 |
| 569—589 | 基准 A、比较 B | 确定差值方向 B−A |
| 590—603 | higher / lower | 表示指标越大还是越小更好，不自动决定检验方向 |
| 604—622 | descriptive / independent / paired | 明确设计，不靠正态性或列名猜 |
| 623—635 | 实验单位 | 说明真正独立的对象 |
| 636—640 | 样本 ID 列 | 后端识别重复实验单位 |
| 641—642 | 配对 ID 列 | 仅配对设计显示并必填 |
| 643—660 | error / drop | 无效数据是停止还是明确排除记录 |
| 661—678 | 双侧 / 单侧 | 明确假设方向 |
| 679—683 | 组名 datalist | 只辅助填写 |
| 684—688 | 差值 / 相对变化 / 单指标提示 | 防止把不同约定混淆 |
| 689—702 | confirmed 复选框 | 人工核对数据版本和设计 |
| 703—718 | 执行按钮 | busy 或未确认时不能点击 |


**真实代码（摘录）：frontend/src/Experiments.tsx 第 684—718 行**

~~~tsx
                          <Alert>
                            所有差值统一为 B − A；相对变化以 |A|
                            为分母。每次只检验一个主要指标。均值差的 95%
                            区间、统计显著性与实际价值需要分别解释。
                          </Alert>
                          <label className="checkbox confirmation">
                            <input
                              type="checkbox"
                              required
                              checked={config.confirmed}
                              onChange={(e) =>
                                setConfig({
                                  ...config,
                                  confirmed: e.target.checked,
                                })
                              }
                            />
                            我已核对数据版本、实验单位、独立/配对设计、两组对象与缺失值处理，同意执行以上配置。
                          </label>
                          <div className="form-actions">
                            <span className="tiny muted">
                              统计计算由后端确定性函数执行
                            </span>
                            <button
                              className="button primary"
                              disabled={busy || !config.confirmed}
                            >
                              {busy ? (
                                <LoaderCircle size={16} className="spin" />
                              ) : (
                                <BarChart3 size={16} />
                              )}
                              运行并保存分析
                            </button>
                          </div>
~~~


表单每次 update 都取消 confirmed，AI 填入建议也取消确认。这使“先看建议再人工核对”成为真实行为。

#### 清洗与 AI 建议弹窗

第 807—825 行按列勾选要排除缺失行的列；第 826—833 行选择完全重复行规则；没选任何规则时保存按钮禁用。既不填补缺失值，也不改变单位。

AI 建议的应用代码：


**真实代码（摘录）：frontend/src/Experiments.tsx 第 862—889 行**

~~~tsx
            {suggestion.configured && (
              <>
                <pre className="json-preview">
                  {JSON.stringify(suggestion.suggestion, null, 2)}
                </pre>
                <p className="muted">
                  导入建议只填写表单，不会执行。请逐项核对后，勾选确认并点击运行。
                </p>
                <div className="form-actions">
                  <button
                    className="button secondary"
                    onClick={() => setSuggestion(null)}
                  >
                    关闭
                  </button>
                  <button
                    className="button primary"
                    onClick={() => {
                      setConfig((c) => ({
                        ...c,
                        ...suggestion.suggestion,
                        confirmed: false,
                      }));
                      setSuggestion(null);
                    }}
                  >
                    填入表单，继续核对
                  </button>
~~~


这段只 setConfig，不调用 run。Partial 代表模型建议可以只给部分字段，剩下沿用原草稿；后端的建议过滤和分析参数校验仍是最终限制。

### 9. ExperimentForm · 第 899—1023 行

输入：pid、papers、关闭 / 成功 / 通知回调。state 为 name、hypothesis、paper_ids、conditions、parameters、notes 以及 busy。

save 阻止默认提交，POST /experiments，成功把后端 Experiment 交给 onSaved，再通知；finally 恢复按钮。


**真实代码（摘录）：frontend/src/Experiments.tsx 第 912—936 行**

~~~tsx
  const [form, setForm] = useState({
      name: "",
      hypothesis: "",
      paper_ids: [] as string[],
      conditions: "",
      parameters: "",
      notes: "",
    }),
    [busy, setBusy] = useState(false);
  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const x = await api<Experiment>(
        "/projects/" + pid + "/experiments",
        json(form),
      );
      onSaved(x);
      notify("实验记录已创建");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
~~~


第 940—972 行是名称、假设、条件、参数受控输入；第 973—999 行勾选关联论文 ID；第 1000—1006 行备注；第 1007—1021 行操作按钮。当前该组件实现的是创建表单，不是实验编辑界面。

### 10. Quality · 第 1024—1057 行

输入：一个 Dataset。它不重算缺失值，只显示后端返回的 quality：

- quality.columns 是数组时转成详情表。
- duplicate_rows 优先，兼容旧的 duplicates 名称，均不存在则 0。
- 显示总行数、完全重复行、工作表，并说明检查针对全量数据。
- 没有 columns 数组时用 JSON 展示质量详情，避免静默丢掉未知结构。


**真实代码（摘录）：frontend/src/Experiments.tsx 第 1024—1057 行**

~~~tsx
function Quality({ dataset }: { dataset: Dataset }) {
  const quality = dataset.quality || {};
  const columns = Array.isArray(quality.columns)
    ? (quality.columns as Record<string, unknown>[])
    : [];
  const duplicate = quality.duplicate_rows ?? quality.duplicates ?? 0;
  return (
    <div className="quality">
      <div className="row wrap">
        <Badge tone="blue">{dataset.row_count} 行观测</Badge>
        <Badge>完全重复行：{fmt(duplicate)}</Badge>
        {dataset.sheet && <Badge>工作表：{dataset.sheet}</Badge>}
        <span className="tiny muted">完整性检查针对全量数据</span>
      </div>
      {columns.length > 0 && (
        <details>
          <summary>
            查看各列缺失、数值与异常值情况 <ChevronDown size={13} />
          </summary>
          <DataTable rows={columns} columns={Object.keys(columns[0])} />
        </details>
      )}
      {!columns.length && (
        <details>
          <summary>
            查看数据质量详情
            <ChevronDown size={13} />
          </summary>
          <pre className="json-preview">{JSON.stringify(quality, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
~~~


### 11. AnalysisResult · 第 1058—1216 行

输入：已保存的 Analysis 与项目 ID。唯一局部状态 plot 决定 points / box / hist；r=analysis.result、cfg=analysis.config，不读取旁边正在编辑的草稿。

| 行号 | 显示内容 |
|---|---|
| 1071—1085 | 保存时间、绑定版本 ID、设计标签 |
| 1086—1093 | warnings 和 comparison.reason；无法检验时也有解释 |
| 1094—1126 | 均值差、95% 区间、p 值、相对变化四卡 |
| 1127—1142 | 各组 n、mean、median、std、min、max |
| 1143—1183 | 图形选择、对应后端 PNG 下载、InteractivePlot |
| 1184—1191 | 明确点、箱须、频数含义，说明没有均值误差线 |
| 1193—1197 | 显著性、实际价值、因果关系区分 |
| 1198—1213 | 展开已保存配置、排除记录、状态和原因 |

均值差区间必须两端都有值才展示；空值显示“—”，不会把缺失结果渲染成 0。相对变化标出分母是 |A|。


**真实代码（摘录）：frontend/src/Experiments.tsx 第 1094—1125 行**

~~~tsx
      <div className="stats-grid result-stats">
        {[
          { label: "均值差 B − A", value: c.difference, unit: cfg.unit },
          {
            label: "95% 置信区间",
            value:
              c.ci_low != null && c.ci_high != null
                ? "[" + fmt(c.ci_low) + ", " + fmt(c.ci_high) + "]"
                : "—",
            unit: cfg.unit,
          },
          {
            label: "p 值",
            value: c.pvalue,
            unit: cfg.alternative === "two-sided" ? "双侧检验" : "单侧检验",
          },
          {
            label: "相对变化",
            value: c.relative_change_percent,
            unit: "% · 分母为 |A|",
          },
        ].map((v) => (
          <div className="stat-card" key={v.label}>
            <div>
              <span>{v.label}</span>
              <strong className="number">
                {typeof v.value === "string" ? v.value : fmt(v.value)}
              </strong>
              <small>{v.unit || "无量纲"}</small>
            </div>
          </div>
        ))}
~~~


导出 PNG 的 URL 指向 analysis.id，而不是当前 datasetId；因此导出绑定你正在看的那次保存分析。交互图是浏览器的 Recharts / SVG，导出图由后端 Matplotlib 生成，视觉排版可能不同，但取同一保存结果。

### 12. quantile · 第 1217—1224 行

输入：**已升序排序**数组和 0—1 分位位置 q。输出：相邻值线性插值得出的分位数。调用者在箱线图分组后先 sort，因此这里不重复排序。


**真实代码（摘录）：frontend/src/Experiments.tsx 第 1217—1224 行**

~~~ts
function quantile(values: number[], q: number) {
  const pos = (values.length - 1) * q,
    base = Math.floor(pos),
    rest = pos - base;
  return (
    values[base] + ((values[base + 1] ?? values[base]) - values[base]) * rest
  );
}
~~~


例如五个值求中位数，pos=(5−1)×0.5=2，取第 3 个值；落在两个位置之间时按 rest 比例插值。这个函数为画箱体用，不是后端推断检验程序。

### 13. InteractivePlot · 第 1225—1489 行

输入：保存结果、图种、单位、指标名。先从 result.points 提取组名，指定稳定配色，把单位并入轴标签；没有效点则显示 Empty。

#### 原始散点：第 1240—1297 行

每个点的 y 值保持原始 value，x 按组位置加一个**确定性的**小偏移，减少重叠：


**真实代码（摘录）：frontend/src/Experiments.tsx 第 1240—1244 行**

~~~ts
  if (kind === "points") {
    const data = result.points.map((p, i) => ({
      ...p,
      x: groups.indexOf(p.group) + 1 + (((i * 37) % 19) / 19 - 0.5) * 0.2,
    }));
~~~


这里 i×37 的取余表达式不调用随机数，所以刷新后点位不会乱跳。横向偏移不代表真实测量变量。XAxis 按组标注，YAxis 标单位；Tooltip 显示组、原值和可选 pair_id。Scatter 的 isAnimationActive={false} 避免动画中的中间值看起来像最终数字。

#### 直方图：第 1298—1345 行

所有组的点先合在一起生成公共箱；箱数用样本数平方根向上取整，并限制在 3—12。每个公共箱再统计每组频数：


**真实代码（摘录）：frontend/src/Experiments.tsx 第 1298—1313 行**

~~~tsx
  if (kind === "hist") {
    const values = result.points.map((p) => p.value),
      count = Math.min(12, Math.max(3, Math.ceil(Math.sqrt(values.length)))),
      hist = makeHistogram(values, count);
    const bins = hist.bins.map((b) => {
      const record: Record<string, number | string> = { range: b.range };
      groups.forEach((_, i) => (record["g" + i] = 0));
      return record;
    });
    result.points.forEach((p, i) => {
      const index = hist.binIndices[i];
      if (index >= 0) {
        const key = "g" + groups.indexOf(p.group);
        bins[index][key] = Number(bins[index][key]) + 1;
      }
    });
~~~


g0 / g1 是内部数据键，真实组名可能含空格或特殊字符，因此不直接用作 Recharts 字段路径。Y 轴只显示整数频数，柱动画关闭，横轴标签倾斜便于看边界。当前这个直方图横轴用数值区间标签，未额外绘制指标单位轴标题；单位在结果区上下文已有显示。

#### 箱线图：第 1346—1489 行

因为当前 Recharts 用法没有直接的箱线组件，这里手写 SVG：

1. 第 1346—1352 行扫描总体极值，建立数值到画布 y 坐标的转换；SVG y 向下增大，所以用 275 减去缩放值。
2. 第 1354—1379 行画五条网格线和刻度。
3. 第 1380—1387 行画旋转的指标 / 单位标题。
4. 第 1388—1403 行每组排序，计算 Q1、Q3、中位数、IQR，找 1.5×IQR 范围内实际最小 / 最大观测。
5. 第 1404—1459 行画须、端帽、箱体、中位数线；title 中有 n 和分位数。
6. 第 1460—1473 行把须外的观测画成小圆点，只标记，不删除。
7. 第 1474—1482 行画组名和样本量。


**真实代码（摘录）：frontend/src/Experiments.tsx 第 1388—1403 行**

~~~tsx
        {groups.map((g, i) => {
          const values = result.points
              .filter((p) => p.group === g)
              .map((p) => p.value)
              .sort((a, b) => a - b),
            q1 = quantile(values, 0.25),
            q3 = quantile(values, 0.75),
            med = quantile(values, 0.5),
            iqr = q3 - q1,
            inside = values.filter(
              (v) => v >= q1 - 1.5 * iqr && v <= q3 + 1.5 * iqr,
            ),
            lo = inside[0],
            hi = inside[inside.length - 1],
            x = 100 + ((i + 0.5) * 630) / groups.length,
            color = colors[i % colors.length];
~~~


箱体高度至少 2 像素，常量组也能看见。SVG 的 role 和 aria-label 提供基本描述。这个图展示分布，不能从箱体是否重叠直接断言统计显著；检验结果仍读后端的 comparison。


## styles.css：所有样式区域

源文件：[styles.css](../../frontend/src/styles.css)，2,665 行。

CSS 代码通常不是“函数”。读一条规则时分成**选中谁、改哪个属性、值是多少**：

~~~css
/* 讲解语法示意，不是本项目新增代码 */
.类名 {
  属性: 值;
}
~~~

下面表格按源文件连续区域覆盖全部规则；同类颜色、字号、边距合在一起解释，完整数值可在源码附录逐条查。样式不会上传论文、检索数据库或计算统计，只影响展示与交互感受。

### 1. 第 1—542 行：底层规范、整体布局、通用组件

| 行号 | 全部规则组 | 行为 |
|---|---|---|
| 1—16 | Tailwind 三层、:root | 引入工具样式；统一字体、14px 基准、行高和四色变量 |
| 17—52 | *、body、button / input 等、a、disabled | border-box、去默认外边距、字体继承、按钮默认样式和禁用反馈 |
| 53—78 | h1—h4、p | 清默认 margin，设置标题层级 |
| 79—128 | 输入框、focus、checkbox、placeholder、focus-visible、summary | 边框圆角、聚焦提示、复选框尺寸、键盘可见焦点、折叠标记 |
| 129—178 | app、sidebar、brand、brand-mark、brand 文案 | flex 总布局；固定 235px 深色左栏；品牌块 |
| 179—234 | workspace-label、sidebar nav、nav-item / active / hover、nav-count | 导航纵排、选中状态、数量徽标 |
| 235—299 | sidebar-bottom、local-card、status-dot、user-row、avatar、local-pill | 左栏底部贴下、本地说明、用户信息 |
| 300—338 | workspace、topbar、project-switch、top-spacer | 内容避开左栏；顶栏粘在顶部；项目选择和弹性空白 |
| 339—393 | connection、online、content-layout、main、page-heading、breadcrumb | AI 状态样式、主区最大宽、标题说明 |
| 394—408 | row、between、center、wrap | 重复使用的横排与对齐工具 |
| 409—491 | button 各变体、text-button、icon-button、danger | 主 / 次 / 小按钮、全宽、hover、删除颜色 |
| 492—542 | muted、tiny、prewrap、badge 各色、eyebrow | 辅助文字、保留换行、状态小标签 |


**真实代码（摘录）：frontend/src/styles.css 第 1—19 行**

~~~css
@tailwind base;
@tailwind components;
@tailwind utilities;
:root {
  font-family: Inter, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
  color: #213c42;
  background: #f4f7f8;
  font-synthesis: none;
  font-size: 14px;
  line-height: 1.55;
  font-weight: 400;
  --teal: #278679;
  --dark: #142f33;
  --line: #e6ebed;
  --muted: #7d8c90;
}
* {
  box-sizing: border-box;
}
~~~


**真实代码（摘录）：frontend/src/styles.css 第 129—143 行**

~~~css
.app {
  display: flex;
  min-height: 100vh;
}
.sidebar {
  width: 235px;
  background: var(--dark);
  color: #d4dfe1;
  padding: 30px 18px 0;
  position: fixed;
  inset: 0 auto 0 0;
  display: flex;
  flex-direction: column;
  z-index: 30;
}
~~~


**真实代码（摘录）：frontend/src/styles.css 第 300—316 行**

~~~css
.workspace {
  margin-left: 235px;
  width: calc(100% - 235px);
  min-width: 0;
}
.topbar {
  height: 72px;
  background: #fff;
  border-bottom: 1px solid var(--line);
  padding: 0 34px;
  display: flex;
  align-items: center;
  gap: 17px;
  position: sticky;
  top: 0;
  z-index: 20;
}
~~~


几个容易误解的属性：

- position: fixed：相对窗口固定，例如左导航。
- position: sticky：滚动到规定位置后贴住，例如顶栏和桌面证据栏。
- flex: 1：占据剩余可用空间。
- min-width: 0：允许 flex / grid 子项真正收缩，避免长标题把整个页面撑破。
- z-index：控制叠放；toast 比弹窗更靠上，弹窗比普通导航更靠上。
- overflow-wrap: anywhere：超长词、哈希或英文路径可以换行。
- :hover / :focus-visible / :disabled：鼠标经过、键盘焦点、禁用三种状态，并不产生业务数据。

### 2. 第 543—1011 行：首页、卡片、空状态、提示

| 行号 | 全部规则组 | 行为 |
|---|---|---|
| 543—577 | research-banner、其标题说明、banner-tag | 淡绿项目横幅、标签 |
| 578—649 | banner-art、orbit 三层、center、point a/b/c | 用圆、边框、定位绘制装饰，不需要外部图片 |
| 650—711 | stats-grid、stat-card、stat-icon、list-icon 颜色 | 四列统计卡，真实数字的容器 |
| 712—767 | section-title、action-grid、action-card 及子项 | 三列研究入口、hover 边框、标题文案 |
| 768—798 | card、card-heading、two-col | 白色容器、标题行、双列布局 |
| 799—845 | list-row、list-icon、hypothesis、mini-empty | 最近实验列表、假设与简短空态 |
| 846—869 | demo-note、page-footer | 示例导入说明和页脚横排 |
| 870—929 | welcome、hero-icon、welcome-grid 及文案 | 新用户欢迎区域和三步说明 |
| 930—955 | empty、empty-icon、标题 / 说明 | 通用空数据状态 |
| 956—972 | loading、spin、@keyframes spin | 等待行与持续旋转的图标 |
| 973—1002 | alert、strong / p、warning / error、提示内按钮 | 不同语气的说明框 |
| 1003—1011 | space-top、pad、pad-x | 常用间距 |


**真实代码（摘录）：frontend/src/styles.css 第 650—679 行**

~~~css
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 15px;
  margin: 20px 0 30px;
}
.stat-card {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  padding: 20px 18px;
  display: flex;
  align-items: center;
  gap: 13px;
  min-width: 0;
}
.stat-card > svg {
  margin-left: auto;
  color: #b9c7c9;
}
.stat-card > div {
  min-width: 0;
}
.stat-card strong {
  font-size: 25px;
  line-height: 1.1;
  color: #2b474e;
  font-weight: 600;
  display: block;
}
~~~


**真实代码（摘录）：frontend/src/styles.css 第 956—972 行**

~~~css
.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 48px;
  color: #829c96;
  font-size: 12px;
}
.spin {
  animation: spin 1.1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
~~~


@keyframes spin 定义旋转终点，animation 用 1.1 秒线性无限重复。这个动画只表示“正在等待”，不是任务实际完成了百分之多少。

### 3. 第 1012—1485 行：论文、证据、问答、对比

| 行号 | 全部规则组 | 行为 |
|---|---|---|
| 1012—1022 | file-button、隐藏 file input、upload-zone input | 原生文件控件透明覆盖按钮区域，保留真正的选择能力 |
| 1023—1060 | search-card、search-input、filter-row、compact-input | 搜索横排、可换行筛选 |
| 1061—1094 | table-scroll、table、th、td、末行、check-cell | 横向滚动、表头、分隔、复选列 |
| 1095—1141 | paper-title、paper-icon、tag-wrap、inline-error | 论文信息行、标签、错误原因 |
| 1142—1164 | search-hit、hit-title、结果正文 | 原文命中卡，保留换行 |
| 1165—1198 | evidence 及其标题、摘录、按钮 | 桌面右侧 sticky 证据栏，独立滚动 |
| 1199—1222 | citations、citation-button、页码 span | 可换行引用集合、长标题省略 |
| 1223—1248 | ai-disclosure 及子项 | 模型启用与外发说明 |
| 1249—1297 | chat-layout、chat-card、messages、welcome、prompt-grid | 问答主区 + 历史侧区、空白提问引导 |
| 1298—1344 | chat-message、avatar、message-body、composer | 消息排布、输入区 |
| 1345—1379 | scope、summary、scope-options、inline | 论文范围下拉与表单内版本 |
| 1380—1424 | checkbox、history、history-item 及 active | 复选项、历史对话截断与选中样式 |
| 1425—1455 | compare-selection、select-paper、selected、子文案 | 两列论文选择卡 |
| 1456—1485 | comparison-grid、column、reading-field | 横向比较矩阵与结构化栏目 |


**真实代码（摘录）：frontend/src/styles.css 第 1165—1175 行**

~~~css
.evidence {
  width: 290px;
  flex-shrink: 0;
  position: sticky;
  top: 72px;
  height: calc(100vh - 72px);
  background: #fff;
  border-left: 1px solid #e4ece9;
  padding: 24px 20px;
  overflow: auto;
}
~~~


**真实代码（摘录）：frontend/src/styles.css 第 1249—1258 行**

~~~css
.chat-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 20px;
}
.chat-card {
  display: flex;
  flex-direction: column;
  min-height: 550px;
}
~~~


grid-template-columns: minmax(0, 1fr) 220px 表示主问答区吃剩余宽度、历史区固定 220px；minmax(0,...) 避免长消息把布局撑出屏幕。

### 4. 第 1486—1904 行：弹窗、阅读器、实验、图表

| 行号 | 全部规则组 | 行为 |
|---|---|---|
| 1486—1514 | modal-scrim、modal、wide | 固定遮罩、模糊底图、普通 / 宽阅读弹窗 |
| 1515—1530 | modal-head 及 h2 | 弹窗滚动时标题仍留在顶部 |
| 1531—1557 | form-body、field、名称 / 提示 / 控件 | 统一表单纵排、标签、提示 |
| 1558—1589 | form-grid、single / three、form-actions、checkbox-grid | 二列 / 一列 / 三列，底部操作，清洗列选择 |
| 1590—1602 | reader、pdf-pane | PDF 与信息双栏，最小高度和溢出约束 |
| 1603—1639 | pdf-toolbar、页码、pdf-canvas、canvas | 工具栏、内部滚动、画布自适应最大宽度 |
| 1640—1655 | reader-info、text-preview | 右侧滚动、提取文本换行 |
| 1656—1684 | tabs、active、small-tabs | 通用页签与阅读器小页签 |
| 1685—1731 | experiment-tabs、heading、details、section-tabs | 实验切换、条件展开、数据 / 结果页签 |
| 1732—1774 | upload-data、upload-zone、options | 文件区与工作表选项 |
| 1775—1801 | dataset-meta、label / select / span | 版本选择与哈希说明 |
| 1802—1826 | quality、details、table、confirmation | 数据质量详情与确认强调 |
| 1827—1853 | result-selector、analysis-provenance | 保存记录选择、版本与时间 |
| 1854—1873 | result-stats、number、stat-card small | 结果卡，长置信区间允许换行 |
| 1874—1904 | plot-tabs、chart、tooltip、box-chart / svg | 图形容器、悬浮说明、SVG 按宽缩放 |


**真实代码（摘录）：frontend/src/styles.css 第 1486—1514 行**

~~~css
.modal-scrim {
  position: fixed;
  inset: 0;
  background: #102f3266;
  backdrop-filter: blur(3px);
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
}
.modal {
  background: #fff;
  border: 1px solid #d8e6df;
  border-radius: 13px;
  box-shadow: 0 20px 90px #112d3240;
  width: 600px;
  max-width: 100%;
  max-height: 90vh;
  overflow: auto;
  outline: 0;
}
.modal.wide {
  width: 1330px;
  height: 90vh;
  display: flex;
  flex-direction: column;
  max-height: 95vh;
}
~~~


**真实代码（摘录）：frontend/src/styles.css 第 1590—1602 行**

~~~css
.reader {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  flex: 1;
  min-height: 0;
}
.pdf-pane {
  background: #ecf1f0;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}
~~~


**真实代码（摘录）：frontend/src/styles.css 第 1625—1639 行**

~~~css
.pdf-canvas {
  overflow: auto;
  flex: 1;
  padding: 24px;
  display: flex;
  align-items: flex-start;
  justify-content: center;
}
.pdf-canvas canvas {
  width: auto;
  max-width: 100%;
  height: auto;
  box-shadow: 0 3px 15px #1b40311a;
  background: #fff;
}
~~~


width / height 的 CSS 自适应只决定画布在页面上的显示尺寸；Reader 还会设置 canvas.width / height 的实际像素，两者作用不同。

### 5. 第 1905—2064 行：报告、设置、临时反馈

| 行号 | 全部规则组 | 行为 |
|---|---|---|
| 1905—1940 | reports-layout、list、item、active、子标题 | 报告列表与正文双列 |
| 1941—1964 | preview、download-row、markdown-report | 报告标题、下载排列、初始正文样式 |
| 1965—1999 | settings-layout、body、model-info、子项 | 模型信息与设置正文 |
| 2000—2013 | json-preview | 等宽字、可滚动的配置 / 处理记录 |
| 2014—2054 | toast、error、图标 / 关闭按钮 | 固定在底部的操作反馈，z-index=100 |
| 2055—2060 | mobile-menu、mobile-mask | 默认隐藏，进入小屏规则才出现 |
| 2061—2064 | disabled | 灰掉并禁用指针交互；只是 UI 提示，不代替后端校验 |

### 6. 第 2065—2606 行：全部响应式断点

@media 的意思是“在这个屏幕条件下应用下列覆盖规则”。下方规则与上方同时成立时，按选择器优先级和出现顺序决定最终值。

| 行号 | 条件 | 全部重要覆盖区域 |
|---|---|---|
| 2065—2085 | 宽度至少 1600px | 增加 main / topbar 留白、banner 高度、入口卡内边距、统计 / 入口列间隔 |
| 2086—2157 | 宽度至多 1250px | sidebar 缩到 205px 并同步 workspace；品牌 / 导航 / 留白 / 统计图标缩小；隐藏统计箭头；证据 250px；问答 / 阅读器 / 报告侧栏缩窄；版本信息竖排；三列表单变两列 |
| 2158—2222 | 至多 1050px | 统计两列；证据改右侧 fixed 覆盖层；双列卡改单列；问答历史隐藏；报告列表横滚；论文选择改单列；横幅装饰减弱；结果选择区竖排 |
| 2223—2315 | 至多 800px | 左栏移出屏幕，mobile-open 滑入；workspace 全宽；菜单 / 遮罩显示；顶栏 64px；阅读器上下排列；证据位置与新顶栏一致；toast 居中；上传区单列；欢迎区 / 示例说明调整 |
| 2316—2606 | 至多 560px | 项目选择缩窄并隐藏部分顶栏元素；主区缩边距；横幅装饰隐藏；入口卡单列；搜索 / 问答 / 提示缩字号；所有表单单列；弹窗与底部操作适配；欢迎步骤单列；数据版本纵排；清洗选项两列；结果卡 / 图形 / 下载 / 报告间距缩小；报告列表和对比矩阵限宽；证据 290px |

小屏导航最关键的真实代码：


**真实代码（摘录）：frontend/src/styles.css 第 2223—2246 行**

~~~css
@media (max-width: 800px) {
  .sidebar {
    width: 195px;
    transform: translateX(-100%);
    transition: transform 0.2s;
  }
  .sidebar.mobile-open {
    transform: translateX(0);
  }
  .workspace {
    margin: 0;
    width: 100%;
  }
  .mobile-menu {
    display: inline-grid;
  }
  .mobile-mask {
    display: block;
    position: fixed;
    inset: 0;
    background: #15372955;
    backdrop-filter: blur(2px);
    z-index: 29;
  }
~~~


这里界面不是重新写一套手机版，而是保留同一批组件，在较小宽度时换布局。历史对话侧栏在 1050px 以下被 display:none 隐藏，说明当前小屏能力有取舍，不应说所有桌面功能入口完全等价。

### 7. 第 2608—2665 行：渲染报告与设置指标的最终覆盖

第 2607 行为空行；后面是较晚加入的实际 Markdown 排版规则：

| 行号 | 规则 | 用途 |
|---|---|---|
| 2608—2613 | rendered-report | 把原先 pre-wrap 改 normal，让真正 Markdown 段落正常流动 |
| 2614—2626 | h1、h2、p | 正文标题层级、分节间距、分隔线 |
| 2627—2630 | ul / ol | 恢复列表缩进 |
| 2631—2636 | img | 图片最大宽 100%，等比例高度 |
| 2637—2642 | table | 报告表格可横向滚动 |
| 2643—2647 | blockquote | 引用左边框 |
| 2648—2651 | a | 链接颜色与下划线 |
| 2652—2665 | settings-metrics、p、strong | 按最小 180px 自动排设置指标卡 |


**真实代码（摘录）：frontend/src/styles.css 第 2608—2636 行**

~~~css
.rendered-report {
  font-family: inherit;
  white-space: normal;
  line-height: 1.85;
  overflow-wrap: anywhere;
}
.rendered-report h1 {
  font-size: 24px;
  margin-bottom: 24px;
}
.rendered-report h2 {
  margin-top: 34px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 10px;
}
.rendered-report p {
  margin: 10px 0;
}
.rendered-report ul,
.rendered-report ol {
  padding-left: 24px;
}
.rendered-report img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  margin: 16px 0;
}
~~~


**真实代码（摘录）：frontend/src/styles.css 第 2652—2665 行**

~~~css
.settings-metrics {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}
.settings-metrics p {
  background: #f5f8f8;
  padding: 14px;
  border-radius: 8px;
}
.settings-metrics strong {
  display: block;
  margin-top: 5px;
}
~~~


CSS 最后一段的 white-space: normal 会覆盖前面 markdown-report 的 pre-wrap；理解“后写的规则有时会覆盖前面的规则”，才能解释最终页面为什么和最初定义不同。

## 把一次点击连成完整调用链

不要只看单个函数。沿着一次真实用户操作追踪，会更容易建立整体认识。

### 路线 A：检索并打开引用

1. Library 的 query 输入 onChange → setQuery。
2. 提交表单 → search，携带 pid、selected、年份、标签。
3. api.ts 包装 POST /api/projects/{pid}/search。
4. 后端检索，返回 Citation[]。
5. Library setSearchResult，React 画摘录。
6. 点“查看证据” → onCite → App.openCitation → setCitation。
7. App 挂载 Evidence。
8. 点“打开原文对应页” → App.setReader({paperId, page})。
9. Reader 从同项目文件 API 加载 PDF，getPage(page) 画 canvas。

这条链里，PDF 页码来自后端保存的 Citation；前端没有用“搜索结果第几条”冒充 PDF 页码。

### 路线 B：保存一次分析并导出报告

1. 上传 File → FormData → 后端创建 DatasetVersion。
2. setDatasetId 选中新版本；config 重置为未确认。
3. selector 和各输入 onChange → update → confirmed=false。
4. 用户核对并勾选 → config.confirmed=true。
5. run 发送 {dataset_id, config}。
6. 后端验证、计算、保存 AnalysisRun，返回结果。
7. setAnalysis + panel=result → AnalysisResult。
8. 用户点“生成研究报告” → createReport 仅传 analysis_id。
9. Reports 获取已保存 Markdown；图表 URL 仍指向同一 analysis_id。
10. 下载 ZIP 向后端取复现包，浏览器不临时编造统计数字。

## 阅读本章时需要记住的边界

- **前端类型不是安全校验。** api<T> 只约定开发者预期；项目隔离、上传限制、分析设计校验和引用真实性检查在后端执行。
- **状态防护是局部实现。** 实验详情用请求序号与实验 ID 防止旧响应覆盖；PDF 绘制有取消任务。其他列表和写操作没有统一的 AbortController 机制，不能笼统称所有异步场景都彻底消除了竞态。
- **预览不等于全部。** DataTable 默认只展示前 15 行；分组候选来自 preview。后端对全量数据检查和计算。
- **绘图计算不等于科研推断。** 浏览器会算箱线图分位数和直方图频数；均值差、置信区间、t 值、p 值由后端固定函数决定。
- **有图不自动代表结论。** 箱线图、散点和直方图说明分布，不能仅靠外形宣布显著、实用或因果。
- **模型配置不写在网页里。** 设置页展示配置状态与开关，真实密钥留在后端环境变量；本章不读取或展示真实 .env。
- **源码中的功能边界需要如实看待。** 当前实验表单是创建；首页接收但不渲染 recent_reports 列表；问答非流式；小屏隐藏历史侧栏；统一网络取消与完整焦点恢复尚未实现。
- **本章是解释性文档。** 为了不因讲解改变现有行为，本次没有修改业务文件，也没有重新执行应用测试。测试章节与实际验收记录应分别阅读，不能把“写完讲解”当成新增测试通过。

## 本章覆盖核对表

| 文件 | 行数 | 覆盖方式 |
|---|---:|---|
| frontend/src/App.tsx | 2,043 | 全部 9 个组件函数、内嵌事件函数、全部 effect、类型 / 常量、全部 JSX 功能区 |
| frontend/src/Experiments.tsx | 1,489 | 主组件、创建表单、质量 / 结果 / 图形组件、quantile、全部事件和 effect、完整表单字段 |
| frontend/src/components.tsx | 653 | 10 个导出组件、statusLabel、worker、内部 nameControls / render、全部 effect |
| frontend/src/api.ts | 186 | 全部 14 个数据类型、fmt / date / api / json |
| frontend/src/numeric.ts | 112 | formatNumber、两个 Histogram 类型、makeHistogram 和内部 boundary |
| frontend/src/styles.css | 2,665 | 全部连续区域、全部响应式断点、最终覆盖 |
| frontend/src/main.tsx | 9 | 完整入口 |
| frontend/src/vite-env.d.ts | 1 | 完整声明 |
| frontend/index.html | 13 | 完整 HTML |
| frontend/vite.config.ts | 11 | 完整开发代理与构建配置 |
| frontend/tsconfig.json | 17 | 全部编译选项 |
| frontend/tailwind.config.js | 5 | 完整配置 |
| frontend/postcss.config.js | 1 | 完整配置 |
| frontend/copy-pdf-assets.mjs | 10 | 完整资源复制脚本 |
| frontend/package.json | 37 | 全部脚本、运行与开发依赖 |
| **合计** | **7,252** | 关键真实源码摘录 + 完整定义与行为索引；全部原文在源码附录 |

建议第一次读的顺序：main.tsx → api.ts → components.tsx 的 Field → ProjectForm → Library.search → Experiments.run → AnalysisResult。先打通一条链，再回来看所有 CSS 数值，比从两千多行样式开头逐字符背诵更容易理解。
