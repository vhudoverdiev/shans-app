import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from flask import render_template
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402


def main():
    chat_dir = ROOT / "_codex_chat_files"
    chat_dir.mkdir(exist_ok=True)
    database_path = chat_dir / "account-push-visual.db"
    if database_path.exists():
        database_path.unlink()

    original_database_name = Config.DATABASE_NAME
    Config.DATABASE_NAME = str(database_path)

    app = create_app()
    app.config.update(TESTING=True)

    @app.get("/__visual_account_settings")
    def visual_account_settings():
        return render_template(
            "account_settings.html",
            avatar_letter="Ш",
            avatar_url="",
            otp_enabled=True,
            login_history=[],
            recovery_codes=[],
            can_manage_users=True,
            managed_users=[],
            available_sections={
                "schedule": "График",
                "budget": "Бюджет",
            },
        )

    server = make_server("127.0.0.1", 5092, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    node = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "bin"
        / "node.exe"
    )
    node_modules = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "node_modules"
    )

    js = r"""
const { chromium } = require("playwright");

async function checkViewport(page, name, width, height) {
  await page.goto("http://127.0.0.1:5092/__visual_account_settings", { waitUntil: "networkidle" });
  const card = page.locator("#push-notifications-card");
  await card.waitFor({ state: "visible" });

  const state = await card.evaluate((node) => {
    const visibleButtons = Array.from(node.querySelectorAll("button")).filter((button) => {
      const style = window.getComputedStyle(button);
      return !button.hidden && style.display !== "none" && style.visibility !== "hidden";
    });
    return {
      visibleText: node.innerText.trim(),
      visibleButtonCount: visibleButtons.length,
      buttonText: visibleButtons[0]?.innerText.trim() || "",
      hasHiddenStatus: Boolean(node.querySelector("#push-notifications-status[hidden]")),
      hasTestButton: Boolean(node.querySelector("#push-notifications-test")),
    };
  });

  if (state.visibleButtonCount !== 1) {
    throw new Error(`${name}: expected one visible push button, got ${JSON.stringify(state)}`);
  }
  if (!["Включить", "Выключить"].includes(state.buttonText)) {
    throw new Error(`${name}: unexpected button text ${state.buttonText}`);
  }
  for (const forbidden of ["Уведомления личного графика", "В 10:00", "Прислать", "Проверяем"]) {
    if (state.visibleText.includes(forbidden)) {
      throw new Error(`${name}: extra text is visible: ${forbidden}`);
    }
  }
  if (!state.hasHiddenStatus || state.hasTestButton) {
    throw new Error(`${name}: hidden status/test button contract failed`);
  }

  const usersState = await page.evaluate(() => {
    const usersTab = document.querySelector('[data-account-tab="users"]');
    const usersPanel = document.querySelector('[data-account-panel="users"]');
    const tabStyle = usersTab ? window.getComputedStyle(usersTab) : null;
    const panelStyle = usersPanel ? window.getComputedStyle(usersPanel) : null;
    return {
      hasUsersTab: Boolean(usersTab),
      hasUsersPanel: Boolean(usersPanel),
      usersTabDisplay: tabStyle ? tabStyle.display : "",
      usersPanelDisplay: panelStyle ? panelStyle.display : "",
    };
  });

  if (name === "desktop") {
    if (!usersState.hasUsersTab || usersState.usersTabDisplay === "none") {
      throw new Error(`${name}: users tab is not visible`);
    }
    await page.locator('[data-account-tab="users"]').click();
    const createTitle = page.locator('[data-account-panel="users"] h2').filter({ hasText: "Создать пользователя" });
    await createTitle.waitFor({ state: "visible" });
  } else if (usersState.hasUsersTab && usersState.usersTabDisplay !== "none") {
    throw new Error(`${name}: users tab must be hidden`);
  } else if (usersState.hasUsersPanel && usersState.usersPanelDisplay !== "none") {
    throw new Error(`${name}: users panel must be hidden`);
  }

  await page.screenshot({
    path: `C:/Users/Владимир/Desktop/Сайты/Shans/_codex_chat_files/account-push-${name}.png`,
    fullPage: true,
  });
}

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const desktopContext = await browser.newContext({ viewport: { width: 1365, height: 900 } });
    const desktopPage = await desktopContext.newPage();
    await checkViewport(desktopPage, "desktop", 1365, 900);
    await desktopContext.close();

    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      isMobile: true,
      hasTouch: true,
    });
    const mobilePage = await mobileContext.newPage();
    await checkViewport(mobilePage, "mobile", 390, 844);
    await mobileContext.close();
  } finally {
    await browser.close();
  }
})();
"""

    env = os.environ.copy()
    env["NODE_PATH"] = str(node_modules)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(js)
        js_path = handle.name
    try:
        result = subprocess.run(
            [str(node), js_path],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
    finally:
        server.shutdown()
        Config.DATABASE_NAME = original_database_name
        Path(js_path).unlink(missing_ok=True)
        database_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
