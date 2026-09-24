const STORAGE_KEY = "cindy-summary-ending-template-v1";
const SUMMARY_DURATION = 3500;
const ENDING_DURATION = 2000;
const MIN_SUMMARY_DURATION = 1500;
const MIN_ENDING_DURATION = 2000;
const TOTAL_DURATION = SUMMARY_DURATION + ENDING_DURATION;

const defaults = {
  previewLocale: "zh",
  editLocale: "zh",
  copy: {
    zh: [
      "安装插件，扩展 Cindy。",
      "一句话，调起真实工具。",
      "跨应用、跨设备执行任务。",
      "从开始到完成，少一步切换。",
    ],
    en: [
      "Install plugins. Extend Cindy.",
      "One prompt. Real tools.",
      "Work across apps and devices.",
      "Finish tasks. Less switching.",
    ],
  },
  ending: {
    color: "#F70121",
    animation: "center-wipe",
  },
  timing: {
    summaryMs: SUMMARY_DURATION,
    endingMs: ENDING_DURATION,
  },
};

const labels = {
  zh: {
    kicker: "插件工作流",
    footer: "让 Cindy 直接把任务做完。",
  },
  en: {
    kicker: "PLUGIN WORKFLOW",
    footer: "Let Cindy finish the work.",
  },
};

const cloneDefaults = () => JSON.parse(JSON.stringify(defaults));

function normalizeStoredTiming(value) {
  const summaryMs = Number(value?.summaryMs ?? SUMMARY_DURATION);
  if (!Number.isFinite(summaryMs)) return { ...defaults.timing };
  const normalizedSummaryMs = clampSummaryDuration(summaryMs);
  return {
    summaryMs: normalizedSummaryMs,
    endingMs: TOTAL_DURATION - normalizedSummaryMs,
  };
}

function loadState() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (!stored) return cloneDefaults();
    return {
      ...cloneDefaults(),
      ...stored,
      copy: { ...cloneDefaults().copy, ...stored.copy },
      ending: { ...cloneDefaults().ending, ...stored.ending },
      timing: normalizeStoredTiming(stored.timing),
    };
  } catch {
    return cloneDefaults();
  }
}

let state = loadState();
let playbackTimers = [];

const dom = {
  stage: document.querySelector("#stage"),
  summaryScene: document.querySelector("#summary-scene"),
  endingScene: document.querySelector("#ending-scene"),
  summaryRows: document.querySelector("#summary-rows"),
  summaryKicker: document.querySelector("#summary-kicker"),
  summaryFooter: document.querySelector("#summary-footer"),
  previewLocaleButtons: [...document.querySelectorAll("[data-preview-locale]")],
  editLocaleButtons: [...document.querySelectorAll("[data-edit-locale]")],
  copyList: document.querySelector("#copy-list"),
  addCopy: document.querySelector("#add-copy"),
  endingColor: document.querySelector("#ending-color"),
  endingColorText: document.querySelector("#ending-color-text"),
  endingAnimation: document.querySelector("#ending-animation"),
  playPreview: document.querySelector("#play-preview"),
  playLabel: document.querySelector("#play-preview span:last-child"),
  timelineTrack: document.querySelector("#timeline-track"),
  timelineSummary: document.querySelector(".timeline-summary"),
  timelineEnding: document.querySelector(".timeline-ending"),
  timelineDivider: document.querySelector("#timeline-divider"),
  timelineSummaryLabel: document.querySelector("#timeline-summary-label"),
  timelineEndingLabel: document.querySelector("#timeline-ending-label"),
  clickSound: document.querySelector("#click-sound"),
  switchSound: document.querySelector("#switch-sound"),
  arcadeSound: document.querySelector("#arcade-sound"),
  logoSound: document.querySelector("#logo-sound"),
  resetConfig: document.querySelector("#reset-config"),
  downloadConfig: document.querySelector("#download-config"),
  importConfig: document.querySelector("#import-config"),
  configFile: document.querySelector("#config-file"),
  copyConfig: document.querySelector("#copy-config"),
  saveState: document.querySelector("#save-state"),
  actionStatus: document.querySelector("#action-status"),
};

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  dom.saveState.textContent = "已自动保存";
  dom.saveState.animate(
    [{ opacity: 0.4 }, { opacity: 1 }],
    { duration: 260, easing: "ease-out" },
  );
}

