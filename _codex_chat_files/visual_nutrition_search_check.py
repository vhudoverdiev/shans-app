import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app import nutrition as nutrition_module  # noqa: E402
from config import Config  # noqa: E402


class VisualUser:
    id = 1
    is_authenticated = True
    is_active = True
    is_anonymous = False

    def get_id(self):
        return str(self.id)


def main():
    chat_dir = ROOT / "_codex_chat_files"
    chat_dir.mkdir(exist_ok=True)
    database_path = chat_dir / "nutrition-search-visual.db"
    if database_path.exists():
        database_path.unlink()

    original_database_name = Config.DATABASE_NAME
    Config.DATABASE_NAME = str(database_path)
    nutrition_module.current_user = VisualUser()

    app = create_app()
    app.config.update(TESTING=True, LOGIN_DISABLED=True)
    nutrition_module.add_custom_food(1, "Визуальный йогурт", 88, 7, 3, 9)
    nutrition_module.add_custom_food(2, "Визуальный хлебец", 120, 4, 2, 20)

    @app.get("/__visual_ping")
    def visual_ping():
        return "ok"

    server = make_server("127.0.0.1", 5091, app)
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
  await page.setViewportSize({ width, height });
  await page.goto("http://127.0.0.1:5091/nutrition", { waitUntil: "networkidle" });
  const addButtonText = (await page.locator("#add-food-entry button[type='submit']").innerText()).trim();
  if (addButtonText !== "Добавить") {
    throw new Error(`${name}: quick entry button text is ${addButtonText}`);
  }
  const customFoodControls = await page.evaluate(() => {
    const rows = Array.from(document.querySelectorAll(".nutrition-food-row"));
    const ownerRow = rows.find((row) => row.textContent.includes("Визуальный йогурт"));
    const sharedRow = rows.find((row) => row.textContent.includes("Визуальный хлебец"));
    return {
      hasOwnerRow: Boolean(ownerRow),
      ownerCanDelete: Boolean(ownerRow?.querySelector("form[action*='/delete']")),
      hasSharedRow: Boolean(sharedRow),
      sharedCanDelete: Boolean(sharedRow?.querySelector("form[action*='/delete']")),
    };
  });
  if (!customFoodControls.hasOwnerRow || !customFoodControls.hasSharedRow) {
    throw new Error(`${name}: shared custom foods are missing from catalog`);
  }
  if (!customFoodControls.ownerCanDelete || customFoodControls.sharedCanDelete) {
    throw new Error(`${name}: custom food delete visibility is wrong`);
  }
  const search = page.locator("#nutrition-catalog-search");
  const rows = page.locator(".nutrition-food-row");
  await search.fill("греч");
  await page.waitForFunction(() => {
    const rows = Array.from(document.querySelectorAll(".nutrition-food-row"));
    return rows.some((row) => row.hidden) && rows.some((row) => !row.hidden);
  }, null, { timeout: 5000 });

  const state = await page.evaluate(() => {
    const normalize = (value) => String(value || "").trim().toLocaleLowerCase("ru");
    const rows = Array.from(document.querySelectorAll(".nutrition-food-row"));
    const visibleRows = rows.filter((row) => !row.hidden);
    const hiddenRows = rows.filter((row) => row.hidden);
    return {
      visible: visibleRows.length,
      hidden: hiddenRows.length,
      countText: document.querySelector("#nutrition-visible-count")?.textContent?.trim(),
      allVisibleMatch: visibleRows.every((row) => normalize(row.dataset.foodSearch).includes("греч")),
      hiddenDisplay: hiddenRows.length ? getComputedStyle(hiddenRows[0]).display : "",
    };
  });

  if (!state.visible || !state.hidden) {
    throw new Error(`${name}: expected visible and hidden rows, got ${JSON.stringify(state)}`);
  }
  if (!state.allVisibleMatch) {
    throw new Error(`${name}: visible rows include unrelated products`);
  }
  if (state.hiddenDisplay !== "none") {
    throw new Error(`${name}: hidden row display is ${state.hiddenDisplay}`);
  }
  if (String(state.visible) !== state.countText) {
    throw new Error(`${name}: count ${state.countText} does not match visible ${state.visible}`);
  }

  await page.screenshot({
    path: `C:/Users/Владимир/Desktop/Сайты/Shans/_codex_chat_files/nutrition-search-${name}.png`,
    fullPage: true,
  });

  await search.fill("");
  await page.waitForFunction(() => {
    return Array.from(document.querySelectorAll(".nutrition-food-row")).every((row) => !row.hidden);
  }, null, { timeout: 5000 });
}

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const page = await browser.newPage();
    await checkViewport(page, "desktop", 1365, 900);
    await checkViewport(page, "mobile", 390, 844);
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
