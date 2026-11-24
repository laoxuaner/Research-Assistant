import csv
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from app.exports import build_export, build_markdown, render_plot
from app.stats_engine import AnalysisConfig, analyze, apply_transforms, read_dataset


def fixture_context(frame, **dataset_changes):
    config = AnalysisConfig(
        group_column="group", metric_column="value", group_a="A", group_b="B",
        design="independent", sample_id_column="id", experimental_unit="subject",
        confirmed=True, missing_policy="drop", unit="ms",
    )
    result = analyze(frame, config)
    dataset = {
        "id": "version-1", "filename": "experiment.csv", "sha256": "version-hash",
        "sheet": None, "transform": {"steps": []},
    }
    dataset.update(dataset_changes)
    return {
        "project": {"name": "测试项目", "question": "对比两组响应", "hypothesis": "B 组响应存在差异"},
        "experiment": {"name": "测试实验", "hypothesis": "示例假设", "conditions": "相同测量协议"},
        "dataset": dataset,
        "analysis": {"id": "analysis-1", "config": config.model_dump(), "result": result},
        "citations": [{"paper_id": "paper-1", "chunk_id": "chunk-1", "title": "测试材料", "page_number": 2, "quote": "This is synthetic test evidence."}],
        "report_title": "测试报告", "versions": {"code_version": "test"},
    }


def frame():
    return pd.DataFrame({
        "id": ["a1", "a2", "a3", "b1", "b2", "b3"],
        "group": ["A"] * 3 + ["B"] * 3, "value": [1, 2, 3, 3, 5, 6],
    })


@pytest.mark.parametrize("kind", ["points", "box", "hist"])
def test_plot_is_valid_png_with_real_data(kind):
    context = fixture_context(frame())
    image = render_plot(context["analysis"]["result"], kind)
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(image) > 10000


def test_report_uses_saved_numbers_and_evidence():
    context = fixture_context(frame())
    markdown = build_markdown(context)
    assert "# 测试报告" in markdown
    assert "测试材料，PDF 第 2 页" in markdown
    assert "This is synthetic test evidence." in markdown
    assert "chunk-1" in markdown
    assert "| A | 3 | 2 | 2 | 1 | 1 | 3 |" in markdown
    assert "统计显著性不能直接解释为实际价值" in markdown
    assert "95% 双侧" in markdown
    assert "original/" in markdown


def test_unsupported_design_report_has_no_fake_pvalue():
    source = frame()
    source.loc[0:2, "value"] = 0
    context = fixture_context(source)
    markdown = build_markdown(context)
    assert "unsupported" in markdown
    assert "常量" in markdown
    assert "p 值：" not in markdown


def write_bundle(files, folder):
    for relative, payload in files.items():
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def run_reproduction(folder):
    isolated_environment = dict(os.environ)
    isolated_environment.pop("PYTHONPATH", None)
    isolated_environment.pop("PYTHONHOME", None)
    return subprocess.run(
        [sys.executable, str(folder / "reproduce.py")], cwd=str(folder),
        env=isolated_environment, capture_output=True, text=True, timeout=90,
    )


def test_self_contained_export_replays_original_cleaning_chain(tmp_path):
    original_frame = pd.concat([frame(), frame().iloc[[0]], pd.DataFrame({"id": ["bad"], "group": ["A"], "value": [None]})], ignore_index=True)
    original = tmp_path / "source.csv"
    original_frame.to_csv(original, index=False)
    transform = {"steps": [
        {"drop_duplicate_rows": True},
        {"drop_missing_columns": ["value"]},
    ], "sheet": None}
    parsed, _ = read_dataset(original)
    cleaned, audit = apply_transforms(parsed, transform)
    assert len(cleaned) == 6
    assert len(audit) == 2
    context = fixture_context(cleaned, transform=transform)
    files = build_export(context, original)
    required = {
        "original/data.csv", "report.md", "summary.csv", "plot.png", "box.png",
        "histogram.png", "reproduce.py", "stats_engine.py", "analysis_config.json",
        "saved_result.json", "provenance.json", "requirements.txt",
    }
    assert required <= set(files)
    assert files["original/data.csv"] == original.read_bytes()
    manifest = json.loads(files["provenance.json"])
    assert manifest["effective_rows"] == 6
    assert manifest["transform"] == transform
    assert all("==" in line for line in files["requirements.txt"].decode().splitlines())
    extracted = tmp_path / "isolated"
    extracted.mkdir()
    write_bundle(files, extracted)
    completed = run_reproduction(extracted)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "REPRODUCTION PASSED" in completed.stdout
    assert json.loads((extracted / "reproduced_result.json").read_text(encoding="utf-8")) == context["analysis"]["result"]
    restored_audit = json.loads((extracted / "reproduced_cleaning_audit.json").read_text(encoding="utf-8"))
    assert restored_audit == audit
    # A changed input must never silently produce a successful reproduction.
    (extracted / "original" / "data.csv").write_text("changed", encoding="utf-8")
    changed = run_reproduction(extracted)
    assert changed.returncode != 0
    assert "Original data hash does not match" in changed.stderr


