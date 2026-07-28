import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const outDir = path.resolve(".codex_artifacts");
const finalPptx = path.resolve("Shans_presentation_light_3_slides.pptx");
const logoPath = path.resolve("app/static/logo.png");
const developerPhotoPath = path.resolve(".codex_artifacts/developer.jpg");

const ink = "#111827";
const softInk = "#334155";
const muted = "#64748b";
const blue = "#2563eb";
const purple = "#7c3aed";
const paper = "#f6f8fc";
const line = "#dbe3ef";

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function readBytes(filePath) {
  const bytes = await fs.readFile(filePath);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function t(slide, value, position, style = {}) {
  const s = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  s.text = value;
  s.text.style = {
    fontFace: "Arial",
    fontSize: 18,
    color: ink,
    ...style,
  };
  return s;
}

function box(slide, position, fill, stroke = line, radius = 0, shadow = undefined) {
  return slide.shapes.add({
    geometry: radius ? "roundRect" : "rect",
    position,
    fill,
    line: { style: "solid", fill: stroke, width: stroke === "none" ? 0 : 1 },
    borderRadius: radius,
    ...(shadow ? { shadow } : {}),
  });
}

function rule(slide, left, top, width, color = line, weight = 1) {
  slide.shapes.add({
    geometry: "line",
    position: { left, top, width, height: 0 },
    fill: "none",
    line: { style: "solid", fill: color, width: weight },
  });
}

function footer(slide, number) {
  rule(slide, 72, 652, 1136, "#dde5f0", 1);
  t(slide, `0${number}`, { left: 72, top: 670, width: 42, height: 20 }, {
    fontSize: 12,
    bold: true,
    color: muted,
  });
  t(slide, "Shans · project presentation", { left: 1058, top: 670, width: 150, height: 20 }, {
    fontSize: 11,
    color: muted,
    alignment: "right",
  });
}

function topMark(slide, logoBytes) {
  slide.images.add({
    blob: logoBytes,
    contentType: "image/png",
    alt: "Логотип Shans",
    fit: "cover",
    position: { left: 72, top: 44, width: 42, height: 42 },
    geometry: "roundRect",
    borderRadius: 11,
  });
  t(slide, "SHANS", { left: 130, top: 46, width: 110, height: 22 }, {
    fontSize: 16,
    bold: true,
    color: ink,
  });
  t(slide, "personal management system", { left: 130, top: 68, width: 220, height: 18 }, {
    fontSize: 11,
    color: muted,
  });
}

function chip(slide, label, x, y, fill = "#ffffff", stroke = line, color = blue) {
  box(slide, { left: x, top: y, width: 132, height: 34 }, fill, stroke, 17);
  t(slide, label, { left: x, top: y + 8, width: 132, height: 18 }, {
    fontSize: 12,
    bold: true,
    color,
    alignment: "center",
  });
}

function metric(slide, n, title, body, left, top) {
  t(slide, n, { left, top, width: 40, height: 22 }, { fontSize: 13, bold: true, color: blue });
  t(slide, title, { left: left + 48, top, width: 250, height: 24 }, { fontSize: 19, bold: true, color: ink });
  t(slide, body, { left: left + 48, top: top + 32, width: 265, height: 42 }, { fontSize: 14, color: muted });
}

async function main() {
  await fs.mkdir(outDir, { recursive: true });
  const logoBytes = await readBytes(logoPath);
  const developerBytes = await readBytes(developerPhotoPath);
  const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });

  const s1 = deck.slides.add();
  s1.background.fill = "#ffffff";
  box(s1, { left: 0, top: 0, width: 1280, height: 720 }, "#ffffff", "none");
  box(s1, { left: 804, top: 82, width: 372, height: 522 }, "#f8fbff", "#dbe3ef", 30, "shadow-sm");
  topMark(s1, logoBytes);
  t(s1, "Shans помогает держать порядок", { left: 72, top: 164, width: 560, height: 124 }, {
    fontSize: 54,
    bold: true,
    color: ink,
  });
  t(s1, "Личная система для графика, проектов, финансов, авто, обучения и здоровья в одном аккуратном веб-приложении.", {
    left: 72,
    top: 318,
    width: 560,
    height: 76,
  }, {
    fontSize: 22,
    color: softInk,
  });
  chip(s1, "PWA", 72, 452);
  chip(s1, "Push", 214, 452);
  chip(s1, "2FA", 356, 452);
  chip(s1, "Excel", 498, 452);
  s1.images.add({
    blob: developerBytes,
    contentType: "image/jpeg",
    alt: "Фотография разработчика проекта Shans",
    fit: "cover",
    crop: { left: 0.03, top: 0.15, right: 0.25, bottom: 0.01 },
    position: { left: 828, top: 102, width: 296, height: 474 },
    geometry: "roundRect",
    borderRadius: 24,
  });
  box(s1, { left: 780, top: 552, width: 234, height: 74 }, "#ffffff", "#dde5f0", 22, "shadow-sm");
  t(s1, "1 интерфейс", { left: 802, top: 572, width: 190, height: 22 }, { fontSize: 22, bold: true, color: ink });
  t(s1, "для ежедневных процессов", { left: 802, top: 600, width: 190, height: 18 }, { fontSize: 12, color: muted });
  footer(s1, 1);
  s1.speakerNotes.textFrame.setText("[Sources]\nЛокальный проект Shans; фотография разработчика из файла пользователя.");
  s1.speakerNotes.setVisible(true);

  const s2 = deck.slides.add();
  s2.background.fill = paper;
  box(s2, { left: 0, top: 0, width: 1280, height: 720 }, paper, "none");
  topMark(s2, logoBytes);
  t(s2, "Архитектура продукта", { left: 72, top: 138, width: 460, height: 42 }, {
    fontSize: 36,
    bold: true,
    color: ink,
  });
  t(s2, "Внутри Shans нет случайных разделов. Каждый блок отвечает за конкретный сценарий: запланировать, выполнить, зафиксировать результат и вернуться к данным позже.", {
    left: 72,
    top: 206,
    width: 470,
    height: 92,
  }, {
    fontSize: 19,
    color: softInk,
  });
  box(s2, { left: 670, top: 116, width: 424, height: 416 }, "#ffffff", line, 34, "shadow-sm");
  box(s2, { left: 812, top: 250, width: 140, height: 140 }, "#eef2ff", "none", 34);
  t(s2, "SHANS", { left: 812, top: 300, width: 140, height: 28 }, {
    fontSize: 23,
    bold: true,
    color: ink,
    alignment: "center",
  });
  t(s2, "core", { left: 812, top: 332, width: 140, height: 20 }, {
    fontSize: 12,
    color: blue,
    alignment: "center",
  });
  for (const [label, x, y, color] of [
    ["График", 736, 156, blue],
    ["Съёмки", 946, 176, purple],
    ["Отчёты", 952, 414, "#15803d"],
    ["Авто", 720, 434, "#d97706"],
    ["Обучение", 636, 296, "#475569"],
    ["Спорт", 1032, 296, "#15803d"],
  ]) {
    chip(s2, label, x, y, "#ffffff", line, color);
  }
  rule(s2, 650, 558, 500, "#cbd5e1", 1);
  t(s2, "Единая логика: данные не теряются между разделами", { left: 650, top: 576, width: 500, height: 22 }, {
    fontSize: 15,
    bold: true,
    color: muted,
    alignment: "center",
  });
  metric(s2, "01", "Планирование", "Календарь, задачи, статусы и напоминания.", 72, 350);
  metric(s2, "02", "Учет", "Бюджет, авто, история и экспорт в Excel.", 72, 444);
  metric(s2, "03", "Развитие", "Курсы, тренировки, питание и прогресс.", 72, 538);
  footer(s2, 2);
  s2.speakerNotes.textFrame.setText("[Sources]\nЛокальный проект Shans: app/routes.py, app/planner.py, app/learning.py, app/workouts.py, app/nutrition.py.");
  s2.speakerNotes.setVisible(true);

  const s3 = deck.slides.add();
  s3.background.fill = "#ffffff";
  box(s3, { left: 0, top: 0, width: 1280, height: 720 }, "#ffffff", "none");
  box(s3, { left: 72, top: 92, width: 372, height: 520 }, "#f8fbff", "#dbe3ef", 28);
  topMark(s3, logoBytes);
  t(s3, "Почему это выглядит цельно", { left: 104, top: 174, width: 290, height: 82 }, {
    fontSize: 36,
    bold: true,
    color: ink,
  });
  t(s3, "Проект собран вокруг реальных ежедневных задач, поэтому его можно расширять без потери логики.", {
    left: 104,
    top: 282,
    width: 286,
    height: 88,
  }, {
    fontSize: 19,
    color: softInk,
  });
  chip(s3, "Практичность", 104, 416, "#eef2ff", "#c7d2fe", blue);
  chip(s3, "Мобильность", 104, 466, "#f5f3ff", "#ddd6fe", purple);
  chip(s3, "Безопасность", 104, 516, "#ecfdf5", "#bbf7d0", "#15803d");
  t(s3, "Разработчик", { left: 520, top: 74, width: 150, height: 22 }, {
    fontSize: 13,
    bold: true,
    color: blue,
  });
  t(s3, "Владимир\nХудовердиев", { left: 520, top: 108, width: 340, height: 84 }, {
    fontSize: 42,
    bold: true,
    color: ink,
  });
  t(s3, "Shans - авторский проект, созданный под личные рабочие процессы: от расписания и финансов до проектов, обучения и здоровья.", {
    left: 520,
    top: 218,
    width: 430,
    height: 82,
  }, {
    fontSize: 20,
    color: softInk,
  });
  rule(s3, 520, 332, 446, "#bfdbfe", 2);
  t(s3, "Итоговая ценность", { left: 520, top: 368, width: 220, height: 22 }, {
    fontSize: 16,
    bold: true,
    color: ink,
  });
  t(s3, "Меньше хаоса в повседневных данных. Больше контроля, прозрачности и внимания на важном.", {
    left: 520,
    top: 404,
    width: 398,
    height: 102,
  }, {
    fontSize: 28,
    bold: true,
    color: ink,
  });
  s3.images.add({
    blob: developerBytes,
    contentType: "image/jpeg",
    alt: "Фотография разработчика проекта Shans",
    fit: "cover",
    crop: { left: 0.03, top: 0.17, right: 0.23, bottom: 0.01 },
    position: { left: 992, top: 76, width: 216, height: 548 },
    geometry: "roundRect",
    borderRadius: 26,
  });
  footer(s3, 3);
  s3.speakerNotes.textFrame.setText("[Sources]\nФотография разработчика: файл пользователя C:/Users/Владимир/Desktop/ываыва.jpg.\nЛогика и функции проекта: локальный проект Shans.");
  s3.speakerNotes.setVisible(true);

  for (const [index, slide] of deck.slides.items.entries()) {
    const stem = `light-slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(path.join(outDir, `${stem}.png`), await deck.export({ slide, format: "png", scale: 1 }));
    await fs.writeFile(path.join(outDir, `${stem}.layout.json`), await (await slide.export({ format: "layout" })).text());
  }
  await writeBlob(path.join(outDir, "Shans_light_montage.webp"), await deck.export({ format: "webp", montage: true, scale: 1 }));
  const pptx = await PresentationFile.exportPptx(deck);
  await pptx.save(finalPptx);
  console.log(finalPptx);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
