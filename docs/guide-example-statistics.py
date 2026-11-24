"""Plot the actual teaching dataset using the project's statistics engine.

Run with the project .venv Python. Only the adjacent PNG is written.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.stats_engine import analyze, read_dataset


def main() -> None:
    frame, _ = read_dataset(ROOT / "samples" / "independent.csv")
    result = analyze(frame, {
        "group_column": "group", "metric_column": "score",
        "group_a": "A", "group_b": "B", "design": "independent",
        "experimental_unit": "每个 sample_id 代表一个独立教学样本",
        "sample_id_column": "sample_id", "missing_policy": "error",
        "alternative": "two-sided", "confirmed": True,
    })
    comp = result["comparison"]
    assert comp["status"] == "completed", comp
    summaries = {s["group"]: s for s in result["summary"]}
    assert [summaries[g]["n"] for g in ["A", "B"]] == [5, 5]
    assert np.allclose([summaries[g]["mean"] for g in ["A", "B"]], [3, 5])

    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if not font_path.exists():
        raise FileNotFoundError("本图要求 Windows 微软雅黑：" + str(font_path))
    font = FontProperties(fname=str(font_path))
    bold = FontProperties(fname=str(font_path), weight="bold")
    plt.rcParams.update({"font.family": font.get_name(), "axes.unicode_minus": False})

    ink, muted, grid = "#19332f", "#60746e", "#e4ebe5"
    teal, blue, orange = "#177b70", "#4277b3", "#a66522"
    fig = plt.figure(figsize=(14, 6), dpi=100, facecolor="#f6f8f4")
    fig.text(.045, .925, "看懂实验结果：差值之外，还要看不确定性",
             color=ink, fontproperties=bold, fontsize=22)
    fig.text(.045, .87,
             "独立样本 · Welch t 检验（双侧）  |  数据与计算均来自本项目的示例文件",
             color=muted, fontproperties=font, fontsize=12)

    left = fig.add_axes([.065, .285, .36, .45], facecolor="white")
    right = fig.add_axes([.53, .285, .425, .45], facecolor="white")
    for ax in [left, right]:
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(axis="both", colors=muted, labelsize=11, length=0, pad=9)
        ax.set_axisbelow(True)

    left.set_title("① 先看每一个原始样本", loc="left", pad=21,
                   color=ink, fontproperties=FontProperties(fname=str(font_path), size=16, weight="bold"))
    offsets = np.array([-.075, .04, -.015, .075, -.04])
    for pos, group, color in [(0, "A", teal), (1, "B", blue)]:
        values = np.array([p["value"] for p in result["points"] if p["group"] == group])
        left.scatter(pos + offsets, values, s=95, color=color,
                     edgecolors="white", linewidths=1.6, zorder=4)
        mean = summaries[group]["mean"]
        left.plot([pos-.23, pos+.23], [mean, mean], color=color,
                  linewidth=3, solid_capstyle="round", zorder=3)
        left.text(pos+.26, mean, f"均值 {mean:g}", va="center", color=color,
                  fontsize=12, fontproperties=bold)
    left.set_xlim(-.55, 1.77)
    left.set_ylim(0, 8)
    left.set_xticks([0, 1], ["A 组\nn = 5", "B 组\nn = 5"])
    left.set_yticks([0, 2, 4, 6, 8])
    left.grid(axis="y", color=grid, linewidth=.8)
    left.set_ylabel("示例指标（无单位）", fontproperties=font,
                    color=muted, labelpad=12, fontsize=11)
    left.text(.02, .965, "一个点 = 一个独立样本；短横线 = 该组平均值",
              transform=left.transAxes, va="top", fontsize=10,
              color=muted, fontproperties=font)

    right.set_title("② 再看两组均值差：B − A", loc="left", pad=21,
                    color=ink, fontproperties=FontProperties(fname=str(font_path), size=16, weight="bold"))
    lo, hi, delta = comp["ci_low"], comp["ci_high"], comp["difference"]
    right.set_xlim(-1.2, 5.1)
    right.set_ylim(0, 1)
    right.axvline(0, color=orange, linewidth=1.7,
                  linestyle=(0, (4, 4)), zorder=1)
    right.text(0, .94, "零差值线", ha="center", va="top",
               color=orange, fontproperties=font, fontsize=11)
    y = .55
    right.plot([lo, hi], [y, y], color=teal, linewidth=5,
               solid_capstyle="round", zorder=3)
    right.vlines([lo, hi], y-.055, y+.055, color=teal, linewidth=2, zorder=3)
    right.scatter([delta], [y], color=teal, edgecolors="white",
                  linewidths=2, s=180, zorder=4)
    right.text(delta, y+.14, f"差值估计 = {delta:g}", ha="center",
               color=ink, fontproperties=bold, fontsize=13)
    right.text(lo, y-.105, f"{lo:.3f}", ha="center", va="top", color=muted, fontsize=11)
    right.text(hi, y-.105, f"{hi:.3f}", ha="center", va="top", color=muted, fontsize=11)
    right.text(.5, .19, "线段 = 均值差的 95% 置信区间",
               transform=right.transAxes, ha="center", color=muted,
               fontproperties=font, fontsize=11)
    right.text(.5, .075, f"区间包含 0   ·   p = {comp['pvalue']:.3f}",
               transform=right.transAxes, ha="center", color=orange,
               fontproperties=bold, fontsize=13)
    right.set_xticks([-1, 0, 1, 2, 3, 4, 5])
    right.set_yticks([])
    right.grid(axis="x", color=grid, linewidth=.8)
    right.set_xlabel("均值差（B − A）", fontproperties=font,
                     fontsize=11, color=muted, labelpad=11)

    fig.text(.5, .112,
             "这次观察到 B 组均值高 2，但当前样本还不足以确认总体均值不同。",
             ha="center", color=ink, fontproperties=bold, fontsize=14,
             bbox={"facecolor": "#e9f0e9", "edgecolor": "none",
                   "boxstyle": "round,pad=.7"})
    fig.text(.5, .035,
             "合成教学数据，不代表真实研究。未达到常用的 0.05 显著性阈值，不等于“没有差异”。",
             ha="center", color=muted, fontproperties=font, fontsize=11)
    target = Path(__file__).with_suffix(".png")
    fig.savefig(target, dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(json.dumps({"output": str(target), "summary": result["summary"],
                      "comparison": comp}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