function renderPreview() {
  const locale = state.previewLocale;
  const copy = state.copy[locale];

  dom.summaryScene.dataset.locale = locale;
  dom.summaryKicker.textContent = labels[locale].kicker;
  dom.summaryFooter.textContent = labels[locale].footer;
  dom.summaryRows.style.setProperty("--row-count", copy.length);
  dom.summaryRows.replaceChildren(
    ...copy.map((text, index) => {
      const row = document.createElement("div");
      row.className = "summary-row";
      row.style.setProperty("--row-index", index);

      const order = document.createElement("span");
      order.className = "summary-index";
      order.textContent = String(index + 1).padStart(2, "0");

      const paragraph = document.createElement("p");
      paragraph.className = "summary-copy";
      paragraph.textContent = text || (locale === "zh" ? "输入总结文案" : "ADD SUMMARY COPY");

      row.append(order, paragraph);
      return row;
    }),
  );

  document.documentElement.style.setProperty("--ending-color", state.ending.color);
  dom.endingScene.dataset.animation = state.ending.animation;
  dom.endingColor.value = state.ending.color;
  dom.endingColorText.value = state.ending.color;
  dom.endingAnimation.value = state.ending.animation;
  renderTimeline();

  dom.previewLocaleButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.previewLocale === locale);
  });
}

function formatDuration(ms) {
  const seconds = ms / 1000;
  return `${Number.isInteger(seconds) ? seconds : seconds.toFixed(1)}s`;
}

function renderTimeline() {
  const summaryMs = state.timing.summaryMs;
  const endingMs = state.timing.endingMs;
  const totalMs = summaryMs + endingMs;
  const summaryRatio = `${summaryMs}fr`;
  const endingRatio = `${endingMs}fr`;
  const summaryShare = `${(summaryMs / totalMs) * 100}%`;

  dom.timelineTrack.style.setProperty("--summary-ratio", summaryRatio);
  dom.timelineTrack.style.setProperty("--ending-ratio", endingRatio);
  dom.timelineTrack.style.setProperty("--summary-share", summaryShare);
  dom.timelineSummaryLabel.textContent = `SUMMARY · ${formatDuration(summaryMs)}`;
  dom.timelineEndingLabel.textContent = `ENDING · ${formatDuration(endingMs)}`;
  dom.timelineDivider.setAttribute("aria-valuenow", String(summaryMs / 1000));
  dom.timelineDivider.setAttribute(
    "aria-valuetext",
    `Summary ${formatDuration(summaryMs)}，Ending ${formatDuration(endingMs)}`,
  );
  dom.timelineTrack.style.setProperty("--timeline-total-seconds", String(totalMs / 1000));
}

function clampSummaryDuration(ms) {
  return Math.min(
    TOTAL_DURATION - MIN_ENDING_DURATION,
    Math.max(MIN_SUMMARY_DURATION, Math.round(ms / 100) * 100),
  );
}

function setTimingFromSummary(ms, shouldSave = true) {
  const summaryMs = clampSummaryDuration(ms);
  state.timing = {
    summaryMs,
    endingMs: TOTAL_DURATION - summaryMs,
  };
  renderTimeline();
  if (shouldSave) saveState();
}

function updateTimingFromPointer(event) {
  const rect = dom.timelineTrack.getBoundingClientRect();
  if (!rect.width) return;
  const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
  setTimingFromSummary(ratio * TOTAL_DURATION, false);
}

