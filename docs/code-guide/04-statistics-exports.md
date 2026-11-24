# 04｜实验数据、统计计算、报告与复现：逐文件读代码

本章对应三个实际源文件：

- [backend/app/stats_engine.py](../../backend/app/stats_engine.py)：把表格变成可核对的统计结果，386 行。
- [backend/app/api_experiments.py](../../backend/app/api_experiments.py)：接收网页请求，保存实验、数据版本、分析和报告，245 行。
- [backend/app/exports.py](../../backend/app/exports.py)：生成报告、图表和可复现 ZIP，353 行。

所有 Python 代码框均为真实源代码节选；完整源文件请在源码阅读器和完整源码附录查看。行号对应本次阅读的源文件。本章不改变应用。

## 1. 三个文件如何配合

~~~text
网页上的分析配置
    ↓ POST .../experiments/{experiment_id}/analyses
api_experiments.run_analysis
    ├─ 检查项目、实验、数据版本归属
    ├─ load_version：校验文件并重建确定的数据版本
    ├─ stats_engine.analyze：固定统计算法
    ├─ 保存 stats_engine.py 快照及 SHA-256
    └─ 保存 AnalysisRun：配置 + 结果 + 来源记录
          ↓
create_report：固定报告上下文
          ↓
exports.build_markdown：文字
exports.render_plot：PNG
exports.build_export：原文件 + 代码 + 配置 + 结果 + 依赖
          ↓
download_report：单文件或 ZIP
~~~

| 术语 | 通俗意思 | 代码形式 |
| --- | --- | --- |
| DataFrame | 一张内存中的表格 | pandas 对象，常叫 frame/data |
| 配置 | 哪列、哪两组、哪种设计 | AnalysisConfig |
| 来源记录 | 用了什么数据、代码和环境 | provenance 字典 |

同一张表在不同配置下可以得到不同分析，所以程序保存的不是孤立的 p 值，而是数据版本、配置、结果和来源。

## 2. stats_engine.py：确定性的计算模块

### 2.1 导入，1—11 行

