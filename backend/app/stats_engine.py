"""Deterministic tabular analysis. This module is copied into reproduction bundles."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scipy import stats


class AnalysisConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_column: str = Field(min_length=1, max_length=300)
    metric_column: str = Field(min_length=1, max_length=300)
    group_a: str = Field(min_length=1, max_length=500)
    group_b: str = Field(min_length=1, max_length=500)
    design: Literal["descriptive", "independent", "paired"] = "descriptive"
    experimental_unit: str = Field(default="", max_length=500)
    missing_policy: Literal["error", "drop"] = "error"
    alternative: Literal["two-sided", "less", "greater"] = "two-sided"
    pair_column: str | None = None
    sample_id_column: str | None = None
    unit: str = Field(default="", max_length=100)
    direction: Literal["higher", "lower"] = "higher"
    confirmed: bool = False

    @model_validator(mode="after")
    def validate_design(self):
        if self.group_a == self.group_b:
            raise ValueError("两组比较对象必须不同。")
        if self.design != "descriptive":
            if not self.confirmed:
                raise ValueError("推断分析必须先确认实验设计与配置。")
            if not self.experimental_unit.strip():
                raise ValueError("请明确填写实验单位。")
            if self.design == "independent" and not self.sample_id_column:
                raise ValueError("独立样本分析必须选择样本 ID 列，以检查重复实验单位。")
            if self.design == "paired" and not self.pair_column:
                raise ValueError("配对分析必须选择配对 ID 列。")
        return self


def json_safe(value: Any) -> Any:
    """Return standard JSON values; never emit NaN or Infinity."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    try:
        missing = pd.isna(value)
        if isinstance(missing, (bool, np.bool_)) and missing:
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (str, int, bool)):
        return value
    return str(value)


def read_dataset(path: str | Path, sheet: str | None = None) -> tuple[pd.DataFrame, list[str]]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        if sheet:
            raise ValueError("CSV 文件没有工作表。")
        try:
            frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
        except UnicodeDecodeError:
            frame = pd.read_csv(path, encoding="gb18030", dtype=str, keep_default_na=False, na_values=[""])
        sheets = []
    elif suffix == ".xlsx":
        with pd.ExcelFile(path, engine="openpyxl") as book:
            sheets = book.sheet_names
            chosen = sheet if sheet is not None else sheets[0]
            if chosen not in sheets:
                raise ValueError(f"工作表不存在：{chosen}")
            frame = pd.read_excel(book, sheet_name=chosen, dtype=str, keep_default_na=False, na_values=[""])
    else:
        raise ValueError("仅支持 CSV 和 XLSX 数据文件。")
    if frame.empty:
        raise ValueError("数据文件没有可分析的数据行。")
    if len(frame) > 200_000 or len(frame.columns) > 300:
        raise ValueError("第一版最多支持 200000 行、300 列。")
    frame.columns = [str(c) for c in frame.columns]
    if len(set(frame.columns)) != len(frame.columns):
        raise ValueError("列名重复，请先修正原文件列名。")
    return frame.reset_index(drop=True), sheets


def _missing(series: pd.Series) -> pd.Series:
    blank = series.astype("string").str.strip().eq("").fillna(False)
    return series.isna() | blank


def _numeric(series: pd.Series) -> pd.Series:
    result = pd.to_numeric(series, errors="coerce")
    return result.where(np.isfinite(result), np.nan)


def profile_dataframe(frame: pd.DataFrame) -> dict:
    columns = []
    for name in frame.columns:
        series = frame[name]
        missing = _missing(series)
        converted = _numeric(series)
        valid = converted.dropna()
        non_numeric = (~missing & converted.isna()).sum()
        if len(valid):
            q1, q3 = valid.quantile([0.25, 0.75])
            iqr = q3 - q1
            outlier_mask = (converted < q1 - 1.5 * iqr) | (converted > q3 + 1.5 * iqr)
            outlier_rows = [int(i) + 2 for i in np.flatnonzero(outlier_mask.to_numpy())]
        else:
            outlier_rows = []
        columns.append({
            "name": str(name), "dtype": str(series.dtype),
            "missing": int(missing.sum()), "missing_count": int(missing.sum()),
            "non_numeric": int(non_numeric), "non_numeric_count": int(non_numeric),
            "numeric_count": int(converted.notna().sum()),
            "unique_count": int(series.nunique(dropna=True)),
            "outlier_count": len(outlier_rows), "outlier_rows": outlier_rows[:100],
            "outlier_method": "1.5 × IQR；仅标记，未删除",
        })
    quality = {
        "columns": columns, "duplicate_rows": int(frame.duplicated(keep=False).sum()),
        "duplicate_excess_rows": int(frame.duplicated().sum()),
        "missing_cells": int(sum(c["missing"] for c in columns)),
        "row_numbering": "行号从 2 开始，包含表头占用的一行。",
        "outliers_removed": False,
    }
    return json_safe({
        "columns": [str(c) for c in frame.columns], "row_count": len(frame),
        "preview": frame.head(50).to_dict(orient="records"), "quality": quality,
    })