function renderCopyEditor() {
  const locale = state.editLocale;
  const copy = state.copy[locale];

  dom.editLocaleButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.editLocale === locale);
  });

  dom.copyList.replaceChildren(
    ...copy.map((text, index) => {
      const item = document.createElement("div");
      item.className = "copy-item";

      const order = document.createElement("span");
      order.className = "copy-order";
      order.textContent = String(index + 1).padStart(2, "0");

      const input = document.createElement("input");
      input.className = `copy-input${locale === "en" ? " is-en" : ""}`;
      input.type = "text";
      input.maxLength = 30;
      input.value = text;
      input.setAttribute("aria-label", `第 ${index + 1} 条${locale === "zh" ? "中文" : "英文"}文案`);

      const count = document.createElement("span");
      count.className = "copy-count";
      count.textContent = `${text.length}/30`;

      const remove = document.createElement("button");
      remove.className = "remove-copy";
      remove.type = "button";
      remove.textContent = "×";
      remove.disabled = copy.length === 1;
      remove.setAttribute("aria-label", `删除第 ${index + 1} 条文案`);

      input.addEventListener("input", () => {
        state.copy[locale][index] = input.value.slice(0, 30);
        count.textContent = `${state.copy[locale][index].length}/30`;
        if (state.previewLocale === locale) renderPreview();
        saveState();
      });

      remove.addEventListener("click", () => {
        if (state.copy[locale].length === 1) return;
        state.copy[locale].splice(index, 1);
        renderCopyEditor();
        if (state.previewLocale === locale) renderPreview();
        saveState();
      });

      item.append(order, input, count, remove);
      return item;
    }),
  );

  dom.addCopy.disabled = copy.length >= 4;
  dom.addCopy.textContent = copy.length >= 4 ? "已达到 4 条上限" : "＋ 添加一条";
}

function setScene(scene) {
  const isSummary = scene === "summary";
  dom.summaryScene.classList.toggle("is-active", isSummary);
  dom.endingScene.classList.toggle("is-active", !isSummary);
}

function clearPlayback() {
  playbackTimers.forEach(window.clearTimeout);
  playbackTimers = [];
  dom.stage.classList.remove("is-playing");
  dom.timelineTrack.classList.remove("is-playing");
  dom.playPreview.classList.remove("is-playing");
  dom.playLabel.textContent = "播放预览";
  dom.logoSound.pause();
  dom.logoSound.currentTime = 0;
  dom.clickSound.pause();
  dom.clickSound.currentTime = 0;
  dom.switchSound.pause();
  dom.switchSound.currentTime = 0;
  dom.arcadeSound.pause();
  dom.arcadeSound.currentTime = 0;
}

function playSound(audio, volume = 0.5) {
  audio.pause();
  audio.currentTime = 0;
  audio.volume = volume;
  audio.play().catch(() => {});
}

function restartAnimation(element) {
  const animation = element.style.animation;
  element.style.animation = "none";
  void element.offsetWidth;
  element.style.animation = animation;
}

function playPreview() {
  const summaryMs = state.timing.summaryMs;
  const endingMs = state.timing.endingMs;
  clearPlayback();
  setScene("summary");
  void dom.stage.offsetWidth;
  dom.stage.classList.add("is-playing");
  dom.timelineTrack.classList.add("is-playing");
  dom.playPreview.classList.add("is-playing");
  dom.playLabel.textContent = "播放中";

  state.copy[state.previewLocale].forEach((_, index) => {
    playbackTimers.push(window.setTimeout(() => playSound(dom.clickSound, 0.24), 120 + index * 150));
  });

  playbackTimers.push(window.setTimeout(() => {
    setScene("ending");
    restartAnimation(dom.endingScene.querySelector(".ending-panel"));
  }, summaryMs));

  playbackTimers.push(window.setTimeout(() => {
    dom.logoSound.volume = 0.5;
    dom.logoSound.currentTime = 0;
    dom.logoSound.play().catch(() => {});
  }, summaryMs + 500));

  if (state.ending.animation === "arcade-clear") {
    playbackTimers.push(window.setTimeout(() => playSound(dom.arcadeSound, 0.45), summaryMs + 760));
  }

  playbackTimers.push(window.setTimeout(() => {
    dom.playPreview.classList.remove("is-playing");
    dom.playLabel.textContent = "重新播放";
    dom.stage.classList.remove("is-playing");
    dom.timelineTrack.classList.remove("is-playing");
  }, summaryMs + endingMs));
}

