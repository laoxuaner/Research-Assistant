"""Build a local, offline source reader and exact source appendices.

Documentation only: reads an explicit allowlist, never .env or data/, never edits app code.
Run: .venv/Scripts/python.exe docs/code-guide/build_code_book.py
"""
from __future__ import annotations
import ast
import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
CHAPTERS = [
    ("00-start-here.md", "先读：语法、目录与完整调用路线"),
    ("01-core-database.md", "启动、配置、数据库与输入校验"),
    ("02-papers-ai.md", "论文、检索、AI 与引用"),
    ("03-frontend.md", "全部前端、组件、状态与样式"),
    ("04-statistics-exports.md", "数据版本、统计与报告复现"),
    ("05-tests-scripts.md", "全部测试、启动脚本与示例生成"),
]

def collect_paths():
    paths = set()
    for folder in ("backend/app", "backend/tests", "scripts"):
        paths.update(p for p in (ROOT / folder).glob("*") if p.suffix in {".py", ".ps1"})
    for folder in ("frontend/src", "frontend/tests"):
        paths.update(p for p in (ROOT / folder).glob("*") if p.suffix in {".ts", ".tsx", ".css"})
    for name in ("index.html", "vite.config.ts", "tsconfig.json", "tailwind.config.js",
                 "postcss.config.js", "copy-pdf-assets.mjs", "package.json", "package-lock.json",
                 "playwright.config.ts"):
        paths.add(ROOT / "frontend" / name)
    for name in ("pyproject.toml", "requirements.txt", "requirements.lock.txt", ".env.example", ".gitignore"):
        paths.add(ROOT / name)
    paths.update((ROOT / "samples").glob("*.csv"))
    paths.add(ROOT / "samples/expected_results.json")
    paths.add(ROOT / "docs/guide-example-statistics.py")
    paths.add(Path(__file__).resolve())
    return sorted((p for p in paths if p.is_file()), key=lambda p: p.relative_to(ROOT).as_posix())

def line_count(content):
    return len(content.splitlines())

def definitions(path, content):
    result = []
    if path.suffix == ".py":
        tree = ast.parse(content)
        def visit(nodes, prefix=""):
            for node in nodes:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = prefix + node.name
                    result.append({"name": name, "line": node.lineno, "end": node.end_lineno})
                    visit(node.body, name + ".")
        visit(tree.body)
    else:
        patterns = [
            r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([\w-]+)",
            r"^\s*function\s+([\w-]+)",
            r"^\s*(?:export\s+)?(?:type|interface|class)\s+(\w+)",
            r"^\s*(?:export\s+)?(?:const|let)\s+(\w+)\s*=",
            r'^\s*test\("([^"]+)"',
        ]
        for number, line in enumerate(content.splitlines(), 1):
            for pattern in patterns:
                match = re.search(pattern, line, re.I if path.suffix == ".ps1" else 0)
                if match:
                    result.append({"name": match.group(1), "line": number})
                    break
    return result

