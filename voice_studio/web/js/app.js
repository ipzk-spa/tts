/**
 * Spag Voice Studio (SVS+) — клієнтський інтерфейс.
 */

const EXAMPLES = [
  "Прив+іт! Як тво+ї справи сьогодні? Сподіваюся, все до+бре.",
  "Кам'ян+ець-Под+ільський — м+істо в Хмельн+ицькій +області Укра+їни.",
  "Зустріч призначено на 24.08.1991 о 14:30, кабінет №5. [пауза=0.8] Не забудьте документи.",
  "[повільно]Говорю дуже повільно і розбірливо[/повільно], а тепер [швидко]швидко-швидко-швидко[/швидко].",
  "Це був звичайний вечір 1 січня 2024 року, коли все змінилося назавжди.",
];

let appStatus = null;
let synthStartedAt = 0;
let resultSeq = 0;
const results = []; // newest first

function $(id) {
  return document.getElementById(id);
}

function bindSlider(sliderId, labelId, formatter = (v) => v) {
  const slider = $(sliderId);
  const label = $(labelId);
  if (!slider || !label) return;
  const update = () => { label.textContent = formatter(slider.value); };
  slider.addEventListener("input", update);
  update();
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { Accept: "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok && res.status !== 422) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

function getEngine() {
  const checked = document.querySelector('input[name="engine"]:checked');
  return checked ? checked.value : "robinhad";
}

function setEngine(engine) {
  const radio = document.querySelector(`input[name="engine"][value="${engine}"]`);
  if (radio) radio.checked = true;
  onEngineChange();
}

function onEngineChange() {
  const engine = getEngine();
  $("robinhad-settings").classList.toggle("hidden", engine !== "robinhad");
  $("styletts2-settings").classList.toggle("hidden", engine !== "styletts2");
  if (appStatus) {
    $("engine-note").textContent =
      engine === "robinhad" ? appStatus.robinhad.status : appStatus.styletts2.status;
  }
}

function showToastError(message) {
  const el = $("toast-error");
  if (!message) {
    el.classList.add("hidden");
    el.textContent = "";
    return;
  }
  el.textContent = message;
  el.classList.remove("hidden");
}

function showProgress(show) {
  $("progress-panel").classList.toggle("hidden", !show);
  if (!show) {
    $("progress-fill").style.width = "0%";
    $("progress-meta").textContent = "0%";
    $("progress-eta").textContent = "~ —";
    $("progress-label").textContent = "Синтез…";
  }
}

function formatEta(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "~ —";
  if (seconds < 5) return "~ кілька секунд";
  if (seconds < 60) return `~ ${Math.ceil(seconds)} с`;
  const m = Math.floor(seconds / 60);
  const s = Math.ceil(seconds % 60);
  return `~ ${m} хв ${s} с`;
}

function updateProgress(evt) {
  const total = Math.max(1, Number(evt.total) || 1);
  const current = Math.max(0, Number(evt.current) || 0);
  let pct = Math.round((current / total) * 100);
  if (evt.phase === "export") pct = 95;
  if (evt.phase === "rvc" && current >= total) pct = 90;
  pct = Math.min(99, Math.max(pct, current > 0 ? 3 : 1));

  $("progress-fill").style.width = `${pct}%`;
  $("progress-label").textContent = evt.message || "Синтез…";
  $("progress-meta").textContent =
    `${pct}% · ${current}/${total}` + (evt.phase ? ` · ${evt.phase}` : "");

  const engine = getEngine();
  const table = (appStatus && appStatus.eta_sec_per_chunk) || {};
  const perChunk = table[engine] || 5;
  const remainingChunks = Math.max(0, total - current);
  let eta = remainingChunks * perChunk;
  if (evt.phase === "rvc") eta = (table.rvc || 8) * Math.max(0, total - current + 0.5);
  if (evt.phase === "export") eta = 2;

  if (synthStartedAt && current > 0 && evt.phase === "tts") {
    const elapsed = (Date.now() - synthStartedAt) / 1000;
    const avg = elapsed / current;
    eta = avg * remainingChunks;
  }
  $("progress-eta").textContent = formatEta(eta);
}

function updateResultsCount() {
  const n = results.length;
  $("results-count").textContent = n
    ? `${n} запис${n === 1 ? "" : n < 5 ? "и" : "ів"} у сесії`
    : "Поки порожньо — натисніть «Синтезувати»";
  $("results-empty").classList.toggle("hidden", n > 0);
}

function engineLabel(engine, hybrid) {
  const base = engine === "styletts2" ? "StyleTTS2" : "Robinhad";
  return hybrid ? `${base} + RVC` : base;
}

function voiceLabelForPayload(payload) {
  if (payload.engine === "styletts2") return payload.styletts2_voice || "StyleTTS2";
  const sel = $("rh-voice");
  const opt = sel && sel.selectedOptions[0];
  return (opt && opt.textContent) || payload.robinhad_voice || "голос";
}

function formatClock(date = new Date()) {
  return date.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function renderResultCard(item, { isNew = false } = {}) {
  const card = document.createElement("article");
  card.className = "result-card" + (isNew ? " is-new" : "");
  card.dataset.id = item.id;

  const previewId = `preview-${item.id}`;
  const title = item.title || `Озвучка #${item.id}`;
  const preview = item.preview || "";
  const hasPreview = Boolean(preview.trim());

  card.innerHTML = `
    <div class="result-card-top">
      <div class="result-meta">
        <p class="result-title">${escapeHtml(title)}</p>
        <p class="result-time">${escapeHtml(item.timeLabel)}</p>
        <span class="result-engine">${escapeHtml(item.engineLabel)}</span>
      </div>
      <button type="button" class="btn btn-icon result-delete" title="Видалити" aria-label="Видалити">✕</button>
    </div>
    <audio controls preload="metadata" src="${item.wavUrl}"></audio>
    ${hasPreview ? `
      <button type="button" class="result-preview-toggle" aria-expanded="false" aria-controls="${previewId}">
        <span class="chev">▸</span> Наголошений / опрацьований текст
      </button>
      <div class="result-preview" id="${previewId}">${escapeHtml(preview)}</div>
    ` : ""}
    <div class="download-row">
      <a class="btn btn-download" href="${item.wavUrl}" download="${escapeAttr(item.wavFilename || "audio.wav")}">⬇️ WAV</a>
      ${item.mp3Url
        ? `<a class="btn btn-download" href="${item.mp3Url}" download="${escapeAttr(item.mp3Filename || "audio.mp3")}">⬇️ MP3</a>`
        : `<a class="btn btn-download" style="opacity:.45;pointer-events:none" href="#">MP3 н/д</a>`}
    </div>
  `;

  card.querySelector(".result-delete").addEventListener("click", () => removeResult(item.id));

  const toggle = card.querySelector(".result-preview-toggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const box = card.querySelector(`#${previewId}`);
      const open = box.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  return card;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(str) {
  return escapeHtml(str).replace(/'/g, "&#39;");
}

function prependResult(item) {
  results.unshift(item);
  const list = $("results-list");
  const card = renderResultCard(item, { isNew: true });
  list.prepend(card);
  updateResultsCount();

  const audio = card.querySelector("audio");
  if (audio) {
    audio.play().catch(() => {});
  }

  setTimeout(() => card.classList.remove("is-new"), 2400);
  $("results-rail").scrollTo({ top: 0, behavior: "smooth" });
}

function removeResult(id) {
  const idx = results.findIndex((r) => r.id === id);
  if (idx >= 0) results.splice(idx, 1);
  const node = $("results-list").querySelector(`[data-id="${id}"]`);
  if (node) {
    node.style.transition = "opacity .2s, transform .2s";
    node.style.opacity = "0";
    node.style.transform = "translateY(-8px)";
    setTimeout(() => node.remove(), 180);
  }
  updateResultsCount();
}

async function loadStatus() {
  appStatus = await api("/api/status");
  if ($("app-title")) $("app-title").textContent = appStatus.title || "Spag Voice Studio";
  document.title = appStatus.title || "Spag Voice Studio";

  const rhSelect = $("rh-voice");
  rhSelect.innerHTML = "";
  for (const v of appStatus.robinhad.voices) {
    const opt = document.createElement("option");
    opt.value = v.value;
    opt.textContent = v.label;
    rhSelect.appendChild(opt);
  }

  const stSelect = $("st-voice");
  stSelect.innerHTML = "";
  for (const name of appStatus.styletts2.voices) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    stSelect.appendChild(opt);
  }
  if (!stSelect.options.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "(запустіть tools\\setup_styletts2.ps1)";
    stSelect.appendChild(opt);
  }

  const f0Select = $("hybrid-f0");
  f0Select.innerHTML = "";
  for (const m of appStatus.rvc.f0_methods) {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = m;
    if (m === "rmvpe") opt.selected = true;
    f0Select.appendChild(opt);
  }

  $("rvc-status").textContent = appStatus.rvc.status;
  setEngine(appStatus.default_engine);
}

function initExamples() {
  const container = $("examples");
  EXAMPLES.forEach((text) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "example-chip";
    chip.textContent = text.length > 72 ? text.slice(0, 72) + "…" : text;
    chip.title = text;
    chip.addEventListener("click", () => { $("text-in").value = text; });
    container.appendChild(chip);
  });
}

async function onVerbalize() {
  const text = $("text-in").value;
  $("verbalize-btn").disabled = true;
  showToastError("");
  try {
    const data = await api("/api/verbalize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    $("text-in").value = data.text;
  } catch (e) {
    showToastError(`❌ ${e.message}`);
  } finally {
    $("verbalize-btn").disabled = false;
  }
}

async function onStressPreview() {
  const text = $("text-in").value;
  $("stress-btn").disabled = true;
  showToastError("");
  try {
    const data = await api("/api/stress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, mode: "auto" }),
    });
    $("text-in").value = data.text;
  } catch (e) {
    showToastError(`❌ ${e.message}`);
  } finally {
    $("stress-btn").disabled = false;
  }
}

function collectSynthesizePayload() {
  return {
    engine: getEngine(),
    text: $("text-in").value,
    robinhad_voice: $("rh-voice").value,
    robinhad_verbalize: $("rh-verbalize").checked,
    robinhad_threshold: parseFloat($("rh-threshold").value),
    robinhad_maxlenratio: parseFloat($("rh-maxlen").value),
    robinhad_att_constraint: $("rh-att").checked,
    robinhad_stress_mode: $("rh-stress").value,
    styletts2_voice: $("st-voice").value,
    styletts2_speed: parseFloat($("st-speed").value),
    styletts2_verbalize: $("st-verbalize").checked,
    hybrid_enabled: $("hybrid-enabled").checked,
    hybrid_pth: $("hybrid-pth-path").value.trim(),
    hybrid_index: $("hybrid-index-path").value.trim(),
    hybrid_f0: $("hybrid-f0").value,
    hybrid_index_rate: parseFloat($("hybrid-index-rate").value),
    hybrid_pitch: parseInt($("hybrid-pitch").value, 10),
  };
}

function addResultFromResponse(data, payload) {
  if (!data.ok || !data.wav_url) {
    showToastError(data.status || "❌ Синтез не вдався");
    return;
  }

  resultSeq += 1;
  const stamp = Date.now();
  const voice = voiceLabelForPayload(payload);
  const item = {
    id: String(resultSeq),
    title: `${voice}`,
    timeLabel: formatClock(new Date(stamp)),
    engineLabel: engineLabel(payload.engine, payload.hybrid_enabled),
    preview: data.preview || "",
    wavUrl: data.wav_url + "?t=" + stamp,
    mp3Url: data.mp3_url ? data.mp3_url + "?t=" + stamp : null,
    wavFilename: data.wav_filename || "audio.wav",
    mp3Filename: data.mp3_filename || "audio.mp3",
  };
  prependResult(item);
}

async function onSynthesize() {
  const btn = $("synth-btn");
  btn.disabled = true;
  synthStartedAt = Date.now();
  showToastError("");
  showProgress(true);
  updateProgress({
    current: 0,
    total: 1,
    phase: "tts",
    message: "Старт синтезу…",
  });

  const payload = collectSynthesizePayload();

  try {
    const res = await fetch("/api/synthesize/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/x-ndjson",
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let finalData = null;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        let evt;
        try {
          evt = JSON.parse(line);
        } catch {
          continue;
        }
        if (evt.type === "progress") updateProgress(evt);
        else if (evt.type === "done" || evt.type === "error") finalData = evt;
      }
    }

    if (buffer.trim()) {
      try {
        const evt = JSON.parse(buffer);
        if (evt.type === "progress") updateProgress(evt);
        else finalData = evt;
      } catch { /* ignore */ }
    }

    if (!finalData) throw new Error("Потік синтезу обірвався без результату.");

    $("progress-fill").style.width = "100%";
    $("progress-meta").textContent = "100%";
    $("progress-eta").textContent = "готово";
    $("progress-label").textContent = "Готово";

    addResultFromResponse(finalData, payload);
    setTimeout(() => showProgress(false), finalData.ok ? 700 : 0);
    if (!finalData.ok) showProgress(false);
  } catch (e) {
    showToastError(`❌ ${e.message}`);
    showProgress(false);
  } finally {
    btn.disabled = false;
  }
}

async function onUploadRvc() {
  const pthFile = $("hybrid-pth-file").files[0];
  const indexFile = $("hybrid-index-file").files[0];
  if (!pthFile && !indexFile) {
    $("hybrid-upload-status").textContent = "Оберіть хоча б один файл.";
    return;
  }

  const form = new FormData();
  if (pthFile) form.append("pth", pthFile);
  if (indexFile) form.append("index", indexFile);

  $("hybrid-upload-btn").disabled = true;
  try {
    const res = await fetch("/api/upload/rvc", { method: "POST", body: form });
    const data = await res.json();
    $("hybrid-upload-status").textContent = data.message;
    if (data.pth_path) $("hybrid-pth-path").value = data.pth_path;
    if (data.index_path) $("hybrid-index-path").value = data.index_path;
  } catch (e) {
    $("hybrid-upload-status").textContent = `❌ ${e.message}`;
  } finally {
    $("hybrid-upload-btn").disabled = false;
  }
}

function onHybridToggle() {
  $("hybrid-inner").classList.toggle("hidden", !$("hybrid-enabled").checked);
}

function init() {
  initExamples();
  bindSlider("rh-threshold", "rh-threshold-val");
  bindSlider("rh-maxlen", "rh-maxlen-val");
  bindSlider("st-speed", "st-speed-val", (v) => parseFloat(v).toFixed(2));
  bindSlider("hybrid-index-rate", "hybrid-index-rate-val", (v) => parseFloat(v).toFixed(2));
  bindSlider("hybrid-pitch", "hybrid-pitch-val");

  document.querySelectorAll('input[name="engine"]').forEach((el) => {
    el.addEventListener("change", onEngineChange);
  });

  $("verbalize-btn").addEventListener("click", onVerbalize);
  $("stress-btn").addEventListener("click", onStressPreview);
  $("synth-btn").addEventListener("click", onSynthesize);
  $("hybrid-enabled").addEventListener("change", onHybridToggle);
  $("hybrid-upload-btn").addEventListener("click", onUploadRvc);

  onHybridToggle();
  updateResultsCount();
  loadStatus().catch((e) => showToastError(`❌ Не вдалося завантажити статус: ${e.message}`));
}

document.addEventListener("DOMContentLoaded", init);