function normalizeHex(value) {
  const raw = value.trim().toUpperCase();
  return /^#[0-9A-F]{6}$/.test(raw) ? raw : null;
}

function configurationPayload() {
  return {
    version: 1,
    copy: state.copy,
    ending: state.ending,
    timing: { ...state.timing },
  };
}

function validateConfiguration(value) {
  if (!value || typeof value !== "object") throw new Error("配置不是 JSON 对象");
  const copy = value.copy;
  if (!copy || !Array.isArray(copy.zh) || !Array.isArray(copy.en)) {
    throw new Error("缺少中英文文案");
  }
  for (const locale of ["zh", "en"]) {
    if (copy[locale].length < 1 || copy[locale].length > 4) {
      throw new Error("每种语言必须有 1–4 条文案");
    }
    if (copy[locale].some((item) => typeof item !== "string" || item.length > 30)) {
      throw new Error("每条文案最多 30 个字符");
    }
  }
  const color = normalizeHex(value.ending?.color || "");
  const animation = value.ending?.animation;
  if (!color || !["center-wipe", "fade-scale", "slide-up", "arcade-clear"].includes(animation)) {
    throw new Error("Ending 配置无效");
  }
  const summaryMs = Number(value.timing?.summaryMs ?? SUMMARY_DURATION);
  const endingMs = Number(value.timing?.endingMs ?? ENDING_DURATION);
  if (!Number.isFinite(summaryMs) || !Number.isFinite(endingMs)) {
    throw new Error("时长配置无效");
  }
  const normalizedSummaryMs = clampSummaryDuration(summaryMs);
  if (Math.abs(normalizedSummaryMs - summaryMs) > 0.001 || Math.abs((TOTAL_DURATION - normalizedSummaryMs) - endingMs) > 0.001) {
    throw new Error("Summary / Ending 时长必须合计 5.5 秒，且分别满足最小时长");
  }
  return {
    copy: {
      zh: [...copy.zh],
      en: [...copy.en],
    },
    ending: { color, animation },
    timing: { summaryMs: normalizedSummaryMs, endingMs },
  };
}

function applyConfiguration(value) {
  const next = validateConfiguration(value);
  state = {
    ...cloneDefaults(),
    ...next,
    copy: next.copy,
    ending: next.ending,
    timing: next.timing,
  };
  clearPlayback();
  setScene("summary");
  renderCopyEditor();
  renderPreview();
  saveState();
}

