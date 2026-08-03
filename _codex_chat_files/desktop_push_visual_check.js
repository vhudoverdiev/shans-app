const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    permissions: ["notifications"],
    serviceWorkers: "allow",
  });
  const page = await context.newPage();
  await page.goto("http://127.0.0.1:5000/login", { waitUntil: "networkidle" });
  await page.fill("#username", "codexvisual");
  await page.fill("#password", "CodexVisual123!");
  await page.click("button[type='submit']");
  await page.waitForURL("**/account/settings", { timeout: 10000 }).catch(async () => {
    await page.goto("http://127.0.0.1:5000/account/settings", { waitUntil: "networkidle" });
  });
  await page.waitForSelector("#push-notifications-card", { state: "visible" });
  await page.screenshot({ path: "_codex_chat_files/desktop-push-settings.png", fullPage: true });

  const desktop = await page.evaluate(async () => {
    const card = document.querySelector("#push-notifications-card");
    const toggle = document.querySelector("#push-notifications-toggle");
    const test = document.querySelector("#push-notifications-test");
    const status = document.querySelector("#push-notifications-status");
    const rect = card.getBoundingClientRect();
    return {
      visible: Boolean(card) && rect.width > 0 && rect.height > 0,
      top: Math.round(rect.top),
      width: Math.round(rect.width),
      toggleText: toggle ? toggle.textContent.trim().replace(/\s+/g, " ") : "",
      testHidden: test ? test.hidden : null,
      status: status ? status.textContent.trim() : "",
      permission: Notification.permission,
    };
  });

  await page.click("#push-notifications-toggle");
  await page.waitForFunction(() => {
    const status = document.querySelector("#push-notifications-status");
    const toggle = document.querySelector("#push-notifications-toggle");
    return status && toggle && !toggle.disabled && status.textContent.trim().length > 0;
  }, { timeout: 10000 });
  const afterToggle = await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    const toggle = document.querySelector("#push-notifications-toggle");
    const test = document.querySelector("#push-notifications-test");
    const status = document.querySelector("#push-notifications-status");
    return {
      subscribed: Boolean(sub),
      enabled: toggle ? toggle.dataset.enabled : "",
      testHidden: test ? test.hidden : null,
      status: status ? status.textContent.trim() : "",
      permission: Notification.permission,
    };
  });

  const mobileContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    permissions: ["notifications"],
    serviceWorkers: "allow",
  });
  const mobilePage = await mobileContext.newPage();
  await mobilePage.setViewportSize({ width: 390, height: 844 });
  await mobilePage.goto("http://127.0.0.1:5000/login", { waitUntil: "networkidle" });
  await mobilePage.fill("#username", "codexvisual");
  await mobilePage.fill("#password", "CodexVisual123!");
  await mobilePage.click("button[type='submit']");
  await mobilePage.waitForURL("**/account/settings", { timeout: 10000 }).catch(async () => {
    await mobilePage.goto("http://127.0.0.1:5000/account/settings", { waitUntil: "networkidle" });
  });
  await mobilePage.goto("http://127.0.0.1:5000/account/settings", { waitUntil: "networkidle" });
  await mobilePage.waitForSelector("#push-notifications-card", { state: "visible" });
  await mobilePage.screenshot({ path: "_codex_chat_files/mobile-push-settings.png", fullPage: true });
  const mobile = await mobilePage.evaluate(() => {
    const card = document.querySelector("#push-notifications-card");
    const desktopOnly = document.querySelector(".account-push-desktop-only");
    const status = document.querySelector("#push-notifications-status");
    const rect = card.getBoundingClientRect();
    return {
      visible: Boolean(card) && rect.width > 0 && rect.height > 0,
      innerWidth: window.innerWidth,
      coarseMatch: window.matchMedia("(max-width: 900px) and (pointer: coarse)").matches,
      width: Math.round(rect.width),
      desktopOnlyDisplay: desktopOnly ? getComputedStyle(desktopOnly).display : "",
      statusDisplay: status ? getComputedStyle(status).display : "",
    };
  });

  console.log(JSON.stringify({ desktop, afterToggle, mobile }, null, 2));
  await mobileContext.close();
  await browser.close();
})();
