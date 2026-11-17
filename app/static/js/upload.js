"use strict";

/* =========================================================================
 * upload.js —— 上传页
 * 数据来源：POST /api/v1/analyze（multipart/form-data）
 * 文件校验只做“能不能发给后端”的前置检查；真正的校验与落盘由后端完成。
 * ========================================================================= */

const MAX_UPLOAD_BYTES = 8 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const ALLOWED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];
const ANALYSIS_DRAFT_KEY = "analysisResult";

const uploadState = {
  file: null,
  previewUrl: null,
  fileToken: 0,
  loading: false,
};

document.addEventListener("DOMContentLoaded", initUploadPage);

function initUploadPage() {
  const form = document.getElementById("upload-form");
  const fileInput = document.getElementById("file-input");
  const dropZone = document.getElementById("drop-zone");
  const clearButton = document.getElementById("clear-file-btn");
  const manualButton = document.getElementById("manual-entry-btn");

  if (!form || !fileInput || !dropZone) return;

  const defaultMealType = guessMealType();
  const defaultRadio = document.querySelector(
    `input[name="meal_type"][value="${defaultMealType}"]`
  );
  if (defaultRadio) defaultRadio.checked = true;

  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    if (file) onFileSelected(file);
    else resetFile();
  });

  form.addEventListener("submit", handleSubmit);

  document.querySelectorAll('input[name="meal_type"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      if (radio.checked) uploadState.mealType = radio.value;
    });
  });

  if (clearButton) {
    clearButton.addEventListener("click", () => {
      resetFile();
      fileInput.click();
    });
  }

  if (manualButton) {
    manualButton.addEventListener("click", startManualEntry);
  }

  ["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropZone.classList.add("is-dragover");
    });
  });

  ["dragleave", "dragend", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, () => {
      dropZone.classList.remove("is-dragover");
    });
  });

  dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    const file =
      event.dataTransfer &&
      event.dataTransfer.files &&
      event.dataTransfer.files[0];
    if (file) onFileSelected(file);
  });

  setLoading(false);
  syncAnalyzeButton();
}

function guessMealType(now = new Date()) {
  const hour = now.getHours();
  if (hour >= 6 && hour < 11) return "breakfast";
  if (hour >= 11 && hour < 15) return "lunch";
  if (hour >= 17 && hour < 21) return "dinner";
  return "snack";
}

async function onFileSelected(file) {
  const token = ++uploadState.fileToken;
  clearError();

  const validationCode = validateFile(file);
  if (validationCode) {
    resetFile();
    showError(validationCode);
    return;
  }

  const signatureOk = await hasImageSignature(file);
  if (token !== uploadState.fileToken) return;
  if (!signatureOk) {
    resetFile();
    showError("INVALID_IMAGE");
    return;
  }

  uploadState.file = file;

  if (uploadState.previewUrl) {
    URL.revokeObjectURL(uploadState.previewUrl);
    uploadState.previewUrl = null;
  }

  uploadState.previewUrl = URL.createObjectURL(file);

  const preview = document.getElementById("preview");
  const previewWrap = document.getElementById("preview-wrap");
  const dropZone = document.getElementById("drop-zone");
  const fileMeta = document.getElementById("file-meta");
  const status = document.getElementById("analyze-status");

  if (preview) preview.src = uploadState.previewUrl;
  if (previewWrap) previewWrap.hidden = false;
  if (dropZone) dropZone.hidden = true;
  if (fileMeta) fileMeta.textContent = `${file.name} · ${formatBytes(file.size)}`;
  if (status) status.textContent = "照片已就绪，点击下方按钮开始分析。";

  uploadState.mealType = getSelectedMealType();
  syncAnalyzeButton();
}

function resetFile() {
  uploadState.fileToken += 1;
  uploadState.file = null;

  if (uploadState.previewUrl) {
    URL.revokeObjectURL(uploadState.previewUrl);
    uploadState.previewUrl = null;
  }

  const preview = document.getElementById("preview");
  const previewWrap = document.getElementById("preview-wrap");
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const fileMeta = document.getElementById("file-meta");
  const status = document.getElementById("analyze-status");

  if (preview) preview.removeAttribute("src");
  if (previewWrap) previewWrap.hidden = true;
  if (dropZone) dropZone.hidden = false;
  if (fileInput) fileInput.value = "";
  if (fileMeta) fileMeta.textContent = "";
  if (status) status.textContent = "";
  if (uploadState.loading) setLoading(false);
  syncAnalyzeButton();
}

function validateFile(file) {
  if (!file) return "INVALID_REQUEST";

  const name = String(file.name || "").toLowerCase();
  const extension = name.match(/\.[^.]+$/);
  const typeAllowed = ALLOWED_IMAGE_TYPES.has(file.type);
  const extensionAllowed = extension && ALLOWED_IMAGE_EXTENSIONS.includes(extension[0]);

  if (!typeAllowed && !extensionAllowed) return "UNSUPPORTED_MEDIA_TYPE";
  if (file.size > MAX_UPLOAD_BYTES) return "IMAGE_TOO_LARGE";
  if (file.size <= 0) return "INVALID_IMAGE";
  return null;
}

