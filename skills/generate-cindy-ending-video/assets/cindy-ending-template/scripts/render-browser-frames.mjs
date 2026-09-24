#!/usr/bin/env node
import {spawn, spawnSync} from "node:child_process";
import {existsSync, mkdirSync, readFileSync, writeFileSync} from "node:fs";
import {tmpdir} from "node:os";
import {basename, join, resolve} from "node:path";
import {pathToFileURL} from "node:url";

function arg(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

function findChrome() {
  const candidates = [
    process.env.CHROME_BIN,
    process.platform === "darwin" ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" : null,
    process.platform === "darwin" ? "/Applications/Chromium.app/Contents/MacOS/Chromium" : null,
    process.platform === "win32" ? `${process.env.PROGRAMFILES || "C:\\Program Files"}\\Google\\Chrome\\Application\\chrome.exe` : null,
    process.platform === "win32" ? `${process.env["PROGRAMFILES(X86)"] || "C:\\Program Files (x86)"}\\Google\\Chrome\\Application\\chrome.exe` : null,
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (candidate.includes("/") || candidate.includes("\\")) {
      if (existsSync(candidate)) return candidate;
      continue;
    }
    const probe = spawnSync(candidate, ["--version"], {stdio: "ignore"});
    if (!probe.error && probe.status === 0) return candidate;
  }
  throw new Error("Chrome/Chromium not found. Set CHROME_BIN to its executable path.");
}

async function waitForPort(file, child) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (child.exitCode !== null) throw new Error(`Chrome exited before opening DevTools (code ${child.exitCode}).`);
    if (existsSync(file)) {
      const [port] = readFileSync(file, "utf8").trim().split(/\r?\n/);
      if (port) return Number(port);
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 50));
  }
  throw new Error("Timed out waiting for Chrome DevTools.");
}

async function connectCdp(url) {
  if (typeof WebSocket !== "function") throw new Error("Node.js 22 or newer is required (global WebSocket is unavailable). ");
  const socket = new WebSocket(url);
  await new Promise((resolveOpen, rejectOpen) => {
    socket.addEventListener("open", resolveOpen, {once: true});
    socket.addEventListener("error", rejectOpen, {once: true});
  });
  let id = 0;
  const pending = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const {resolveCall, rejectCall} = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) rejectCall(new Error(message.error.message));
    else resolveCall(message.result);
  });
  return {
    call(method, params = {}) {
      const callId = ++id;
      socket.send(JSON.stringify({id: callId, method, params}));
      return new Promise((resolveCall, rejectCall) => pending.set(callId, {resolveCall, rejectCall}));
    },
    close() { socket.close(); },
  };
}

const template = resolve(arg("--template"));
const configPath = resolve(arg("--config"));
const outputDir = resolve(arg("--output-dir"));
const locale = arg("--locale", "zh");
const scene = arg("--scene", "summary");
const width = Number(arg("--width", "1920"));
const height = Number(arg("--height", "1080"));
const duration = Number(arg("--duration", scene === "summary" ? "3.5" : "2"));
if (!existsSync(template) || !existsSync(configPath)) throw new Error("Template or config file does not exist.");
if (!Number.isFinite(width) || !Number.isFinite(height) || !Number.isFinite(duration)) throw new Error("Invalid render dimensions or duration.");
if (!['summary', 'ending'].includes(scene)) throw new Error("--scene must be summary or ending.");

mkdirSync(outputDir, {recursive: true});
const config = JSON.parse(readFileSync(configPath, "utf8"));
const profile = join(tmpdir(), `cindy-ending-chrome-${process.pid}-${Date.now()}`);
mkdirSync(profile, {recursive: true});
const chrome = spawn(findChrome(), [
  "--headless=new",
  "--disable-gpu",
  "--hide-scrollbars",
  "--no-first-run",
  "--no-default-browser-check",
  "--remote-debugging-port=0",
  `--user-data-dir=${profile}`,
  "about:blank",
], {stdio: "ignore"});

