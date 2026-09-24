#!/usr/bin/env node
import {spawnSync} from "node:child_process";
import {existsSync} from "node:fs";

function commandWorks(command, args = ["--version"]) {
  const result = spawnSync(command, args, {stdio: "ignore"});
  return !result.error && result.status === 0;
}
function chromeCandidates() {
  return [
    process.env.CHROME_BIN,
    process.platform === "darwin" ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" : null,
    process.platform === "darwin" ? "/Applications/Chromium.app/Contents/MacOS/Chromium" : null,
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
  ].filter(Boolean);
}

const failures = [];
const major = Number(process.versions.node.split(".")[0]);
if (major < 22 || typeof WebSocket !== "function") failures.push("Node.js 22+ is required");
if (!commandWorks(process.env.FFMPEG || "ffmpeg", ["-version"])) failures.push("ffmpeg not found (set FFMPEG if needed)");
if (!commandWorks(process.env.FFPROBE || "ffprobe", ["-version"])) failures.push("ffprobe not found (set FFPROBE if needed)");
const chrome = chromeCandidates().find((candidate) => candidate.includes("/") ? existsSync(candidate) : commandWorks(candidate));
if (!chrome) failures.push("Chrome/Chromium not found (set CHROME_BIN if needed)");
if (failures.length) {
  console.error(`PREFLIGHT FAILED\n${failures.map((item) => `- ${item}`).join("\n")}`);
  process.exit(1);
}
console.log("PREFLIGHT PASSED: Node, Chrome/Chromium, ffmpeg and ffprobe are available");
