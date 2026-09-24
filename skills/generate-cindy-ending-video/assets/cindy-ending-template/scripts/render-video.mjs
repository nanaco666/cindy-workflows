#!/usr/bin/env node
import {execFileSync, spawnSync} from "node:child_process";
import {existsSync, mkdirSync, readFileSync, writeFileSync} from "node:fs";
import {tmpdir} from "node:os";
import {dirname, join, resolve} from "node:path";
import {fileURLToPath} from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const frameRenderer = join(root, "scripts/render-browser-frames.mjs");
const ffmpeg = process.env.FFMPEG || "ffmpeg";
const ffprobe = process.env.FFPROBE || "ffprobe";
const clickSound = join(root, "assets/audio/click.wav");
const logoSound = join(root, "assets/audio/logo.wav");
const arcadeSound = join(root, "assets/audio/arcade-clear.wav");

const defaults = {
  copy: {
    zh: ["安装插件，扩展 Cindy。", "一句话，调起真实工具。", "跨应用、跨设备执行任务。", "从开始到完成，少一步切换。"],
    en: ["Install plugins. Extend Cindy.", "One prompt. Real tools.", "Work across apps and devices.", "Finish tasks. Less switching."],
  },
  ending: {color: "#F70121", animation: "center-wipe"},
  timing: {summaryMs: 3500, endingMs: 2000},
};

function arg(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : fallback;
}
function requireCommand(command, variable) {
  const result = spawnSync(command, ["-version"], {stdio: "ignore"});
  if (result.error || result.status !== 0) throw new Error(`${command} is required. Install it or set ${variable}.`);
}
function validateHex(value) {
  return /^#[0-9A-F]{6}$/i.test(value) ? value.toUpperCase() : defaults.ending.color;
}
function normalizeTiming(value) {
  const totalMs = defaults.timing.summaryMs + defaults.timing.endingMs;
  const summaryMs = Number(value?.summaryMs ?? defaults.timing.summaryMs);
  const normalized = Number.isFinite(summaryMs)
    ? Math.min(totalMs - 2000, Math.max(1500, Math.round(summaryMs / 100) * 100))
    : defaults.timing.summaryMs;
  return {summaryMs: normalized, endingMs: totalMs - normalized};
}

if (process.argv.includes("--help")) {
  console.log(`Usage: node scripts/render-video.mjs [options]\n\n  --config <file>   JSON exported from the HTML template\n  --input <file>    Optional source video\n  --output <file>   MP4 output path\n  --locale <zh|en>  Summary language (default: zh)\n  --width <number>  Output width (default: 1920)\n  --height <number> Output height (default: 1080)`);
  process.exit(0);
}

requireCommand(ffmpeg, "FFMPEG");
requireCommand(ffprobe, "FFPROBE");
const configPath = arg("--config");
const rawConfig = configPath && existsSync(resolve(configPath))
  ? JSON.parse(readFileSync(resolve(configPath), "utf8"))
  : defaults;
const locale = arg("--locale", "zh");
if (!["zh", "en"].includes(locale)) throw new Error("--locale must be zh or en.");
const width = Number(arg("--width", "1920"));
const height = Number(arg("--height", "1080"));
const input = arg("--input");
const output = resolve(arg("--output", "renders/cindy-summary-ending.mp4"));
const timing = normalizeTiming(rawConfig.timing);
const config = {
  version: 1,
  copy: {
    zh: Array.isArray(rawConfig.copy?.zh) ? rawConfig.copy.zh.slice(0, 4).map((text) => String(text).slice(0, 30)) : defaults.copy.zh,
    en: Array.isArray(rawConfig.copy?.en) ? rawConfig.copy.en.slice(0, 4).map((text) => String(text).slice(0, 30)) : defaults.copy.en,
  },
  ending: {
    color: validateHex(rawConfig.ending?.color || defaults.ending.color),
    animation: ["center-wipe", "fade-scale", "slide-up", "arcade-clear"].includes(rawConfig.ending?.animation)
      ? rawConfig.ending.animation : defaults.ending.animation,
  },
  timing,
};
if (!config.copy[locale].length) throw new Error(`No ${locale} copy found.`);
if (!Number.isFinite(width) || !Number.isFinite(height) || width < 320 || height < 240) throw new Error("Invalid output dimensions.");