def apply_transforms(frame: pd.DataFrame, transform: dict | None) -> tuple[pd.DataFrame, list[dict]]:
    """Apply only explicit, whitelisted cleaning steps; raw files stay unchanged."""
    result = frame.copy()
    audit = []
    for index, step in enumerate((transform or {}).get("steps", []), start=1):
        unknown = set(step) - {"drop_missing_columns", "drop_duplicate_rows"}
        if unknown:
            raise ValueError(f"不支持的清洗操作：{sorted(unknown)}")
        before = len(result)
        columns = step.get("drop_missing_columns") or []
        absent = set(columns) - set(result.columns)
        if absent:
            raise ValueError(f"清洗列不存在：{sorted(absent)}")
        if columns:
            mask = pd.Series(False, index=result.index)
            for column in columns:
                mask |= _missing(result[column])
            result = result.loc[~mask].copy()
        after_missing = len(result)
        if step.get("drop_duplicate_rows", False):
            result = result.drop_duplicates().copy()
        audit.append({
            "step": index, "rules": step, "before_rows": before, "after_rows": len(result),
            "dropped_missing_rows": before - after_missing,
            "dropped_duplicate_rows": after_missing - len(result),
        })
    return result.reset_index(drop=True), audit


def _stable_mean(values: np.ndarray) -> float:
    scale = float(np.max(np.abs(values))) if len(values) else 0.0
    return float(np.mean(values / scale) * scale) if scale else 0.0


def _stable_std(values: np.ndarray) -> float:
    scale = float(np.max(np.abs(values))) if len(values) else 0.0
    with np.errstate(over="ignore", invalid="ignore"):
        return float(np.std(values / scale, ddof=1) * scale) if scale else 0.0


def _summary(values: np.ndarray, group: str) -> dict:
    scale = float(np.max(np.abs(values))) if len(values) else 0.0
    return {
        "group": group, "n": len(values),
        "mean": _stable_mean(values) if len(values) else None,
        "median": float(np.median(values / scale) * scale) if scale else (0.0 if len(values) else None),
        "std": _stable_std(values) if len(values) > 1 else None,
        "min": np.min(values) if len(values) else None,
        "max": np.max(values) if len(values) else None,
    }


