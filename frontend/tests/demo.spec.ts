import { test, expect, type Page, type Route } from "@playwright/test";

const backend = "http://127.0.0.1:8001/api";
const nav = (page: Page, name: string) =>
  page
    .locator(".sidebar")
    .getByRole("button", { name: new RegExp("^" + name) })
    .click();

test("read-only demo UI keeps evidence, saved results and exports available", async ({
  page,
  request,
}) => {
  // Exercise the real local API for fixtures; override only the deployment flags
  // to verify the browser presentation independently of the backend demo tests.
  const seeded = await request.post(backend + "/demo", { data: {} });
  expect(seeded.ok()).toBe(true);
  const { project_id: pid } = await seeded.json();
  const experiments = await (
    await request.get(`${backend}/projects/${pid}/experiments`)
  ).json();
  const detail = await (
    await request.get(
      `${backend}/projects/${pid}/experiments/${experiments[0].id}`,
    )
  ).json();
  const report = await request.post(`${backend}/projects/${pid}/reports`, {
    data: { analysis_id: detail.analyses[0].id, title: "DEMO · 合成测试报告" },
  });
  expect(report.ok()).toBe(true);
  await page.route("**/api/settings", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: {
        ...(await response.json()),
        deployment_mode: "demo",
        read_only: true,
      },
    });
  });
  // The public backend intentionally returns no persisted conversation ID.
  await page.route("**/api/projects/*/ask", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: { ...(await response.json()), conversation_id: null },
    });
  });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("note", { name: "公开演示说明" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "新建项目", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "编辑项目", exact: true }),
  ).toBeDisabled();
  await nav(page, "论文知识库");
  await expect(page.getByLabel("上传 PDF", { exact: true })).toBeDisabled();
  await expect(
    page.getByRole("button", { name: /^删除 / }).first(),
  ).toBeDisabled();
  // Closing during a stalled PDF download must abort the request instead of
  // leaving a half-initialized worker or an unhandled cancellation promise.
  const filePattern = "**/api/projects/*/papers/*/file";
  let stalledRoute: Route | undefined;
  await page.route(filePattern, (route) => { stalledRoute = route; });
  await page.evaluate(() => {
    const fetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      if (/\/papers\/[^/]+\/file$/.test(String(input))) {
        init?.signal?.addEventListener("abort", () => {
          document.documentElement.dataset.pdfDownloadAborted = "true";
        });
        window.fetch = fetch;
      }
      return fetch(input, init);
    };
  });
  const pendingFile = page.waitForRequest((r) =>
    /\/papers\/[^/]+\/file$/.test(new URL(r.url()).pathname),
  );
  await page
    .getByRole("button", { name: /^阅读 / })
    .first()
    .click();
  await pendingFile;
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "关闭", exact: true })
    .click();
  await expect(page.locator("html")).toHaveAttribute("data-pdf-download-aborted", "true");
  await stalledRoute!.continue();
  await page.unroute(filePattern);
  await page.getByLabel("论文检索词").fill("均值差");
  await page.getByRole("button", { name: "检索原文", exact: true }).click();
  await expect(page.locator(".search-hit")).not.toHaveCount(0);
  await page.getByRole("button", { name: "查看证据 1", exact: true }).click();
  await page
    .getByRole("button", { name: "打开原文对应页", exact: true })
    .click();
  const reader = page.getByRole("dialog");
  await expect(reader.getByLabel("PDF 页码")).toHaveValue("2");
  await expect(reader.locator("canvas")).toHaveAttribute(
    "data-rendered-page",
    "2",
  );
  await reader.getByRole("button", { name: "信息笔记", exact: true }).click();
  await expect(reader.getByLabel("标题", { exact: true })).toBeDisabled();
  await expect(
    reader.getByRole("button", { name: "保存信息", exact: true }),
  ).toBeDisabled();
  await reader.getByRole("button", { name: "关闭", exact: true }).click();
  await nav(page, "科研问答");
  await page
    .getByRole("textbox", { name: "研究问题", exact: true })
    .fill("均值差");
  await page.getByRole("button", { name: "发送问题", exact: true }).click();
  await expect(
    page.locator(".chat-message.assistant .citation-button"),
  ).not.toHaveCount(0);
  await expect(
    page.getByText("原文检索 · 非 AI 总结", { exact: true }),
  ).toBeVisible();
  await nav(page, "实验分析");
  await expect(
    page.getByRole("button", { name: "新建实验", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "生成研究报告", exact: true }),
  ).toBeDisabled();
  await expect(page.getByText("均值差 B − A", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "数据与分析配置", exact: true })
    .click();
  await expect(page.getByLabel("实验数据文件", { exact: true })).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "清洗为新版本", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "运行并保存分析", exact: true }),
  ).toBeDisabled();
  await nav(page, "研究报告");
  await expect(page.locator(".rendered-report img")).toHaveCount(3);
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "完整复现包", exact: true }).click();
  expect((await download).suggestedFilename()).toMatch(/\.zip$/);
  await nav(page, "模型与设置");
  await expect(
    page.getByRole("button", { name: "同意并启用 AI", exact: true }),
  ).toBeDisabled();
  expect(errors).toEqual([]);
});
