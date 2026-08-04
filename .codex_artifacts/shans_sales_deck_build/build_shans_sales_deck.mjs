import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const projectDir = path.resolve("C:/Users/Владимир/Desktop/Сайты/Shans");
const outDir = path.join(projectDir, ".codex_artifacts", "shans_sales_deck_build");
const finalPptx = path.join(projectDir, "Shans_sales_presentation_3_slides.pptx");

const assets = {
  logo: path.join(projectDir, "app/static/logo.png"),
  learning: path.join(projectDir, "_codex_chat_files/english-desktop-blue-theme.png"),
  nutrition: path.join(projectDir, "_codex_chat_files/nutrition-search-desktop.png"),
  workouts: path.join(projectDir, "_codex_chat_files/calendar-small-desktop.png"),
  push: path.join(projectDir, "_codex_chat_files/desktop-push-settings.png"),
};

const C = {
  ink: "#101827",
  slate: "#334155",
  muted: "#667085",
  hair: "#D9E2F1",
  paper: "#F5F7FB",
  blue: "#2F63F1",
  blue2: "#155EEF",
  violet: "#6941C6",
  green: "#0E9F6E",
  amber: "#B7791F",
  rose: "#C2415C",
  white: "#FFFFFF",
  off: "#FBFCFF",
};

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function readBytes(filePath) {
  const bytes = await fs.readFile(filePath);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function box(slide, position, fill, line = "none", radius = 0, shadow = undefined) {
  return slide.shapes.add({
    geometry: radius ? "roundRect" : "rect",
    position,
    fill,
    line: { style: "solid", fill: line, width: line === "none" ? 0 : 1 },
    ...(radius ? { borderRadius: radius } : {}),
    ...(shadow ? { shadow } : {}),
  });
}

function text(slide, value, position, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = value;
  shape.text.style = {
    fontFace: "Arial",
    fontSize: 18,
    color: C.ink,
    ...style,
  };
  return shape;
}

function line(slide, left, top, width, color = C.hair, weight = 1) {
  slide.shapes.add({
    geometry: "line",
    position: { left, top, width, height: 0 },
    fill: "none",
    line: { style: "solid", fill: color, width: weight },
  });
}

function brand(slide, logoBytes, dark = false) {
  slide.images.add({
    blob: logoBytes,
    contentType: "image/png",
    alt: "Логотип Shans",
    fit: "cover",
    position: { left: 72, top: 46, width: 44, height: 44 },
    geometry: "roundRect",
    borderRadius: 12,
  });
  text(slide, "SHANS", { left: 132, top: 48, width: 120, height: 22 }, {
    fontSize: 16,
    bold: true,
    color: dark ? C.white : C.ink,
  });
  text(slide, "personal operating system", { left: 132, top: 70, width: 220, height: 18 }, {
    fontSize: 11,
    color: dark ? "#C7D2FE" : C.muted,
  });
}

function footer(slide, number, dark = false) {
  line(slide, 72, 668, 1136, dark ? "#344054" : "#DDE5F0", 1);
  text(slide, `0${number}`, { left: 72, top: 686, width: 44, height: 18 }, {
    fontSize: 12,
    bold: true,
    color: dark ? "#CBD5E1" : C.muted,
  });
  text(slide, "Shans · sales presentation", { left: 1020, top: 686, width: 188, height: 18 }, {
    fontSize: 11,
    color: dark ? "#CBD5E1" : C.muted,
    alignment: "right",
  });
}

function tag(slide, label, left, top, color = C.blue, fill = C.white, width = 126) {
  box(slide, { left, top, width, height: 34 }, fill, "#D6E0F0", 17);
  text(slide, label, { left, top: top + 8, width, height: 18 }, {
    fontSize: 12,
    bold: true,
    color,
    alignment: "center",
  });
}

function direction(slide, n, title, body, left, top, color) {
  text(slide, n, { left, top, width: 44, height: 24 }, {
    fontSize: 16,
    bold: true,
    color,
  });
  line(slide, left + 56, top + 12, 232, color, 2);
  text(slide, title, { left, top: top + 42, width: 290, height: 34 }, {
    fontSize: 26,
    bold: true,
    color: C.ink,
  });
  text(slide, body, { left, top: top + 88, width: 292, height: 76 }, {
    fontSize: 17,
    color: C.slate,
  });
}

async function main() {
  await fs.mkdir(outDir, { recursive: true });
  const logo = await readBytes(assets.logo);
  const learning = await readBytes(assets.learning);
  const push = await readBytes(assets.push);

  const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });

  const s1 = deck.slides.add();
  s1.background.fill = C.off;
  box(s1, { left: 0, top: 0, width: 1280, height: 720 }, C.off);
  box(s1, { left: 768, top: 0, width: 512, height: 720 }, "#111827");
  brand(s1, logo);
  text(s1, "Продающая презентация проекта", { left: 72, top: 124, width: 430, height: 26 }, {
    fontSize: 16,
    bold: true,
    color: C.blue,
  });
  text(s1, "Shans превращает личные процессы в управляемую систему", { left: 72, top: 178, width: 635, height: 188 }, {
    fontSize: 55,
    bold: true,
    color: C.ink,
  });
  text(s1, "Единое веб-приложение для расписания, проектов, финансов, авто, обучения, спорта и питания. Не просто список функций, а рабочий контур на каждый день.", {
    left: 72,
    top: 396,
    width: 600,
    height: 86,
  }, {
    fontSize: 22,
    color: C.slate,
  });
  tag(s1, "PWA", 72, 536, C.blue);
  tag(s1, "Push", 212, 536, C.violet);
  tag(s1, "2FA", 352, 536, C.green);
  tag(s1, "Excel", 492, 536, C.amber);
  box(s1, { left: 812, top: 88, width: 430, height: 528 }, "#192339", "#334155", 28, "shadow-lg");
  s1.images.add({
    blob: learning,
    contentType: "image/png",
    alt: "Интерфейс раздела обучения Shans",
    fit: "cover",
    crop: { left: 0.02, top: 0.00, right: 0.02, bottom: 0.02 },
    position: { left: 834, top: 112, width: 386, height: 254 },
    geometry: "roundRect",
    borderRadius: 22,
  });
  text(s1, "1 интерфейс", { left: 842, top: 438, width: 180, height: 28 }, {
    fontSize: 26,
    bold: true,
    color: C.white,
  });
  text(s1, "для всех ежедневных решений", { left: 842, top: 474, width: 278, height: 24 }, {
    fontSize: 17,
    color: "#CBD5E1",
  });
  footer(s1, 1);
  s1.speakerNotes.textFrame.setText("[Sources]\nЛокальный проект Shans: README.md, app/templates/*.html, app/routes.py. Визуальный источник: _codex_chat_files/english-desktop-blue-theme.png, app/static/logo.png.");
  s1.speakerNotes.setVisible(true);

  const s2 = deck.slides.add();
  s2.background.fill = C.paper;
  box(s2, { left: 0, top: 0, width: 1280, height: 720 }, C.paper);
  brand(s2, logo);
  text(s2, "Три направления закрывают полный цикл дня", { left: 72, top: 128, width: 920, height: 50 }, {
    fontSize: 38,
    bold: true,
    color: C.ink,
  });
  text(s2, "Shans связывает планирование, учет и развитие в одной логике: пользователь ставит задачи, фиксирует факты и видит прогресс без разрозненных инструментов.", {
    left: 72,
    top: 188,
    width: 920,
    height: 58,
  }, {
    fontSize: 19,
    color: C.slate,
  });
  box(s2, { left: 66, top: 286, width: 1110, height: 248 }, C.white, "#DDE5F0", 28, "shadow-sm");
  direction(s2, "01", "Планирование", "График, задачи, съемки и проекты собираются в один операционный день.", 106, 324, C.blue);
  direction(s2, "02", "Учет", "Бюджет, автомобиль, отчеты и Excel-экспорт превращают данные в контроль.", 446, 324, C.green);
  direction(s2, "03", "Развитие", "Обучение, тренировки и питание делают прогресс измеримым и регулярным.", 786, 324, C.violet);
  box(s2, { left: 116, top: 566, width: 950, height: 54 }, "#EDF4FF", "#C7D7FE", 27);
  text(s2, "Единая траектория: план → действие → факт → прогресс", { left: 150, top: 581, width: 880, height: 24 }, {
    fontSize: 24,
    bold: true,
    color: C.blue2,
    alignment: "center",
  });
  footer(s2, 2);
  s2.speakerNotes.textFrame.setText("[Sources]\nЛокальный проект Shans: app/planner.py, app/routes.py, app/workouts.py, app/nutrition.py, app/learning.py. Визуальный источник: app/static/logo.png.");
  s2.speakerNotes.setVisible(true);

  const s3 = deck.slides.add();
  s3.background.fill = "#0B1220";
  box(s3, { left: 0, top: 0, width: 1280, height: 720 }, "#0B1220");
  brand(s3, logo, true);
  text(s3, "Почему проект можно продавать и развивать дальше", { left: 72, top: 136, width: 650, height: 96 }, {
    fontSize: 43,
    bold: true,
    color: C.white,
  });
  text(s3, "У Shans уже есть признаки зрелого продукта: мобильный сценарий, безопасность, уведомления, экспорт данных и модульная архитектура Flask.", {
    left: 72,
    top: 262,
    width: 586,
    height: 76,
  }, {
    fontSize: 21,
    color: "#CBD5E1",
  });
  box(s3, { left: 72, top: 392, width: 176, height: 104 }, "#111C31", "#27364F", 22);
  box(s3, { left: 280, top: 392, width: 176, height: 104 }, "#111C31", "#27364F", 22);
  box(s3, { left: 488, top: 392, width: 176, height: 104 }, "#111C31", "#27364F", 22);
  text(s3, "PWA", { left: 96, top: 416, width: 120, height: 28 }, { fontSize: 25, bold: true, color: "#A7C7FF" });
  text(s3, "установка на экран", { left: 96, top: 450, width: 126, height: 20 }, { fontSize: 14, color: "#CBD5E1" });
  text(s3, "Push", { left: 304, top: 416, width: 120, height: 28 }, { fontSize: 25, bold: true, color: "#DDD6FE" });
  text(s3, "события и Telegram", { left: 304, top: 450, width: 130, height: 20 }, { fontSize: 14, color: "#CBD5E1" });
  text(s3, "2FA", { left: 512, top: 416, width: 120, height: 28 }, { fontSize: 25, bold: true, color: "#A7F3D0" });
  text(s3, "защита доступа", { left: 512, top: 450, width: 126, height: 20 }, { fontSize: 14, color: "#CBD5E1" });
  line(s3, 72, 532, 592, "#334155", 1);
  text(s3, "Главный продающий тезис", { left: 72, top: 560, width: 260, height: 24 }, {
    fontSize: 17,
    bold: true,
    color: "#93C5FD",
  });
  text(s3, "Shans показывает конкретный порядок: что запланировано, что сделано, где деньги, где прогресс и что требует внимания.", {
    left: 72,
    top: 592,
    width: 624,
    height: 56,
  }, {
    fontSize: 19,
    color: C.white,
  });
  box(s3, { left: 754, top: 102, width: 416, height: 516 }, "#111C31", "#27364F", 30, "shadow-lg");
  s3.images.add({
    blob: push,
    contentType: "image/png",
    alt: "Настройки уведомлений и безопасности Shans",
    fit: "cover",
    crop: { left: 0.08, top: 0.00, right: 0.08, bottom: 0.38 },
    position: { left: 778, top: 126, width: 368, height: 300 },
    geometry: "roundRect",
    borderRadius: 22,
  });
  text(s3, "Готовность к реальному использованию", { left: 782, top: 468, width: 330, height: 62 }, {
    fontSize: 24,
    bold: true,
    color: C.white,
  });
  text(s3, "Проект уже выглядит как продукт, который можно демонстрировать, упаковывать и постепенно выводить к аудитории.", {
    left: 782,
    top: 544,
    width: 336,
    height: 58,
  }, {
    fontSize: 16,
    color: "#CBD5E1",
  });
  footer(s3, 3, true);
  s3.speakerNotes.textFrame.setText("[Sources]\nЛокальный проект Shans: app/static/site.webmanifest, app/static/service-worker.js, app/web_push.py, app/auth.py, app/routes.py, telegram_crm_push.py, README.md. Визуальный источник: _codex_chat_files/desktop-push-settings.png, app/static/logo.png.");
  s3.speakerNotes.setVisible(true);

  for (const [index, slide] of deck.slides.items.entries()) {
    const stem = `sales-slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(path.join(outDir, `${stem}.png`), await deck.export({ slide, format: "png", scale: 1 }));
    await fs.writeFile(path.join(outDir, `${stem}.layout.json`), await (await slide.export({ format: "layout" })).text(), "utf8");
  }
  await writeBlob(path.join(outDir, "Shans_sales_montage.webp"), await deck.export({ format: "webp", montage: true, scale: 1 }));
  const inspect = await deck.inspect({ kind: "slide,textbox,shape,image,notes", maxChars: 16000 });
  await fs.writeFile(path.join(outDir, "Shans_sales.inspect.ndjson"), inspect.ndjson, "utf8");
  const pptx = await PresentationFile.exportPptx(deck);
  await pptx.save(finalPptx);
  console.log(finalPptx);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