~~~python
"""Deterministic tabular analysis. This module is copied into reproduction bundles."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scipy import stats
~~~

NumPy 管数值数组；pandas 管表格；Pydantic 检查配置；SciPy 提供 t 分布函数。这个模块没有数据库、FastAPI 或模型调用，可以随复现包独立使用。

“确定性”指固定输入与配置按固定算法计算，不靠模型生成数字，也没有随机抽样。它不意味着研究数据或结论一定正确。

### 2.2 AnalysisConfig：先规定允许怎样分析，14—43 行

字段节选，16—28 行：

~~~python
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
~~~

冒号后的 str 是字符串，bool 是真或假，str | None 是字符串或未选择。Literal 是允许值清单。第 15 行 extra="forbid" 拒绝多余字段。

| 字段 | 作用 | 容易混淆处 |
| --- | --- | --- |
| group_column | 存组名的列名 | 写 group，不是直接写 A |
| metric_column | 主要数值列名 | 一次只对一个主要指标推断 |
| group_a/group_b | 基准组和比较组的值 | 差值始终 B−A |
| experimental_unit | 一个独立对象是什么 | 需要人说明，列名不能证明 |
| sample_id_column | 检查重复实验单位 | 独立设计必须提供 |
| pair_column | 按编号匹配两侧 | 配对设计必须提供 |
| missing_policy | 遇无效值停止或显式排除 | 默认停止，不填补 |
| alternative | 双侧/小于/大于 | 针对 B−A |
| direction | 越大好或越小好 | 不自动改成单侧，也不反转 B−A |
| confirmed | 用户确认 | 模型建议不能代替 |

validate_design 完整函数，30—43 行：

~~~python
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
~~~

输入是组装后的配置，输出是通过检查的对象；不合规抛 ValueError。作为接口请求，Pydantic/FastAPI 会产生验证错误。描述统计只描述这批记录，推断还需确认设计。

### 2.3 json_safe：让数值能够保存，46—72 行

关键分支节选：

~~~python
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
~~~

递归把字典、数组、NumPy/pandas 类型转成普通 JSON 值。非有限数变 None，JSON 中是 null；日期变 ISO 字符串。62—72 行继续处理其他缺失值、带 isoformat 的对象、普通字符串整数布尔值，最后才 str(value)。

它做序列化，不负责解释为何没算。原因在 analyze 的 reason/warnings；null 不能读成 0。

### 2.4 read_dataset：读取 CSV/XLSX，75—102 行

输入路径及可选 sheet，输出 (DataFrame, 工作表名列表)。CSV 分支节选：

~~~python
    if suffix == ".csv":
        if sheet:
            raise ValueError("CSV 文件没有工作表。")
        try:
            frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
        except UnicodeDecodeError:
            frame = pd.read_csv(path, encoding="gb18030", dtype=str, keep_default_na=False, na_values=[""])
        sheets = []
~~~

优先 UTF-8，解码失败尝试 GB18030；dtype=str 先保留文本，避免编号 001 自动变 1；文字 NA 不自动全当缺失，空单元格仍是缺失。CSV 没有工作表。

XLSX 分支节选，86—94 行：

~~~python
    elif suffix == ".xlsx":
        with pd.ExcelFile(path, engine="openpyxl") as book:
            sheets = book.sheet_names
            chosen = sheet if sheet is not None else sheets[0]
            if chosen not in sheets:
                raise ValueError(f"工作表不存在：{chosen}")
            frame = pd.read_excel(book, sheet_name=chosen, dtype=str, keep_default_na=False, na_values=[""])
    else:
        raise ValueError("仅支持 CSV 和 XLSX 数据文件。")
~~~

with 会关闭文件资源。无指定则首个工作表。95—102 行拒绝空表、超过 200000 行/300 列、读取后的重复列名，统一列名为字符串并重置索引。

API 另有可配置限制；这层硬上限仍生效。检查发生在读取后，不是逐行流式读取。pandas 可能先给原始重复表头改名，因此读取后检查不等于完整验证原始重复表头的全部情况。

### 2.5 _missing 和 _numeric，105—112 行

两个完整函数：

~~~python
def _missing(series: pd.Series) -> pd.Series:
    blank = series.astype("string").str.strip().eq("").fillna(False)
    return series.isna() | blank


def _numeric(series: pd.Series) -> pd.Series:
    result = pd.to_numeric(series, errors="coerce")
    return result.where(np.isfinite(result), np.nan)
~~~

series 是一列。_missing 识别真空值及全空格文字；_numeric 将能转的值变数字，"abc" 和无穷值变 NaN。例如 ["3","","abc","inf"] 只有第一个是有效有限数值，不会把其他内容改成 0。下划线仅是辅助函数命名约定。

### 2.6 profile_dataframe：预览与质量概况，115—149 行

输入整表，返回 columns、row_count、preview、quality。按列计算缺失、非数值、有效数值、不同值和异常值数量。

异常值规则节选，123—129 行：

~~~python
        if len(valid):
            q1, q3 = valid.quantile([0.25, 0.75])
            iqr = q3 - q1
            outlier_mask = (converted < q1 - 1.5 * iqr) | (converted > q3 + 1.5 * iqr)
            outlier_rows = [int(i) + 2 for i in np.flatnonzero(outlier_mask.to_numpy())]
        else:
            outlier_rows = []
~~~

IQR 是第三四分位数减第一四分位数。此规则仅标记，不删除。ID 列有非数值通常正常，质量概况不等于认定所有列都必须数字。

140—148 行还保存：

- duplicate_rows：全部参与完全重复的行；两行相同计 2。
- duplicate_excess_rows：保留一份后多出的行；同例计 1。
- preview：最多前 50 行。
- outlier_rows：最多列前 100 个位置，outlier_count 保留总数。

行号是当前位置 +2，考虑表头占一行。清洗后指当前版本行位，不是最初文件永久行 ID。

### 2.7 apply_transforms：明确允许的清洗，152—178 行

输入表格和 transform，输出 (新表, 审计列表)。先 frame.copy()，不覆盖输入。核心节选，156—172 行：

~~~python
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
~~~

只允许指定列缺失行排除、全行完全重复排除。未知键和不存在列直接报错，没有任意代码执行。

每步先处理缺失，再去全行重复；记录 before_rows、after_rows、dropped_missing_rows、dropped_duplicate_rows。"abc" 非空，缺失清洗不自动排它，数值分析另查。也不自动填补、删异常、换单位或按重复 ID 聚合测量。

### 2.8 _stable_mean、_stable_std、_summary，181—201 行

三个完整函数：

~~~python
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
~~~

均值和标准差先除以最大绝对值，再乘回来，减少大数求和/平方溢出的机会。ddof=1 是样本标准差，分母 n−1。np.errstate 控制浮点警告，不会替代业务检查。

_summary 处理空数组和 n=1：没有数据的值为 None；一个样本不能估计样本标准差，也为 None。不能把 None 理解成 0。

### 2.9 analyze：一次完整分析，204—386 行

输入表和配置，返回结果字典。下面按真实执行顺序读。

#### A. 配置与列检查，204—215 行

~~~python
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
~~~

:= 是赋值并判断；& 求交集，集合减号找缺少项。原列不能与内部工作列重名，所选列必须存在。

#### B. 选择两组和处理无效指标，217—247 行

复制原表，增加 _source_row；组名转字符串，仅保留 A、B。其他非空组记录排除原因。分组缺失默认 error 停止，drop 才排除；两组都无数据时报错。

无效指标分支节选：

~~~python
    if invalid.any():
        invalid_rows = data.loc[invalid, "_source_row"].astype(int).tolist()
        if config.missing_policy == "error":
            raise ValueError(f"主要指标存在缺失、非数值或无穷值，行号：{invalid_rows[:20]}。请修正或显式选择排除。")
        exclusions.extend({"row": int(r), "reason": "主要指标缺失、非数值或非有限值"}
                          for r in data.loc[invalid, "_source_row"])
        if config.design == "paired":
            invalid_pair_ids = set(data.loc[invalid, config.pair_column].dropna().astype(str))
        data = data.loc[~invalid].copy()
~~~

只有明确选 drop 才排除。配对设计记住 invalid_pair_ids，后面排除另一侧。行号相对传入的当前分析表；清洗后不是最初文件永久行号。

#### C. 实验单位检查，249—282 行

关键节选：

~~~python
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
~~~

检查使用主要指标排除前的原始选中记录。否则同一对象两条记录中一条缺失，先删后就可能误当成独立。

独立设计：样本 ID 全局不重复，跨组重复也不行。配对设计：每组 pair_id 唯一，两侧集合完全一致，不会偷偷只取匹配的部分。如果还选择 sample_id_column，271—276 行检查每组实验单位 ID 缺失或重复，避免用不同配对编号掩饰重复测量。

配对无效指标的另一侧处理，277—282 行：

~~~python
            if invalid_pair_ids:
                counterpart = data[id_column].astype(str).isin(invalid_pair_ids)
                exclusions.extend({"row": int(r), "reason": "另一侧主要指标无效，整对排除"}
                                  for r in data.loc[counterpart, "_source_row"])
                data = data.loc[~counterpart].copy()
                warnings.append("按显式缺失值策略整对排除了含无效指标的配对。")
~~~

ID 唯一只是形式检查，不能凭编号证明真实实验单位独立。

#### D. 描述统计与初始比较结果，284—301 行

关键节选：

~~~python
    a = data.loc[data["_group"] == config.group_a, "_value"].to_numpy(dtype=float)
    b = data.loc[data["_group"] == config.group_b, "_value"].to_numpy(dtype=float)
    summary = [_summary(a, config.group_a), _summary(b, config.group_b)]
    difference = float(_stable_mean(b) - _stable_mean(a)) if len(a) and len(b) else None
    relative = difference / abs(_stable_mean(a)) * 100 if difference is not None and _stable_mean(a) != 0 else None
    if len(a) and _stable_mean(a) == 0:
        warnings.append("A 组均值为零，未计算相对变化。")
~~~

差值是 B−A，相对变化是 (B−A)/|A均值|×100%。A 均值 0 不算相对变化；正负指标的百分比需要领域解释。

comparison 初始 status="descriptive"，p、t、df、CI 都为 None。最终状态：

| 状态 | 意思 |
| --- | --- |
| descriptive | 只请求描述统计 |
| completed | 条件通过，完成推断 |
| unsupported | 当前设计/数据不受支持，保留描述统计和原因 |

direction 是指标好坏方向，不改变数值差的正负定义。

#### E. 配对 t 检验，303—332 行

先要求每组至少 2 个有效单位；这是计算下限，不是科研充分样本量保证。配对按 ID 对齐，不按原表行顺序。

节选，311—318 行：

~~~python
                paired_a = data.loc[data["_group"] == config.group_a].set_index(id_column)
                paired_b = data.loc[data["_group"] == config.group_b].set_index(id_column)
                # String matching is shared with the uniqueness checks; original order is irrelevant.
                paired_a.index = paired_a.index.astype(str)
                paired_b.index = paired_b.index.astype(str)
                keys = sorted(set(paired_a.index) & set(paired_b.index))
                with np.errstate(over="ignore", invalid="ignore"):
                    raw_differences = paired_b.loc[keys, "_value"].to_numpy(float) - paired_a.loc[keys, "_value"].to_numpy(float)
~~~

前面已要求 ID 集合相同，此处交集仅用于排序取值，不是接受缺配。319—323 行优先原始相减后缩放；出现非有限差值则先缩放再相减。

节选，324—332 行：

~~~python
                spread = float(np.std(paired_differences, ddof=1))
                if spread == 0 or not np.isfinite(spread):
                    reason = "配对差值为常量或数值不稳定，t 检验无法估计标准误；保留描述统计。"
                else:
                    df = len(paired_differences) - 1
                    scaled_se = spread / math.sqrt(len(paired_differences))
                    se = scaled_se * scale
                    statistic = float(np.mean(paired_differences) / scaled_se)
                    difference = float(np.mean(paired_differences) * scale)
~~~

~~~text
每对差值 d_i = B_i − A_i
SE = 差值的样本标准差 / √配对数
t = 平均差值 / SE
df = 配对数 − 1
~~~

差值全为常量时不输出无限 t 或虚假确定结论。

#### F. 独立样本 Welch t 检验，333—342 行

完整分支：

~~~python
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
~~~

未缩放的同样公式：

~~~text
SE² = s_A²/n_A + s_B²/n_B
df = (s_A²/n_A + s_B²/n_B)² /
     [(s_A²/n_A)²/(n_A−1) + (s_B²/n_B)²/(n_B−1)]
t = (B均值 − A均值) / SE
~~~

Welch 不强行假设两组方差一样。任意一组常量时本版不做推断，这是产品采取的保守边界，不代表所有软件都必定无法处理任何相关检验。

#### G. p 值与双侧 95% CI，343—361 行

关键节选：

~~~python
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
~~~

sf 是右尾概率，cdf 是累计左侧概率，ppf 是从概率找分位点。

- two-sided：B−A 不同于 0，取两侧。
- greater：B−A 大于 0，取右侧。
- less：B−A 小于 0，取左侧。
- CI 始终差值 ± t(0.975,df)×SE，双侧 95%；选单侧 p 也不自动改成单侧区间。

程序返回数值和限制，不自动写“显著就有价值”。浮点缩放降低部分风险，不保证任何极端数值范围都稳定。

#### H. 有效点、次要指标、返回值，363—386 行

每个点保存 group、value、source_row，有 pair_column 时还带 pair_id。次要列的完整循环节选：

~~~python
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
~~~

剩余列至少一个数字，且非空内容全部有效，才做描述统计。使用主要指标筛选后的行，不是对每列另外显著性检验。

最终 json_safe 返回 summary、comparison、points、warnings、exclusions、config、input_rows、effective_rows、supplementary。解释结论时，要同时看状态、排除记录和有效样本数。

## 3. api_experiments.py：网页请求怎样落到真实数据

### 3.1 导入和路由，1—24 行

本文件连接数据库模型、请求结构、统计函数、导出函数、论文检索和模型研究模块。第 24 行：

~~~python
router=APIRouter(prefix="/api")
~~~

APIRouter 是接口集合，@router.get / @router.post 将 URL 绑定到函数。GET 主要读，POST 创建数据或发起操作。

db:Session=Depends(session, scope="function") 由数据库依赖提供会话，并在函数范围结束时处理事务/清理。这里的“依赖”是框架管理资源，不是执行用户代码。

### 3.2 RunInput：运行分析的请求体，25—28 行

~~~python
class RunInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    dataset_id:str
    config:AnalysisConfig
~~~

必须提供确定的数据版本 ID 和合规配置。不是只扔一张表让程序猜设计。

### 3.3 versions、hash_file、verify_dataset

versions，30—33 行：

~~~python
@lru_cache(maxsize=1)
def versions():
    names=["pandas","numpy","scipy","pydantic","matplotlib","openpyxl"]
    return {**{name:importlib.metadata.version(name) for name in names},"python":sys.version.split()[0],"platform":platform.platform()}
~~~

无输入，返回当前运行环境的真实包版本、Python 和平台。lru_cache 缓存一次，避免反复查询。不是凭空写“推荐版本”。

hash_file，35—36 行：

~~~python
def hash_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
~~~

输入路径，返回 SHA-256，可以理解为文件字节的“指纹”。内容变动通常会变指纹；它检查一致性，不认证数据真实性。

verify_dataset，38—40 行：

~~~python
def verify_dataset(row):
    if not Path(row.storage_path).exists() or hash_file(row.storage_path)!=row.sha256:
        raise HTTPException(409,"数据版本文件缺失或哈希变化，请恢复备份或重新导入")
~~~

输入 DatasetVersion 记录，检查对应文件存在且哈希一致；否则返回 HTTP 409，不继续使用改动后的数据。

### 3.4 load_version：版本的真正含义，42—49 行

完整函数：

~~~python
def load_version(row):
    verify_dataset(row)
    if (row.transform or {}).get("steps"):
        if not Path(row.original_path).exists() or hash_file(row.original_path)!=row.original_sha256:
            raise HTTPException(409,"原始数据缺失或哈希变化，无法重建数据版本")
        frame,_=read_dataset(row.original_path,sheet=(row.transform or {}).get("sheet"))
        return apply_transforms(frame,row.transform)[0]
    return read_dataset(row.storage_path,sheet=row.sheet if Path(row.storage_path).suffix.lower()==".xlsx" else None)[0]
~~~

清洗版虽然保存了 CSV，但再次分析时用“原始字节 + 固定工作表 + 全部步骤链”重建。清洗 CSV 是可审计导出，原文件仍是语义基础，减少重复读写改变 ID/工作表的风险。

先查当前文件，再查清洗版的原文件哈希；无清洗步骤则直接按上传时保存的 sheet 读取。

### 3.5 validate_shape：设置中的行列限制，51—53 行

~~~python
def validate_shape(frame,settings):
    if len(frame)>settings.max_dataset_rows or len(frame.columns)>settings.max_dataset_columns:
        raise HTTPException(400,f"数据超过限制：最多 {settings.max_dataset_rows} 行、{settings.max_dataset_columns} 列")
~~~

输入表和设置。与 read_dataset 的硬上限共同生效，不是互相替代。

### 3.6 实验列表、创建、详情

| 函数与行号 | 接口（省略 /api） | 输入/输出 |
| --- | --- | --- |
| experiments，55—58 | GET /projects/{project_id}/experiments | 检查项目，按新到旧返回本项目实验 |
| create_experiment，60—64 | POST 同路径 | 验证关联论文归属，新增 Experiment，返回 201 |
| get_experiment，66—71 | GET /projects/{project_id}/experiments/{experiment_id} | 验证归属，返回实验、数据版本、分析列表 |

创建函数完整代码：

~~~python
@router.post("/projects/{project_id}/experiments",status_code=201)
def create_experiment(project_id:str,body:ExperimentInput,db:Session=Depends(session, scope="function")):
    project(db,project_id);paper_ids(db,project_id,body.paper_ids)
    row=Experiment(project_id=project_id,**body.model_dump());db.add(row);db.flush()
    return serialize(row)
~~~

body.model_dump() 将已验证请求转字典，** 展开为参数。db.add 放入会话；flush 将操作送数据库，取得生成字段；最终事务由会话依赖处理。serialize 转成 JSON 可返回形式。

scoped 不只按 ID 查记录，还检查项目归属，阻止用项目 A 的 URL 取项目 B 的资源。

### 3.7 upload_dataset：上传文件，73—105 行

类型、大小、解压限制节选：

~~~python
    filename=(file.filename or "").replace("\\","/").split("/")[-1][:240]
    suffix=Path(filename).suffix.lower()
    if suffix not in (".csv",".xlsx"): raise HTTPException(400,"仅支持 CSV 和 XLSX")
    value=await file.read(settings.max_upload_mb*1024*1024+1);await file.close()
    if len(value)>settings.max_upload_mb*1024*1024: raise HTTPException(413,"文件超过大小限制")
    if not value: raise HTTPException(400,"上传文件为空")
    if suffix==".xlsx":
        try:
            with zipfile.ZipFile(io.BytesIO(value)) as archive:
                if sum(f.file_size for f in archive.infolist())>settings.max_xlsx_uncompressed_mb*1024*1024:
                    raise HTTPException(413,"XLSX 解压大小超过限制")
        except zipfile.BadZipFile:
            raise HTTPException(400,"不是有效的 XLSX 文件") from None
~~~

XLSX 内部是 ZIP 结构，还检查声明的解压总大小。扩展名通过后仍需真实解析。大小上限多读 1 字节，是为了判断是否超限。

显示文件名去掉目录部分并截长；服务器实际路径用 uid()+suffix，不直接用用户名字拼服务器位置。

92—99 行尝试 read_dataset、validate_shape、profile_dataframe。失败删除刚存文件，再返回简洁错误；不会覆盖已有版本。

新版本节选，100—105 行：

~~~python
    chosen=(sheet or sheets[0]) if sheets else None
    digest=hashlib.sha256(value).hexdigest()
    row=DatasetVersion(project_id=project_id,experiment_id=experiment_id,filename=filename,
        storage_path=str(path),original_path=str(path),sha256=digest,original_sha256=digest,
        sheet=chosen,sheets=sheets,transform={"steps":[],"sheet":chosen,"original_filename":filename},**profile)
    db.add(row);db.flush();return serialize(row)
~~~

初始版本的当前文件等于原文件，两套路径/哈希相同，steps 为空，工作表固定保存下来。

### 3.8 preview_dataset：只预览，不改绑定，107—118 行

输入项目、数据版本和可选 sheet；先核对归属、哈希。CSV 不允许切 sheet；原始 XLSX 可以临时预览其他工作表。清洗版通过 load_version 重建。返回预览、质量概况和工作表列表。

118 行提示：

~~~python
        "notice":"预览不会改变数据版本；分析固定使用上传时选择的工作表"}
~~~

临时看哪个 sheet 与分析绑定哪个 sheet 不同。要分析另一 sheet，需要按该 sheet 导入确定版本。

### 3.9 clean_dataset：创建新版本，120—141 行

核对实验/数据归属；没有明确规则时报错；清洗后空表不创建新版本。保存节选：

~~~python
    path=request.app.state.settings.directory()/"datasets"/(uid()+".csv")
    cleaned.to_csv(path,index=False,encoding="utf-8-sig")
    # Original bytes + explicit steps define version semantics; CSV is an audited export.
    profile=profile_dataframe(cleaned)
    steps=list((row.transform or {}).get("steps",[]))+[step]
    version=DatasetVersion(project_id=project_id,experiment_id=experiment_id,parent_id=row.id,
        filename=Path(row.filename).stem+"-cleaned.csv",storage_path=str(path),
        original_path=row.original_path,original_sha256=row.original_sha256,sha256=hash_file(path),
        sheet=None,sheets=[],transform={"steps":steps,"sheet":(row.transform or {}).get("sheet",row.sheet),
            "audit":list((row.transform or {}).get("audit",[]))+audit,
            "original_filename":(row.transform or {}).get("original_filename",row.filename)},**profile)
    db.add(version);db.flush();return serialize(version)
~~~

新版本有自己的 ID、文件、哈希，parent_id 指上一版；原始路径和原始哈希保持。多次清洗会累积 steps 和 audit，不改写历史分析。

### 3.10 run_analysis：计算并保存来源，143—160 行

完整函数主体：

~~~python
def run_analysis(project_id:str,experiment_id:str,body:RunInput,request:Request,db:Session=Depends(session, scope="function")):
    scoped(db,Experiment,experiment_id,project_id)
    dataset=scoped(db,DatasetVersion,body.dataset_id,project_id)
    if dataset.experiment_id!=experiment_id: raise HTTPException(404,"数据不属于此实验")
    frame=load_version(dataset)
    result=analyze(frame,body.config)
    engine_bytes=(Path(__file__).parent/"stats_engine.py").read_bytes()
    code_sha=hashlib.sha256(engine_bytes).hexdigest()
    engine_dir=request.app.state.settings.directory()/"engines"
    engine_dir.mkdir(parents=True,exist_ok=True)
    (engine_dir/(code_sha+".py")).write_bytes(engine_bytes)
    provenance={"dataset_sha256":dataset.sha256,"original_sha256":dataset.original_sha256,
        "transform":dataset.transform,"versions":versions(),"app_version":"1.0.0",
        "analysis_code_sha256":code_sha,"random_seed":None,"random_process":"统计计算未使用随机过程"}
    row=AnalysisRun(project_id=project_id,experiment_id=experiment_id,dataset_id=dataset.id,
        config=body.config.model_dump(),result=json_safe(result),provenance=provenance)
    db.add(row);db.flush();return serialize(row)
~~~

把当时 stats_engine.py 按哈希命名存到 data/engines，将来升级后旧分析仍能带走当时算法。

app_version 在这里是写定的 1.0.0，不是 Git 提交号；代码哈希则直接来自实际文件。random_seed=None 因为没有随机过程，不是遗漏抽样种子。

### 3.11 get_analysis 与 plot，162—170 行

get_analysis 按项目读保存的 AnalysisRun，不重新计算。plot 完整函数：

~~~python
@router.get("/projects/{project_id}/analyses/{analysis_id}/plot.png")
def plot(project_id:str,analysis_id:str,kind:str="points",db:Session=Depends(session, scope="function")):
    if kind not in ("points","box","hist"): raise HTTPException(400,"不支持的图表类型")
    row=scoped(db,AnalysisRun,analysis_id,project_id)
    return Response(render_plot(row.result,kind),media_type="image/png")
~~~

只允许点图、箱线、直方图，绘图输入是保存结果，不是重新让模型生成点。

### 3.12 suggest：AI 只建议配置，172—194 行

未就绪分支：

~~~python
    if not research.chat_ready(request.app.state.settings,db):
        return {"configured":False,"suggestion":{},"explanation":"未配置或未启用模型，请手动填写分析配置","requires_confirmation":True}
~~~

有模型时发送问题、实验名/假设、列名、前 8 行预览、质量概况。系统要求设计不明确时建议描述统计，不生成统计数值或代码，不用正态性检验猜独立性。

过滤节选：

~~~python
    suggestion=result.get("suggestion",{})
    if not isinstance(suggestion,dict): raise HTTPException(502,"模型未返回有效的配置建议")
    allowed=set(AnalysisConfig.model_fields)-{"confirmed"}
    suggestion={k:v for k,v in suggestion.items() if k in allowed and isinstance(v,(str,type(None)))}
    for key in ("group_column","metric_column","sample_id_column","pair_column"):
        if suggestion.get(key) and suggestion[key] not in dataset.columns: suggestion.pop(key,None)
    suggestion["confirmed"]=False
    return {"configured":True,"suggestion":suggestion,"explanation":str(result.get("explanation","请核对实验单位与设计后手动确认。"))[:2000],"requires_confirmation":True}
~~~

仅允许字段和字符串/空值，去掉不存在的列名，强制 confirmed=False。草案不保证已构成完整合法配置，运行仍需 AnalysisConfig 校验。此函数不调用 analyze，没有任意代码执行器。

### 3.13 reports：报告列表，196—199 行

核对项目，按新到旧返回其报告。serialize(r,["context"]) 省略体积大的上下文，避免列表反复传全部复现材料。

### 3.14 create_report：固定上下文，201—226 行

输入 analysis_id、可选 title。由保存分析找到实验/数据版本。

证据处理，207—214 行：有关联论文则按研究问题/假设/实验名检索最多 5 段；没有命中时，回退到关联论文首个可用片段。因此可定位片段不等于必定支持实验结论，特别是首片段回退仍需人核对；无片段不编造论文结论。

上下文/快照节选：

~~~python
    title=body.title or experiment.name+" · 研究报告"
    context={"project":serialize(p),"experiment":serialize(experiment),"dataset":serialize(dataset),
        "analysis":serialize(analysis),"citations":citations,"report_title":title,"versions":analysis.provenance.get("versions",versions())}
    code_hash=analysis.provenance.get("analysis_code_sha256")
    snapshot=request.app.state.settings.directory()/"engines"/(str(code_hash)+".py")
    if code_hash:
        if not snapshot.exists() or hash_file(snapshot)!=code_hash:
            raise HTTPException(409,"分析代码快照缺失或哈希变化，无法导出可信复现包")
        context["analysis_engine_source"]=snapshot.read_bytes().decode("utf-8")
    markdown=build_markdown(context)
    row=Report(project_id=project_id,analysis_id=analysis.id,title=title,markdown=markdown,context=context)
~~~

context 是生成时快照，之后编辑项目不会自动改历史报告上下文。固定模板不需要模型，也不由模型重写统计数字。

### 3.15 download_report：下载，228—245 行

确认格式允许、项目归属正确、原始数据存在且哈希一致，然后 build_export。主要分支节选：

~~~python
    exports=build_export(row.context,Path(dataset.original_path))
    if format=="zip":
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,"w",zipfile.ZIP_DEFLATED) as archive:
            for name,value in exports.items(): archive.writestr(name,value)
        return Response(stream.getvalue(),media_type="application/zip",headers={"Content-Disposition":'attachment; filename="research-report.zip"'})
    names={"md":"report.md","csv":"summary.csv","png":"plot.png","py":"reproduce.py","json":"analysis_config.json"}
    mime={"md":"text/markdown; charset=utf-8","csv":"text/csv; charset=utf-8","png":"image/png","py":"text/x-python; charset=utf-8","json":"application/json"}
    name=names[format]
    return Response(exports[name],media_type=mime[format],headers={"Content-Disposition":f'attachment; filename="{name}"'})
~~~

BytesIO 是内存文件，ZipFile 压缩各项，Content-Disposition 告诉浏览器下载附件。

单独 py 只有脚本，还需配置和数据；完整复现用 ZIP。当前实现先建全部导出，再选单文件，因此即使下载 Markdown，也会校验原始数据并准备图片等全部材料。

## 4. exports.py：报告、图表和完整复现包

### 4.1 初始化，1—25 行

~~~python
_mpl_cache = Path(tempfile.gettempdir()) / "research-workbench-mpl"
_mpl_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_mpl_cache))
~~~

将 Matplotlib 缓存放临时目录；setdefault 保留用户已有设置。FigureCanvasAgg 是无窗口绘图后端，服务可直接输出图片字节，不必弹绘图窗口。

### 4.2 四个小工具：_json、_label、_number、_font

_json，28—29 行：

~~~python
def _json(value: Any) -> bytes:
    return (json.dumps(json_safe(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
~~~

先清理类型，再输出带中文、排版好的严格 JSON；allow_nan=False 拒绝不合规 NaN。最后返回 bytes，实际可写入文件的字节。

_label，32—33 行：

~~~python
def _label(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").replace("|", "\\|")
~~~

换行变空格，Markdown 表格竖线转义，避免标签打乱表格。它不是万能 Markdown/HTML 清洗；前端安全渲染由对应组件负责。

_number，36—39 行：

~~~python
def _number(value: Any) -> str:
    if value is None:
        return "未计算"
    return f"{value:.8g}" if isinstance(value, (float, int)) else _label(value)
~~~

8 位有效数字显示，小/大数可能科学计数法。仅改变报告格式，不覆盖保存的精度。None 不是 0，明确写“未计算”。

_font，42—49 行：

~~~python
def _font():
    for candidate in (
        Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ):
        if candidate.exists():
            return font_manager.FontProperties(fname=str(candidate))
    return font_manager.FontProperties(family="DejaVu Sans")
~~~

依次找微软雅黑、黑体、Noto CJK，否则 DejaVu Sans。回退字体不一定含全部中文，换环境需要适当中文字体。

### 4.3 render_plot：三种 PNG，52—119 行

输入保存结果和 kind，输出 PNG bytes。只允许 points、box、hist。55—65 行从配置取两组名，从 result.points 提取各组有效值，创建 9.6×5.6 英寸、150 DPI 图。

#### 点图，66—83 行

配对且推断 completed 时先按 pair_id 连两边。每组画点、均值线，节选：

~~~python
        for index, values in enumerate(arrays):
            if len(values):
                # Fixed jitter, no random seed or hidden data transformation.
                jitter = np.sin(np.arange(len(values)) * 2.3999632297) * 0.12
                ax.scatter(index + jitter, values, color=colors[index], s=30, alpha=0.8, zorder=3)
                ax.hlines(np.mean(values), index - 0.24, index + 0.24, color=colors[index], lw=2.5, zorder=4)
~~~

jitter 仅固定左右错开，避免重叠，纵轴数据不变，无随机数。短线是均值，不是 CI，也不是误差线。

#### 箱线图，84—95 行

ax.boxplot 使用 whis=1.5、showfliers=True：箱体 Q1—Q3，中线中位数，须至 1.5×IQR 内最远点，须外值仍显示；标签有 n。显示须外点不等于删异常。

#### 直方图，96—108 行

~~~python
        if len(all_values):
            edges = np.histogram_bin_edges(all_values, bins=min(20, max(3, math.ceil(math.sqrt(len(all_values))))))
            for group, values, color in zip(groups, arrays, colors):
                if len(values):
                    ax.hist(values, bins=edges, color=color, alpha=0.5, edgecolor="white",
                            label=f"{group} (n={len(values)})")
~~~

两组共同确定相同分箱边界，防止各自分箱产生误导；箱数按总数平方根取整并限定 3—20，纵轴观测数，不是概率密度。

#### 公共输出，109—119 行

标明指标/单位，没单位写“未指定单位”，标题解释图义，无有效值写“没有有效观测”。savefig 存入 BytesIO，写 Software 元数据，clear 清图，返回 PNG 字节。

点图均值线这里直接 np.mean；数值汇总使用 _stable_mean。正常范围一致，但不能把汇总缩放机制理解成所有绘图底层运算都同样处理了极端数值。

### 4.4 build_markdown：固定模板报告，122—229 行

输入 context，输出 Markdown 字符串。122—133 行取出项目、实验、版本、分析、配置、引用，缺失时用空对象/默认标题，不凑假内容。

| 行号 | 报告部分 | 取值与分支 |
| --- | --- | --- |
| 134—139 | 标题、研究问题、假设 | 保存字段，缺失写未填写 |
| 140—149 | 文献证据 | 标题、paper_id、chunk_id、实际 PDF 页、原文；无证据明确说明 |
| 150—162 | 实验设计 | 设计、单位、组别、方向、ID、条件、参数 |
| 163—173 | 数据处理 | 版本、原文件、哈希、策略、行数、清洗链 |
| 174—179 | 排除记录 | result.exclusions |
| 180—199 | 主要结果 | summary/comparison，成功才展示检验 |
| 200—203 | 次要指标 | 仅描述统计 |
| 204—211 | 三种图表 | 相对路径图片及含义 |
| 212—218 | 局限 | 设计边界与保存警告 |
| 219—223 | 后续建议 | 固定待验证模板，不冒充发现 |
| 224—229 | 复现 | 使用完整 ZIP 的说明 |

引文分支节选：

~~~python
    if citations:
        for index, citation in enumerate(citations, 1):
            lines.extend([
                f"{index}. {_label(citation.get('title'))}，PDF 第 {_label(citation.get('page_number'))} 页",
                f"   - 论文 ID：{_label(citation.get('paper_id'))}；片段 ID：{_label(citation.get('chunk_id'))}",
                f"   - 原文摘录：{_label(citation.get('quote'))}", "",
            ])
        lines.append("上述摘录属于论文已有报告，不自动构成本次实验结论；引用定位校验不等于结论正确性证明。")
    else:
        lines.append("本报告未关联已验证的文献片段，不生成论文已有结论。")
~~~

检验显示分支节选：

~~~python
    if comparison.get("status") == "completed":
        lines.extend([
            f"- 方法：{_label(comparison.get('method'))}",
            f"- 95% 双侧均值差置信区间：[{_number(comparison.get('ci_low'))}, {_number(comparison.get('ci_high'))}]",
            f"- t 统计量：{_number(comparison.get('statistic'))}；自由度：{_number(comparison.get('df'))}；p 值：{_number(comparison.get('pvalue'))}",
        ])
    else:
        lines.extend([f"- 推断状态：{_label(comparison.get('status'))}", f"- 说明：{_label(comparison.get('reason'))}"])
~~~

没有 completed 就写原因，不拼出显著结论。数字取保存对象，不重新计算，不调用模型。图路径在完整包里对应图片；单独 MD 不是自动包含图片文件。

### 4.5 _summary_csv：统计表，232—244 行

完整函数：

~~~python
def _summary_csv(result: dict) -> bytes:
    output = io.StringIO(newline="")
    fields = ["group", "n", "mean", "median", "std", "min", "max"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for item in result.get("summary", []):
        safe_item = {key: item.get(key) for key in fields}
        # Avoid spreadsheet formula execution in user-supplied group labels.
        group = str(safe_item["group"])
        if group[:1] in {"=", "+", "-", "@", "\t", "\r"}:
            safe_item["group"] = "'" + group
        writer.writerow(safe_item)
    return ("\ufeff" + output.getvalue()).encode("utf-8")
~~~

只导出组别、n、均值、中位数、SD、最小最大；完整检验在报告和 saved_result.json。用户组名以公式触发符号开头时加单引号；保护的是组名，不会把所有负数样本改文字。UTF-8 BOM 改善部分 Excel 中文识别。

### 4.6 REPRODUCE_SCRIPT：另一份 Python 程序的文字，247—293 行

它是原始字符串，导出为 reproduce.py。应用导入本文件时不会执行其中程序，下载后由用户运行。不需要 FastAPI/数据库/模型，直接导入旁边 stats_engine。

ROOT 是脚本目录，不要求在项目原目录执行。

#### equal：递归核对，源文件中 261—273 行

~~~python
def equal(a, b, location="result"):
    if isinstance(a, dict):
        assert isinstance(b, dict) and set(a) == set(b), f"Different keys at {location}"
        for key in a:
            equal(a[key], b[key], location + "." + key)
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), f"Different list at {location}"
        for index, (first, second) in enumerate(zip(a, b)):
            equal(first, second, f"{location}[{index}]")
    elif isinstance(a, (int, float)) and not isinstance(a, bool):
        assert isinstance(b, (int, float)) and math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-300), f"Different number at {location}: {a} vs {b}"
    else:
        assert a == b, f"Different value at {location}: {a!r} vs {b!r}"
~~~

输入期望值、实际值和位置提示。逐层比字典键、列表长度、数值、文字，不只核对均值。浮点比较允许很小容差，因为计算机小数有精度限制；错误带 location。

assert 不成立就停止。普通命令 python reproduce.py 会执行断言；Python -O 优化模式会跳过 assert，不应把带 -O 运行视为相同验证。

#### main：原始输入重新计算，275—289 行

~~~python
def main():
    provenance = json.loads((ROOT / "provenance.json").read_text(encoding="utf-8"))
    original = ROOT / provenance["original_path"]
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    assert digest == provenance["original_sha256"], "Original data hash does not match"
    assert hashlib.sha256((ROOT / "stats_engine.py").read_bytes()).hexdigest() == provenance["stats_engine_sha256"], "Analysis source hash does not match"
    frame, _ = read_dataset(original, sheet=provenance.get("sheet"))
    frame, audit = apply_transforms(frame, provenance["transform"])
    config = AnalysisConfig.model_validate_json((ROOT / "analysis_config.json").read_text(encoding="utf-8"))
    result = analyze(frame, config)
    expected = json.loads((ROOT / "saved_result.json").read_text(encoding="utf-8"))
    equal(expected, result)
    (ROOT / "reproduced_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (ROOT / "reproduced_cleaning_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("REPRODUCTION PASSED: input hash, analysis source, cleaning chain and saved results match.")
~~~

流程：读来源 → 校验原始文件 → 校验代码 → 固定 sheet 读表 → 重放清洗 → 校验配置 → 重算 → 全量核对 → 写新结果和审计。

291—292 行 if __name__ == "__main__": main() 表示直接运行才开始，被导入时不开始复现。

它验证和复现统计结果，不重新生成报告文字或 PNG。原 ZIP 已带图；计算不需要网络模型/API Key。

### 4.7 build_export：把材料装齐，296—353 行

输入 context 和原始文件路径；输出“文件名→字节”字典，由 API 压 ZIP。

#### 原文件，297—312 行

重新算原始 SHA-256 并核对。扩展名必须确认 csv/xlsx；包内用 original/data.csv 或 original/data.xlsx，避免拿用户文件名构造目录。原始 XLSX 保持 XLSX，sheet 在来源中记录，不偷换成清洗 CSV。

#### 代码和依赖，313—322 行

~~~python
    engine_source = context.get("analysis_engine_source")
    engine = engine_source.encode("utf-8") if isinstance(engine_source, str) else Path(__file__).with_name("stats_engine.py").read_bytes()
    recorded = analysis.get("provenance") or {}
    engine_hash = hashlib.sha256(engine).hexdigest()
    if recorded.get("analysis_code_sha256") and recorded["analysis_code_sha256"] != engine_hash:
        raise ValueError("保存的分析代码快照缺失或哈希不一致，请恢复快照或重新运行分析。")
    recorded_versions = recorded.get("versions") or context.get("versions") or {}
    dependencies = {}
    for package in ("numpy", "pandas", "scipy", "pydantic", "openpyxl"):
        dependencies[package] = recorded_versions.get(package) or importlib.metadata.version(package)
~~~

优先保存快照，旧记录没快照才回退当前文件。有 analysis_code_sha256 必须匹配，不能静默换算法。依赖优先分析时版本，旧记录缺项才查当前环境。

复现只算统计，不画图，所以 requirements.txt 包含 numpy/pandas/scipy/pydantic/openpyxl，没有 Matplotlib。完整 versions 仍保留分析时 Python/平台/Matplotlib 等信息。锁依赖不保证所有硬件平台浮点逐位相同，所以脚本继续比较结果。

#### 清洗与来源，323—339 行

旧 transform 没 steps 时兼容包装。sheet 优先取 transform 再 dataset。provenance 记原始/版本哈希、版本/分析 ID、sheet、处理链、配置、行数、排除、代码哈希、依赖、B−A 和双侧区间。random_seed=None 因为没有随机过程。

dataset_sha256 是当前版本指纹；脚本从原文件重建并比全部统计结果，不逐字节重建清洗 CSV。

#### 返回完整文件集，340—353 行

~~~python
    return {
        original_path: original,
        "report.md": build_markdown(context).encode("utf-8"),
        "summary.csv": _summary_csv(result),
        "plot.png": render_plot(result, "points"),
        "box.png": render_plot(result, "box"),
        "histogram.png": render_plot(result, "hist"),
        "reproduce.py": REPRODUCE_SCRIPT.encode("utf-8"),
        "stats_engine.py": engine,
        "analysis_config.json": _json(config),
        "saved_result.json": _json(result),
        "provenance.json": _json(provenance),
        "requirements.txt": ("\n".join(f"{name}=={version}" for name, version in dependencies.items()) + "\n").encode("ascii"),
    }
~~~

这只“计算档案盒”带走原料、处理方式、当时算法和结果，方便核对，而不只是截图。

## 5. 用项目示例串一次数字

samples/independent.csv 的合成教学数据 A=[1,2,3,4,5]，B=[3,4,5,6,7]，按独立/双侧配置：

~~~text
A：n=5，mean=3，sample std≈1.5811388301
B：n=5，mean=5，sample std≈1.5811388301
B−A=2，SE=1，df=8，t=2
two-sided p≈0.08051623796
95% CI≈[−0.3060041352, 4.3060041352]
~~~

此框是数值说明，不是源代码。数字来自项目已验收的合成示例分析：

_summary → Welch 公式 → SciPy 尾概率/分位点 → 保存结果/代码快照 → 报告/PNG/CSV → 复现从原文件再算。

它支持“本次样本 B 均值高 2”。若事先选常见 0.05 门槛，双侧 p 未达门槛，CI 含 0，不能说已证明 B 更好，也不能说已证明两组没差异。

## 6. 全部定义覆盖清单

### stats_engine.py

| 定义 | 行号 | 主要输入 → 输出 |
| --- | --- | --- |
| AnalysisConfig | 14—43 | 配置字段 → 经约束的对象 |
| AnalysisConfig.validate_design | 30—43 | 对象 → 通过或验证失败 |
| json_safe | 46—72 | 混合值 → 标准 JSON 值 |
| read_dataset | 75—102 | 路径/sheet → 表、sheet 名列表 |
| _missing | 105—107 | 一列 → 缺失布尔列 |
| _numeric | 110—112 | 一列 → 有限数字/NaN |
| profile_dataframe | 115—149 | 表 → 预览/质量概况 |
| apply_transforms | 152—178 | 表/步骤 → 新表/审计 |
| _stable_mean | 181—183 | 数组 → 均值 |
| _stable_std | 186—189 | 数组 → 样本 SD |
| _summary | 192—201 | 数组/组名 → 描述统计 |
| analyze | 204—386 | 表/配置 → 完整结果 |

### api_experiments.py

| 定义 | 行号 | 职责 |
| --- | --- | --- |
| RunInput | 25—28 | 确定数据版本与配置 |
| versions | 30—33 | 运行环境版本 |
| hash_file | 35—36 | 文件指纹 |
| verify_dataset | 38—40 | 当前版本完整性 |
| load_version | 42—49 | 原始+步骤重建版本 |
| validate_shape | 51—53 | 可配置行列限制 |
| experiments | 55—58 | 项目实验列表 |
| create_experiment | 60—64 | 创建及论文归属 |
| get_experiment | 66—71 | 实验/数据/分析详情 |
| upload_dataset | 73—105 | 上传验证与初始版本 |
| preview_dataset | 107—118 | 预览与工作表 |
| clean_dataset | 120—141 | 新版本及清洗链 |
| run_analysis | 143—160 | 计算、快照、保存 |
| get_analysis | 162—164 | 保存结果查询 |
| plot | 166—170 | PNG 接口 |
| suggest | 172—194 | AI 草案过滤/确认 |
| reports | 196—199 | 省略大上下文的列表 |
| create_report | 201—226 | 固定证据/结果/代码上下文 |
| download_report | 228—245 | 单文件/ZIP 下载 |

### exports.py

| 定义 | 行号 | 主要输入 → 输出 |
| --- | --- | --- |
| _json | 28—29 | 值 → JSON bytes |
| _label | 32—33 | 标签 → 表格可用字符串 |
| _number | 36—39 | 数值/空 → 显示文字 |
| _font | 42—49 | 无 → 字体配置 |
| render_plot | 52—119 | 保存结果/类型 → PNG |
| build_markdown | 122—229 | context → 报告字符串 |
| _summary_csv | 232—244 | result → CSV bytes |
| REPRODUCE_SCRIPT 常量 | 247—293 | 复现程序文本 |
| 脚本内 equal | 261—273 | 期望/实际 → 通过或失败 |
| 脚本内 main | 275—289 | 包内文件 → 重算与核对 |
| build_export | 296—353 | context/原路径 → 文件字节映射 |

## 7. 从实际代码得出的边界

- ID 唯一只能做表面核验，不能代替独立性设计；重复测量、多层、多组和多个主要指标推断未实现。
- 异常值只标记；清洗与无效值排除需明确规则，不能据此理解成自动“修好”数据。
- 当前表行位不等于最初文件永久行 ID，清洗后尤其要区别。
- unsupported 不等于零差异，也不等于上传失败。
- 单侧 p 配双侧 95% CI 已明确标注，不能混用阈值判断。
- 文献片段可定位不代表论证正确，回退首片段尤其需要核查相关性。
- 报告取保存结果，不是自动可发表论文；哈希保一致，不认证科学真实性。
- 完整复现用 ZIP，普通 python reproduce.py；只下载脚本不够，优化模式 -O 会跳过脚本断言。
- 当前复现核对统计，不重新生成图片/报告文字。跨环境字体和极端数值仍有实际边界。

建议在完整源码阅读器里沿 run_analysis → analyze → build_export 再看一次，将页面按钮、固定算法、保存记录、可复现导出连接起来。
