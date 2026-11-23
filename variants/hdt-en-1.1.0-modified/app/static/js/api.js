"use strict";

/* =========================================================================
 * api.js — the only place in the app that calls fetch()
 * Contract: 00_MAIN_TECHNICAL_ROUTE.md §E, §F
 * ========================================================================= */

const API_BASE = "/api/v1";
const REQUEST_TIMEOUT_MS = 60000;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"];
const MEAL_TYPE_LABELS = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner",
  snack: "Snack",
};

const ERROR_TEXT = {
  INVALID_REQUEST: "Invalid request. Please check your input.",
  INVALID_IMAGE: "This image could not be read. Please try another one.",
  IMAGE_TOO_LARGE: "The image is larger than 8 MB. Please compress it and try again.",
  UNSUPPORTED_MEDIA_TYPE: "Only JPG / PNG / WebP are supported.",
  INVALID_WEIGHT: "Enter a valid weight (1–5000 g).",
  FOOD_NOT_FOUND: "No matching entry was found in the food database. Please choose a standard food again.",
  MEAL_NOT_FOUND: "This record no longer exists. It may have been deleted.",
  AI_PROVIDER_ERROR: "The AI service is temporarily unavailable. Please try again later.",
  INVALID_AI_RESPONSE: "The AI returned a response that could not be parsed. Please try again.",
  DATABASE_ERROR: "Save failed. Please try again.",
  INTERNAL_ERROR: "The server encountered an error. Please try again later.",
  NETWORK_ERROR: "Could not connect to the server. Make sure the app is still running.",
  REQUEST_TIMEOUT: "The request timed out. Check your network and try again.",
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

/* ------------------------------ Error handling ------------------------------ */

function makeApiError(code, message, httpStatus, details) {
  const error = new Error(message || errorText(code));
  error.name = "ApiError";
  error.code = code || "INTERNAL_ERROR";
  error.httpStatus = typeof httpStatus === "number" ? httpStatus : null;
  error.details = details === undefined ? null : details;
  return error;
}

function errorText(code) {
  return ERROR_TEXT[code] || "Something went wrong. Please try again.";
}

/* ------------------------------ Request entry ------------------------------ */

/**
 * Call an endpoint under /api/v1.
 * On success, returns the data field of the response envelope; on failure, throws an Error with a code.
 * Note: HTTP 2xx does not mean business success; the envelope status is authoritative.
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
    throw makeApiError("NETWORK_ERROR", "Failed to read the server response.", response.status);
  }

  let body = null;
  if (raw) {
    try {
      body = JSON.parse(raw);
    } catch (_) {
      const code = HTTP_STATUS_TO_CODE[response.status] || "INTERNAL_ERROR";
      throw makeApiError(code, "The server returned a non-JSON response.", response.status);
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
    throw makeApiError("INTERNAL_ERROR", "The server returned an empty response.", response.status);
  }

  return body.data === undefined ? {} : body.data;
}

/* ------------------------------ Toast component ------------------------------ */

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
  close.setAttribute("aria-label", "Close notification");
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

function showPageError(bannerId, textId, err, fallback = "Please try again later.") {
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

/* ------------------------------ Display formatting ------------------------------ */

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
  return MEAL_TYPE_LABELS[type] || "Meal";
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

/* ------------------------------ Dates and storage ------------------------------ */

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
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", weekday: "short" });
}

function formatDateTimeShort(isoString) {
  const match = String(isoString || "").match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!match) return isoString || "";
  const [, , month, day, hour, minute] = match;
  return `${MONTHS[Number(month) - 1]} ${Number(day)}, ${hour}:${minute}`;
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
    /* Degrade silently when sessionStorage is unavailable */
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
