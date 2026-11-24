import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFile, mkdir, copyFile } from "node:fs/promises";
const root = fileURLToPath(new URL("../..", import.meta.url));
const sample = (name: string) => path.join(root, "samples", name);

async function createProject(page: Page, name: string) {
  await page.getByRole("button", { name: "新建项目", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "创建科研项目" });
  await dialog.getByLabel("项目名称", { exact: true }).fill(name);
  await dialog
    .getByLabel("研究问题", { exact: true })
    .fill("均值差与独立样本实验");
  await dialog
    .getByLabel("研究假设", { exact: true })
    .fill("B 组得分可能高于 A 组；用于测试流程。");
  await dialog.getByRole("button", { name: "保存项目", exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByLabel("当前科研项目")).toContainText(name);
}
async function nav(page: Page, name: string) {
  await page.getByRole("button", { name, exact: true }).click();
}
test("complete offline research workflow with original PDF and reproducible export", async ({
  page,
}, info) => {
  const external: string[] = [];
  const pageErrors: string[] = [];
  page.on("pageerror", (e) => pageErrors.push(e.message));
  page.on("request", (r) => {
    if (
      /^https?:/.test(r.url()) &&
      !["localhost", "127.0.0.1"].includes(new URL(r.url()).hostname)
    )
      external.push(r.url());
  });
  await page.goto("/");
  await createProject(page, "浏览器验收 · 科研闭环");
  await nav(page, "论文知识库");
  await page
    .getByLabel("上传 PDF", { exact: true })
    .setInputFiles([sample("demo_paper_zh.pdf"), sample("demo_paper_en.pdf")]);
  await expect(page.getByText("已就绪", { exact: true })).toHaveCount(2);
  await page.getByLabel("论文检索词").fill("均值差");
  await page.getByRole("button", { name: "检索原文", exact: true }).click();
  await expect(page.locator(".search-hit")).not.toHaveCount(0);
  await page.getByRole("button", { name: "查看证据 1", exact: true }).click();
  await expect(page.locator(".evidence")).toContainText("PDF 第 2 页");
  await page
    .getByRole("button", { name: "打开原文对应页", exact: true })
    .click();
  const reader = page.getByRole("dialog");
  await expect(reader.getByLabel("PDF 页码")).toHaveValue("2");
  await expect
    .poll(() =>
      reader
        .locator("canvas")
        .evaluate((el) => (el as HTMLCanvasElement).width),
    )
    .toBeGreaterThan(100);
  await expect(reader.getByText(/PDF 预览失败/)).toHaveCount(0);
  await reader.getByRole("button", { name: "关闭", exact: true }).click();

  await nav(page, "科研问答");
  await page
    .getByRole("textbox", { name: "研究问题", exact: true })
    .fill("均值差");
  await page.getByRole("button", { name: "发送问题", exact: true }).click();
  await expect(
    page.getByText("原文检索 · 非 AI 总结", { exact: true }),
  ).not.toHaveCount(0);
  await expect(
    page.locator(".chat-message.assistant .citation-button"),
  ).not.toHaveCount(0);
  await page
    .getByRole("textbox", { name: "研究问题", exact: true })
    .fill("Europa orbital eccentricity");
  await page.getByRole("button", { name: "发送问题", exact: true }).click();
  await expect(page.getByText(/当前资料不足以支持该结论/)).toBeVisible();

  await nav(page, "文献对比");
  await page.locator(".select-paper input").nth(0).check();
  await page.locator(".select-paper input").nth(1).check();
  await page.getByRole("button", { name: "生成对比表", exact: true }).click();
  await expect(page.locator(".comparison-column")).toHaveCount(2);
  await expect(page.locator(".comparison-grid")).toContainText(
    "未配置或未启用模型",
  );

  await nav(page, "实验分析");
  await page.getByRole("button", { name: "新建实验", exact: true }).click();
  const form = page.getByRole("dialog", { name: "创建实验记录" });
  await form.getByLabel("实验名称", { exact: true }).fill("浏览器实验");
  await form
    .getByLabel("研究假设", { exact: true })
    .fill("人工构造数据，用于验证 B-A=2。");
  await form.getByRole("button", { name: "创建实验", exact: true }).click();
  await expect(form).toBeHidden();
  await page
    .getByLabel("实验数据文件")
    .setInputFiles(sample("independent.csv"));
  await page.getByRole("button", { name: "导入为新版本", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "明确分析设计" }),
  ).toBeVisible();
  await page.getByLabel("分组列", { exact: true }).selectOption("group");
  await page.getByLabel("主要指标列", { exact: true }).selectOption("score");
  await page.getByLabel("指标单位", { exact: true }).fill("分");
  await page.getByLabel("基准组 A", { exact: true }).fill("A");
  await page.getByLabel("比较组 B", { exact: true }).fill("B");
  await page
    .getByLabel("分析设计", { exact: true })
    .selectOption("independent");
  await page.getByRole("textbox", { name: /^实验单位/ }).fill("独立实验样本");
  await page
    .getByLabel("实验单位 / 样本 ID 列", { exact: true })
    .selectOption("sample_id");
  await expect(
    page.getByRole("button", { name: "运行并保存分析", exact: true }),
  ).toBeDisabled();
  await page.getByRole("checkbox", { name: /我已核对数据版本/ }).check();
  const computed = page.waitForResponse(
    (r) => r.url().endsWith("/analyses") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "运行并保存分析", exact: true })
    .click();
  const saved = await (await computed).json();
  expect(saved.result.comparison.difference).toBe(2);
  expect(saved.result.comparison.pvalue).toBeCloseTo(0.08051623795726257, 12);
  expect(saved.result.summary.map((x: { n: number }) => x.n)).toEqual([5, 5]);
  await expect(page.locator(".result-stats .number").nth(0)).toHaveText("2");
  await page.getByRole("button", { name: "箱线图", exact: true }).click();
  await expect(
    page.getByRole("img", { name: "score (分) 箱线图" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "分布图", exact: true }).click();
  await expect(page.locator(".recharts-bar")).toHaveCount(2);
  await page.getByRole("button", { name: "生成研究报告", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "本次实验结果", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".rendered-report img")).toHaveCount(3);
  await expect
    .poll(() =>
      page
        .locator(".rendered-report img")
        .first()
        .evaluate((el) => (el as HTMLImageElement).naturalWidth),
    )
    .toBeGreaterThan(100);
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "完整复现包", exact: true }).click();
  const file = await download;
  const archive = info.outputPath("research-report.zip");
  await file.saveAs(archive);
  expect((await readFile(archive)).subarray(0, 2).toString()).toBe("PK");
  await nav(page, "实验分析");
  await page.getByRole("button", { name: /分析结果/ }).click();
  await mkdir(path.join(root, "docs"), { recursive: true });
  await page.screenshot({
    path: path.join(root, "docs", "workbench-preview.png"),
    fullPage: true,
  });
  expect(external).toEqual([]);
  expect(pageErrors).toEqual([]);
});

test("project switching isolates documents and displays OCR/failure states", async ({
  page,
}) => {
  await page.goto("/");
  await createProject(page, "浏览器验收 · 隔离与失败");
  await nav(page, "论文知识库");
  await expect(
    page.getByText("建立你的第一份文献证据", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("上传 PDF", { exact: true })
    .setInputFiles([sample("scanned_demo.pdf"), sample("corrupt_demo.pdf")]);
  await expect(page.getByText("需要 OCR", { exact: true })).toBeVisible();
  await expect(page.getByText("处理失败", { exact: true })).toBeVisible();
  await page.getByLabel("论文检索词").fill("均值差");
  await page.getByRole("button", { name: "检索原文", exact: true }).click();
  await expect(
    page.getByText("没有找到匹配的原文", { exact: true }),
  ).toBeVisible();
});

test("mobile navigation stays within viewport and opens settings without a model", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "打开导航", exact: true }).click();
  await nav(page, "模型与设置");
  await expect(
    page.getByRole("heading", { name: "外部 AI 模型", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "同意并启用 AI", exact: true }),
  ).toBeDisabled();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
});
