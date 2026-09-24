#!/usr/bin/env node
import {readFileSync, writeFileSync} from "node:fs";
import {dirname, join, resolve} from "node:path";
import {fileURLToPath} from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const output = resolve(process.argv[2] || join(root, "..", "cindy-ending-template.html"));

const mime = {
  "assets/brand/cindy-white.png": "image/png",
  "assets/brand/Anton-Latin.woff2": "font/woff2",
  "assets/brand/BebasNeue-Regular.ttf": "font/ttf",
  "assets/audio/click.wav": "audio/wav",
  "assets/audio/switch.wav": "audio/wav",
  "assets/audio/arcade-clear.wav": "audio/wav",
  "assets/audio/logo.wav": "audio/wav",
};

const dataUri = (relativePath) => {
  const absolute = join(root, relativePath);
  return `data:${mime[relativePath]};base64,${readFileSync(absolute).toString("base64")}`;
};

let html = readFileSync(join(root, "index.html"), "utf8");
let css = readFileSync(join(root, "styles.css"), "utf8");
let js = readFileSync(join(root, "app.js"), "utf8");

for (const relativePath of Object.keys(mime)) {
  const uri = dataUri(relativePath);
  html = html.split(relativePath).join(uri);
  css = css.split(relativePath).join(uri);
  js = js.split(relativePath).join(uri);
}

html = html.replace(/<link rel="stylesheet" href="styles\.css"\s*\/>/, `<style>\n${css}\n</style>`);
html = html.replace(/<script src="app\.js"><\/script>/, `<script>\n${js}\n</script>`);
html = html.replace(/\n\s*<!-- SINGLE_FILE_ASSET_BOUNDARY -->/g, "");

writeFileSync(output, html);
console.log(`Built single-file HTML: ${output}`);
