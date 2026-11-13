"use strict";

/* =========================================================================
 * api.js —— 全站唯一写 fetch() 的地方
 * 契约来源：00_MAIN_TECHNICAL_ROUTE.md §E、§F
 * ========================================================================= */

const API_BASE = "/api/v1";
const REQUEST_TIMEOUT_MS = 60000;
const MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"];
const MEAL_TYPE_LABELS = {
  breakfast: "早餐",
  lunch: "午餐",
  dinner: "晚餐",
  snack: "加餐",
};

const ERROR_TEXT = {
  INVALID_REQUEST: "请求有误，请检查输入。",
  INVALID_IMAGE: "这张图片无法识别，请换一张。",
  IMAGE_TOO_LARGE: "图片超过 8 MB，请压缩后再上传。",
  UNSUPPORTED_MEDIA_TYPE: "只支持 JPG / PNG / WebP。",
  INVALID_WEIGHT: "请填写有效的重量（1–5000 克）。",
  FOOD_NOT_FOUND: "食物库里没有可匹配的条目，请重新选择标准食物。",
  MEAL_NOT_FOUND: "这条记录不存在，可能已被删除。",
  AI_PROVIDER_ERROR: "AI 服务暂时不可用，请稍后重试。",
  INVALID_AI_RESPONSE: "AI 返回了无法解析的结果，请重试。",
  DATABASE_ERROR: "保存失败，请重试。",
  INTERNAL_ERROR: "服务器出错了，请稍后重试。",
  NETWORK_ERROR: "无法连接到服务器，请确认应用仍在运行。",
  REQUEST_TIMEOUT: "请求超时了，请检查网络后重试。",
};

const HTTP_STATUS_TO_CODE = {
  400: "INVALID_REQUEST",
  404: "MEAL_NOT_FOUND",
  405: "INVALID_REQUEST",
  413: "IMAGE_TOO_LARGE",
  415: "UNSUPPORTED_MEDIA_TYPE",
  422: "INVALID_REQUEST",
  500: "INTERNAL_ERROR",
  502: "AI_PROVIDER_ERROR",
};

/* ------------------------------ 错误处理 ------------------------------ */

function makeApiError(code, message, httpStatus, details) {
  const error = new Error(message || errorText(code));
  error.name = "ApiError";
  error.code = code || "INTERNAL_ERROR";
  error.httpStatus = typeof httpStatus === "number" ? httpStatus : null;
  error.details = details === undefined ? null : details;
  return error;
}

function errorText(code) {
  return ERROR_TEXT[code] || "出错了，请重试。";
}

/* ------------------------------ 请求入口 ------------------------------ */

/**
 * 调用 /api/v1 下的接口。
 * 成功时返回响应信封里的 data；失败时抛出带 code 的 Error。
 * 注意：HTTP 2xx 不代表业务成功，外层 status 才是信封状态。
 */
