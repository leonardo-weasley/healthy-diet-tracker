/* =========================================================================
 * 由 android/web/js/app.js 抽取（2026-11-19 未提交改动），仅作阅读/重写参考。
 * 不要直接放进构建：真实文件仍是 android/web/js/app.js。
 * 行号对应抽取时的源文件。
 * ========================================================================= */

/* --- 源文件 app.js:19 --- */
  var CUSTOM_FOODS_KEY = "hdt.customFoods";

/* --- 源文件 app.js:42（DEFAULT_SETTINGS 增加项） --- */
    usdaApiKey: "DEMO_KEY",

/* --- 源文件 app.js:126-181（自定义食物库：读取/合并/注册） --- */
  /* ------------------------- 自定义 USDA 食物 ------------------------- */

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
      hdtToast("自定义食物保存失败，本次仍可使用。", "warning");
    }
    mergeCustomFoods(list);
    return food;
  }

  // Load before any page script calls the local API.
  mergeCustomFoods(readCustomFoods());

/* --- 源文件 app.js:833-837（设置弹窗新增 USDA Key 字段） --- */
      field("USDA API Key（可选，用于未匹配食物检索）", el("input", {
        id: "hdt-usda-key", type: "password", autocomplete: "off",
        placeholder: "DEMO_KEY", value: settings.usdaApiKey || "DEMO_KEY",
      })),
      el("p", { class: "hdt-note", text: "支持任何 OpenAI 兼容的 /chat/completions 视觉接口。请求由原生网络层直接发出，不经过本应用的服务器；Key 保存在本机 localStorage，可在关于页随时修改。USDA API Key 仅用于未匹配食物的检索，留空则使用 DEMO_KEY（有速率限制）。" }),

/* --- 源文件 app.js:854-856（collect() 保存 usdaApiKey） --- */
        usdaApiKey: (document.getElementById("hdt-usda-key") || {}).value
          ? document.getElementById("hdt-usda-key").value.trim() || "DEMO_KEY"
          : (settings.usdaApiKey || "DEMO_KEY"),

/* --- 源文件 app.js:1241-1243（init：延迟加载的 food-options.js 之后重新合并） --- */
    // food-options.js is deferred and may load after this file; re-apply saved foods
    // so the standard-food selects include USDA entries registered in earlier sessions.
    mergeCustomFoods(readCustomFoods());

/* --- 源文件 app.js:1263-1269（window.HDT 新增导出） --- */
    getCustomFoods: getCustomFoods,
    registerCustomFood: registerCustomFood,
    toast: hdtToast,
    openModal: openModal,
    closeModal: closeModal,
    el: el,
    button: button,