def test_xlsx_selected_sheet_reproduces(tmp_path):
    original = tmp_path / "source.xlsx"
    with pd.ExcelWriter(original, engine="openpyxl") as book:
        pd.DataFrame({"unused": [1]}).to_excel(book, sheet_name="ignore", index=False)
        frame().to_excel(book, sheet_name="实验", index=False)
    source, _ = read_dataset(original, sheet="实验")
    context = fixture_context(source, filename="测试.xlsx", sheet="实验", transform={"steps": [], "sheet": "实验"})
    files = build_export(context, original)
    extracted = tmp_path / "xlsx_reproduction"
    extracted.mkdir()
    write_bundle(files, extracted)
    completed = run_reproduction(extracted)
    assert completed.returncode == 0, completed.stderr + completed.stdout


def test_export_rejects_original_hash_mismatch(tmp_path):
    original = tmp_path / "source.csv"
    frame().to_csv(original, index=False)
    context = fixture_context(frame(), original_sha256="tampered")
    with pytest.raises(ValueError, match="哈希"):
        build_export(context, original)


def test_csv_summary_uses_same_saved_numbers_and_escapes_formulas(tmp_path):
    source = frame()
    source["group"] = source["group"].replace("A", "=SUM(1,2)")
    config = AnalysisConfig(group_column="group", metric_column="value", group_a="=SUM(1,2)", group_b="B")
    result = analyze(source, config)
    original = tmp_path / "source.csv"
    source.to_csv(original, index=False)
    context = fixture_context(frame())
    context["analysis"] = {"id": "a", "config": config.model_dump(), "result": result}
    files = build_export(context, original)
    rows = list(csv.DictReader(io.StringIO(files["summary.csv"].decode("utf-8-sig"))))
    assert rows[0]["group"] == "'=SUM(1,2)"
    assert float(rows[0]["mean"]) == result["summary"][0]["mean"]

def test_cleaned_xlsx_export_keeps_original_extension_and_literal_ids(tmp_path):
    source = tmp_path / "untouched.xlsx"
    original_frame = pd.DataFrame({
        "id": ["001", "002", "003", "004", "005", "006", "bad"],
        "group": ["A"] * 3 + ["B"] * 3 + ["A"],
        "value": [1.0000000000000002, 2.25, 3.1, 3.5, 5.7, 6.8, None],
    })
    original_frame.to_excel(source, sheet_name="原始", index=False)
    original, _ = read_dataset(source, sheet="原始")
    transform = {"sheet": "原始", "steps": [{"drop_missing_columns": ["value"]}]}
    cleaned, _ = apply_transforms(original, transform)
    persisted = tmp_path / "cleaned.csv"
    cleaned.to_csv(persisted, index=False, encoding="utf-8-sig")
    reloaded, _ = read_dataset(persisted)
    pd.testing.assert_frame_equal(cleaned, reloaded)
    context = fixture_context(cleaned, filename="original-cleaned.csv", sheet=None, transform=transform)
    files = build_export(context, source)
    assert "original/data.xlsx" in files
    assert "original/data.csv" not in files
    destination = tmp_path / "original_xlsx_reproduction"
    destination.mkdir()
    write_bundle(files, destination)
    completed = run_reproduction(destination)
    assert completed.returncode == 0, completed.stderr + completed.stdout


def test_saved_engine_and_versions_are_exported_instead_of_current_runtime(tmp_path):
    import hashlib
    source = tmp_path / "raw.csv"
    frame().to_csv(source, index=False)
    context = fixture_context(frame())
    engine_source = (Path(__file__).resolve().parents[1] / "app" / "stats_engine.py").read_text(encoding="utf-8")
    engine_source += "\n# historical snapshot\n"
    digest = hashlib.sha256(engine_source.encode("utf-8")).hexdigest()
    context["analysis_engine_source"] = engine_source
    context["analysis"]["provenance"] = {
        "analysis_code_sha256": digest, "app_version": "old-app",
        "versions": {"numpy": "old-version"},
    }
    files = build_export(context, source)
    assert files["stats_engine.py"].decode("utf-8") == engine_source
    assert "numpy==old-version\n" in files["requirements.txt"].decode("ascii")
    provenance = json.loads(files["provenance.json"])
    assert provenance["stats_engine_sha256"] == digest
    assert provenance["code_version"] == "old-app"
    context["analysis"]["provenance"]["analysis_code_sha256"] = "different"
    with pytest.raises(ValueError, match="代码"):
        build_export(context, source)
