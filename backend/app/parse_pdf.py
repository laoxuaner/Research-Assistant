"""Isolated parser: subprocess timeout keeps malformed PDFs from blocking the API."""
import json
import sys
from pypdf import PdfReader

def parse(path, max_pages):
    reader = PdfReader(path)
    if reader.is_encrypted:
        raise ValueError("加密 PDF 暂不支持，请先提供可读取版本")
    if len(reader.pages) > max_pages:
        raise ValueError(f"PDF 超过页数限制（{max_pages} 页）")
    pages = []
    for i, page in enumerate(reader.pages):
        contents = page.get_contents()
        if contents and len(contents.get_data()) > 20 * 1024 * 1024:
            raise ValueError(f"第 {i+1} 页内容流过大")
        value = page.extract_text(extraction_mode="layout") or ""
        if len(value) > 200000:
            raise ValueError(f"第 {i+1} 页提取文本过大")
        pages.append({"page_number": i+1, "text": value.replace("\x00", "")})
    title = str(reader.metadata.title or "").strip() if reader.metadata else ""
    return {"pages": pages, "title": title[:500]}

if __name__ == "__main__":
    try:
        print(json.dumps(parse(sys.argv[1], int(sys.argv[2])), ensure_ascii=True))
    except Exception as exc:
        print(json.dumps({"error": str(exc)[:400]}, ensure_ascii=True))
        sys.exit(2)
