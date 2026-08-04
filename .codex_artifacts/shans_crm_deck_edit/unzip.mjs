import fs from "node:fs/promises";
import JSZip from "C:/Users/Владимир/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/jszip/lib/index.js";

const args = process.argv.slice(2);
const listMode = args[0] === "-Z1";
const printMode = args[0] === "-p";
const archivePath = args[1];
const entryName = args[2];

if ((!listMode && !printMode) || !archivePath) {
  process.exit(2);
}

const zip = await JSZip.loadAsync(await fs.readFile(archivePath));

if (listMode) {
  process.stdout.write(`${Object.keys(zip.files).join("\n")}\n`);
} else {
  const entry = zip.file(entryName);
  if (!entry) process.exit(1);
  process.stdout.write(await entry.async("nodebuffer"));
}