def category(relative):
    if relative.endswith("package-lock.json") or relative.endswith("requirements.lock.txt"):
        return "依赖锁文件"
    if relative.startswith("samples/"):
        return "测试数据"
    if relative.startswith("backend/tests/") or relative.startswith("frontend/tests/"):
        return "测试"
    if relative.startswith("backend/app/"):
        return "后端"
    if relative.startswith("frontend/src/"):
        return "前端"
    if relative.startswith("scripts/"):
        return "脚本"
    if relative.startswith("docs/"):
        return "教学工具"
    return "配置"

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source_dir = OUT / "source"
    source_dir.mkdir(exist_ok=True)
    entries = []
    fence = chr(96) * 4
    language = {".py":"python", ".ps1":"powershell", ".ts":"typescript",
                ".tsx":"tsx", ".css":"css", ".json":"json", ".html":"html",
                ".js":"javascript", ".mjs":"javascript", ".toml":"toml", ".csv":"csv"}
    for index, path in enumerate(collect_paths(), 1):
        blob = path.read_bytes()
        content = blob.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
        rel = path.relative_to(ROOT).as_posix()
        entry = {"path": rel, "content": content, "lines": line_count(content),
                 "sha256": hashlib.sha256(blob).hexdigest(), "category": category(rel),
                 "definitions": definitions(path, content), "source_page": f"source/{index:02d}.md"}
        entries.append(entry)
        origin = ROOT.as_posix() + "/" + rel
        document = "\n".join([
            "# " + rel, "", f"[打开原文件]({origin}) · [返回目录](../README.md)",
            "", f"类别：{entry['category']}；{entry['lines']} 行。以下为生成时的完整源文本，未省略代码。",
            "仅归一化 UTF-8 BOM 编码标记及换行格式，不改动代码；SHA-256 按原始字节计算：" + entry["sha256"],
            "", fence + language.get(path.suffix, "text"), content.rstrip("\n\r"), fence, "",
        ])
        (OUT / entry["source_page"]).write_text(document, encoding="utf-8")

    total = sum(e["lines"] for e in entries)
    own = [e for e in entries if e["category"] not in {"依赖锁文件", "测试数据"}]
    manifest = {"file_count":len(entries), "line_count":total,
                "code_config_file_count":len(own), "code_config_lines":sum(e["lines"] for e in own),
                "scope":"项目自有源码、测试、脚本、配置及文本测试材料；排除第三方依赖、PDF.js字体/字符表、缓存、构建产物、真实.env与用户data。",
                "files":[{k:v for k,v in e.items() if k != "content"} for e in entries]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = ["| 文件 | 类别 | 行数 | 完整代码 |", "| --- | --- | ---: | --- |"]
    for e in entries:
        rows.append(f"| {e['path']} | {e['category']} | {e['lines']} | [展开]({e['source_page']}) |")
    intro = [
        "# 研知：完整源码图解与逐文件解读", "",
        "适合先阅读过使用指南、准备开始学习代码的读者。讲解按实际源码编写，节选处明确标注；完整原代码在附录中展示。",
        "", f"本次收录 {len(entries)} 个文件，共 {total:,} 行；其中自有代码与配置 {len(own)} 个文件、{sum(e['lines'] for e in own):,} 行，另外包含依赖锁文件和文本测试材料。",
        "", "## 阅读入口", "",
        "- [离线源码阅读器](code-reader.html)：用浏览器打开，可切换文件、按文件名或源码内容筛选、跳到函数/行号、复制完整代码。无需启动服务或联网。",
        "- [完整源码合订本](ALL_SOURCE.md)：所有收录文件的完整文本。",
        "- [覆盖清单与源码指纹](manifest.json)：文件、行数、函数/类型定位和 SHA-256。",
        "", "## 按学习顺序阅读", "",
    ]
    intro.extend(f"{i}. [{title}]({filename})" for i,(filename,title) in enumerate(CHAPTERS,1))
    intro.extend(["", "建议每次只读一个章节：先看它解决的问题，再看代码，最后顺着函数调用找到下一层。文档只补充讲解，不改变应用行为。",
                  "", "## 范围说明", "", manifest["scope"],
                  "依赖锁文件解释整体作用并保留全文，不逐条讲解第三方软件包内部实现。已有 README 与验收文档是说明材料，原始 PDF/XLSX 是二进制样例，均可在项目目录查看。",
                  "源码附录是生成时快照。以后修改应用后，运行构建脚本即可刷新；讲解中的行号也应随之复核。",
                  "", "## 所有文件与完整代码", ""] + rows + [""])
    (OUT / "README.md").write_text("\n".join(intro), encoding="utf-8")
    combined = ["# 全部收录源码", "", "[学习目录](README.md) · [离线源码阅读器](code-reader.html)",
                "", "每个文件完整展示，无省略号替代代码。依赖与测试材料见学习目录范围说明。", ""]
    for e in entries:
        combined += ["## " + e["path"], "", fence + language.get(Path(e["path"]).suffix,"text"),
                     e["content"].rstrip("\n\r"), fence, ""]
    (OUT / "ALL_SOURCE.md").write_text("\n".join(combined), encoding="utf-8")

    data = json.dumps(entries, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    chapter_links = "".join('<a href="' + html.escape(name, quote=True) + '">' + html.escape(title) + "</a>" for name,title in CHAPTERS)
    page = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>研知 · 完整源码阅读器</title>
<style>
:root{font-family:system-ui,"Microsoft YaHei",sans-serif;color:#213c38;background:#f4f7f5;color-scheme:light}
*{box-sizing:border-box}body{margin:0}header{padding:16px 24px;background:#153b37;color:#fff;display:flex;align-items:center;gap:20px;flex-wrap:wrap}
header h1{font-size:19px;margin:0}header p{font-size:12px;margin:0;color:#c7ded6}
a{color:#16776b}header a{color:#c7ede1}button,input,select{font:inherit}button{cursor:pointer;background:white;color:#185d53;border:1px solid #adcac2;border-radius:6px;padding:7px 12px}
.layout{display:grid;grid-template-columns:300px minmax(0,1fr);height:calc(100vh - 78px)}
aside{border-right:1px solid #d4e1da;overflow:auto;padding:18px 12px}label{font-size:12px;display:block;margin:8px 0}
input{width:100%;padding:9px;border:1px solid #b6cdc4;border-radius:6px}
.hint{color:#667c74;font-size:12px;line-height:1.7}#files{display:flex;flex-direction:column;gap:4px}
.file{text-align:left;word-break:break-word;line-height:1.45;border-color:transparent;background:transparent;padding:8px;font-size:12px}
.file.active{background:#d9ece4;border-color:#84b5a7}.file small{display:block;color:#617b70}
main{min-width:0;min-height:0;display:flex;flex-direction:column;background:white}.toolbar{border-bottom:1px solid #d7e4dc;padding:14px 18px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
#path{font-size:14px;margin:0;overflow-wrap:anywhere;width:100%}#meta{font-size:12px;color:#698075}
#jump{min-width:180px;max-width:360px;padding:6px}#lineInput{width:85px;padding:6px}
#source{overflow:auto;flex:1;min-height:0;margin:0;padding:14px 0 60px;tab-size:4;font:13px/1.65 Consolas,"Cascadia Mono",monospace;color:#20332d}
.line{display:flex;min-width:max-content}.line:hover{background:#f4f8ef}.line.target{background:#fff0c6}
.number{display:inline-block;flex:0 0 64px;text-align:right;padding-right:18px;color:#8c9d94;user-select:none;cursor:pointer}
.text{white-space:pre;padding-right:30px}details{margin:12px 0;font-size:12px}details a{display:block;margin:10px 0;line-height:1.5}
@media(max-width:750px){.layout{grid-template-columns:1fr;height:auto}aside{max-height:280px;border-bottom:1px solid #ccc}#source{height:70vh}.toolbar{padding:12px}header{padding:14px}}
</style></head><body>
<header><h1>研知 · 完整源码阅读器</h1><p>原代码全文 · 行号定位 · 函数导航 · 全库文本筛选</p><a href="README.md">学习目录</a></header>
<div class="layout"><aside>
<label for="filter">筛选文件名或源码内容</label><input id="filter" type="search" placeholder="例如 analyze / paper_id / useEffect">
<p id="count" class="hint"></p><details><summary>逐文件讲解章节</summary>CHAPTER_LINKS</details><div id="files"></div>
</aside><main><div class="toolbar">
<h2 id="path"></h2><span id="meta"></span><select id="jump" aria-label="跳到函数或定义"></select>
<label>行号 <input id="lineInput" type="number" min="1" aria-label="目标行号"></label><button id="go">跳转</button>
<button id="copy">复制完整代码</button><span id="notice" role="status" class="hint"></span>
</div><pre id="source" aria-label="完整源代码"></pre></main></div>
<script id="source-data" type="application/json">SOURCE_DATA</script>
<script>
"use strict";
const entries=JSON.parse(document.getElementById("source-data").textContent);
const el=id=>document.getElementById(id);
let current=entries[0], activeLine=1;
function showFiles(){
 const q=el("filter").value.trim().toLocaleLowerCase();
 const found=entries.filter(e=>!q||e.path.toLocaleLowerCase().includes(q)||e.content.toLocaleLowerCase().includes(q));
 el("count").textContent="显示 "+found.length+" / "+entries.length+" 个文件；包含完整测试、脚本与配置。";
 el("files").replaceChildren(...found.map(e=>{
  const b=document.createElement("button");b.className="file"+(current.path===e.path?" active":"");
  const name=document.createElement("span");name.textContent=e.path;b.appendChild(name);
  const info=document.createElement("small");info.textContent=e.category+" · "+e.lines+" 行";b.appendChild(info);
  b.onclick=()=>{selectFile(e,1);location.hash=new URLSearchParams({file:e.path,line:"1"}).toString()};return b;
 }));
}
function selectFile(entry,line){
 current=entry;el("path").textContent=entry.path;
 el("meta").textContent=entry.category+" · "+entry.lines+" 行 · SHA-256 "+entry.sha256.slice(0,12)+"…";
 const lines=entry.content.split(/\r?\n/);if(lines.at(-1)==="")lines.pop();
 el("source").replaceChildren(...lines.map((text,index)=>{
  const row=document.createElement("span");row.className="line";row.id="L"+(index+1);
  const n=document.createElement("span");n.className="number";n.textContent=String(index+1);
  n.onclick=()=>{location.hash=new URLSearchParams({file:entry.path,line:String(index+1)}).toString()};
  const code=document.createElement("span");code.className="text";code.textContent=text||" ";
  row.append(n,code);return row;
 }));
 const placeholder=document.createElement("option");placeholder.value="";placeholder.textContent="跳到函数 / 类型 / 定义";
 const options=entry.definitions.map(d=>{const o=document.createElement("option");o.value=String(d.line);o.textContent=d.name+" · L"+d.line;return o});
 el("jump").replaceChildren(placeholder,...options);el("lineInput").max=String(entry.lines);el("notice").textContent="";
 showFiles();jumpTo(line);
}
function jumpTo(line){
 const max=Math.max(1,current.lines);const value=Math.min(max,Math.max(1,Number(line)||1));activeLine=value;
 el("source").querySelectorAll(".target").forEach(n=>n.classList.remove("target"));
 const target=el("L"+value);if(target){target.classList.add("target");el("source").scrollTop=target.offsetTop-el("source").offsetTop-30}
 el("lineInput").value=String(value);
}
function restore(){
 const p=new URLSearchParams(location.hash.slice(1));const e=entries.find(e=>e.path===p.get("file"))||entries[0];
 selectFile(e,Number(p.get("line"))||1);
}
el("filter").addEventListener("input",showFiles);
el("go").onclick=()=>{jumpTo(el("lineInput").value);location.hash=new URLSearchParams({file:current.path,line:String(activeLine)}).toString()};
el("jump").onchange=()=>{if(el("jump").value){jumpTo(el("jump").value);location.hash=new URLSearchParams({file:current.path,line:String(activeLine)}).toString()}};
el("copy").onclick=async()=>{
 try{if(!navigator.clipboard)throw Error("clipboard unavailable");await navigator.clipboard.writeText(current.content);el("notice").textContent="已复制完整代码";}
 catch{el("notice").textContent="浏览器未允许复制，请在代码区域手动选择复制，或打开原文件。"}
};
window.addEventListener("hashchange",restore);restore();
</script></body></html>'''
    page = page.replace("CHAPTER_LINKS",chapter_links).replace("SOURCE_DATA",data)
    (OUT / "code-reader.html").write_text(page,encoding="utf-8")
    # Verify every displayed source snapshot against the current allowlisted original.
    for entry in entries:
        original = ROOT / entry["path"]
        assert hashlib.sha256(original.read_bytes()).hexdigest() == entry["sha256"]
        assert original.read_text(encoding="utf-8-sig") == entry["content"]
        assert entry["content"].rstrip("\n\r") in (OUT / entry["source_page"]).read_text(encoding="utf-8")
    print(json.dumps({k:v for k,v in manifest.items() if k!="files"},ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()
