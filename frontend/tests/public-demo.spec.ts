import {
  test,
  expect,
  type APIRequestContext,
  type APIResponse,
  type Page,
} from "@playwright/test";
import { readFile } from "node:fs/promises";

const publicURL = (process.env.PUBLIC_DEMO_URL || "").replace(/\/+$/, "");
const nav = (page: Page, name: string) =>
  page.locator(".sidebar").getByRole("button", { name: new RegExp("^" + name) }).click();

// Keep normal local Playwright runs independent of the temporary public link.
test.skip(!publicURL, "Set PUBLIC_DEMO_URL to run the real public demo smoke test.");

// Retry transport failures only, never failed status/content assertions.
async function getPublic(request: APIRequestContext, path: string): Promise<APIResponse> {
  let lastError: unknown;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      return await request.get(publicURL + path, { timeout: 15000, maxRetries: 1 });
    } catch (error) {
      lastError = error;
      if (attempt < 2) await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  throw lastError;
}

test("real public demo serves evidence, saved statistics and reproducible downloads", async ({
  page,
  request,
}, info) => {
  expect(new URL(publicURL).protocol).toBe("https:");
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  const pid = await test.step("verify real demo API and read-only enforcement", async () => {
    const health = await getPublic(request, "/api/health");
    expect(health.status()).toBe(200);
    expect((await health.json()).status).toBe("ok");
    const settingsResponse = await getPublic(request, "/api/settings");
    expect(settingsResponse.status()).toBe(200);
    const settings = await settingsResponse.json();
    // Check demo mode before testing a write, so an incorrect target is not modified.
    expect(settings.deployment_mode).toBe("demo");
    expect(settings.read_only).toBe(true);
    expect(settings.chat_configured).toBe(false);
    expect(settings.embedding_configured).toBe(false);
    expect(settings.ai_enabled).toBe(false);
    const projectsResponse = await getPublic(request, "/api/projects");
    expect(projectsResponse.status()).toBe(200);
    const projects = await projectsResponse.json();
    expect(projects).toHaveLength(1);
    expect(projects[0].name).toContain("示例");
    const forbidden = await request.post(publicURL + "/api/projects", {
      data: { name: "public smoke test must not create a project" },
      headers: { Origin: publicURL },
      timeout: 15000,
    });
    expect(forbidden.status()).toBe(403);
    expect((await forbidden.json()).detail).toContain("只读");
    return projects[0].id as string;
  });

  await test.step("search real paper evidence and render PDF page 2", async () => {
    await page.goto(publicURL + "/", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("note", { name: "公开演示说明" })).toBeVisible();
    await expect(page.getByRole("button", { name: "新建项目", exact: true })).toBeDisabled();
    await nav(page, "论文知识库");
    await expect(page.getByLabel("上传 PDF", { exact: true })).toBeDisabled();
    await page.getByLabel("论文检索词").fill("均值差");
    await page.getByRole("button", { name: "检索原文", exact: true }).click();
    await expect(page.locator(".search-hit")).not.toHaveCount(0);
    await page.getByRole("button", { name: "查看证据 1", exact: true }).click();
    await expect(page.locator(".evidence")).toContainText("PDF 第 2 页");
    await page.getByRole("button", { name: "打开原文对应页", exact: true }).click();
    const reader = page.getByRole("dialog");
    await expect(reader.getByLabel("PDF 页码")).toHaveValue("2");
    await expect(reader.locator("canvas")).toHaveAttribute("data-rendered-page", "2");
    await expect(reader.getByText(/PDF 预览失败/)).toHaveCount(0);
    await reader.getByRole("button", { name: "关闭", exact: true }).click();
  });

  await test.step("show real offline evidence without storing a shared conversation", async () => {
    await nav(page, "科研问答");
    await page.getByRole("textbox", { name: "研究问题", exact: true }).fill("均值差");
    await page.getByRole("button", { name: "发送问题", exact: true }).click();
    await expect(page.locator(".chat-message.assistant .citation-button")).not.toHaveCount(0);
    await expect(page.getByText("原文检索 · 非 AI 总结", { exact: true })).toBeVisible();
    const conversations = await getPublic(request, `/api/projects/${pid}/conversations`);
    expect(conversations.status()).toBe(200);
    expect(await conversations.json()).toEqual([]);
  });

  await test.step("inspect saved statistics and download the real report ZIP", async () => {
    await nav(page, "实验分析");
    await expect(page.getByText("均值差 B − A", { exact: true })).toBeVisible();
    await expect(page.locator(".result-stats .number").nth(0)).toHaveText("2");
    await expect(page.getByRole("button", { name: "生成研究报告", exact: true })).toBeDisabled();
    await nav(page, "研究报告");
    await expect(page.locator(".rendered-report img")).toHaveCount(3);
    await expect.poll(() => page.locator(".rendered-report img").first().evaluate(
      (element) => (element as HTMLImageElement).naturalWidth,
    )).toBeGreaterThan(100);
    const downloaded = page.waitForEvent("download");
    await page.getByRole("link", { name: "完整复现包", exact: true }).click();
    const archive = await downloaded;
    expect(archive.suggestedFilename()).toMatch(/\.zip$/);
    const archivePath = info.outputPath("public-research-report.zip");
    await archive.saveAs(archivePath);
    expect((await readFile(archivePath)).subarray(0, 2).toString()).toBe("PK");
    expect(await archive.failure()).toBeNull();
  });
  expect(pageErrors).toEqual([]);
});
