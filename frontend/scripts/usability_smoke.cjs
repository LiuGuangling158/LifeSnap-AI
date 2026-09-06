
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const net = require("node:net");
const { chromium } = require("playwright");
const root = path.resolve(__dirname, "../..");
const runDir = fs.mkdtempSync(path.join(os.tmpdir(), "lifesnap-ui-"));
const python = process.env.LIFESNAP_PYTHON || path.join(root, "backend/.venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
let server, browser, serverLog = "";
async function main() {
  const port = await new Promise(resolve => { const listener = net.createServer(); listener.listen(0, "127.0.0.1", () => { const port = listener.address().port; listener.close(() => resolve(port)); }); });
  const base = `http://127.0.0.1:${port}`;
  const env = { ...process.env, LIFESNAP_DATA_DIR: path.join(runDir, "data") };
  for (const key of Object.keys(env)) if (/^LIFESNAP_(OCR|AI_PARSE|LLM)_/.test(key)) delete env[key];
  server = spawn(python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port)], { cwd: path.join(root, "backend"), env, windowsHide: true });
  server.stdout.on("data", data => { serverLog += data; });
  server.stderr.on("data", data => { serverLog += data; });
  server.on("error", error => { serverLog += error.message; });
  let ready = false;
  for (let i = 0; i < 80; i++) { try { if ((await fetch(`${base}/health`)).ok) { ready = true; break; } } catch {} await delay(100); }
  assert(ready, `Temporary server did not start: ${serverLog}`);
  browser = await chromium.launch({ headless: true, ...(process.platform === "win32" ? { channel: process.env.PLAYWRIGHT_CHANNEL || "msedge" } : {}) });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, timezoneId: "Asia/Bangkok" });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  async function route(id) { await page.goto(`${base}/#${id}`); await page.locator(".simple-page-header").waitFor(); }
  async function overflow(label) { const sizes = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth })); if(sizes.document > sizes.viewport + 1) { await shot("overflow"); console.log(await page.evaluate(() => [...document.querySelectorAll("body *")].filter(node => node.getBoundingClientRect().right > innerWidth + 1).map(node => ({tag:node.tagName, cls:node.className, width:node.getBoundingClientRect().width, right:node.getBoundingClientRect().right})).slice(0,25))); } assert(sizes.document <= sizes.viewport + 1, `${label} overflows: ${JSON.stringify(sizes)}`); }
  async function shot(name) { await page.screenshot({ path: path.join(runDir, `${name}.png`), fullPage: true, animations: "disabled" }); }
  async function allBills() { return (await (await fetch(`${base}/bills`)).json()); }
  await route("dashboard");
  assert(await page.getByRole("heading", { name: "从第一笔开始" }).isVisible());
  await shot("home-empty");
  await page.getByRole("button", { name: "记一笔", exact: true }).click();
  await page.locator("#amount").fill("28.50"); await page.locator("#merchant").fill("测试午餐");
  assert.equal(await page.locator("#category").inputValue(), "其他");
  assert.equal(await page.locator("[data-bill-details]").getAttribute("open"), null);
  await shot("entry-desktop");
  await page.getByRole("button", { name: "保存账单", exact: true }).click();
  await page.locator("[data-bill-form]").waitFor({ state: "detached" });
  assert.equal((await allBills()).total, 1);
  await page.locator("[data-edit-bill]").first().click();
  await page.locator("#amount").fill("26.50");
  await page.getByText("支付方式和备注", { exact: true }).click();
  await page.locator("#payment_method").fill("微信支付"); await page.locator("#note").fill("测试备注");
  await page.getByRole("button", { name: "保存修改", exact: true }).click();
  await page.locator("[data-bill-form]").waitFor({ state: "detached" });
  let bills = (await allBills()).items;
  assert.equal(Number(bills[0].amount), 26.5); assert.equal(bills[0].note, "测试备注");
  for (let i = 0; i < 15; i++) {
    await fetch(`${base}/bills`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ amount: 10 + i, merchant: `分页记录 ${i + 1}`, category: i % 2 ? "交通" : "餐饮", transaction_type: i === 0 ? "income" : "expense", paid_at: new Date(new Date().getFullYear(), new Date().getMonth(), 1, 12, i).toISOString() }) });
  }
  await page.reload(); await page.locator(".simple-page-header").waitFor(); await shot("home-desktop");
  await route("bills");
  assert.equal(await page.locator(".simple-bill-row").count(), 12);
  const firstPage = await page.locator(".simple-bill-description").allTextContents();
  await page.getByRole("button", { name: "下一页", exact: true }).click();
  await page.getByText("第 2 / 2 页", { exact: true }).waitFor();
  assert.equal(await page.locator(".simple-bill-row").count(), 4);
  assert((await page.locator(".simple-bill-description").allTextContents()).every(item => !firstPage.includes(item)));
  await page.locator("#bill-search").fill("测试午餐");
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  await page.locator(".simple-list-caption").filter({ hasText: "1 笔" }).waitFor();
  assert.equal(await page.locator(".simple-bill-row").count(), 1);
  await page.locator("[data-clear-bill-search]").click(); await page.locator(".simple-bill-row").nth(11).waitFor(); await shot("bills-desktop");
  await page.locator('[data-bill-type="income"]').click();
  await page.locator(".simple-list-caption").filter({ hasText: "1 笔" }).waitFor();
  assert.equal(await page.locator('[data-bill-type="income"]').getAttribute("aria-pressed"), "true");
  assert.equal(await page.locator('[data-bill-type=""]').getAttribute("aria-pressed"), "false");
  await route("dashboard");
  await page.getByRole("button", { name: "记一笔", exact: true }).click();
  await page.locator("#amount").fill("15.60"); await page.locator("#merchant").fill("失败重试记录");
  await page.getByText("支付方式和备注", { exact: true }).click(); await page.locator("#note").fill("不能丢失的备注");
  let failed = false;
  await page.route(/\/bills$/, async route => {
    if (route.request().method() === "POST" && !failed) { failed = true; await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "暂时无法保存，请重试" }) }); }
    else await route.continue();
  });
  await page.getByRole("button", { name: "保存账单", exact: true }).click();
  await page.getByText("暂时无法保存，请重试", { exact: true }).waitFor();
  assert.equal(await page.locator("#amount").inputValue(), "15.6");
  assert.equal(await page.locator("#merchant").inputValue(), "失败重试记录"); assert.equal(await page.locator("#note").inputValue(), "不能丢失的备注");
  await page.getByRole("button", { name: "保存账单", exact: true }).click(); await page.locator("[data-bill-form]").waitFor({ state: "detached" });
  await page.unroute(/\/bills$/);
  await route("assistant"); await page.getByRole("button", { name: "记一笔午餐", exact: true }).click();
  const before = (await allBills()).total;
  await page.getByRole("button", { name: "帮我整理", exact: true }).click(); await page.locator(".chat-candidate").waitFor();
  assert.equal((await allBills()).total, before); assert.equal(await page.locator(".chat-agent-steps").count(), 0);
  assert(!(await page.locator(".chat-candidate").innerText()).includes("可信度")); await shot("assistant-desktop");
  await page.getByRole("button", { name: "修改信息", exact: true }).click(); await page.getByRole("dialog").waitFor(); await page.getByRole("dialog").locator('[name="amount"]').fill("30"); await shot("candidate-editor");
  await page.getByRole("button", { name: "完成修改", exact: true }).click(); await page.getByRole("dialog").waitFor({ state: "detached" });
  await page.getByRole("button", { name: "保存这笔账", exact: true }).click(); await page.getByText("账单已保存", { exact: true }).last().waitFor();
  assert.equal((await allBills()).total, before + 1);
  assert((await allBills()).items.some(bill => bill.merchant === "沙县小吃" && Number(bill.amount) === 30));

  await route("tasks");
  await page.getByRole("button", { name: "添加事项", exact: true }).click();
  await page.locator("#task_title").fill("测试买牛奶");
  await page.getByRole("button", { name: "保存事项", exact: true }).click();
  await page.getByRole("dialog").waitFor({ state: "detached" });
  await page.getByText("测试买牛奶", { exact: true }).waitFor();
  assert.equal((await (await fetch(`${base}/tasks`)).json()).total, 1);
  await route("diary");
  assert(await page.getByRole("heading", { name: "这一天，还没写日记" }).isVisible());
  assert.equal(await page.locator(".diary-entry-body").count(), 0);
  await page.getByRole("button", { name: "写日记", exact: true }).click();
  await page.locator("#diary_content").fill("今天测试了更简单的记账界面。");
  await page.getByRole("button", { name: "保存日记", exact: true }).click();
  await page.getByRole("dialog").waitFor({ state: "detached" });
  await page.locator(".diary-entry-body").filter({ hasText: "今天测试了更简单的记账界面。" }).waitFor();
  await route("dashboard");
  await page.locator("[data-bill-image-input]").setInputFiles({ name: "test-receipt.png", mimeType: "image/png", buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=", "base64") });
  await page.getByRole("heading", { name: "核对这笔账单" }).waitFor();
  assert(await page.locator(".simple-notice").isVisible());
  assert.equal(await page.locator("#note").inputValue(), "");
  await page.keyboard.press("Escape");
  await page.getByRole("dialog").waitFor({ state: "detached" });

  await page.setViewportSize({ width: 390, height: 844 });
  for (const id of ["dashboard", "bills", "assistant", "settings", "tasks", "diary"]) {
    await page.goto(`${base}/#${id}`); await page.locator('[data-route="settings"]').last().waitFor();
    await page.waitForFunction(() => !document.body.innerText.includes("正在加载你的记录"));
    await overflow(`390 ${id}`); await shot(`${id}-mobile`);
  }
  await route("dashboard"); await page.getByRole("button", { name: "记一笔", exact: true }).click();
  await overflow("390 bill form");
  assert(await page.getByRole("dialog").evaluate(node => node.scrollWidth <= node.clientWidth + 1), "Dialog has horizontal scrolling");
  await page.locator("#merchant").fill("提示消失时保留输入");
  await page.waitForTimeout(4500);
  assert.equal(await page.locator("#merchant").inputValue(), "提示消失时保留输入");
  assert.equal(await page.locator("#merchant").evaluate(node => node === document.activeElement), true);
  await shot("entry-mobile"); await page.keyboard.press("Escape"); await page.getByRole("dialog").waitFor({ state: "detached" });
  for (const width of [320, 900]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const id of ["dashboard", "bills", "assistant", "settings"]) { await route(id); await overflow(`${width} ${id}`); }
  }
  assert.deepEqual(errors, [], "Browser JavaScript errors");
  console.log(JSON.stringify({ status: "passed", checks: ["create", "edit", "pagination", "search", "type filters", "failed-save retry", "AI edit and confirm", "create unscheduled task", "diary empty and save", "image fallback", "six mobile routes", "320/390/900px overflow", "no browser exceptions"], artifacts: runDir }));
}
main().catch(error => { console.error(error); console.error(`Artifacts: ${runDir}`); process.exitCode = 1; }).finally(async () => { if (browser) await browser.close(); if (server) server.kill(); });