def analyze(frame: pd.DataFrame, config: AnalysisConfig | dict) -> dict:
    config = config if isinstance(config, AnalysisConfig) else AnalysisConfig.model_validate(config)
    reserved = {"_source_row", "_group", "_value", "_pair", "_subject"}
    if conflicts := reserved & set(frame.columns):
        raise ValueError(f"列名与分析内部保留字段冲突，请重命名：{sorted(conflicts)}")
    requested = {config.group_column, config.metric_column}
    if config.sample_id_column:
        requested.add(config.sample_id_column)
    if config.pair_column:
        requested.add(config.pair_column)
    if absent := requested - set(frame.columns):
        raise ValueError(f"列不存在：{', '.join(sorted(absent))}")

    data = frame.copy().reset_index(drop=True)
    data["_source_row"] = np.arange(len(data)) + 2
    group_missing = _missing(data[config.group_column])
    data["_group"] = data[config.group_column].astype(str)
    selected = data["_group"].isin([config.group_a, config.group_b])
    exclusions = [
        {"row": int(row["_source_row"]), "reason": "不属于选定的两组"}
        for _, row in data.loc[~selected & ~group_missing].iterrows()
    ]
    if group_missing.any():
        if config.missing_policy == "error":
            raise ValueError(f"分组列有 {int(group_missing.sum())} 行缺失；请修正或显式选择排除缺失。")
        exclusions.extend({"row": int(r), "reason": "分组缺失"}
                          for r in data.loc[group_missing, "_source_row"])
    data = data.loc[selected & ~group_missing].copy()
    if data.empty:
        raise ValueError("所选的两组没有数据；请检查组名与分组列。")
    data["_value"] = _numeric(data[config.metric_column])
    invalid = data["_value"].isna()
    warnings = ["差值和检验方向均为 B − A；95% CI 始终为双侧区间。",
                "异常值仅标记，不自动删除；统计显著性不代表实际价值或因果关系。"]
    invalid_pair_ids: set[str] = set()
    if invalid.any():
        invalid_rows = data.loc[invalid, "_source_row"].astype(int).tolist()
        if config.missing_policy == "error":
            raise ValueError(f"主要指标存在缺失、非数值或无穷值，行号：{invalid_rows[:20]}。请修正或显式选择排除。")
        exclusions.extend({"row": int(r), "reason": "主要指标缺失、非数值或非有限值"}
                          for r in data.loc[invalid, "_source_row"])
        if config.design == "paired":
            invalid_pair_ids = set(data.loc[invalid, config.pair_column].dropna().astype(str))
        data = data.loc[~invalid].copy()

    unsupported = ""
    id_column = config.pair_column if config.design == "paired" else config.sample_id_column
    # Inspect the full selected input before metric exclusion: repeated observations cannot
    # become independent merely because one repeated row had a missing outcome.
    identity_input = frame.copy().reset_index(drop=True)
    identity_input["_group"] = identity_input[config.group_column].astype(str)
    identity_input = identity_input.loc[identity_input["_group"].isin([config.group_a, config.group_b])]
    if config.design != "descriptive" and id_column:
        if _missing(identity_input[id_column]).any():
            unsupported = "实验单位或配对 ID 缺失；无法确认独立性或严格配对，保留描述统计。"
        elif config.design == "independent":
            if identity_input[id_column].astype(str).duplicated(keep=False).any():
                unsupported = "检测到重复实验单位 ID（含跨组重复）；可能存在重复测量，第一版仅保留描述统计。"
        else:
            identities = identity_input.assign(_pair=identity_input[id_column].astype(str))
            if identities.duplicated(["_group", "_pair"], keep=False).any():
                unsupported = "同一组内配对 ID 重复；不自动平均或删除，保留描述统计。"
            else:
                aset = set(identities.loc[identities["_group"] == config.group_a, "_pair"])
                bset = set(identities.loc[identities["_group"] == config.group_b, "_pair"])
                if aset != bset:
                    unsupported = "两组配对 ID 集合不一致；存在未匹配对象，保留描述统计。"
            if config.sample_id_column:
                subjects = identities[config.sample_id_column]
                if _missing(subjects).any():
                    unsupported = "样本 ID 缺失；无法核验配对之间的实验单位独立性，保留描述统计。"
                elif identities.assign(_subject=subjects.astype(str)).duplicated(["_group", "_subject"], keep=False).any():
                    unsupported = "配对数据存在重复实验单位 ID；独特的配对编号不能使重复测量独立，保留描述统计。"
            if invalid_pair_ids:
                counterpart = data[id_column].astype(str).isin(invalid_pair_ids)
                exclusions.extend({"row": int(r), "reason": "另一侧主要指标无效，整对排除"}
                                  for r in data.loc[counterpart, "_source_row"])
                data = data.loc[~counterpart].copy()
                warnings.append("按显式缺失值策略整对排除了含无效指标的配对。")

    if config.design == "paired":
        warnings.append("配对 ID 须代表独立实验单位或独立匹配对；重复测量序号不能充当独立对象。")
    a = data.loc[data["_group"] == config.group_a, "_value"].to_numpy(dtype=float)
    b = data.loc[data["_group"] == config.group_b, "_value"].to_numpy(dtype=float)
    summary = [_summary(a, config.group_a), _summary(b, config.group_b)]
    difference = float(_stable_mean(b) - _stable_mean(a)) if len(a) and len(b) else None
    relative = difference / abs(_stable_mean(a)) * 100 if difference is not None and _stable_mean(a) != 0 else None
    if len(a) and _stable_mean(a) == 0:
        warnings.append("A 组均值为零，未计算相对变化。")
    comparison = {
        "difference": difference, "relative_change_percent": relative,
        "ci_low": None, "ci_high": None, "pvalue": None, "statistic": None, "df": None,
        "method": {"descriptive": "描述统计", "independent": "Welch t 检验", "paired": "配对 t 检验"}[config.design],
        "status": "descriptive", "reason": "仅请求描述统计。" if config.design == "descriptive" else "",
        "difference_direction": "B - A", "ci_level": 0.95,
        "ci_type": "two-sided", "alternative": config.alternative,
        "improvement_direction": config.direction,
    }

    if config.design != "descriptive":
        reason = unsupported
        if not reason and min(len(a), len(b)) < 2:
            reason = "每组至少需要 2 个有效实验单位；当前样本不足，保留描述统计。"
        if not reason:
            scale = max(float(np.max(np.abs(a))), float(np.max(np.abs(b)))) or 1.0
            scaled_a, scaled_b = a / scale, b / scale
            if config.design == "paired":
                paired_a = data.loc[data["_group"] == config.group_a].set_index(id_column)
                paired_b = data.loc[data["_group"] == config.group_b].set_index(id_column)
                # String matching is shared with the uniqueness checks; original order is irrelevant.
                paired_a.index = paired_a.index.astype(str)
                paired_b.index = paired_b.index.astype(str)
                keys = sorted(set(paired_a.index) & set(paired_b.index))
                with np.errstate(over="ignore", invalid="ignore"):
                    raw_differences = paired_b.loc[keys, "_value"].to_numpy(float) - paired_a.loc[keys, "_value"].to_numpy(float)
                if np.isfinite(raw_differences).all():
                    scale = float(np.max(np.abs(raw_differences))) or 1.0
                    paired_differences = raw_differences / scale
                else:
                    paired_differences = paired_b.loc[keys, "_value"].to_numpy(float) / scale - paired_a.loc[keys, "_value"].to_numpy(float) / scale
                spread = float(np.std(paired_differences, ddof=1))
                if spread == 0 or not np.isfinite(spread):
                    reason = "配对差值为常量或数值不稳定，t 检验无法估计标准误；保留描述统计。"
                else:
                    df = len(paired_differences) - 1
                    scaled_se = spread / math.sqrt(len(paired_differences))
                    se = scaled_se * scale
                    statistic = float(np.mean(paired_differences) / scaled_se)
                    difference = float(np.mean(paired_differences) * scale)
            else:
                va, vb = float(np.var(scaled_a, ddof=1)), float(np.var(scaled_b, ddof=1))
                if va == 0 or vb == 0:
                    reason = "至少一组指标为常量，第一版不进行推断检验；保留描述统计。"
                else:
                    se2 = va / len(a) + vb / len(b)
                    df = se2 ** 2 / ((va / len(a)) ** 2 / (len(a) - 1) + (vb / len(b)) ** 2 / (len(b) - 1))
                    scaled_se = math.sqrt(se2)
                    se = scaled_se * scale
                    statistic = float((np.mean(scaled_b) - np.mean(scaled_a)) / scaled_se)
            if not reason:
                if not all(math.isfinite(float(v)) for v in (df, se, statistic, difference)) or se <= 0:
                    reason = "数值范围导致推断不稳定，保留描述统计。"
                else:
                    if config.alternative == "two-sided":
                        pvalue = float(2 * stats.t.sf(abs(statistic), df))
                    elif config.alternative == "greater":
                        pvalue = float(stats.t.sf(statistic, df))
                    else:
                        pvalue = float(stats.t.cdf(statistic, df))
                    margin = float(stats.t.ppf(0.975, df) * se)
                    comparison.update(
                        difference=difference, statistic=statistic, pvalue=pvalue, df=df,
                        ci_low=difference - margin, ci_high=difference + margin,
                        status="completed", reason="",
                    )
        if reason:
            comparison.update(status="unsupported", reason=reason)
            warnings.append(reason)

    points = []
    for _, row in data.iterrows():
        point = {"group": row["_group"], "value": float(row["_value"]), "source_row": int(row["_source_row"])}
        if config.pair_column and not pd.isna(row[config.pair_column]):
            point["pair_id"] = str(row[config.pair_column])
        points.append(point)
    # Secondary numeric outcomes are descriptive only, never multiple unadjusted tests.
    supplementary = []
    for column in frame.columns:
        if column in {config.metric_column, config.group_column, config.sample_id_column, config.pair_column}:
            continue
        numeric = _numeric(data[column])
        if numeric.notna().sum() and numeric.notna().sum() == (~_missing(data[column])).sum():
            supplementary.append({
                "metric": column, "method": "仅描述统计，未检验",
                "summary": [_summary(numeric.loc[data["_group"] == g].dropna().to_numpy(float), g)
                            for g in (config.group_a, config.group_b)],
            })
    return json_safe({
        "summary": summary, "comparison": comparison, "points": points,
        "warnings": warnings, "exclusions": exclusions, "config": config.model_dump(),
        "input_rows": len(frame), "effective_rows": len(data),
        "supplementary": supplementary,
    })
