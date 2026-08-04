import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const projectDir = "C:/Users/Владимир/Desktop/Сайты/Shans";
const workDir = path.join(projectDir, ".codex_artifacts", "shans_crm_deck_edit");
const sourcePptx = path.join(workDir, "template-starter.pptx");
const finalPptx = path.join(projectDir, "Shans_CRM_capabilities_3_slides.pptx");
const previewDir = path.join(workDir, "final-preview");
const layoutDir = path.join(workDir, "final-layout");

async function writeBlob(filePath, blob) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

const deck = await PresentationFile.importPptx(await FileBlob.load(sourcePptx));
const snapshot = await deck.inspect({
  kind: "slide,textbox,shape,image,notes",
  maxChars: 100000,
});
const records = snapshot.ndjson
  .split(/\r?\n/)
  .filter(Boolean)
  .map((line) => JSON.parse(line));
const usedTextIds = new Set();

function findText(value) {
  const record = records.find(
    (item) => item.kind === "textbox" && item.text === value && !usedTextIds.has(item.id),
  );
  if (!record) throw new Error(`Text not found: ${value}`);
  usedTextIds.add(record.id);
  return deck.resolve(record.id);
}

function rewrite(oldText, newText, position) {
  const shape = findText(oldText);
  shape.text.replace(oldText, newText);
  if (position) shape.position = position;
  return shape;
}

function removeLargeImages(slide) {
  for (const image of [...slide.images.items]) {
    const frame = image.position;
    if ((frame?.width || 0) > 100) image.delete();
  }
}

const slide1 = deck.slides.getItem(0);
rewrite("personal operating system", "CRM для личных процессов");
rewrite("Продающая презентация проекта", "ОБЗОР ВОЗМОЖНОСТЕЙ CRM");
rewrite(
  "Shans превращает личные процессы в управляемую систему",
  "CRM Shans объединяет ключевые процессы в одной системе",
);
rewrite(
  "Единое веб-приложение для расписания, проектов, финансов, авто, обучения, спорта и питания. Не просто список функций, а рабочий контур на каждый день.",
  "Единое пространство для планирования, проектов, финансов, автомобиля, обучения, тренировок, питания и уведомлений.",
);
rewrite("PWA", "Планирование");
rewrite("Push", "Финансы");
rewrite("2FA", "Развитие");
rewrite("Excel", "Сервисы");
rewrite(
  "1 интерфейс",
  "В CRM входят",
  { left: 842, top: 142, width: 330, height: 40 },
);
rewrite(
  "для всех ежедневных решений",
  "• Календарь, задачи и проекты\n• Бюджет, баланс и отчеты\n• Автомобиль и сервисные работы\n• Обучение и база материалов\n• Тренировки и питание\n• Фото-проекты и съемки\n• Push- и Telegram-уведомления",
  { left: 842, top: 214, width: 338, height: 300 },
);
rewrite("Shans · sales presentation", "Shans · возможности CRM");
removeLargeImages(slide1);
slide1.speakerNotes.textFrame.setText(
  "[Sources]\nЛокальный проект Shans: README.md, app/routes.py, app/planner.py, app/learning.py, app/workouts.py, app/nutrition.py, app/static/logo.png.",
);
slide1.speakerNotes.setVisible(true);

const slide2 = deck.slides.getItem(1);
rewrite("personal operating system", "CRM для личных процессов");
rewrite("Три направления закрывают полный цикл дня", "CRM Shans охватывает три группы процессов");
rewrite(
  "Shans связывает планирование, учет и развитие в одной логике: пользователь ставит задачи, фиксирует факты и видит прогресс без разрозненных инструментов.",
  "Разделы работают в общей системе: задачи формируют план, операции сохраняют факты, а история показывает текущее состояние и прогресс.",
);
rewrite("Планирование", "Работа и проекты");
rewrite(
  "График, задачи, съемки и проекты собираются в один операционный день.",
  "Календарь и расписание\nЗадачи и напоминания\nПроекты и съемки\nИстория выполнения",
  { left: 106, top: 412, width: 292, height: 100 },
);
rewrite("Учет", "Финансы и ресурсы");
rewrite(
  "Бюджет, автомобиль, отчеты и Excel-экспорт превращают данные в контроль.",
  "Доходы и расходы\nБаланс и история\nАвтомобиль и работы\nОтчеты и Excel",
  { left: 446, top: 412, width: 292, height: 100 },
);
rewrite("Развитие", "Знания и здоровье");
rewrite(
  "Обучение, тренировки и питание делают прогресс измеримым и регулярным.",
  "Обучающие материалы\nТренировки и планы\nРацион и продукты\nОтслеживание прогресса",
  { left: 786, top: 412, width: 292, height: 100 },
);
rewrite(
  "Единая траектория: план → действие → факт → прогресс",
  "План → действие → данные → контроль → прогресс",
);
rewrite("Shans · sales presentation", "Shans · возможности CRM");
slide2.speakerNotes.textFrame.setText(
  "[Sources]\nЛокальный проект Shans: app/planner.py, app/routes.py, app/learning.py, app/workouts.py, app/nutrition.py, app/static/logo.png.",
);
slide2.speakerNotes.setVisible(true);

