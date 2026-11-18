/* =========================================================================
 * app.js —— Android 版运行时（无 Python 后端）
 *
 * 职责：
 *   1. 在 WebView 内接管 /api/v1/*，用 IndexedDB + 本地营养库实现同样的契约；
 *   2. 通过原生桥 AndroidHost 调用用户配置的 OpenAI 兼容视觉接口（避免 CORS）；
 *   3. 注入右上角菜单、API 设置、开屏画面设置、关于页与拍照入口。
 *
 * 本文件必须早于 api.js 执行，fetch 拦截才会生效。
 * ========================================================================= */
(function () {
  "use strict";

  var APP_VERSION = "1.0.0";
  var APP_BUILD = "2026-11-18";
  var REPO_URL = "https://github.com/leonardo-weasley/healthy-diet-tracker";
  var SETTINGS_KEY = "hdt.settings";
  var SPLASH_KEY = "hdt.splashImage";

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
  };

  /* ------------------------------ 小工具 ------------------------------ */

  function sleep(ms) {
    return new Promise(function (resolve) { window.setTimeout(resolve, ms); });
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        if (key === "text") node.textContent = attrs[key];
        else if (key === "html") node.innerHTML = attrs[key];
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

  /* 纯领域逻辑在 core.js（可被 Node 单测），这里只做少量适配。 */

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

  /* ------------------------------ 错误 ------------------------------ */

  function ApiError(code, message, status, details) {
    this.name = "ApiError";
    this.code = code;
    this.message = message || code;
    this.status = status || 500;
    this.details = details === undefined ? null : details;
  }
  ApiError.prototype = Object.create(Error.prototype);
  ApiError.prototype.constructor = ApiError;

  /* --------------------------- IndexedDB --------------------------- */

  var dbPromise = null;

  function openDatabase() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise(function (resolve, reject) {
      if (!window.indexedDB) {
        reject(new ApiError("DATABASE_ERROR", "当前 WebView 不支持本地数据库。", 500));
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
        reject(new ApiError("DATABASE_ERROR", "本地数据库打开失败。", 500));
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
          reject(new ApiError("DATABASE_ERROR", "本地数据库读写失败。", 500));
        };
        transaction.onabort = function () {
          reject(new ApiError("DATABASE_ERROR", "本地数据库事务已中止。", 500));
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

  /* ------------------------------ 设置 ------------------------------ */

  function loadSettings() {
    var settings = Object.assign({}, DEFAULT_SETTINGS);
    try {
      var raw = localStorage.getItem(SETTINGS_KEY);
      if (raw) {
        var parsed = JSON.parse(raw);
        Object.keys(DEFAULT_SETTINGS).forEach(function (key) {
          if (parsed[key] !== undefined && parsed[key] !== null) settings[key] = parsed[key];
        });
      }
    } catch (err) {
      /* 配置损坏时使用默认值 */
    }
    return settings;
  }

  function persistSettings(settings) {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
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
        reject(new ApiError("AI_PROVIDER_ERROR", "原生 AI 通道不可用。", 502, { reason: "bridge_unavailable" }));
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
          info.message || "AI 服务调用失败。",
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
        reject(new ApiError("AI_PROVIDER_ERROR", "无法调用原生 AI 通道。", 502, { reason: "bridge_error" }));
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
          throw new ApiError("AI_PROVIDER_ERROR", "AI 服务返回 HTTP " + response.status, 502, {
            reason: classifyStatus(response.status),
            status_code: response.status,
            body: text.slice(0, 500),
          });
        }
        return text;
      });
    }).catch(function (err) {
      if (err && err.name === "AbortError") {
        throw new ApiError("AI_PROVIDER_ERROR", "AI 请求超时。", 502, { reason: "timeout" });
      }
      if (err instanceof ApiError) throw err;
      throw new ApiError("AI_PROVIDER_ERROR", "无法连接 AI 服务。", 502, { reason: "network" });
    }).finally(function () {
      window.clearTimeout(timer);
    });
  }

  function requestCompletion(settings, imageDataUrl) {
    if (window.AndroidHost && typeof window.AndroidHost.chat === "function") {
      return nativeChat(settings, imageDataUrl);
    }
    return webChat(settings, imageDataUrl);
  }

  function extractJson(text) {
    var body = String(text || "").trim();
    if (!body) throw new ApiError("INVALID_AI_RESPONSE", "AI 返回了空内容。", 502, { reason: "not_json" });
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
      throw new ApiError("INVALID_AI_RESPONSE", "AI 返回的内容不是 JSON。", 502, { reason: "not_json" });
    }
  }

  function parseCompletion(raw) {
    var payload = extractJson(raw);
    var choice = payload && payload.choices && payload.choices[0];
    if (!choice) throw new ApiError("INVALID_AI_RESPONSE", "AI 没有返回候选结果。", 502, { reason: "not_json" });
    if (choice.finish_reason === "length") {
      throw new ApiError("INVALID_AI_RESPONSE", "AI 输出被 max_tokens 截断。", 502, { reason: "truncated" });
    }
    if (choice.finish_reason === "content_filter") {
      throw new ApiError("INVALID_AI_RESPONSE", "AI 输出被内容过滤拦截。", 502, { reason: "content_filtered" });
    }
    var content = choice.message && choice.message.content;
    if (typeof content !== "string" || !content.trim()) {
      throw new ApiError("INVALID_AI_RESPONSE", "AI 返回了空内容。", 502, { reason: "not_json" });
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

  /* --------------------------- 图片处理 --------------------------- */

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
        reject(new ApiError("INVALID_IMAGE", "读取图片失败。", 400));
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
        reject(new ApiError("INVALID_IMAGE", "这张图片无法解码。", 400));
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
      return Promise.reject(new ApiError("UNSUPPORTED_MEDIA_TYPE", "只支持 JPG / PNG / WebP。", 415));
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      return Promise.reject(new ApiError("IMAGE_TOO_LARGE", "图片超过 8 MB，请压缩后再上传。", 413));
    }
    var settings = loadSettings();
    if (!settings.apiKey) {
      hdtToast("还没有填写 API Key，请到右上角 ⋮ → API 设置里配置。", "warning", 7000);
      window.setTimeout(function () { openSettingsModal("missing"); }, 400);
      return Promise.reject(new ApiError("AI_PROVIDER_ERROR", "API Key 未配置。", 502, { reason: "missing_api_key" }));
    }
    if (!settings.endpoint) {
      return Promise.reject(new ApiError("AI_PROVIDER_ERROR", "API 地址为空。", 502, { reason: "missing_endpoint" }));
    }
    return compressImage(file, 1024, 0.85).then(function (dataUrl) {
      return callVision(settings, dataUrl);
    }).then(function (raw) {
      var analysis = validateAnalysis(raw);
      analysis.image_path = null;
      return analysis;
    });
  }

  /* --------------------------- 本地 API 路由 --------------------------- */

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
    var error = err instanceof ApiError ? err : new ApiError("INTERNAL_ERROR", "本地服务出错。", 500);
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
      throw new ApiError("FOOD_NOT_FOUND", "食物库里没有可匹配的条目。", 422, { warnings: nutrition.warnings });
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
      throw new ApiError("INVALID_REQUEST", "date_from 与 date_to 必须同时提供。", 400);
    }
    var limit = Number(params.get("limit") || 50);
    var offset = Number(params.get("offset") || 0);
    if (!Number.isInteger(limit) || limit < 1 || limit > 200) {
      throw new ApiError("INVALID_REQUEST", "limit 不合法。", 400);
    }
    if (!Number.isInteger(offset) || offset < 0) {
      throw new ApiError("INVALID_REQUEST", "offset 不合法。", 400);
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
      if (!found) throw new ApiError("MEAL_NOT_FOUND", "这条记录不存在。", 404, { meal_id: id });
      return mealDetail(found);
    });
  }

  function removeMeal(id) {
    return deleteMealRecord(Number(id)).then(function (deleted) {
      if (!deleted) throw new ApiError("MEAL_NOT_FOUND", "这条记录不存在。", 404, { meal_id: Number(id) });
      return { meal_id: Number(id), deleted: true };
    });
  }

  function dailySummary(date) {
    var day = date || todayLocalIso();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) {
      throw new ApiError("INVALID_REQUEST", "date 格式必须是 YYYY-MM-DD。", 400);
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
          throw new ApiError("INVALID_REQUEST", "缺少 image 字段。", 400);
        }
        if (MEAL_TYPES.indexOf(mealType) < 0) {
          throw new ApiError("INVALID_REQUEST", "meal_type 不合法。", 400, { allowed: MEAL_TYPES.slice().sort() });
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
        work = Promise.reject(new ApiError("INVALID_REQUEST", "本地接口不存在：" + method + " " + clean, 404));
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
    var close = el("button", { type: "button", class: "toast-close", "aria-label": "关闭提示", text: "×" });
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
      el("button", { type: "button", class: "hdt-modal-close", "aria-label": "关闭", text: "×" }),
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
      el("option", { value: "qwen", text: "通义千问 Qwen-VL（阿里云百炼）" }),
      el("option", { value: "openai", text: "OpenAI（gpt-4o-mini）" }),
      el("option", { value: "custom", text: "自定义 / 自建服务" }),
    ]);
    presetSelect.value = settings.preset || "custom";
    var endpointInput = el("input", { id: "hdt-endpoint", type: "url", inputmode: "url", placeholder: "https://dashscope.aliyuncs.com/compatible-mode/v1", value: settings.endpoint });
    var modelInput = el("input", { id: "hdt-model", type: "text", placeholder: "qwen-vl-max", value: settings.model });
    var keyInput = el("input", { id: "hdt-key", type: "password", autocomplete: "off", placeholder: "sk-...", value: settings.apiKey });
    var reveal = el("button", { type: "button", class: "hdt-reveal", text: "显示" });
    reveal.addEventListener("click", function () {
      var showing = keyInput.type === "text";
      keyInput.type = showing ? "password" : "text";
      reveal.textContent = showing ? "显示" : "隐藏";
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
      reason === "missing" ? el("p", { class: "hdt-note is-warning", text: "还没有配置 API Key。填写后即可识别餐食照片；Key 只保存在本机。" }) : null,
      field("服务预设", presetSelect),
      field("API 地址（Base URL）", endpointInput),
      field("模型名称", modelInput),
      field("API Key", el("div", { class: "hdt-input-wrap" }, [keyInput, reveal])),
      field("请求超时（秒）", timeoutInput),
      el("p", { class: "hdt-note", text: "支持任何 OpenAI 兼容的 /chat/completions 视觉接口。请求由原生网络层直接发出，不经过本应用的服务器；Key 保存在本机 localStorage，可在关于页随时修改。" }),
      status,
    ]);

    function collect() {
      var endpoint = endpointInput.value.trim();
      if (!/^https?:\/\//i.test(endpoint)) {
        throw new Error("API 地址需要以 http:// 或 https:// 开头");
      }
      var timeout = Number(timeoutInput.value) || 60;
      timeout = Math.max(10, Math.min(180, timeout));
      return {
        preset: presetSelect.value,
        endpoint: endpoint,
        model: modelInput.value.trim(),
        apiKey: keyInput.value.trim(),
        timeoutMs: Math.round(timeout * 1000),
      };
    }

    var testButton = button("测试连接", "ghost", function () {
      var next;
      try { next = collect(); } catch (err) { status.textContent = err.message; status.className = "hdt-status is-error"; return; }
      if (!next.apiKey) {
        status.textContent = "请先填写 API Key。";
        status.className = "hdt-status is-error";
        return;
      }
      status.textContent = "正在连接…";
      status.className = "hdt-status";
      testConnection(next).then(function () {
        status.textContent = "连接成功，模型可用。";
        status.className = "hdt-status is-ok";
      }).catch(function (err) {
        status.textContent = "连接失败：" + (err.message || "未知错误");
        status.className = "hdt-status is-error";
      });
    });

    var saveButton = button("保存设置", "primary", function () {
      var next;
      try { next = collect(); } catch (err) { status.textContent = err.message; status.className = "hdt-status is-error"; return; }
      try {
        persistSettings(next);
        hdtToast("API 设置已保存", "success");
        closeModal();
      } catch (err) {
        status.textContent = "保存失败：" + err.message;
        status.className = "hdt-status is-error";
      }
    });

    content.appendChild(el("div", { class: "hdt-actions" }, [testButton, saveButton]));
    openModal({ title: "API 设置", content: content });
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
            reject(new Error(info.message || "HTTP 错误"));
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
          reject(new Error("无法调用原生网络层"));
        }
      });
    }
    return webChat(settings, null).then(function () { return true; });
  }

  function openSplashModal() {
    var current = null;
    try { current = localStorage.getItem(SPLASH_KEY); } catch (err) { current = null; }
    var preview = el("div", { class: "hdt-splash-preview", id: "hdt-splash-preview" }, [
      el("span", { text: current ? "当前自定义开屏" : "默认开屏" }),
    ]);
    if (current) preview.style.backgroundImage = 'url("' + current.replace(/"/g, "%22") + '")';

    var fileInput = el("input", { type: "file", class: "hdt-file-input", id: "hdt-splash-file", accept: "image/*,.svg,image/svg+xml" });
    var note = el("p", { class: "hdt-muted", text: "支持 JPG、PNG、WebP、GIF、SVG 等常见格式，建议使用竖版图片（如 1080×1920）。图片只保存在本机，不会上传。" });

    function setPreview(dataUrl) {
      if (dataUrl) {
        preview.style.backgroundImage = 'url("' + dataUrl.replace(/"/g, "%22") + '")';
        preview.querySelector("span").textContent = "当前自定义开屏";
      } else {
        preview.style.backgroundImage = "";
        preview.querySelector("span").textContent = "默认开屏";
      }
    }

    var pickButton = button("选择图片", "primary", function () { fileInput.click(); });
    var resetButton = button("恢复默认", "ghost", function () {
      try { localStorage.removeItem(SPLASH_KEY); } catch (err) { /* 忽略 */ }
      setPreview(null);
      hdtToast("已恢复默认开屏", "success");
    });
    var doneButton = button("完成", "ghost", function () { closeModal(); });

    fileInput.addEventListener("change", function () {
      var file = fileInput.files && fileInput.files[0];
      fileInput.value = "";
      if (!file) return;
      var mime = guessMime(file);
      if (mime.indexOf("image/") !== 0) {
        hdtToast("请选择图片文件。", "error");
        return;
      }
      if (file.size > 8 * 1024 * 1024) {
        hdtToast("图片超过 8 MB，请换一张。", "error");
        return;
      }
      var work = (mime === "image/svg+xml" || mime === "image/gif")
        ? readAsDataUrl(file)
        : compressImage(file, 1440, 0.85);
      work.then(function (dataUrl) {
        try {
          localStorage.setItem(SPLASH_KEY, dataUrl);
        } catch (err) {
          hdtToast("图片太大，无法保存，请换一张更小的图片。", "error", 6000);
          return;
        }
        setPreview(dataUrl);
        hdtToast("开屏图片已保存，下次启动生效。", "success");
      }).catch(function () {
        hdtToast("这张图片无法读取，请换一张。", "error");
      });
    });

    openModal({
      title: "开屏画面",
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
    { name: "leonardo-weasley", role: "GitHub 贡献者" },
    { name: "jyj0808", role: "GitHub 贡献者" },
    { name: "baihe-love", role: "GitHub 贡献者" },
    { name: "雷曼文", role: "GitHub 贡献者" },
    { name: "pan-yi-fan", role: "GitHub 贡献者" },
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
    { name: "Chart.js 4.4.1", license: "MIT", note: "仪表盘营养图表，已随 APK 打包，离线可用。" },
    { name: "USDA FoodData Central", license: "公有领域", note: "29 条食物营养数据，其中 24 条来自 USDA；逐条保留 fdc_id。" },
    { name: "Android / WebView", license: "Apache-2.0", note: "应用运行环境与页面渲染引擎。" },
    { name: "OpenAI 兼容视觉接口", license: "服务方条款", note: "仅在你主动识别时发送照片与提示词；本应用不转售、不缓存模型输出。" },
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
        el("strong", { text: "健康饮食记录" }),
        el("small", { text: "v" + APP_VERSION + " · " + APP_BUILD + " · 本地离线运行，无需 Python" }),
      ]),
    ]);

    var creditList = el("div", { class: "hdt-credit-list" });
    CREATORS.forEach(function (person) {
      creditList.appendChild(el("div", { class: "hdt-credit" }, [
        el("span", { text: person.name }),
        el("code", { text: person.role }),
      ]));
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
      el("h3", { text: "制作者名单" }),
      el("p", { class: "hdt-muted", text: "名单来自仓库 git 提交记录（GitHub Contributors）。团队按 README §9 分为后端集成、AI 集成、营养引擎、前端、数据库与测试五个角色。" }),
      creditList,
      el("h3", { text: "开源许可" }),
      el("p", {}, ["本项目以 ", el("strong", { text: "MIT License" }), " 发布。"]),
      licenseBox,
      el("h3", { text: "第三方组件与数据来源" }),
      thirdParty,
      el("h3", { text: "数据与隐私" }),
      el("ul", {}, [
        el("li", { text: "餐食记录保存在本机 IndexedDB，卸载应用后清除，不会同步到任何服务器。" }),
        el("li", { text: "API Key、API 地址与开屏图片保存在本机 localStorage，仅用于你配置的接口。" }),
        el("li", { text: "只有点击“分析照片”时，才会把压缩后的照片与提示词发送到你配置的 AI 接口。" }),
        el("li", { text: "营养数值为估算值，不能替代医疗或专业营养建议。" }),
      ]),
      el("h3", { text: "项目仓库" }),
      el("p", {}, [repoLink]),
      el("div", { class: "hdt-actions" }, [
        button("API 设置", "ghost", function () { closeModal(); openSettingsModal(); }),
        button("开屏画面", "ghost", function () { closeModal(); openSplashModal(); }),
        button("关闭", "primary", closeModal),
      ]),
    ]);

    openModal({ title: "关于", content: content });
  }

  function openMenuSheet() {
    closeModal();
    var backdrop = el("div", { class: "hdt-backdrop" });
    var sheet = el("div", { class: "hdt-sheet", role: "dialog", "aria-modal": "true", "aria-label": "应用菜单" });
    sheet.appendChild(el("div", { class: "hdt-sheet-grip" }));
    sheet.appendChild(el("p", { class: "hdt-sheet-title", text: "健康饮食记录 · v" + APP_VERSION }));

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
      "记录一餐", "上传或拍摄餐食照片",
      function () { closeModal(); window.location.href = "upload.html"; }
    ));
    sheet.appendChild(item(
      ["M4 7h16", "M4 12h16", "M4 17h10"],
      "API 设置", "切换 API 地址、模型与 Key",
      function () { closeModal(); openSettingsModal(); }
    ));
    sheet.appendChild(item(
      ["M4 5h16v14H4z", "M4 15l4-4 3 3 3-3 6 6", "M9 9.5h.01"],
      "开屏画面", "自定义启动图片与跳过按钮",
      function () { closeModal(); openSplashModal(); }
    ));
    sheet.appendChild(item(
      ["M12 8h.01", "M11 12h1v4h1", "M12 21a9 9 0 100-18 9 9 0 000 18z"],
      "关于", "制作者、许可与第三方声明",
      function () { closeModal(); openAboutModal(); }
    ));
    sheet.appendChild(item(
      ["M14 4h6v6", "M20 4l-8 8", "M19 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1h5"],
      "项目仓库", "在浏览器中打开 GitHub",
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
    var btn = el("button", { type: "button", id: "hdt-menu-btn", class: "hdt-menu-btn", "aria-label": "应用菜单", title: "更多" });
    btn.appendChild(svgIcon(["M12 6h.01", "M12 12h.01", "M12 18h.01"], 24));
    // 三个点用实心圆更清晰
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
      "拍照",
    ]);
    var gallery = el("button", { type: "button", class: "btn btn-ghost", id: "hdt-gallery-btn" }, [
      svgIcon(["M4 5h16v14H4z", "M4 15l4-4 3 3 3-3 6 6", "M9 9.5h.01"], 17),
      "从相册选择",
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
      text: "当前系统 WebView 版本过低，无法运行本地营养计算。请更新 Android System WebView 后重试。",
    });
    document.body.appendChild(warn);
  }

  function init() {
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
  };
})();
