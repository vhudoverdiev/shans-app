import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const deck = await PresentationFile.importPptx(await FileBlob.load("C:/Users/Владимир/Desktop/Сайты/Shans/.codex_artifacts/shans_crm_deck_edit/template-starter.pptx"));
const image = deck.resolve("im/0jmxony1");
const slide = deck.resolve("sl/y90nupkv");
const title = deck.resolve("sh/sryl4zqx");

function methods(value) {
  const names = new Set();
  let current = value;
  while (current && current !== Object.prototype) {
    for (const name of Object.getOwnPropertyNames(current)) names.add(name);
    current = Object.getPrototypeOf(current);
  }
  return [...names].sort();
}

console.log(JSON.stringify({
  image: methods(image),
  slide: methods(slide),
  images: methods(slide.images),
  shapes: methods(slide.shapes),
  title: methods(title),
  titleText: methods(title.text),
  titleTextString: String(title.text),
}, null, 2));