const slide3 = deck.slides.getItem(2);
rewrite("personal operating system", "CRM для личных процессов");
rewrite(
  "Почему проект можно продавать и развивать дальше",
  "Сервисы CRM поддерживают ежедневную работу",
);
rewrite(
  "У Shans уже есть признаки зрелого продукта: мобильный сценарий, безопасность, уведомления, экспорт данных и модульная архитектура Flask.",
  "CRM доступна как веб-приложение и PWA, защищает вход, хранит историю событий и доставляет уведомления через несколько каналов.",
);
rewrite("PWA", "PWA");
rewrite(
  "установка на экран",
  "установка на устройство",
  { left: 96, top: 450, width: 126, height: 34 },
);
rewrite("Push", "Push");
rewrite(
  "события и Telegram",
  "задачи и Telegram",
  { left: 304, top: 450, width: 130, height: 34 },
);
rewrite("2FA", "2FA");
rewrite(
  "защита доступа",
  "защита входа",
  { left: 512, top: 450, width: 126, height: 34 },
);
rewrite("Главный продающий тезис", "Данные и автоматизация");
rewrite(
  "Shans показывает конкретный порядок: что запланировано, что сделано, где деньги, где прогресс и что требует внимания.",
  "Excel-экспорт, история операций, ежедневные сводки и сервисные напоминания.",
);
rewrite(
  "Готовность к реальному использованию",
  "Платформа CRM",
  { left: 790, top: 150, width: 330, height: 54 },
);
rewrite(
  "Проект уже выглядит как продукт, который можно демонстрировать, упаковывать и постепенно выводить к аудитории.",
  "• Модульная архитектура Flask\n• Авторизация и двухфакторная защита\n• Service Worker и установка PWA\n• Web Push и Telegram-каналы\n• Встроенный центр уведомлений\n• Экспорт отчетов и данных",
  { left: 790, top: 228, width: 332, height: 276 },
);
rewrite("Shans · sales presentation", "Shans · возможности CRM");
removeLargeImages(slide3);
slide3.speakerNotes.textFrame.setText(
  "[Sources]\nЛокальный проект Shans: app/auth.py, app/web_push.py, app/static/service-worker.js, app/static/site.webmanifest, app/routes.py, telegram_crm_push.py, app/static/logo.png.",
);
slide3.speakerNotes.setVisible(true);

await fs.mkdir(previewDir, { recursive: true });
await fs.mkdir(layoutDir, { recursive: true });
for (const [index, slide] of deck.slides.items.entries()) {
  const number = String(index + 1).padStart(2, "0");
  await writeBlob(
    path.join(previewDir, `slide-${number}.png`),
    await deck.export({ slide, format: "png", scale: 1 }),
  );
  await fs.writeFile(
    path.join(layoutDir, `slide-${number}.layout.json`),
    await (await slide.export({ format: "layout" })).text(),
    "utf8",
  );
}

await writeBlob(
  path.join(workDir, "Shans_CRM_capabilities_montage.webp"),
  await deck.export({ format: "webp", montage: true, scale: 1 }),
);
const finalInspect = await deck.inspect({
  kind: "slide,textbox,shape,image,notes",
  maxChars: 100000,
});
await fs.writeFile(path.join(workDir, "final-inspect.ndjson"), finalInspect.ndjson, "utf8");
const pptx = await PresentationFile.exportPptx(deck);
await pptx.save(finalPptx);
console.log(finalPptx);