mkdirSync(dirname(output), {recursive: true});
const work = join(tmpdir(), `cindy-ending-render-${Date.now()}`);
const summaryFrames = join(work, "summary-frames");
const endingFrames = join(work, "ending-frames");
const summaryMp4 = join(work, "summary.mp4");
const endingMp4 = join(work, "ending.mp4");
const inputWithAudio = join(work, "input-with-audio.mp4");
const normalizedConfig = join(work, "config.json");
mkdirSync(summaryFrames, {recursive: true});
mkdirSync(endingFrames, {recursive: true});
writeFileSync(normalizedConfig, JSON.stringify(config, null, 2));

for (const [scene, frames, seconds] of [
  ["summary", summaryFrames, timing.summaryMs / 1000],
  ["ending", endingFrames, timing.endingMs / 1000],
]) {
  execFileSync(process.execPath, [frameRenderer,
    "--template", join(root, "index.html"), "--config", normalizedConfig,
    "--locale", locale, "--scene", scene, "--output-dir", frames,
    "--width", String(width), "--height", String(height), "--duration", String(seconds),
  ], {stdio: "inherit"});
}

const summarySeconds = timing.summaryMs / 1000;
const endingSeconds = timing.endingMs / 1000;
const copy = config.copy[locale];
const clickBranches = copy.map((_, index) => `[c${index}]adelay=${120 + index * 150}:all=1,volume=0.24,apad,atrim=duration=${summarySeconds}[k${index}]`).join(";");
const splitLabels = copy.map((_, index) => `[c${index}]`).join("");
const mixLabels = copy.map((_, index) => `[k${index}]`).join("");
const summaryAudio = `[2:a]asplit=${copy.length}${splitLabels};${clickBranches};[1:a]atrim=duration=${summarySeconds}[silence];${mixLabels}[silence]amix=inputs=${copy.length + 1}:duration=first:normalize=0[a]`;
execFileSync(ffmpeg, [
  "-y", "-framerate", "30", "-i", join(summaryFrames, "summary-%04d.png"),
  "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000", "-i", clickSound,
  "-t", String(summarySeconds), "-filter_complex", `[0:v]format=yuv420p[v];${summaryAudio}`,
  "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
  "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-shortest", summaryMp4,
], {stdio: "inherit"});

const endingAudioInputs = ["-i", logoSound];
let endingAudioFilter = `[1:a]adelay=500:all=1,apad,atrim=duration=${endingSeconds}[a]`;
if (config.ending.animation === "arcade-clear") {
  endingAudioInputs.push("-i", arcadeSound);
  endingAudioFilter = `[1:a]adelay=500:all=1,apad,atrim=duration=${endingSeconds}[logo];[2:a]volume=0.45,adelay=760:all=1,apad,atrim=duration=${endingSeconds}[arcade];[logo][arcade]amix=inputs=2:duration=first:normalize=0[a]`;
}
execFileSync(ffmpeg, [
  "-y", "-framerate", "30", "-i", join(endingFrames, "ending-%04d.png"), ...endingAudioInputs,
  "-filter_complex", endingAudioFilter, "-map", "0:v", "-map", "[a]", "-t", String(endingSeconds),
  "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30",
  "-c:a", "aac", "-b:a", "192k", endingMp4,
], {stdio: "inherit"});

let sourceInput = input ? resolve(input) : null;
if (sourceInput) {
  if (!existsSync(sourceInput)) throw new Error(`Input video not found: ${sourceInput}`);
  let hasAudio = false;
  try {
    hasAudio = execFileSync(ffprobe, ["-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", sourceInput], {encoding: "utf8"}).trim().length > 0;
  } catch {}
  if (!hasAudio) {
    execFileSync(ffmpeg, ["-y", "-i", sourceInput, "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000", "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", inputWithAudio], {stdio: "inherit"});
    sourceInput = inputWithAudio;
  }
}

const inputs = sourceInput ? [sourceInput, summaryMp4, endingMp4] : [summaryMp4, endingMp4];
const args = ["-y"];
for (const file of inputs) args.push("-i", file);
const videos = inputs.map((_, i) => `[${i}:v]fps=30,scale=${width}:${height}:force_original_aspect_ratio=decrease,pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p,setpts=PTS-STARTPTS[v${i}]`).join(";");
const audios = inputs.map((_, i) => `[${i}:a]aresample=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a${i}]`).join(";");
const concat = inputs.map((_, i) => `[v${i}][a${i}]`).join("");
args.push("-filter_complex", `${videos};${audios};${concat}concat=n=${inputs.length}:v=1:a=1[v][a]`, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output);
execFileSync(ffmpeg, args, {stdio: "inherit"});
console.log(`Rendered: ${output}`);
