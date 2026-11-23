/* =========================================================================
 * app.js — Android runtime (no Python backend)
 *
 * Responsibilities:
 *   1. Take over /api/v1/* inside the WebView and implement the same contract with IndexedDB and the local nutrition database;
 *   2. Call the user-configured OpenAI-compatible vision API through the native AndroidHost bridge (avoiding CORS);
 *   3. Inject the top-right menu, API settings, splash settings, About page, and camera entry points.
 *
 * This file must run before api.js for the fetch interception to take effect.
 * ========================================================================= */
(function () {
  "use strict";

  var APP_VERSION = "1.1.0";
  var APP_BUILD = "2026-11-20";
  var REPO_URL = "https://github.com/leonardo-weasley/healthy-diet-tracker";
  var SETTINGS_KEY = "hdt.settings";
  var SPLASH_KEY = "hdt.splashImage";
  var CUSTOM_FOODS_KEY = "hdt.customFoods";
  var SECRET_AI_KEY = "aiApiKey";
  var SECRET_USDA_KEY = "usdaApiKey";

  var Core = window.HDTCore;
  var MEAL_TYPES = Core.MEAL_TYPES;
  var TOTAL_KEYS = Core.TOTAL_KEYS;
  var MAX_WEIGHT_G = Core.MAX_WEIGHT_G;
  var MAX_ITEMS = Core.MAX_MEAL_ITEMS;
  var MAX_UPLOAD_BYTES = 8 * 1024 * 1024;
  var ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
  var RETRYABLE_REASONS = ["timeout", "network", "rate_limited", "provider_5xx", "not_json"];

  var PRESETS = {
    qwen: { endpoint: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-vl-max" },
    openai: { endpoint: "https://api.openai.com/v1", model: "gpt-4o-mini" },
    custom: { endpoint: "", model: "" },
  };

  var DEFAULT_SETTINGS = {
    preset: "qwen",
    endpoint: PRESETS.qwen.endpoint,
    model: PRESETS.qwen.model,
    apiKey: "",
    timeoutMs: 60000,
    usdaApiKey: "DEMO_KEY",
  };

  /* ------------------------------ Utilities ------------------------------ */

  function sleep(ms) {
    return new Promise(function (resolve) { window.setTimeout(resolve, ms); });
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        if (key === "text") node.textContent = attrs[key];
        else if (key === "class") node.className = attrs[key];
        else if (key === "style") node.setAttribute("style", attrs[key]);
        else if (key.indexOf("on") === 0 && typeof attrs[key] === "function") {
          node.addEventListener(key.slice(2), attrs[key]);
        } else if (attrs[key] !== null && attrs[key] !== undefined) {
          node.setAttribute(key, attrs[key]);
        }
      });
    }
    (children || []).forEach(function (child) {
      if (child === null || child === undefined) return;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    });
    return node;
  }

  function svgIcon(paths, size) {
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", String(size || 20));
    svg.setAttribute("height", String(size || 20));
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.8");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    paths.forEach(function (d) {
      var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", d);
      svg.appendChild(path);
    });
    return svg;
  }

  /* Pure domain logic lives in core.js (Node-testable); this file only adapts it. */

  var todayLocalIso = Core.todayLocalIso;
  var localDateOf = Core.localDateOf;
  var toLocalIsoString = Core.toLocalIsoString;
  var isFutureTooFar = Core.isFutureTooFar;

  function toUtcIso(localIso) {
    try {
      return Core.toUtcIso(localIso);
    } catch (err) {
      throw new ApiError("INVALID_REQUEST", err.message, 400, err.details);
    }
  }

  function calculateMeal(foods) {
    return Core.calculateMeal(window.HDT_FOOD_DB || { foods: [] }, foods);
  }

  function totalsOf(items) {
    return Core.totalsOf(items);
  }

  /* ------------------------------ Errors ------------------------------ */

  function ApiError(code, message, status, details) {
    this.name = "ApiError";
    this.code = code;
    this.message = message || code;
    this.status = status || 500;
    this.details = details === undefined ? null : details;
  }
  ApiError.prototype = Object.create(Error.prototype);
  ApiError.prototype.constructor = ApiError;

  /* ------------------------- Custom USDA foods ------------------------- */

  function readCustomFoods() {
    try {
      var raw = localStorage.getItem(CUSTOM_FOODS_KEY);
      var parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.filter(function (food) {
        return food && typeof food.food_name === "string" && food.food_name;
      }) : [];
    } catch (err) {
      return [];
    }
  }

  function mergeCustomFoods(customFoods) {
    var base = window.HDT_FOOD_DB || { foods: [] };
    var customNames = {};
    customFoods.forEach(function (food) { customNames[food.food_name] = true; });
    var foods = (base.foods || []).filter(function (food) {
      return !customNames[food.food_name];
    }).concat(customFoods);
    window.HDT_FOOD_DB = Object.assign({}, base, { foods: foods });

    var options = (Array.isArray(window.FOOD_OPTIONS) ? window.FOOD_OPTIONS : []).filter(function (option) {
      return !customNames[option.food_name];
    });
    customFoods.forEach(function (food) {
      options.push({ food_name: food.food_name, label: food.display_name || food.food_name });
    });
    window.FOOD_OPTIONS = options;
  }

  function getCustomFoods() {
    return readCustomFoods();
  }

  function registerCustomFood(food) {
    if (!food || typeof food.food_name !== "string" || !food.food_name) {
      return null;
    }
    var list = readCustomFoods().filter(function (item) {
      return item.food_name !== food.food_name;
    });
    list.push(food);
    if (list.length > 200) list = list.slice(list.length - 200);
    try {
      localStorage.setItem(CUSTOM_FOODS_KEY, JSON.stringify(list));
    } catch (err) {
      hdtToast("Failed to save the custom food; it is still available for this session.", "warning");
    }
    mergeCustomFoods(list);
    return food;
  }

  // Load before any page script calls the local API.
  mergeCustomFoods(readCustomFoods());

  /* --------------------------- IndexedDB --------------------------- */

  var dbPromise = null;

  function openDatabase() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise(function (resolve, reject) {
      if (!window.indexedDB) {
        reject(new ApiError("DATABASE_ERROR", "This WebView does not support local databases.", 500));
        return;
      }
      var request = window.indexedDB.open("hdt", 1);
      request.onupgradeneeded = function () {
        var database = request.result;
        if (!database.objectStoreNames.contains("meals")) {
          var store = database.createObjectStore("meals", { keyPath: "id", autoIncrement: true });
          store.createIndex("meal_date", "meal_date", { unique: false });
          store.createIndex("meal_datetime_utc", "meal_datetime_utc", { unique: false });
        }
      };
      request.onsuccess = function () { resolve(request.result); };
      request.onerror = function () {
        reject(new ApiError("DATABASE_ERROR", "Failed to open the local database.", 500));
      };
    });
    return dbPromise;
  }

  function withStore(mode, handler) {
    return openDatabase().then(function (database) {
      return new Promise(function (resolve, reject) {
        var transaction = database.transaction("meals", mode);
        var store = transaction.objectStore("meals");
        var result;
        try {
          result = handler(store);
        } catch (err) {
          reject(err);
          return;
        }
        transaction.oncomplete = function () { resolve(result && result.value !== undefined ? result.value : result); };
        transaction.onerror = function () {
          reject(new ApiError("DATABASE_ERROR", "Local database read/write failed.", 500));
        };
        transaction.onabort = function () {
          reject(new ApiError("DATABASE_ERROR", "The local database transaction was aborted.", 500));
        };
      });
    });
  }

  function requestValue(request) {
    return new Promise(function (resolve, reject) {
      request.onsuccess = function () { resolve(request.result); };
      request.onerror = function () { reject(request.error); };
    });
  }

  function getAllMeals() {
    return withStore("readonly", function (store) {
      return requestValue(store.getAll());
    });
  }

  function sortMeals(meals) {
    return meals.sort(function (a, b) {
      if (a.meal_datetime_utc === b.meal_datetime_utc) return b.id - a.id;
      return a.meal_datetime_utc < b.meal_datetime_utc ? 1 : -1;
    });
  }

  function mealDetail(record) { return Core.mealDetail(record); }

  function mealSummary(record) { return Core.mealSummary(record); }

  function saveMealRecord(record) {
    return withStore("readwrite", function (store) {
      var request = store.add(record);
      return requestValue(request).then(function (id) {
        record.id = id;
        return id;
      });
    });
  }

  function deleteMealRecord(id) {
    return withStore("readwrite", function (store) {
      var getRequest = store.get(id);
      return requestValue(getRequest).then(function (existing) {
        if (!existing) return false;
        return requestValue(store.delete(id)).then(function () { return true; });
      });
    });
  }

  /* ------------------------------ Settings ------------------------------ */

  function secretStoreAvailable() {
    return !!(window.AndroidHost
      && typeof window.AndroidHost.getSecret === "function"
      && typeof window.AndroidHost.setSecret === "function");
  }

  function secretGet(name) {
    try {
      return secretStoreAvailable() ? String(window.AndroidHost.getSecret(name) || "") : "";
    } catch (err) {
      return "";
    }
  }

  function secretSet(name, value) {
    try {
      return secretStoreAvailable()
        ? window.AndroidHost.setSecret(name, value) === true
        : false;
    } catch (err) {
      return false;
    }
  }

  function scrubLegacySecret(name) {
    try {
      var raw = localStorage.getItem(SETTINGS_KEY);
      if (!raw) return;
      var parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object" || !(name in parsed)) return;
      parsed[name] = "";
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(parsed));
    } catch (err) {
      /* Keep the old value when localStorage is unavailable; do not block startup */
    }
  }

  function loadSettings() {
    var settings = Object.assign({}, DEFAULT_SETTINGS);
    var legacy = { apiKey: "", usdaApiKey: "" };
    try {
      var raw = localStorage.getItem(SETTINGS_KEY);
      if (raw) {
        var parsed = JSON.parse(raw);
        Object.keys(DEFAULT_SETTINGS).forEach(function (key) {
          if (parsed[key] !== undefined && parsed[key] !== null) settings[key] = parsed[key];
        });
        if (typeof parsed.apiKey === "string") legacy.apiKey = parsed.apiKey;
        if (typeof parsed.usdaApiKey === "string") legacy.usdaApiKey = parsed.usdaApiKey;
      }
    } catch (err) {
      /* Use defaults when the stored configuration is corrupt */
    }

    // Keys live in Android Keystore; migrate plaintext values written by older builds.
    var storedAi = secretGet(SECRET_AI_KEY);
    var storedUsda = secretGet(SECRET_USDA_KEY);
    if (!storedAi && legacy.apiKey && secretSet(SECRET_AI_KEY, legacy.apiKey)) {
      storedAi = legacy.apiKey;
      scrubLegacySecret("apiKey");
    }
    if (!storedUsda && legacy.usdaApiKey
        && legacy.usdaApiKey !== DEFAULT_SETTINGS.usdaApiKey
        && secretSet(SECRET_USDA_KEY, legacy.usdaApiKey)) {
      storedUsda = legacy.usdaApiKey;
      scrubLegacySecret("usdaApiKey");
    }

    settings.apiKey = storedAi || legacy.apiKey || "";
    if (storedUsda) settings.usdaApiKey = storedUsda;
    else if (legacy.usdaApiKey) settings.usdaApiKey = legacy.usdaApiKey;
    if (!settings.usdaApiKey) settings.usdaApiKey = DEFAULT_SETTINGS.usdaApiKey;
    return settings;
  }

  function persistSettings(settings) {
    var stored = Object.assign({}, settings);

    if (secretStoreAvailable()) {
      // Never fall back to plaintext on Android: if the Keystore write fails the save fails.
      if (!secretSet(SECRET_AI_KEY, settings.apiKey || "")) {
        throw new Error("Could not write to secure local storage. Please try again.");
      }
      stored.apiKey = "";

      var usda = settings.usdaApiKey || "";
      if (usda === DEFAULT_SETTINGS.usdaApiKey) {
        if (!secretSet(SECRET_USDA_KEY, "")) {
          throw new Error("Could not write to secure local storage. Please try again.");
        }
        stored.usdaApiKey = DEFAULT_SETTINGS.usdaApiKey;
      } else {
        if (!secretSet(SECRET_USDA_KEY, usda)) {
          throw new Error("Could not write to secure local storage. Please try again.");
        }
        stored.usdaApiKey = "";
      }
    }

    localStorage.setItem(SETTINGS_KEY, JSON.stringify(stored));
  }

  function chatUrl(endpoint) {
    var base = String(endpoint || "").trim().replace(/\/+$/, "");
    if (!base) return "";
    if (/\/chat\/completions$/.test(base)) return base;
    return base + "/chat/completions";
  }

  function classifyStatus(status) {
    if (status === 401) return "auth";
    if (status === 402) return "insufficient_balance";
    if (status === 429) return "rate_limited";
    if (status >= 500) return "provider_5xx";
    return "provider_4xx";
  }

  /* ------------------------------ AI ------------------------------ */

  function buildRequestBody(settings, imageDataUrl) {
    var content = [{ type: "text", text: window.HDT_PROMPT || "Identify the food in this photo." }];
    if (imageDataUrl) {
      content.push({ type: "image_url", image_url: { url: imageDataUrl } });
    }
    var body = {
      model: settings.model,
      messages: [{ role: "user", content: content }],
      response_format: { type: "json_object" },
      temperature: 0,
      max_tokens: 2048,
    };
    if (/deepseek\.com/i.test(settings.endpoint)) {
      body.thinking = { type: "disabled" };
    }
    return body;
  }

  function nativeChat(settings, imageDataUrl) {
    return new Promise(function (resolve, reject) {
      if (!window.AndroidHost || typeof window.AndroidHost.chat !== "function") {
        reject(new ApiError("AI_PROVIDER_ERROR", "The native AI channel is unavailable.", 502, { reason: "bridge_unavailable" }));
        return;
      }
      var id = "ai_" + Date.now() + "_" + Math.random().toString(36).slice(2);
      var previous = window.__hdtNativeAiResult;
      window.__hdtNativeAiResult = function (requestId, ok, payload) {
        if (requestId !== id) {
          if (typeof previous === "function") previous(requestId, ok, payload);
          return;
        }
        window.__hdtNativeAiResult = previous;
        if (ok) {
          resolve(payload);
          return;
        }
        var info = {};
        try { info = JSON.parse(payload); } catch (err) { info = {}; }
        reject(new ApiError(
          "AI_PROVIDER_ERROR",
          info.message || "AI service call failed.",
          502,
          { reason: info.reason || "unknown", status_code: info.status || null, body: info.body || null }
        ));
      };
      try {
        window.AndroidHost.chat(
          id,
          chatUrl(settings.endpoint),
          settings.apiKey,
          settings.model,
          imageDataUrl || "",
          window.HDT_PROMPT || "Identify the food in this photo.",
          String(settings.timeoutMs || 60000)
        );
      } catch (err) {
        reject(new ApiError("AI_PROVIDER_ERROR", "Could not call the native AI channel.", 502, { reason: "bridge_error" }));
      }
    });
  }

  function webChat(settings, imageDataUrl) {
    var controller = new AbortController();
    var timer = window.setTimeout(function () { controller.abort(); }, settings.timeoutMs || 60000);
    return fetch(chatUrl(settings.endpoint), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + settings.apiKey,
      },
      body: JSON.stringify(buildRequestBody(settings, imageDataUrl)),
      signal: controller.signal,
    }).then(function (response) {
      return response.text().then(function (text) {
        if (!response.ok) {
          throw new ApiError("AI_PROVIDER_ERROR", "AI service returned HTTP " + response.status, 502, {
            reason: classifyStatus(response.status),
            status_code: response.status,
            body: text.slice(0, 500),
          });
        }
        return text;
      });
    }).catch(function (err) {
      if (err && err.name === "AbortError") {
        throw new ApiError("AI_PROVIDER_ERROR", "AI request timed out.", 502, { reason: "timeout" });
      }
      if (err instanceof ApiError) throw err;
      throw new ApiError("AI_PROVIDER_ERROR", "Could not connect to the AI service.", 502, { reason: "network" });
    }).finally(function () {
      window.clearTimeout(timer);
    });
  }

  function requestCompletion(settings, imageDataUrl) {
    if (!/^https:\/\//i.test(settings.endpoint || "")) {
      return Promise.reject(new ApiError(
        "AI_PROVIDER_ERROR",
        "For security, the API endpoint must use https://. Change it in API settings.",
        400,
        { reason: "insecure_endpoint" }
      ));
    }
    if (window.AndroidHost && typeof window.AndroidHost.chat === "function") {
      return nativeChat(settings, imageDataUrl);
    }
    return webChat(settings, imageDataUrl);
  }

  function extractJson(text) {
    var body = String(text || "").trim();
    if (!body) throw new ApiError("INVALID_AI_RESPONSE", "The AI returned empty content.", 502, { reason: "not_json" });
    if (body.charAt(0) === "`") {
      body = body.replace(/^```(?:json)?\s*/i, "").replace(/```\s*$/, "").trim();
    }
    try {
      return JSON.parse(body);
    } catch (err) {
      var start = body.indexOf("{");
      var end = body.lastIndexOf("}");
      if (start >= 0 && end > start) {
        try { return JSON.parse(body.slice(start, end + 1)); } catch (inner) { /* fallthrough */ }
      }
      throw new ApiError("INVALID_AI_RESPONSE", "The AI response is not JSON.", 502, { reason: "not_json" });
    }
  }

  function parseCompletion(raw) {
    var payload = extractJson(raw);
    var choice = payload && payload.choices && payload.choices[0];
    if (!choice) throw new ApiError("INVALID_AI_RESPONSE", "The AI returned no candidates.", 502, { reason: "not_json" });
    if (choice.finish_reason === "length") {
      throw new ApiError("INVALID_AI_RESPONSE", "AI output was truncated by max_tokens.", 502, { reason: "truncated" });
    }
    if (choice.finish_reason === "content_filter") {
      throw new ApiError("INVALID_AI_RESPONSE", "AI output was blocked by content filtering.", 502, { reason: "content_filtered" });
    }
    var content = choice.message && choice.message.content;
    if (typeof content !== "string" || !content.trim()) {
      throw new ApiError("INVALID_AI_RESPONSE", "The AI returned empty content.", 502, { reason: "not_json" });
    }
    return extractJson(content);
  }

  function validateAnalysis(raw) {
    try {
      return Core.validateAnalysis(raw);
    } catch (err) {
      if (err && err.code) {
        throw new ApiError(err.code, err.message, err.status || 502, err.details);
      }
      throw err;
    }
  }

  function callVision(settings, imageDataUrl) {
    var attempt = 0;
    function run() {
      return requestCompletion(settings, imageDataUrl).then(parseCompletion).catch(function (err) {
        var reason = err && err.details ? err.details.reason : "";
        if (attempt === 0 && RETRYABLE_REASONS.indexOf(reason) >= 0) {
          attempt += 1;
          var wait = reason === "rate_limited" ? 2000 : 300;
          return sleep(wait).then(run);
        }
        throw err;
      });
    }
    return run();
  }

  /* --------------------------- Image handling --------------------------- */

  function guessMime(file) {
    if (file.type) return file.type.toLowerCase();
    var name = String(file.name || "").toLowerCase();
    if (/\.jpe?g$/.test(name)) return "image/jpeg";
    if (/\.png$/.test(name)) return "image/png";
    if (/\.webp$/.test(name)) return "image/webp";
    return "";
  }

  function readAsDataUrl(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve(String(reader.result || "")); };
      reader.onerror = function () {
        reject(new ApiError("INVALID_IMAGE", "Failed to read the image.", 400));
      };
      reader.readAsDataURL(file);
    });
  }

  function loadImageElement(file) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(file);
      var image = new Image();
      image.onload = function () { URL.revokeObjectURL(url); resolve(image); };
      image.onerror = function () {
        URL.revokeObjectURL(url);
        reject(new ApiError("INVALID_IMAGE", "This image could not be decoded.", 400));
      };
      image.src = url;
    });
  }

  function compressImage(file, maxSide, quality) {
    var mime = guessMime(file);
    if (mime === "image/svg+xml") return readAsDataUrl(file);
    return loadImageElement(file).then(function (image) {
      var width = image.naturalWidth || image.width;
      var height = image.naturalHeight || image.height;
      var scale = Math.min(1, maxSide / Math.max(width, height));
      var canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(width * scale));
      canvas.height = Math.max(1, Math.round(height * scale));
      var context = canvas.getContext("2d");
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL("image/jpeg", quality || 0.85);
    });
  }

  function analyzeImage(file, mealType) {
    var mime = guessMime(file);
    if (ALLOWED_IMAGE_TYPES.indexOf(mime) < 0) {
      return Promise.reject(new ApiError("UNSUPPORTED_MEDIA_TYPE", "Only JPG / PNG / WebP are supported.", 415));
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      return Promise.reject(new ApiError("IMAGE_TOO_LARGE", "The image is larger than 8 MB. Compress it and try again.", 413));
    }
    var settings = loadSettings();
    if (!settings.apiKey) {
      hdtToast("No API key configured. Open ⋮ → API settings in the top-right corner to set one.", "warning", 7000);
      window.setTimeout(function () { openSettingsModal("missing"); }, 400);
      return Promise.reject(new ApiError("AI_PROVIDER_ERROR", "API key is not configured.", 502, { reason: "missing_api_key" }));
    }
    if (!settings.endpoint) {
      return Promise.reject(new ApiError("AI_PROVIDER_ERROR", "API endpoint is empty.", 502, { reason: "missing_endpoint" }));
    }
    return compressImage(file, 1024, 0.85).then(function (dataUrl) {
      return callVision(settings, dataUrl);
    }).then(function (raw) {
      var analysis = validateAnalysis(raw);
      analysis.image_path = null;
      return analysis;
    });
  }

  /* --------------------------- Local API routes --------------------------- */

  function jsonResponse(body, status) {
    return new Response(JSON.stringify(body), {
      status: status || 200,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  }

  function okResponse(data, status) {
    return jsonResponse({ status: "success", data: data }, status || 200);
  }

  function errorResponse(err) {
    var error = err instanceof ApiError ? err : new ApiError("INTERNAL_ERROR", "Local service error.", 500);
    return jsonResponse({
      status: "error",
      error: { code: error.code, message: error.message, details: error.details },
    }, error.status);
  }

  function validateMealPayload(payload) {
    try {
      return Core.validateMealPayload(payload);
    } catch (err) {
      if (err && err.code) {
        throw new ApiError(err.code, err.message, err.status || 400, err.details);
      }
      throw err;
    }
  }

  function createMeal(payload) {
    var normalized = validateMealPayload(payload);
    var foods = normalized.items.map(function (item) {
      return {
        food_name: item.food_name,
        display_name: item.display_name,
        estimated_weight_g: item.weight_g,
      };
    });
    var nutrition = calculateMeal(foods);
    if (!nutrition.items.length) {
      throw new ApiError("FOOD_NOT_FOUND", "No matching entry in the food database.", 422, { warnings: nutrition.warnings });
    }
    var record = {
      meal_type: normalized.meal_type,
      meal_datetime_utc: toUtcIso(normalized.meal_datetime),
      meal_date: localDateOf(normalized.meal_datetime),
      image_path: normalized.image_path,
      created_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      items: nutrition.items,
    };
    return saveMealRecord(record).then(function (id) {
      return mealDetail(Object.assign({}, record, { id: id }));
    });
  }

  function listMeals(path) {
    var params = new URLSearchParams(path.split("?")[1] || "");
    var dateFrom = params.get("date_from");
    var dateTo = params.get("date_to");
    if ((dateFrom === null) !== (dateTo === null)) {
      throw new ApiError("INVALID_REQUEST", "date_from and date_to must be provided together.", 400);
    }
    var limit = Number(params.get("limit") || 50);
    var offset = Number(params.get("offset") || 0);
    if (!Number.isInteger(limit) || limit < 1 || limit > 200) {
      throw new ApiError("INVALID_REQUEST", "Invalid limit.", 400);
    }
    if (!Number.isInteger(offset) || offset < 0) {
      throw new ApiError("INVALID_REQUEST", "Invalid offset.", 400);
    }
    return getAllMeals().then(function (meals) {
      var filtered = meals.filter(function (meal) {
        if (dateFrom && meal.meal_date < dateFrom) return false;
        if (dateTo && meal.meal_date > dateTo) return false;
        return true;
      });
      sortMeals(filtered);
      var page = filtered.slice(offset, offset + limit).map(mealSummary);
      return { meals: page, pagination: { limit: limit, offset: offset, count: page.length } };
    });
  }

  function getMealById(id) {
    return getAllMeals().then(function (meals) {
      var found = meals.find(function (meal) { return String(meal.id) === String(id); });
      if (!found) throw new ApiError("MEAL_NOT_FOUND", "This record does not exist.", 404, { meal_id: id });
      return mealDetail(found);
    });
  }

  function removeMeal(id) {
    return deleteMealRecord(Number(id)).then(function (deleted) {
      if (!deleted) throw new ApiError("MEAL_NOT_FOUND", "This record does not exist.", 404, { meal_id: Number(id) });
      return { meal_id: Number(id), deleted: true };
    });
  }

  function dailySummary(date) {
    var day = date || todayLocalIso();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) {
      throw new ApiError("INVALID_REQUEST", "date must use the YYYY-MM-DD format.", 400);
    }
    return getAllMeals().then(function (meals) {
      var dayMeals = meals.filter(function (meal) { return meal.meal_date === day; });
      var items = [];
      dayMeals.forEach(function (meal) { items = items.concat(meal.items || []); });
      return { date: day, totals: totalsOf(items), meal_count: dayMeals.length };
    });
  }

  function handleLocalApi(path, options) {
    var method = String((options && options.method) || "GET").toUpperCase();
    var clean = path.split("?")[0];
    var work;

    try {
      if (clean === "/analyze" && method === "POST") {
        var form = options.body;
        var image = form && form.get ? form.get("image") : null;
        var mealType = form && form.get ? form.get("meal_type") : null;
        if (!image || typeof image === "string") {
          throw new ApiError("INVALID_REQUEST", "Missing image field.", 400);
        }
        if (MEAL_TYPES.indexOf(mealType) < 0) {
          throw new ApiError("INVALID_REQUEST", "Invalid meal_type.", 400, { allowed: MEAL_TYPES.slice().sort() });
        }
        work = analyzeImage(image, mealType).then(function (data) { return okResponse(data); });
      } else if (clean === "/meals" && method === "POST") {
        var payload = typeof options.body === "string" ? JSON.parse(options.body) : options.body;
        work = createMeal(payload).then(function (data) { return okResponse(data, 201); });
      } else if (clean === "/meals" && method === "GET") {
        work = listMeals(path).then(function (data) { return okResponse(data); });
      } else if (clean === "/dashboard/daily" && method === "GET") {
        var date = new URLSearchParams(path.split("?")[1] || "").get("date");
        work = dailySummary(date).then(function (data) { return okResponse(data); });
      } else if (/^\/meals\/[0-9]+$/.test(clean) && method === "GET") {
        work = getMealById(clean.split("/")[2]).then(function (data) { return okResponse(data); });
      } else if (/^\/meals\/[0-9]+$/.test(clean) && method === "DELETE") {
        work = removeMeal(clean.split("/")[2]).then(function (data) { return okResponse(data); });
      } else {
        work = Promise.reject(new ApiError("INVALID_REQUEST", "Local endpoint not found: " + method + " " + clean, 404));
      }
    } catch (err) {
      work = Promise.reject(err);
    }

    return work.catch(errorResponse);
  }

  var realFetch = window.fetch ? window.fetch.bind(window) : null;
  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    var path = String(url).replace(/^https?:\/\/[^/]+/i, "");
    if (path.indexOf("/api/v1") === 0) {
      return handleLocalApi(path.slice("/api/v1".length), init || {});
    }
    if (realFetch) return realFetch(input, init);
    return Promise.reject(new TypeError("fetch is not available"));
  };

  /* ------------------------------ UI ------------------------------ */

  function hdtToast(message, type, timeout) {
    var region = document.getElementById("toast-region");
    if (!region) {
      region = el("div", { id: "toast-region", class: "toast-region", role: "status" });
      document.body.appendChild(region);
    }
    while (region.children.length >= 3) region.removeChild(region.firstElementChild);
    var toast = el("div", { class: "toast toast-" + (type || "info"), role: type === "error" ? "alert" : "status" }, [
      el("p", { class: "toast-text", text: message }),
    ]);
    var close = el("button", { type: "button", class: "toast-close", "aria-label": "Close notification", text: "×" });
    toast.appendChild(close);
    region.appendChild(toast);
    var dismissed = false;
    function dismiss() {
      if (dismissed) return;
      dismissed = true;
      toast.classList.remove("is-visible");
      window.setTimeout(function () { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 220);
    }
    close.addEventListener("click", dismiss);
    window.requestAnimationFrame(function () { toast.classList.add("is-visible"); });
    window.setTimeout(dismiss, timeout || 4200);
  }

  var activeModal = null;

  function closeModal() {
    if (!activeModal) return;
    var modal = activeModal;
    activeModal = null;
    if (modal.backdrop.parentNode) modal.backdrop.parentNode.removeChild(modal.backdrop);
    document.body.style.overflow = "";
    document.removeEventListener("keydown", modal.onKey);
    if (typeof modal.onClose === "function") modal.onClose();
  }

  function openModal(options) {
    closeModal();
    var backdrop = el("div", { class: "hdt-modal-backdrop" });
    var head = el("div", { class: "hdt-modal-head" }, [
      el("h2", { text: options.title }),
      el("button", { type: "button", class: "hdt-modal-close", "aria-label": "Close", text: "×" }),
    ]);
    var body = el("div", { class: "hdt-modal-body" });
    if (options.content) body.appendChild(options.content);
    var modal = el("div", { class: "hdt-modal", role: "dialog", "aria-modal": "true" }, [head, body]);
    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);
    document.body.style.overflow = "hidden";

    function onKey(event) {
      if (event.key === "Escape") closeModal();
    }
    document.addEventListener("keydown", onKey);
    head.querySelector(".hdt-modal-close").addEventListener("click", closeModal);
    backdrop.addEventListener("click", function (event) {
      if (event.target === backdrop) closeModal();
    });
    activeModal = { backdrop: backdrop, body: body, onKey: onKey, onClose: options.onClose };
    if (typeof options.onMount === "function") options.onMount(body);
    return activeModal;
  }

  function field(labelText, input) {
    return el("div", { class: "hdt-field" }, [el("label", { text: labelText }), input]);
  }

  function button(text, variant, onClick) {
    var node = el("button", { type: "button", class: "btn btn-" + (variant || "ghost") }, [text]);
    if (onClick) node.addEventListener("click", onClick);
    return node;
  }

  function openSettingsModal(reason) {
    var settings = loadSettings();
    var presetSelect = el("select", { id: "hdt-preset" }, [
      el("option", { value: "qwen", text: "Qwen-VL (Alibaba Cloud Model Studio)" }),
      el("option", { value: "openai", text: "OpenAI（gpt-4o-mini）" }),
      el("option", { value: "custom", text: "Custom / self-hosted service" }),
    ]);
    presetSelect.value = settings.preset || "custom";
    var endpointInput = el("input", { id: "hdt-endpoint", type: "url", inputmode: "url", placeholder: "https://dashscope.aliyuncs.com/compatible-mode/v1", value: settings.endpoint });
    var modelInput = el("input", { id: "hdt-model", type: "text", placeholder: "qwen-vl-max", value: settings.model });
    var keyInput = el("input", { id: "hdt-key", type: "password", autocomplete: "off", placeholder: "sk-...", value: settings.apiKey });
    var reveal = el("button", { type: "button", class: "hdt-reveal", text: "Show" });
    reveal.addEventListener("click", function () {
      var showing = keyInput.type === "text";
      keyInput.type = showing ? "password" : "text";
      reveal.textContent = showing ? "Show" : "Hide";
    });
    var timeoutInput = el("input", { id: "hdt-timeout", type: "number", min: "10", max: "180", step: "5", value: String(Math.round((settings.timeoutMs || 60000) / 1000)) });
    var status = el("p", { class: "hdt-status", id: "hdt-test-status" });

    presetSelect.addEventListener("change", function () {
      var preset = PRESETS[presetSelect.value];
      if (preset && preset.endpoint) {
        endpointInput.value = preset.endpoint;
        modelInput.value = preset.model;
      }
    });

    var content = el("div", {}, [
      reason === "missing" ? el("p", { class: "hdt-note is-warning", text: "No API key configured yet. Add one to recognize meal photos; the key stays on this device." }) : null,
      field("Service preset", presetSelect),
      field("API endpoint (Base URL)", endpointInput),
      field("Model name", modelInput),
      field("API Key", el("div", { class: "hdt-input-wrap" }, [keyInput, reveal])),
      field("Request timeout (seconds)", timeoutInput),
      field("USDA API key (optional, for unmatched food lookup)", el("input", {
        id: "hdt-usda-key", type: "password", autocomplete: "off",
        placeholder: "DEMO_KEY", value: settings.usdaApiKey || "DEMO_KEY",
      })),
      el("p", { class: "hdt-note", text: "Works with any OpenAI-compatible /chat/completions vision endpoint. Requests are sent directly by the native network layer and do not pass through an app server. The API key and USDA key are encrypted with the Android Keystore (decryptable only on this device) and are never written to localStorage; non-sensitive settings such as the API endpoint stay on this device. For security, the API endpoint must use https://. The USDA API key is used only for unmatched food lookup; leave it empty to use DEMO_KEY (rate-limited)." }),
      status,
    ]);

    function collect() {
      var endpoint = endpointInput.value.trim();
      if (!/^https:\/\//i.test(endpoint)) {
        throw new Error("For security, the API endpoint must use https:// (plain http is not supported).");
      }
      var timeout = Number(timeoutInput.value) || 60;
      timeout = Math.max(10, Math.min(180, timeout));
      return {
        preset: presetSelect.value,
        endpoint: endpoint,
        model: modelInput.value.trim(),
        apiKey: keyInput.value.trim(),
        timeoutMs: Math.round(timeout * 1000),
        usdaApiKey: (document.getElementById("hdt-usda-key") || {}).value
          ? document.getElementById("hdt-usda-key").value.trim() || "DEMO_KEY"
          : (settings.usdaApiKey || "DEMO_KEY"),
      };
    }

    var testButton = button("Test connection", "ghost", function () {
      var next;
      try { next = collect(); } catch (err) { status.textContent = err.message; status.className = "hdt-status is-error"; return; }
      if (!next.apiKey) {
        status.textContent = "Enter an API key first.";
        status.className = "hdt-status is-error";
        return;
      }
      status.textContent = "Connecting…";
      status.className = "hdt-status";
      testConnection(next).then(function () {
        status.textContent = "Connected. The model is available.";
        status.className = "hdt-status is-ok";
      }).catch(function (err) {
        status.textContent = "Connection failed: " + (err.message || "Unknown error");
        status.className = "hdt-status is-error";
      });
    });

    var saveButton = button("Save settings", "primary", function () {
      var next;
      try { next = collect(); } catch (err) { status.textContent = err.message; status.className = "hdt-status is-error"; return; }
      try {
        persistSettings(next);
        hdtToast("API settings saved", "success");
        closeModal();
      } catch (err) {
        status.textContent = "Save failed: " + err.message;
        status.className = "hdt-status is-error";
      }
    });

    content.appendChild(el("div", { class: "hdt-actions" }, [testButton, saveButton]));
    openModal({ title: "API settings", content: content });
  }

  function testConnection(settings) {
    if (window.AndroidHost && typeof window.AndroidHost.test === "function") {
      return new Promise(function (resolve, reject) {
        var id = "test_" + Date.now() + "_" + Math.random().toString(36).slice(2);
        var previous = window.__hdtNativeAiTest;
        window.__hdtNativeAiTest = function (requestId, ok, payloadText) {
          if (requestId !== id) {
            if (typeof previous === "function") previous(requestId, ok, payloadText);
            return;
          }
          window.__hdtNativeAiTest = previous;
          if (ok) resolve(payloadText);
          else {
            var info = {};
            try { info = JSON.parse(payloadText); } catch (err) { info = {}; }
            reject(new Error(info.message || "HTTP error"));
          }
        };
        try {
          window.AndroidHost.test(
            id,
            chatUrl(settings.endpoint),
            settings.apiKey,
            settings.model,
            String(settings.timeoutMs || 60000)
          );
        } catch (err) {
          reject(new Error("Could not call the native network layer"));
        }
      });
    }
    return webChat(settings, null).then(function () { return true; });
  }

  function openSplashModal() {
    var current = null;
    try { current = localStorage.getItem(SPLASH_KEY); } catch (err) { current = null; }
    var preview = el("div", { class: "hdt-splash-preview", id: "hdt-splash-preview" }, [
      el("span", { text: current ? "Current custom splash" : "Default splash" }),
    ]);
    if (current) preview.style.backgroundImage = 'url("' + current.replace(/"/g, "%22") + '")';

    var fileInput = el("input", { type: "file", class: "hdt-file-input", id: "hdt-splash-file", accept: "image/*,.svg,image/svg+xml" });
    var note = el("p", { class: "hdt-muted", text: "Supports JPG, PNG, WebP, GIF, SVG and other common formats. A portrait image (e.g. 1080×1920) works best. The image stays on this device and is never uploaded." });

    function setPreview(dataUrl) {
      if (dataUrl) {
        preview.style.backgroundImage = 'url("' + dataUrl.replace(/"/g, "%22") + '")';
        preview.querySelector("span").textContent = "Current custom splash";
      } else {
        preview.style.backgroundImage = "";
        preview.querySelector("span").textContent = "Default splash";
      }
    }

    var pickButton = button("Choose image", "primary", function () { fileInput.click(); });
    var resetButton = button("Restore default", "ghost", function () {
      try { localStorage.removeItem(SPLASH_KEY); } catch (err) { /* Ignore */ }
      setPreview(null);
      hdtToast("Default splash restored", "success");
    });
    var doneButton = button("Done", "ghost", function () { closeModal(); });

    fileInput.addEventListener("change", function () {
      var file = fileInput.files && fileInput.files[0];
      fileInput.value = "";
      if (!file) return;
      var mime = guessMime(file);
      if (mime.indexOf("image/") !== 0) {
        hdtToast("Choose an image file.", "error");
        return;
      }
      if (file.size > 8 * 1024 * 1024) {
        hdtToast("The image is larger than 8 MB. Choose another one.", "error");
        return;
      }
      var work = (mime === "image/svg+xml" || mime === "image/gif")
        ? readAsDataUrl(file)
        : compressImage(file, 1440, 0.85);
      work.then(function (dataUrl) {
        try {
          localStorage.setItem(SPLASH_KEY, dataUrl);
        } catch (err) {
          hdtToast("The image is too large to save. Choose a smaller one.", "error", 6000);
          return;
        }
        setPreview(dataUrl);
        hdtToast("Splash image saved. It will appear on the next launch.", "success");
      }).catch(function () {
        hdtToast("This image could not be read. Choose another one.", "error");
      });
    });

    openModal({
      title: "Splash screen",
      content: el("div", {}, [
        preview,
        el("div", { class: "hdt-actions" }, [pickButton, resetButton]),
        note,
        fileInput,
        el("div", { class: "hdt-actions" }, [doneButton]),
      ]),
    });
  }

  var CREATORS = [
    { name: "leonardo-weasley", role: "GitHub contributor" },
    { name: "jyj0808", role: "GitHub contributor" },
    { name: "baihe-love", role: "GitHub contributor" },
    { name: "leimanwen", role: "GitHub contributor" },
    { name: "pan-yi-fan", role: "GitHub contributor" },
  ];

  var MIT_LICENSE = [
    "MIT License",
    "",
    "Copyright (c) 2026 leonardo-weasley",
    "",
    "Permission is hereby granted, free of charge, to any person obtaining a copy",
    'of this software and associated documentation files (the "Software"), to deal',
    "in the Software without restriction, including without limitation the rights",
    "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell",
    "copies of the Software, and to permit persons to whom the Software is",
    "furnished to do so, subject to the following conditions:",
    "",
    "The above copyright notice and this permission notice shall be included in all",
    "copies or substantial portions of the Software.",
    "",
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR',
    "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,",
    "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE",
    "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER",
    "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,",
    "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE",
    "SOFTWARE.",
  ].join("\n");

  var THIRD_PARTY = [
    { name: "Chart.js 4.4.1", license: "MIT", note: "Dashboard nutrition charts, bundled in the APK and available offline." },
    { name: "USDA FoodData Central", license: "Public domain", note: "Nutrition data for 29 foods, 24 of them from USDA; fdc_id is kept per item." },
    { name: "Android / WebView", license: "Apache-2.0", note: "App runtime and page rendering engine." },
    { name: "OpenAI-compatible vision API", license: "Provider terms", note: "Sends photos and prompts only when you start recognition; the app does not resell or cache model output." },
  ];

  function openExternal(url) {
    if (window.AndroidHost && typeof window.AndroidHost.openExternal === "function") {
      window.AndroidHost.openExternal(url);
      return;
    }
    window.open(url, "_blank");
  }

  function openAboutModal() {
    var hero = el("div", { class: "hdt-about-hero" }, [
      el("span", { class: "hdt-about-logo" }, [svgIcon([
        "M12 21c4.2 0 7.5-3.2 7.5-7.2 0-4.2-2.9-7.1-5.6-8.8C11.5 3.6 9 2.4 6.5 3c.2 2.6 1.3 5 3.2 6.7",
        "M12 21c-4.2 0-7.5-3.2-7.5-7.2 0-1.6.4-3 1.2-4.2",
        "M12 21c0-4.5 1.5-8.2 4.5-10.5",
      ], 26)]),
      el("div", {}, [
        el("strong", { text: "Healthy Diet Tracker" }),
        el("small", { text: "v" + APP_VERSION + " · " + APP_BUILD + " · Runs fully offline, no Python required" }),
      ]),
    ]);

    var creditList = el("div", { class: "hdt-credit-list" });
    var eggTaps = 0;
    var eggTimer = null;
    CREATORS.forEach(function (person) {
      var row = el("div", { class: "hdt-credit" }, [
        el("span", { text: person.name }),
        el("code", { text: person.role }),
      ]);
      // Easter egg: tap leonardo-weasley 6 times to open Cloud Genshin in-app.
      if (person.name === "leonardo-weasley") {
        row.style.cursor = "pointer";
        row.addEventListener("click", function () {
          eggTaps += 1;
          if (eggTimer) window.clearTimeout(eggTimer);
          eggTimer = window.setTimeout(function () { eggTaps = 0; }, 2000);
          if (eggTaps >= 6) {
            eggTaps = 0;
            try {
              if (window.AndroidHost && typeof window.AndroidHost.openEgg === "function") {
                window.AndroidHost.openEgg();
              }
            } catch (err) { /* bridge unavailable: no-op */ }
          }
        });
      }
      creditList.appendChild(row);
    });

    var licenseBox = el("pre", { class: "hdt-license", text: MIT_LICENSE });

    var thirdParty = el("div", { class: "hdt-third-party" });
    THIRD_PARTY.forEach(function (entry) {
      thirdParty.appendChild(el("article", {}, [
        el("strong", { text: entry.name }),
        el("p", { text: entry.license + " · " + entry.note }),
      ]));
    });

    var repoLink = el("button", { type: "button", class: "hdt-link", text: "github.com/leonardo-weasley/healthy-diet-tracker" });
    repoLink.addEventListener("click", function () { openExternal(REPO_URL); });

    var content = el("div", {}, [
      hero,
      el("h3", { text: "Credits" }),
      el("p", { class: "hdt-muted", text: "Names come from the repository git history (GitHub Contributors). The team covers five roles per README §9: backend integration, AI integration, nutrition engine, frontend, and database/testing." }),
      creditList,
      el("h3", { text: "Open-source license" }),
      el("p", {}, ["This project is released under the ", el("strong", { text: "MIT License" }), "."]),
      licenseBox,
      el("h3", { text: "Third-party components and data sources" }),
      thirdParty,
      el("h3", { text: "Data and privacy" }),
      el("ul", {}, [
        el("li", { text: "Meal records are stored in local IndexedDB, cleared when the app is uninstalled, and never synced to a server." }),
        el("li", { text: "The API key and USDA key are encrypted with the Android Keystore and stored on this device. Settings such as the API endpoint and splash image are stored in localStorage and used only for the endpoint you configure." }),
        el("li", { text: "The compressed photo and prompt are sent to your configured AI endpoint only when you tap Analyze." }),
        el("li", { text: "Nutrition values are estimates and cannot replace medical or professional dietary advice." }),
      ]),
      el("h3", { text: "Project repository" }),
      el("p", {}, [repoLink]),
      el("div", { class: "hdt-actions" }, [
        button("API settings", "ghost", function () { closeModal(); openSettingsModal(); }),
        button("Splash screen", "ghost", function () { closeModal(); openSplashModal(); }),
        button("Close", "primary", closeModal),
      ]),
    ]);

    openModal({ title: "About", content: content });
  }

  function openMenuSheet() {
    closeModal();
    var backdrop = el("div", { class: "hdt-backdrop" });
    var sheet = el("div", { class: "hdt-sheet", role: "dialog", "aria-modal": "true", "aria-label": "App menu" });
    sheet.appendChild(el("div", { class: "hdt-sheet-grip" }));
    sheet.appendChild(el("p", { class: "hdt-sheet-title", text: "Healthy Diet Tracker · v" + APP_VERSION }));

    function item(iconPaths, title, subtitle, onClick, danger) {
      var node = el("button", { type: "button", class: "hdt-menu-item" + (danger ? " is-danger" : "") }, [
        el("span", { class: "hdt-menu-icon" }, [svgIcon(iconPaths, 19)]),
        el("span", {}, [el("strong", { text: title }), el("small", { text: subtitle })]),
      ]);
      node.addEventListener("click", onClick);
      return node;
    }

    sheet.appendChild(item(
      ["M12 5v14", "M5 12h14"],
      "Log a meal", "Upload or take a meal photo",
      function () { closeModal(); window.location.href = "upload.html"; }
    ));
    sheet.appendChild(item(
      ["M4 7h16", "M4 12h16", "M4 17h10"],
      "API settings", "Change API endpoint, model, and key",
      function () { closeModal(); openSettingsModal(); }
    ));
    sheet.appendChild(item(
      ["M4 5h16v14H4z", "M4 15l4-4 3 3 3-3 6 6", "M9 9.5h.01"],
      "Splash screen", "Customize the launch image and skip button",
      function () { closeModal(); openSplashModal(); }
    ));
    sheet.appendChild(item(
      ["M12 8h.01", "M11 12h1v4h1", "M12 21a9 9 0 100-18 9 9 0 000 18z"],
      "About", "Credits, license, and third-party notices",
      function () { closeModal(); openAboutModal(); }
    ));
    sheet.appendChild(item(
      ["M14 4h6v6", "M20 4l-8 8", "M19 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1h5"],
      "Project repository", "Open GitHub in a browser",
      function () { closeModal(); openExternal(REPO_URL); }
    ));

    backdrop.appendChild(sheet);
    document.body.appendChild(backdrop);
    document.body.style.overflow = "hidden";

    function close() {
      sheet.classList.remove("is-open");
      backdrop.classList.remove("is-open");
      window.setTimeout(function () {
        if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
      }, 220);
      document.body.style.overflow = "";
      document.removeEventListener("keydown", onKey);
    }
    function onKey(event) { if (event.key === "Escape") close(); }
    document.addEventListener("keydown", onKey);
    backdrop.addEventListener("click", close);

    window.requestAnimationFrame(function () {
      backdrop.classList.add("is-open");
      sheet.classList.add("is-open");
    });
  }

  function mountMenuButton() {
    if (document.getElementById("hdt-menu-btn")) return;
    var btn = el("button", { type: "button", id: "hdt-menu-btn", class: "hdt-menu-btn", "aria-label": "App menu", title: "More" });
    btn.appendChild(svgIcon(["M12 6h.01", "M12 12h.01", "M12 18h.01"], 24));
    // Solid dots read more clearly than outlined ones
    btn.innerHTML = "";
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", "22");
    svg.setAttribute("height", "22");
    svg.setAttribute("fill", "currentColor");
    [5, 12, 19].forEach(function (cy) {
      var circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", "12");
      circle.setAttribute("cy", String(cy));
      circle.setAttribute("r", "1.8");
      svg.appendChild(circle);
    });
    btn.appendChild(svg);
    btn.addEventListener("click", openMenuSheet);
    document.body.appendChild(btn);
  }

  function mountCameraActions() {
    if (!document.getElementById("upload-form")) return;
    if (document.getElementById("hdt-source-actions")) return;
    var dropZone = document.getElementById("drop-zone");
    if (!dropZone || !dropZone.parentNode) return;

    var camera = el("button", { type: "button", class: "btn btn-ghost", id: "hdt-camera-btn" }, [
      svgIcon(["M4 8h3l1.5-2h7L17 8h3v11H4z", "M12 16a3 3 0 100-6 3 3 0 000 6z"], 17),
      "Take photo",
    ]);
    var gallery = el("button", { type: "button", class: "btn btn-ghost", id: "hdt-gallery-btn" }, [
      svgIcon(["M4 5h16v14H4z", "M4 15l4-4 3 3 3-3 6 6", "M9 9.5h.01"], 17),
      "Choose from gallery",
    ]);
    var actions = el("div", { class: "hdt-source-actions", id: "hdt-source-actions" }, [camera, gallery]);
    dropZone.parentNode.insertBefore(actions, dropZone.nextSibling);

    function openPicker(capture) {
      var input = document.getElementById("file-input");
      if (!input) return;
      if (capture) input.setAttribute("capture", "environment");
      else input.removeAttribute("capture");
      input.click();
      if (capture) {
        window.setTimeout(function () { input.removeAttribute("capture"); }, 1500);
      }
    }
    camera.addEventListener("click", function () { openPicker(true); });
    gallery.addEventListener("click", function () { openPicker(false); });
  }

  function checkRuntime() {
    if (typeof BigInt === "function" && typeof window.indexedDB !== "undefined") return;
    var warn = el("div", {
      style: "position:fixed;left:0;right:0;bottom:0;z-index:3000;background:#7f1d1d;color:#fff;"
        + "padding:12px 16px;font-size:13px;line-height:1.5;",
      text: "The system WebView is too old to run local nutrition calculations. Update Android System WebView and try again.",
    });
    document.body.appendChild(warn);
  }

  function init() {
    // Migrate any plaintext keys left by older builds into Android Keystore right away.
    loadSettings();
    // food-options.js is deferred and may load after this file; re-apply saved foods
    // so the standard-food selects include USDA entries registered in earlier sessions.
    mergeCustomFoods(readCustomFoods());
    checkRuntime();
    mountMenuButton();
    mountCameraActions();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.HDT = {
    version: APP_VERSION,
    getSettings: loadSettings,
    openSettings: openSettingsModal,
    openAbout: openAboutModal,
    openSplash: openSplashModal,
    calculateMeal: calculateMeal,
    matchFood: function (name) { return Core.matchFood(window.HDT_FOOD_DB || { foods: [] }, name); },
    getCustomFoods: getCustomFoods,
    registerCustomFood: registerCustomFood,
    toast: hdtToast,
    openModal: openModal,
    closeModal: closeModal,
    el: el,
    button: button,
  };
})();