function downloadConfiguration() {
  const blob = new Blob([JSON.stringify(configurationPayload(), null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "cindy-summary-ending-config.json";
  link.click();
  URL.revokeObjectURL(url);
  dom.actionStatus.textContent = "配置 JSON 已下载";
}

function importConfigurationFile(file) {
  if (!file) return;
  file.text()
    .then((text) => applyConfiguration(JSON.parse(text)))
    .then(() => {
      dom.actionStatus.textContent = "配置 JSON 已导入";
    })
    .catch((error) => {
      dom.actionStatus.textContent = error.message || "JSON 导入失败";
    });
}

async function copyConfiguration() {
  const payload = JSON.stringify(configurationPayload(), null, 2);

  try {
    await navigator.clipboard.writeText(payload);
    dom.actionStatus.textContent = "配置 JSON 已复制";
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = payload;
    document.body.append(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
    dom.actionStatus.textContent = "配置 JSON 已复制";
  }
}

dom.previewLocaleButtons.forEach((button) => {
  button.addEventListener("click", () => {
    if (state.previewLocale !== button.dataset.previewLocale) playSound(dom.switchSound, 0.3);
    state.previewLocale = button.dataset.previewLocale;
    renderPreview();
    saveState();
  });
});

dom.editLocaleButtons.forEach((button) => {
  button.addEventListener("click", () => {
    if (state.editLocale !== button.dataset.editLocale) playSound(dom.switchSound, 0.3);
    state.editLocale = button.dataset.editLocale;
    state.previewLocale = state.editLocale;
    renderCopyEditor();
    renderPreview();
    saveState();
  });
});

dom.addCopy.addEventListener("click", () => {
  const copy = state.copy[state.editLocale];
  if (copy.length >= 4) return;
  copy.push("");
  renderCopyEditor();
  if (state.previewLocale === state.editLocale) renderPreview();
  saveState();
  dom.copyList.querySelector(".copy-item:last-child input")?.focus();
});

dom.endingColor.addEventListener("input", () => {
  state.ending.color = dom.endingColor.value.toUpperCase();
  renderPreview();
  saveState();
});

dom.endingColorText.addEventListener("change", () => {
  const value = normalizeHex(dom.endingColorText.value);
  if (!value) {
    dom.endingColorText.value = state.ending.color;
    dom.actionStatus.textContent = "请输入 6 位 HEX 颜色，例如 #F70121";
    return;
  }
  state.ending.color = value;
  renderPreview();
  saveState();
});

dom.endingAnimation.addEventListener("change", () => {
  playSound(dom.switchSound, 0.3);
  state.ending.animation = dom.endingAnimation.value;
  renderPreview();
  saveState();
  setScene("ending");
  playbackTimers.push(window.setTimeout(() => setScene("summary"), 1500));
});

let timelineDragging = false;

dom.timelineDivider.addEventListener("pointerdown", (event) => {
  event.preventDefault();
  timelineDragging = true;
  dom.timelineDivider.setPointerCapture?.(event.pointerId);
  dom.timelineTrack.classList.add("is-dragging");
  updateTimingFromPointer(event);
});

dom.timelineDivider.addEventListener("pointermove", (event) => {
  if (!timelineDragging) return;
  updateTimingFromPointer(event);
});

function finishTimelineDrag(event) {
  if (!timelineDragging) return;
  timelineDragging = false;
  dom.timelineTrack.classList.remove("is-dragging");
  dom.timelineDivider.releasePointerCapture?.(event.pointerId);
  saveState();
}

dom.timelineDivider.addEventListener("pointerup", finishTimelineDrag);
dom.timelineDivider.addEventListener("pointercancel", finishTimelineDrag);

dom.timelineDivider.addEventListener("keydown", (event) => {
  const step = event.shiftKey ? 500 : 100;
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    setTimingFromSummary(state.timing.summaryMs - step);
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    setTimingFromSummary(state.timing.summaryMs + step);
  } else if (event.key === "Home") {
    event.preventDefault();
    setTimingFromSummary(MIN_SUMMARY_DURATION);
  } else if (event.key === "End") {
    event.preventDefault();
    setTimingFromSummary(TOTAL_DURATION - MIN_ENDING_DURATION);
  }
});

dom.playPreview.addEventListener("click", () => {
  playPreview();
  playSound(dom.clickSound, 0.28);
});
dom.copyConfig.addEventListener("click", copyConfiguration);
dom.downloadConfig.addEventListener("click", () => {
  playSound(dom.clickSound, 0.22);
  downloadConfiguration();
});
dom.importConfig.addEventListener("click", () => dom.configFile.click());
dom.configFile.addEventListener("change", () => {
  importConfigurationFile(dom.configFile.files?.[0]);
  dom.configFile.value = "";
});

dom.resetConfig.addEventListener("click", () => {
  state = cloneDefaults();
  localStorage.removeItem(STORAGE_KEY);
  clearPlayback();
  setScene("summary");
  renderCopyEditor();
  renderPreview();
  saveState();
  dom.actionStatus.textContent = "已恢复默认配置";
});

renderCopyEditor();
renderPreview();
setScene("summary");
