/* =========================================================================
 * usda.js —— 未匹配食物的 USDA FoodData Central 检索与补录
 *
 * 只在“确认餐食”页生效：
 *   1. 为标为“未匹配”的食物行加一个「USDA 匹配」按钮；
 *   2. 弹窗里可以手动搜索，也可以自动取第一条结果；
 *   3. 选中的食物写入本地自定义食物库（hdt.customFoods），并立即参与营养计算；
 *   4. 保存时随餐食一起写入 IndexedDB，下次可直接匹配。
 * ========================================================================= */
(function () {
  "use strict";

  var DEFAULT_KEY = "DEMO_KEY";
  var PAGE_SIZE = 10;
  var REQUEST_TIMEOUT = 20000;

  var pending = {};
  var seq = 0;
  var cache = {};
  var autoRunning = false;
  var observer = null;
  var enhanceScheduled = false;

  function settingsKey() {
    try {
      var settings = window.HDT && window.HDT.getSettings ? window.HDT.getSettings() : {};
      var key = settings && settings.usdaApiKey ? String(settings.usdaApiKey).trim() : "";
      return key || DEFAULT_KEY;
    } catch (err) {
      return DEFAULT_KEY;
    }
  }

  function parsePayload(payload) {
    if (payload && typeof payload === "object") return payload;
    if (typeof payload !== "string" || !payload.trim()) return null;
    try {
      return JSON.parse(payload);
    } catch (err) {
      return null;
    }
  }

  function requestNative(query, size) {
    return new Promise(function (resolve, reject) {
      var id = "usda-" + Date.now() + "-" + (++seq);
      var timer = window.setTimeout(function () {
        delete pending[id];
        reject(new Error("USDA 检索超时，请检查网络后重试。"));
      }, REQUEST_TIMEOUT);
      pending[id] = {
        resolve: function (value) {
          window.clearTimeout(timer);
          resolve(value);
        },
        reject: function (error) {
          window.clearTimeout(timer);
          reject(error);
        },
      };
      try {
        window.AndroidHost.usdaSearch(id, query, settingsKey(), String(size));
      } catch (err) {
        window.clearTimeout(timer);
        delete pending[id];
        reject(new Error("无法调用原生 USDA 接口。"));
      }
    });
  }

  window.__hdtUsdaResult = function (id, ok, payload) {
    var handler = pending[id];
    if (!handler) return;
    delete pending[id];
    var data = parsePayload(payload);
    if (!ok) {
      var message = data && data.message ? data.message : "USDA 检索失败。";
      handler.reject(new Error(message));
      return;
    }
    handler.resolve(data);
  };

  function requestWeb(query, size) {
    var url = "https://api.nal.usda.gov/fdc/v1/foods/search?api_key="
      + encodeURIComponent(settingsKey())
      + "&query=" + encodeURIComponent(query)
      + "&pageSize=" + size
      + "&dataType=" + encodeURIComponent("Foundation,SR Legacy,Survey (FNDDS)");
    return fetch(url, { headers: { Accept: "application/json" } }).then(function (response) {
      if (!response.ok) {
        throw new Error("USDA 检索失败（HTTP " + response.status + "）。");
      }
      return response.json();
    });
  }

  function request(query, size) {
    if (window.AndroidHost && typeof window.AndroidHost.usdaSearch === "function") {
      return requestNative(query, size);
    }
    return requestWeb(query, size);
  }

  /* ----------------------------- 营养解析 ----------------------------- */

  function numberOf(value) {
    var num = Number(value);
    return Number.isFinite(num) ? num : null;
  }

  function nutrientValue(food, ids, nameHints) {
    var list = Array.isArray(food.foodNutrients) ? food.foodNutrients : [];
    var i;
    var item;
    for (i = 0; i < list.length; i += 1) {
      item = list[i] || {};
      var id = item.nutrientId;
      if (id === undefined && item.nutrient) id = item.nutrient.id;
      if (ids.indexOf(Number(id)) !== -1) {
        var value = numberOf(item.value !== undefined ? item.value : item.amount);
        if (value !== null) return value;
      }
    }
    if (nameHints && nameHints.length) {
      for (i = 0; i < list.length; i += 1) {
        item = list[i] || {};
        var name = String(item.nutrientName || (item.nutrient && item.nutrient.name) || "").toLowerCase();
        for (var h = 0; h < nameHints.length; h += 1) {
          if (name.indexOf(nameHints[h]) !== -1) {
            var named = numberOf(item.value !== undefined ? item.value : item.amount);
            if (named !== null) return named;
          }
        }
      }
    }
    return null;
  }

  function round(value, digits) {
    var factor = Math.pow(10, digits);
    return Math.round(value * factor) / factor;
  }

  function toFood(raw, displayName) {
    if (!raw) return null;
    var fdcId = raw.fdcId || raw.fdc_id;
    if (!fdcId) return null;

    var kcal = nutrientValue(raw, [1008, 2047, 2048], ["energy"]);
    if (kcal === null) {
      var kj = nutrientValue(raw, [1062], ["energy (kj)", "energy kj"]);
      if (kj !== null) kcal = kj / 4.184;
    }
    var protein = nutrientValue(raw, [1003], ["protein"]);
    var carbs = nutrientValue(raw, [1005], ["carbohydrate"]);
    var fat = nutrientValue(raw, [1004], ["total lipid", "fat"]);
    if (kcal === null || kcal <= 0) return null;
    if ((protein || 0) + (carbs || 0) + (fat || 0) <= 0) return null;

    var description = String(raw.description || displayName || "").trim();
    var label = String(displayName || description || "").trim() || description;
    return {
      food_name: "usda_" + fdcId,
      display_name: label,
      calories_per_100g: round(kcal, 1),
      protein_per_100g: round(protein || 0, 2),
      carbs_per_100g: round(carbs || 0, 2),
      fat_per_100g: round(fat || 0, 2),
      source: "USDA",
      aliases: [],
      is_verified: 0,
      usda: {
        fdc_id: fdcId,
        description: description,
        data_type: String(raw.dataType || raw.data_type || ""),
        fetched_at: new Date().toISOString().slice(0, 10),
      },
    };
  }

  function normalizeResults(data, displayName) {
    var list = data && Array.isArray(data.foods) ? data.foods : [];
    var results = [];
    list.forEach(function (raw) {
      var food = toFood(raw, displayName);
      if (food) results.push(food);
    });
    return results;
  }

  function searchFoods(query, displayName) {
    var trimmed = String(query || "").trim();
    if (!trimmed) return Promise.resolve([]);
    var cacheKey = trimmed.toLowerCase() + "|" + settingsKey();
    if (cache[cacheKey]) return Promise.resolve(cache[cacheKey]);
    return request(trimmed, PAGE_SIZE).then(function (data) {
      var results = normalizeResults(data, displayName);
      cache[cacheKey] = results;
      return results;
    });
  }

  /* ------------------------------ 页面接入 ------------------------------ */

  function api() {
    return window.HDT || null;
  }

  function isUnknown(row) {
    return row && row.classList.contains("is-unknown");
  }

  function rowQuery(row) {
    var input = row.querySelector(".food-name");
    return input && input.value ? input.value.trim() : "";
  }

  function applyFood(row, food) {
    var hdt = api();
    if (!hdt) return;
    if (hdt.registerCustomFood) hdt.registerCustomFood(food);

    var select = row.querySelector(".food-standard");
    if (!select) return;
    var exists = false;
    for (var i = 0; i < select.options.length; i += 1) {
      if (select.options[i].value === food.food_name) {
        exists = true;
        break;
      }
    }
    if (!exists) {
      var option = document.createElement("option");
      option.value = food.food_name;
      option.textContent = food.display_name;
      select.appendChild(option);
    }
    select.value = food.food_name;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function openPicker(row) {
    var hdt = api();
    if (!hdt || !hdt.openModal) return;
    var el = hdt.el;
    var button = hdt.button;

    var initial = rowQuery(row);
    var input = el("input", {
      type: "text",
      class: "input",
      value: initial,
      placeholder: "例如 chicken breast / 白米饭",
      "aria-label": "USDA 食物关键词",
    });
    var status = el("p", { class: "hdt-usda-status", text: "" });
    var list = el("div", { class: "hdt-usda-list" });
    var modal = null;
    var current = [];

    function setStatus(text, isError) {
      status.textContent = text || "";
      status.className = "hdt-usda-status" + (isError ? " is-error" : "");
    }

    function renderResults(results) {
      list.innerHTML = "";
      current = results;
      if (!results.length) {
        list.appendChild(el("p", {
          class: "hdt-usda-empty",
          text: "没有找到可用结果。可以换英文关键词（如 steamed rice），或换一个 USDA API Key。",
        }));
        return;
      }
      results.forEach(function (food) {
        var meta = (food.usda.data_type || "USDA")
          + " · " + food.calories_per_100g + " kcal/100g"
          + " · 蛋白 " + food.protein_per_100g + "g"
          + " · 碳水 " + food.carbs_per_100g + "g"
          + " · 脂肪 " + food.fat_per_100g + "g";
        var item = el("button", { type: "button", class: "hdt-usda-item" }, [
          el("strong", { text: food.usda.description || food.display_name }),
          el("small", { text: meta }),
        ]);
        item.addEventListener("click", function () {
          applyFood(row, food);
          if (modal && hdt.closeModal) hdt.closeModal();
          if (hdt.toast) hdt.toast("已匹配 USDA：" + (food.usda.description || food.display_name), "success");
        });
        list.appendChild(item);
      });
    }

    function runSearch() {
      var query = input.value.trim();
      if (!query) {
        setStatus("请先输入食物名称。", true);
        return Promise.resolve([]);
      }
      setStatus("正在检索 USDA…");
      list.innerHTML = "";
      return searchFoods(query, rowQuery(row) || query).then(function (results) {
        renderResults(results);
        setStatus(results.length ? "共 " + results.length + " 条结果，点击即可使用。" : "没有找到可用结果。", !results.length);
        return results;
      }).catch(function (error) {
        setStatus(error.message || "USDA 检索失败。", true);
        return [];
      });
    }

    var searchButton = button("搜索", "primary", runSearch);
    var autoButton = button("自动选第一条", "ghost", function () {
      var query = input.value.trim();
      if (!query) {
        setStatus("请先输入食物名称。", true);
        return;
      }
      setStatus("正在自动匹配…");
      searchFoods(query, rowQuery(row) || query).then(function (results) {
        renderResults(results);
        if (!results.length) {
          setStatus("没有找到可用结果，请换关键词或手动选择。", true);
          return;
        }
        applyFood(row, results[0]);
        if (modal && hdt.closeModal) hdt.closeModal();
        if (hdt.toast) hdt.toast("已自动匹配 USDA：" + (results[0].usda.description || results[0].display_name), "success");
      }).catch(function (error) {
        setStatus(error.message || "USDA 检索失败。", true);
      });
    });

    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        runSearch();
      }
    });

    var content = el("div", { class: "hdt-usda-modal" }, [
      el("div", { class: "hdt-usda-search" }, [input, searchButton]),
      el("div", { class: "hdt-usda-actions" }, [
        autoButton,
        el("span", {
          class: "hdt-note",
          text: "数据来自 USDA FoodData Central，按每 100g 记录。",
        }),
      ]),
      status,
      list,
    ]);

    modal = hdt.openModal({ title: "从 USDA 选择食物", content: content });
    if (initial) {
      runSearch();
    } else {
      window.setTimeout(function () { input.focus(); }, 60);
    }
  }

  function enhanceRow(row) {
    if (!isUnknown(row)) {
      var stale = row.querySelector(".hdt-usda-btn");
      if (stale && stale.parentNode) stale.parentNode.removeChild(stale);
      return;
    }
    if (row.querySelector(".hdt-usda-btn")) return;
    var head = row.querySelector(".food-row-head");
    if (!head) return;
    var hdt = api();
    if (!hdt || !hdt.el) return;
    var trigger = hdt.el("button", { type: "button", class: "hdt-usda-btn", text: "USDA 匹配" });
    trigger.addEventListener("click", function () { openPicker(row); });
    var remove = head.querySelector(".row-remove");
    head.insertBefore(trigger, remove || null);
  }

  function enhanceAll() {
    var host = document.getElementById("food-rows");
    if (!host) return;
    var rows = host.querySelectorAll(".food-row");
    for (var i = 0; i < rows.length; i += 1) enhanceRow(rows[i]);
    mountAutoButton();
  }

  function scheduleEnhance() {
    if (enhanceScheduled) return;
    enhanceScheduled = true;
    window.requestAnimationFrame(function () {
      enhanceScheduled = false;
      enhanceAll();
    });
  }

  function unknownRows() {
    var host = document.getElementById("food-rows");
    if (!host) return [];
    return Array.prototype.filter.call(host.querySelectorAll(".food-row"), isUnknown);
  }

  function mountAutoButton() {
    var note = document.getElementById("unmatched-note");
    if (!note || note.querySelector(".hdt-usda-auto")) return;
    var hdt = api();
    if (!hdt || !hdt.el) return;
    var auto = hdt.el("button", { type: "button", class: "hdt-usda-btn hdt-usda-auto", text: "自动匹配全部" });
    auto.addEventListener("click", function () {
      if (autoRunning) return;
      var rows = unknownRows();
      if (!rows.length) return;
      autoRunning = true;
      auto.disabled = true;
      auto.textContent = "匹配中…";
      var index = 0;
      var matched = 0;
      function next() {
        if (index >= rows.length) {
          autoRunning = false;
          auto.disabled = false;
          auto.textContent = "自动匹配全部";
          if (hdt.toast) {
            hdt.toast(matched
              ? "已自动匹配 " + matched + " 项，剩余未匹配项可手动选择。"
              : "没有自动匹配到结果，请手动选择。", matched ? "success" : "warning");
          }
          return;
        }
        var row = rows[index];
        index += 1;
        if (!isUnknown(row)) { next(); return; }
        var query = rowQuery(row);
        if (!query) { next(); return; }
        searchFoods(query, query).then(function (results) {
          if (results.length) {
            applyFood(row, results[0]);
            matched += 1;
          }
          window.setTimeout(next, 180);
        }).catch(function () {
          window.setTimeout(next, 180);
        });
      }
      next();
    });
    note.appendChild(auto);
  }

  function init() {
    if (!document.getElementById("food-rows")) return;
    enhanceAll();
    var host = document.getElementById("food-rows");
    if (host && window.MutationObserver && !observer) {
      observer = new MutationObserver(scheduleEnhance);
      observer.observe(host, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