async function apiFetch(path, options = {}) {
  const { timeoutMs = REQUEST_TIMEOUT_MS, ...fetchOptions } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const headers = new Headers(fetchOptions.headers || {});
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  let response;
  try {
    response = await fetch(API_BASE + path, {
      ...fetchOptions,
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw makeApiError("REQUEST_TIMEOUT", errorText("REQUEST_TIMEOUT"));
    }
    throw makeApiError("NETWORK_ERROR", errorText("NETWORK_ERROR"));
  } finally {
    clearTimeout(timer);
  }

  let raw = "";
  try {
    raw = await response.text();
  } catch (_) {
    throw makeApiError("NETWORK_ERROR", "读取服务器响应失败。", response.status);
  }

  let body = null;
  if (raw) {
    try {
      body = JSON.parse(raw);
    } catch (_) {
      const code = HTTP_STATUS_TO_CODE[response.status] || "INTERNAL_ERROR";
      throw makeApiError(code, "服务器返回了非 JSON 响应。", response.status);
    }
  }

  const isEnvelopeError = body && body.status === "error";
  if (!response.ok || isEnvelopeError) {
    const code =
      (body && body.error && body.error.code) ||
      HTTP_STATUS_TO_CODE[response.status] ||
      "INTERNAL_ERROR";
    const message =
      (body && body.error && body.error.message) ||
      errorText(code);
    throw makeApiError(code, message, response.status, body && body.error ? body.error.details : null);
  }

  if (!body || typeof body !== "object") {
    throw makeApiError("INTERNAL_ERROR", "服务器返回了空的响应。", response.status);
  }

  return body.data === undefined ? {} : body.data;
}

/* ------------------------------ 提示组件 ------------------------------ */

function showToast(message, type = "info", timeout = 4200) {
  const region = document.getElementById("toast-region");
  if (!region) return;

  while (region.children.length >= 3) {
    region.removeChild(region.firstElementChild);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.setAttribute("role", type === "error" ? "alert" : "status");

  const text = document.createElement("p");
  text.className = "toast-text";
  text.textContent = message;
  toast.appendChild(text);

  const close = document.createElement("button");
  close.type = "button";
  close.className = "toast-close";
  close.setAttribute("aria-label", "关闭提示");
  close.textContent = "×";
  toast.appendChild(close);

  let dismissed = false;
  const dismiss = () => {
    if (dismissed) return;
    dismissed = true;
    toast.classList.remove("is-visible");
    setTimeout(() => toast.remove(), 220);
  };

  close.addEventListener("click", dismiss);
  region.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("is-visible"));
  if (timeout > 0) setTimeout(dismiss, timeout);
}

function setButtonBusy(button, busy, busyText) {
  if (!button) return;
  if (busy) {
    if (!button.dataset.idleLabel) {
      button.dataset.idleLabel = button.textContent.trim();
    }
    button.disabled = true;
    button.classList.add("is-busy");
    button.setAttribute("aria-busy", "true");
    if (busyText) button.textContent = busyText;
  } else {
    button.disabled = false;
    button.classList.remove("is-busy");
    button.removeAttribute("aria-busy");
    if (button.dataset.idleLabel) {
      button.textContent = button.dataset.idleLabel;
      delete button.dataset.idleLabel;
    }
  }
}

function showPageError(bannerId, textId, err, fallback = "请稍后重试。") {
  const banner = document.getElementById(bannerId);
  const text = document.getElementById(textId);
  if (text) {
    text.textContent = err && err.code ? errorText(err.code) : fallback;
  }
  if (banner) banner.hidden = false;
}

function hidePageError(bannerId) {
  const banner = document.getElementById(bannerId);
  if (banner) banner.hidden = true;
}

/* ------------------------------ 展示格式化 ------------------------------ */

function formatKcal(value) {
  const number = Number(value);
  const safe = Number.isFinite(number) ? number : 0;
  return Math.round(safe).toLocaleString("en-US");
}

function formatMacro(value) {
  const number = Number(value);
  return `${(Number.isFinite(number) ? number : 0).toFixed(1)} g`;
}

function formatWeight(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return `${Math.round(number)} g`;
}

function formatBytes(bytes) {
  const number = Number(bytes) || 0;
  if (number >= 1024 * 1024) return `${(number / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(number / 1024))} KB`;
}

function mealTypeLabel(type) {
  return MEAL_TYPE_LABELS[type] || "餐食";
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    switch (char) {
      case "&": return "&amp;";
      case "<": return "&lt;";
      case ">": return "&gt;";
      case '"': return "&quot;";
      default: return "&#39;";
    }
  });
}

/* ------------------------------ 日期与存储 ------------------------------ */

function pad2(value) {
  return String(value).padStart(2, "0");
}

function todayLocalIso() {
  const now = new Date();
  return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
}

function shiftLocalDate(isoDate, days) {
  const parts = String(isoDate || "").split("-").map(Number);
  if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part))) {
    return todayLocalIso();
  }
  const date = new Date(parts[0], parts[1] - 1, parts[2]);
  date.setDate(date.getDate() + days);
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

function formatDateLabel(isoDate) {
  const parts = String(isoDate || "").split("-").map(Number);
  if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part))) {
    return isoDate || "";
  }
  const date = new Date(parts[0], parts[1] - 1, parts[2]);
  const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return `${parts[1]}月${parts[2]}日 ${weekdays[date.getDay()]}`;
}

function formatDateTimeShort(isoString) {
  const match = String(isoString || "").match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!match) return isoString || "";
  const [, , month, day, hour, minute] = match;
  return `${Number(month)}月${Number(day)}日 ${hour}:${minute}`;
}

function toLocalIsoString(date = new Date()) {
  const offsetMin = -date.getTimezoneOffset();
  const sign = offsetMin >= 0 ? "+" : "-";
  const absolute = Math.abs(offsetMin);
  return (
    `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}` +
    `T${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}` +
    `${sign}${pad2(Math.floor(absolute / 60))}:${pad2(absolute % 60)}`
  );
}

function isValidWeight(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 && number <= 5000;
}

function readJson(key) {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

function storeJson(key, value) {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (_) {
    return false;
  }
}

function removeStored(key) {
  try {
    sessionStorage.removeItem(key);
  } catch (_) {
    /* sessionStorage 不可用时静默降级 */
  }
}

function setFlash(type, message) {
  storeJson("hdt.flash", { type, message });
}

function consumeFlash() {
  const flash = readJson("hdt.flash");
  removeStored("hdt.flash");
  return flash;
}
