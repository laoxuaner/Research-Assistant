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

def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADER)
        writer.writerows(rows)

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
