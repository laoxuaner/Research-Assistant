import { test, expect } from "@playwright/test";
import { formatNumber, makeHistogram } from "../src/numeric";

test("nonzero small measurements and p values retain their magnitude", () => {
  for (const value of [
    0.00003,
    0.000001,
    -0.000001,
    1e-160,
    1e-300,
    Number.MIN_VALUE,
  ]) {
    const displayed = formatNumber(value);
    expect(displayed).not.toBe("0");
    expect(displayed).not.toBe("-0");
    expect(displayed).toContain("e");
    expect(Math.sign(Number(displayed))).toBe(Math.sign(value));
  }
  expect(formatNumber(0.00003)).toBe("3e-5");
  expect(formatNumber(0.0001)).toBe("0.0001");
  expect(formatNumber(1e160)).toBe("1e+160");
});

test("ordinary numbers and identifier strings keep readable formatting", () => {
  expect(formatNumber(1234.56789)).toBe("1,234.5679");
  expect(formatNumber(1.23)).toBe("1.23");
  expect(formatNumber(0)).toBe("0");
  expect(formatNumber(-0)).toBe("0");
  expect(formatNumber("001")).toBe("001");
  expect(formatNumber(null)).toBe("—");
  expect(formatNumber(undefined)).toBe("—");
  expect(formatNumber(Infinity)).toBe("—");
  expect(formatNumber(NaN)).toBe("—");
});

test("floating last-edge rounding cannot drop the maximum observation", () => {
  const values = [0.1, 0.3, 0.5, 0.7, 0.9, 1.1];
  const histogram = makeHistogram(values, 3);
  expect(histogram.total).toBe(values.length);
  expect(histogram.bins.reduce((sum, bin) => sum + bin.count, 0)).toBe(
    values.length,
  );
  expect(histogram.bins.at(-1)?.hi).toBe(1.1);
  expect(histogram.binIndices.at(-1)).toBe(2);
  expect(histogram.bins.at(-1)?.count).toBe(2);
  expect(histogram.binIndices.every((index) => index >= 0 && index < 3)).toBe(
    true,
  );
});

test("interior boundaries have one assignment and final boundary is inclusive", () => {
  const histogram = makeHistogram([0, 1, 2, 3, 4], 4);
  expect(histogram.binIndices).toEqual([0, 1, 2, 3, 3]);
  expect(histogram.bins.map((bin) => bin.count)).toEqual([1, 1, 1, 2]);
});

test("100000 observations do not use array spread arguments", () => {
  const values = Array.from({ length: 100000 }, (_, index) => index / 1000);
  const histogram = makeHistogram(values, 12);
  expect(histogram.min).toBe(0);
  expect(histogram.max).toBe(99.999);
  expect(histogram.total).toBe(100000);
  expect(histogram.bins.reduce((sum, bin) => sum + bin.count, 0)).toBe(100000);
  expect(histogram.binIndices.at(-1)).toBe(11);
});

test("extreme finite numbers and subnormal ranges remain assigned", () => {
  for (const values of [
    [-1e308, -5e307, 0, 5e307, 1e308],
    [0, Number.MIN_VALUE, 2 * Number.MIN_VALUE],
  ]) {
    const histogram = makeHistogram(values, 4);
    expect(histogram.bins.reduce((sum, bin) => sum + bin.count, 0)).toBe(
      values.length,
    );
    expect(
      histogram.bins.every(
        (bin) => Number.isFinite(bin.lo) && Number.isFinite(bin.hi),
      ),
    ).toBe(true);
    expect(
      histogram.binIndices.every(
        (index) => Number.isInteger(index) && index >= 0 && index < 4,
      ),
    ).toBe(true);
  }
});

test("constant, empty and invalid values are explicit", () => {
  const constant = makeHistogram([7, 7, 7], 3);
  expect(constant.bins).toHaveLength(1);
  expect(constant.bins[0].count).toBe(3);
  expect(constant.binIndices).toEqual([0, 0, 0]);
  expect(makeHistogram([], 3)).toEqual({
    min: null,
    max: null,
    total: 0,
    bins: [],
    binIndices: [],
  });
  const mixed = makeHistogram([0, NaN, Infinity, -Infinity, 1], 3);
  expect(mixed.total).toBe(2);
  expect(mixed.binIndices).toEqual([0, -1, -1, -1, 2]);
  for (const count of [0, -1, 1.5, NaN, 1001]) {
    expect(() => makeHistogram([1], count)).toThrow(RangeError);
  }
});