let cdp;
try {
  const port = await waitForPort(join(profile, "DevToolsActivePort"), chrome);
  const targets = await fetch(`http://127.0.0.1:${port}/json/list`).then((response) => response.json());
  const target = targets.find((item) => item.type === "page");
  if (!target) throw new Error("Chrome did not expose a page target.");
  cdp = await connectCdp(target.webSocketDebuggerUrl);
  await cdp.call("Page.enable");
  await cdp.call("Runtime.enable");
  await cdp.call("Emulation.setDeviceMetricsOverride", {width, height, deviceScaleFactor: 1, mobile: false});
  const stored = JSON.stringify({
    previewLocale: locale,
    editLocale: locale,
    copy: config.copy,
    ending: config.ending,
    timing: config.timing,
  });
  await cdp.call("Page.addScriptToEvaluateOnNewDocument", {
    source: `localStorage.setItem("cindy-summary-ending-template-v1", ${JSON.stringify(stored)});`,
  });
  await cdp.call("Page.navigate", {url: pathToFileURL(template).href});
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const ready = await cdp.call("Runtime.evaluate", {expression: "document.readyState === 'complete'", returnByValue: true});
    if (ready.result.value) break;
    await new Promise((resolveWait) => setTimeout(resolveWait, 50));
  }
  const setup = `
    (async () => {
      await document.fonts.ready;
      document.documentElement.style.cssText += 'width:${width}px;height:${height}px;overflow:hidden';
      document.body.style.cssText += 'width:${width}px;height:${height}px;overflow:hidden;margin:0';
      document.querySelector('.app-shell').style.cssText += 'width:${width}px;height:${height}px;min-height:${height}px;padding:0;margin:0';
      document.querySelector('.app-header').style.display = 'none';
      document.querySelector('.config-panel').style.display = 'none';
      document.querySelector('.preview-panel').style.cssText += 'width:${width}px;margin:0;padding:0';
      document.querySelector('.preview-head').style.display = 'none';
      document.querySelector('.stage-frame').style.cssText += 'padding:0;border:0;background:transparent';
      document.querySelector('.timeline').style.display = 'none';
      document.querySelector('#stage').style.cssText += 'width:${width}px;height:${height}px;aspect-ratio:auto';
      return true;
    })()
  `;
  await cdp.call("Runtime.evaluate", {expression: setup, awaitPromise: true, returnByValue: true});

  const frameCount = Math.max(1, Math.ceil(duration * 30));
  for (let frame = 0; frame < frameCount; frame += 1) {
    const timeMs = frame / 30 * 1000;
    const update = `
      (() => {
        const stage = document.querySelector('#stage');
        const summary = document.querySelector('#summary-scene');
        const ending = document.querySelector('#ending-scene');
        stage.classList.add('is-playing');
        summary.classList.toggle('is-active', ${scene === "summary"});
        ending.classList.toggle('is-active', ${scene === "ending"});
        void stage.offsetWidth;
        for (const animation of document.getAnimations({subtree:true})) {
          const target = animation.effect && animation.effect.target;
          if (target && target.closest('#${scene === "summary" ? "summary-scene" : "ending-scene"}')) {
            animation.pause();
            animation.currentTime = ${timeMs};
          }
        }
      })()
    `;
    await cdp.call("Runtime.evaluate", {expression: update});
    const shot = await cdp.call("Page.captureScreenshot", {
      format: "png",
      fromSurface: true,
      captureBeyondViewport: false,
      clip: {x: 0, y: 0, width, height, scale: 1},
    });
    const name = `${scene}-${String(frame + 1).padStart(4, "0")}.png`;
    writeFileSync(join(outputDir, name), Buffer.from(shot.data, "base64"));
  }
  console.log(`Rendered ${scene}: ${frameCount} frames (${basename(outputDir)})`);
} finally {
  cdp?.close();
  chrome.kill("SIGTERM");
}