async function hasImageSignature(file) {
  try {
    const buffer = await file.slice(0, 12).arrayBuffer();
    const bytes = new Uint8Array(buffer);

    const isJpeg =
      bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;

    const isPng =
      bytes.length >= 8 &&
      bytes[0] === 0x89 &&
      bytes[1] === 0x50 &&
      bytes[2] === 0x4e &&
      bytes[3] === 0x47 &&
      bytes[4] === 0x0d &&
      bytes[5] === 0x0a &&
      bytes[6] === 0x1a &&
      bytes[7] === 0x0a;

    const isWebp =
      bytes.length >= 12 &&
      String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3]) === "RIFF" &&
      String.fromCharCode(bytes[8], bytes[9], bytes[10], bytes[11]) === "WEBP";

    return isJpeg || isPng || isWebp;
  } catch (_) {
    // 读取失败时交给后端判断，避免误伤某些浏览器。
    return true;
  }
}

function getSelectedMealType() {
  const checked = document.querySelector('input[name="meal_type"]:checked');
  if (checked && MEAL_TYPES.includes(checked.value)) return checked.value;
  return guessMealType();
}

async function handleSubmit(event) {
  event.preventDefault();
  if (uploadState.loading) return;

  if (!uploadState.file) {
    showError("INVALID_REQUEST");
    return;
  }

  const mealType = getSelectedMealType();
  uploadState.mealType = mealType;
  await analyzeMeal(uploadState.file, mealType);
}

function startManualEntry() {
  const mealType = getSelectedMealType();
  const draft = {
    schema_version: "1.0",
    status: "success",
    foods: [],
    warnings: [],
    image_path: null,
    meal_type: mealType,
    requested_at: new Date().toISOString(),
    manual: true,
  };

  if (!storeJson(ANALYSIS_DRAFT_KEY, draft)) {
    showError("INTERNAL_ERROR");
    return;
  }

  window.location.href = "/result";
}

async function analyzeMeal(file, mealType) {  clearError();
  setLoading(true);

  const status = document.getElementById("analyze-status");
  if (status) status.textContent = "正在上传并识别，请保持页面打开…";

  try {
    const formData = new FormData();
    formData.append("image", file);
    formData.append("meal_type", mealType);

    // 注意：不要手动设置 Content-Type，浏览器会自动加 multipart boundary。
    const data = await apiFetch("/analyze", {
      method: "POST",
      body: formData,
      timeoutMs: 90000,
    });

    data.meal_type = mealType;
    data.requested_at = new Date().toISOString();

    const saved = storeJson(ANALYSIS_DRAFT_KEY, data);
    if (!saved) {
      throw makeApiError("INTERNAL_ERROR", "浏览器无法保存识别结果，请检查隐私模式设置。");
    }

    // 识别不完整不是错误：结果页会用 warnings 和标黄行展示，
    // 这里不写 flash，避免提示被带到首页才弹出来。
    window.location.href = "/result";
  } catch (err) {
    setLoading(false);
    showError(err);
    if (status) status.textContent = "";
  }
}

function setLoading(isLoading) {
  uploadState.loading = isLoading;

  const analyzeButton = document.getElementById("analyze-btn");
  const fileInput = document.getElementById("file-input");
  const clearButton = document.getElementById("clear-file-btn");
  const mealRadios = document.querySelectorAll('input[name="meal_type"]');

  if (fileInput) fileInput.disabled = isLoading;
  if (clearButton) clearButton.disabled = isLoading;
  mealRadios.forEach((radio) => {
    radio.disabled = isLoading;
  });

  if (analyzeButton) {
    analyzeButton.classList.toggle("is-busy", isLoading);
    analyzeButton.textContent = isLoading ? "正在识别…" : "分析这张照片";
    if (isLoading) analyzeButton.setAttribute("aria-busy", "true");
    else analyzeButton.removeAttribute("aria-busy");
  }

  syncAnalyzeButton();
}

function syncAnalyzeButton() {
  const analyzeButton = document.getElementById("analyze-btn");
  if (!analyzeButton) return;
  analyzeButton.disabled = uploadState.loading || !uploadState.file;
}

function showError(codeOrError) {
  const code =
    typeof codeOrError === "string"
      ? codeOrError
      : codeOrError && codeOrError.code
        ? codeOrError.code
        : "INTERNAL_ERROR";

  const banner = document.getElementById("upload-error");
  const text = document.getElementById("upload-error-text");
  if (text) text.textContent = errorText(code);
  if (banner) {
    banner.hidden = false;
    banner.setAttribute("tabindex", "-1");
    banner.focus({ preventScroll: true });
  }
}

function clearError() {
  const banner = document.getElementById("upload-error");
  if (banner) banner.hidden = true;
}
