/** Numeric presentation and deterministic histogram binning shared by the UI. */
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

/**
 * Equal-width bins. Interior bins are [lo, hi); the final bin includes max.
 * Values are assigned once by index, rather than tested against rounded edges.
 * Constant data returns one bin. Nonfinite inputs are explicitly omitted.
 */
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
  const bins: HistogramBin[] = Array.from({ length: binCount }, (_, index) => {
    const lo = boundary(index);
    const hi = boundary(index + 1);
    return {
      index,
      lo,
      hi,
      count: 0,
      range: formatNumber(lo) + "–" + formatNumber(hi),
    };
  });

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
