"use strict";

/* =========================================================================
 * result.js —— 识别结果确认页
 * 数据来源：sessionStorage.analysisResult（由 upload.js 写入）
 * 保存目标：POST /api/v1/meals（契约 B）
 *
 * 这里只收集用户修正后的 food_name / display_name / weight_g；
 * 任何营养数值都不在前端计算，也不允许被前端提交。
 * ========================================================================= */

const RESULT_DRAFT_KEY = "analysisResult";
const MAX_MEAL_ITEMS = 20;

const resultState = {
  foods: [],
  imagePath: null,
  mealType: "lunch",
  saving: false,
  draftStatus: null,
  manual: false,
};

document.addEventListener("DOMContentLoaded", initResultPage);

function initResultPage() {
  const draft = readJson(RESULT_DRAFT_KEY);

  if (!draft || typeof draft !== "object") {
    window.location.href = "/upload";
    return;
  }

  resultState.imagePath =
    typeof draft.image_path === "string" && draft.image_path ? draft.image_path : null;
  resultState.mealType = MEAL_TYPES.includes(draft.meal_type) ? draft.meal_type : "lunch";
  resultState.draftStatus = typeof draft.status === "string" ? draft.status : null;
  resultState.manual = draft.manual === true;
  resultState.foods = (Array.isArray(draft.foods) ? draft.foods : []).map(normalizeFood);

  if (resultState.manual) {
    const lead = document.getElementById("result-lead");
    if (lead) {
      lead.textContent = "没有照片也没关系：选择标准食物、填写重量，保存后服务器会计算营养。";
    }
  }

  renderMealTypeBadge();
  renderDraftWarnings(draft.warnings);
  renderFoodRows();

  const addButton = document.getElementById("add-food-btn");
  const emptyAddButton = document.getElementById("empty-add-btn");
  const saveButton = document.getElementById("save-btn");

  if (addButton) addButton.addEventListener("click", addFoodRow);
  if (emptyAddButton) emptyAddButton.addEventListener("click", addFoodRow);
  if (saveButton) saveButton.addEventListener("click", saveMeal);

  if (!Array.isArray(window.FOOD_OPTIONS) || window.FOOD_OPTIONS.length === 0) {
    showToast("标准食物清单加载失败，请刷新页面重试。", "error", 8000);
  }

  syncSaveButtonState();
}

function normalizeFood(rawFood) {
  const rawName = rawFood && rawFood.food_name;
  const foodName =
    typeof rawName === "string" && rawName.trim() ? rawName.trim().slice(0, 60) : null;

  const rawDisplay = rawFood && rawFood.display_name;
  const displayName = String(rawDisplay || foodName || "").slice(0, 100);

  let weight = null;
  if (rawFood && rawFood.estimated_weight_g !== null && rawFood.estimated_weight_g !== undefined) {
    const parsed = Number(rawFood.estimated_weight_g);
    if (Number.isFinite(parsed)) weight = parsed;
  }

  let confidence = null;
  if (rawFood && rawFood.confidence !== null && rawFood.confidence !== undefined) {
    const parsed = Number(rawFood.confidence);
    if (Number.isFinite(parsed)) confidence = Math.min(Math.max(parsed, 0), 1);
  }

  return {
    food_name: foodName,
    display_name: displayName,
    weight_g: weight,
    confidence,
    notes: (rawFood && rawFood.notes) || null,
    nameDirty: false,
  };
}

function renderMealTypeBadge() {
  const badge = document.getElementById("meal-type-badge");
  if (!badge) return;
  badge.textContent = mealTypeLabel(resultState.mealType);
  MEAL_TYPES.forEach((type) => badge.classList.remove(`meal-${type}`));
  badge.classList.add(`meal-${resultState.mealType}`);
}

function renderFoodRows() {
  const host = document.getElementById("food-rows");
  const template = document.getElementById("food-row-template");
  const emptyState = document.getElementById("food-empty");
  const actions = document.getElementById("food-list-actions");
  if (!host || !template) return;

  host.innerHTML = "";

  const hasFoods = resultState.foods.length > 0;
  host.hidden = !hasFoods;
  if (emptyState) emptyState.hidden = hasFoods;
  if (actions) actions.hidden = !hasFoods;

  if (!hasFoods) {
    const emptyTitle = document.getElementById("food-empty-title");
    const emptyText = document.getElementById("food-empty-text");
    const emptyIcon = document.querySelector("#food-empty .empty-icon");
    if (emptyTitle) {
      emptyTitle.textContent = resultState.manual ? "手动添加这一餐" : "没有识别到食物";
    }
    if (emptyText) {
      emptyText.textContent = resultState.manual
        ? "从标准食物中选择，填写重量；保存后由服务器计算营养。"
        : "可以换一张更清晰、食物更完整的照片；也可以手动添加食物并选择标准条目。";
    }
    if (emptyIcon) emptyIcon.textContent = resultState.manual ? "🍽️" : "🔍";
    syncSaveButtonState();
    return;
  }

  resultState.foods.forEach((food, index) => {
    const row = template.content.firstElementChild.cloneNode(true);
    row.dataset.index = String(index);

    const indexLabel = row.querySelector(".row-index");
    if (indexLabel) indexLabel.textContent = String(index + 1).padStart(2, "0");

    const nameInput = row.querySelector(".food-name");
    const standardSelect = row.querySelector(".food-standard");
    const weightInput = row.querySelector(".food-weight");
    const confidenceText = row.querySelector(".confidence-text");
    const removeButton = row.querySelector(".row-remove");
    const unknownTag = row.querySelector(".tag-unknown");

    if (nameInput) {
      nameInput.value = food.display_name;
      nameInput.addEventListener("input", () => {
        food.display_name = nameInput.value;
        food.nameDirty = true;
        clearResultError();
        syncSaveButtonState();
      });
    }

    if (standardSelect) {
      buildFoodSelect(standardSelect, food);
      standardSelect.addEventListener("change", () => {
        food.food_name = standardSelect.value || null;

        if (!food.nameDirty && food.food_name && nameInput) {
          const option = findFoodOption(food.food_name);
          const label = option ? option.label : food.food_name;
          food.display_name = label;
          nameInput.value = label;
        }

        clearResultError();
        updateRowVisual(row, food);
        syncSaveButtonState();
      });
    }

    if (weightInput) {
      weightInput.value = food.weight_g === null ? "" : String(food.weight_g);
      weightInput.addEventListener("input", () => {
        const raw = weightInput.value.trim();
        if (raw === "") {
          food.weight_g = null;
        } else {
          const parsed = Number(raw);
          food.weight_g = Number.isFinite(parsed) ? parsed : null;
        }
        clearResultError();
        syncSaveButtonState();
      });
    }

    if (confidenceText) {
      confidenceText.textContent =
        food.confidence === null ? "—" : `${Math.round(food.confidence * 100)}%`;
      confidenceText.classList.add(confidenceClass(food.confidence));
    }

    if (removeButton) {
      removeButton.setAttribute("aria-label", `删除第 ${index + 1} 项食物`);
      removeButton.addEventListener("click", () => removeFoodRow(index));
    }

    if (unknownTag) unknownTag.hidden = Boolean(food.food_name);

    host.appendChild(row);
    updateRowVisual(row, food);
  });
}

function buildFoodSelect(select, food) {
  select.innerHTML = "";

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "未匹配（保存时跳过）";
  select.appendChild(placeholder);

  const options = Array.isArray(window.FOOD_OPTIONS) ? window.FOOD_OPTIONS : [];
  const knownIds = new Set();

  options.forEach((option) => {
    const element = document.createElement("option");
    element.value = option.food_name;
    element.textContent = option.label;
    select.appendChild(element);
    knownIds.add(option.food_name);
  });

  if (food.food_name && !knownIds.has(food.food_name)) {
    const custom = document.createElement("option");
    custom.value = food.food_name;
    custom.textContent = `${food.food_name}（未收录）`;
    select.appendChild(custom);
  }

  select.value = food.food_name || "";
}

function findFoodOption(foodName) {
  const options = Array.isArray(window.FOOD_OPTIONS) ? window.FOOD_OPTIONS : [];
  return options.find((option) => option.food_name === foodName) || null;
}

function confidenceClass(confidence) {
  if (confidence === null) return "confidence-none";
  if (confidence >= 0.8) return "confidence-high";
  if (confidence >= 0.5) return "confidence-mid";
  return "confidence-low";
}

function updateRowVisual(row, food) {
  if (!row) return;

  const unknown = !food.food_name;
  row.classList.toggle("is-unknown", unknown);

  const unknownTag = row.querySelector(".tag-unknown");
  if (unknownTag) unknownTag.hidden = !unknown;

  const nameInput = row.querySelector(".food-name");
  const nameError = row.querySelector(".field-error-name");
  const nameInvalid = !food.display_name.trim();
  if (nameInput) {
    nameInput.classList.toggle("is-invalid", nameInvalid);
    nameInput.setAttribute("aria-invalid", nameInvalid ? "true" : "false");
  }
  if (nameError) nameError.hidden = !nameInvalid;

  const weightInput = row.querySelector(".food-weight");
  const weightError = row.querySelector(".field-error-weight");
  const weightInvalid = !isValidWeight(food.weight_g);
  if (weightInput) {
    weightInput.classList.toggle("is-invalid", weightInvalid);
    weightInput.setAttribute("aria-invalid", weightInvalid ? "true" : "false");
  }
  if (weightError) weightError.hidden = !weightInvalid;
}

function addFoodRow() {
  if (resultState.foods.length >= MAX_MEAL_ITEMS) {
    showToast(`一餐最多 ${MAX_MEAL_ITEMS} 项食物。`, "warning");
    return;
  }

  resultState.foods.push({
    food_name: null,
    display_name: "",
    weight_g: null,
    confidence: null,
    notes: null,
    nameDirty: false,
  });

  clearResultError();
  renderFoodRows();
  syncSaveButtonState();

  const host = document.getElementById("food-rows");
  const rows = host ? host.querySelectorAll(".food-row") : [];
  const lastRow = rows[rows.length - 1];
  if (lastRow) {
    const nameInput = lastRow.querySelector(".food-name");
    if (nameInput) nameInput.focus();
    lastRow.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function removeFoodRow(index) {
  if (index < 0 || index >= resultState.foods.length) return;
  resultState.foods.splice(index, 1);
  clearResultError();
  renderFoodRows();
  syncSaveButtonState();
}

function syncSaveButtonState() {
  const host = document.getElementById("food-rows");
  if (host) {
    resultState.foods.forEach((food, index) => {
      const row = host.querySelector(`.food-row[data-index="${index}"]`);
      updateRowVisual(row, food);
    });
  }

  const itemCount = document.getElementById("item-count");
  if (itemCount) itemCount.textContent = String(resultState.foods.length);

  const allValid = resultState.foods.every(
    (food) => food.display_name.trim() && isValidWeight(food.weight_g)
  );
  const matchedCount = resultState.foods.filter((food) => food.food_name).length;
  const unmatchedCount = resultState.foods.length - matchedCount;

  const note = document.getElementById("unmatched-note");
  if (note) note.hidden = unmatchedCount === 0 || resultState.foods.length === 0;

  const metaNote = document.getElementById("result-meta-note");
  if (metaNote) metaNote.hidden = unmatchedCount === 0;

  const saveButton = document.getElementById("save-btn");
  const saveHint = document.getElementById("save-hint");

  let hint = "";
  if (resultState.foods.length === 0) {
    hint = "还没有食物，先添加一项再保存。";
  } else if (!allValid) {
    hint = "请补全食物名称和 1–5000 克的重量。";
  } else if (matchedCount === 0) {
    hint = "至少选择一种标准食物才能保存。";
  } else if (unmatchedCount > 0) {
    hint = `将保存 ${matchedCount} 项；${unmatchedCount} 项未匹配会被跳过。`;
  } else {
    hint = `将保存 ${matchedCount} 项食物。`;
  }

  if (saveHint) saveHint.textContent = hint;
  if (saveButton) {
    saveButton.disabled =
      resultState.saving ||
      resultState.foods.length === 0 ||
      !allValid ||
      matchedCount === 0;
  }

  const addButton = document.getElementById("add-food-btn");
  if (addButton) {
    addButton.disabled = resultState.foods.length >= MAX_MEAL_ITEMS;
    addButton.title =
      resultState.foods.length >= MAX_MEAL_ITEMS
        ? `一餐最多 ${MAX_MEAL_ITEMS} 项食物`
        : "";
  }
}

function buildMealPayload() {
  return {
    meal_type: resultState.mealType,
    meal_datetime: toLocalIsoString(new Date()),
    image_path: resultState.imagePath,
    items: resultState.foods.map((food) => ({
      food_name: food.food_name || null,
      display_name: food.display_name.trim(),
      weight_g: Number(food.weight_g),
    })),
  };
}

async function saveMeal() {
  if (resultState.saving) return;

  const matchedCount = resultState.foods.filter((food) => food.food_name).length;
  if (resultState.foods.length === 0 || matchedCount === 0) {
    showError("FOOD_NOT_FOUND");
    return;
  }

  const allValid = resultState.foods.every(
    (food) => food.display_name.trim() && isValidWeight(food.weight_g)
  );
  if (!allValid) {
    showError("INVALID_WEIGHT");
    syncSaveButtonState();
    return;
  }

  const saveButton = document.getElementById("save-btn");
  resultState.saving = true;
  clearResultError();
  setButtonBusy(saveButton, true, "保存中…");
  syncSaveButtonState();

  try {
    const data = await apiFetch("/meals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildMealPayload()),
    });

    const warnings = Array.isArray(data && data.warnings) ? data.warnings : [];
    if (warnings.length > 0) {
      setFlash("warning", `已保存，但有 ${warnings.length} 项食物因未匹配被跳过。`);
    }
    // 没有告警时不写 flash：首页的 ?saved=<id> 已经会显示成功提示，
    // 两处同时写会弹出两条重复 toast。

    removeStored(RESULT_DRAFT_KEY);
    window.location.href = `/?saved=${encodeURIComponent(data.meal_id)}`;
  } catch (err) {
    resultState.saving = false;
    setButtonBusy(saveButton, false);
    syncSaveButtonState();
    showError(err);
  }
}

function renderDraftWarnings(warnings) {
  const host = document.getElementById("result-warnings");
  const list = document.getElementById("result-warning-list");
  const title = document.getElementById("result-warning-title");
  if (!host || !list) return;

  if (resultState.manual) {
    host.hidden = true;
    return;
  }

  if (title) {
    title.textContent =
      resultState.draftStatus === "error"
        ? "没有识别到食物"
        : "AI 对部分内容不太确定";
  }

  const messages = (Array.isArray(warnings) ? warnings : [])
    .map(formatWarning)
    .filter(Boolean);

  if (resultState.draftStatus === "error" && messages.length === 0) {
    messages.push("没有检测到食物。");
  }

  list.innerHTML = "";
  if (messages.length === 0) {
    host.hidden = true;
    return;
  }

  messages.slice(0, 8).forEach((message) => {
    const item = document.createElement("li");
    item.textContent = message;
    list.appendChild(item);
  });

  if (messages.length > 8) {
    const more = document.createElement("li");
    more.textContent = `还有 ${messages.length - 8} 条提示未显示。`;
    list.appendChild(more);
  }

  host.hidden = false;
}

function formatWarning(warning) {
  const text = String(warning || "").trim();
  if (!text) return "";

  if (text.startsWith("food_unrecognized:")) {
    return `未识别：${text.slice("food_unrecognized:".length).trim()}`;
  }
  if (text.startsWith("missing_weight:")) {
    return `缺少重量：${text.slice("missing_weight:".length).trim()}`;
  }
  if (text.startsWith("food_not_matched:")) {
    return `食物库未收录：${text.slice("food_not_matched:".length).trim()}`;
  }
  if (text === "no_food_detected") return "没有检测到食物。";
  return text;
}

function showError(codeOrError) {
  const code =
    typeof codeOrError === "string"
      ? codeOrError
      : codeOrError && codeOrError.code
        ? codeOrError.code
        : "INTERNAL_ERROR";

  const banner = document.getElementById("result-error");
  const text = document.getElementById("result-error-text");
  if (text) text.textContent = errorText(code);
  if (banner) {
    banner.hidden = false;
    banner.setAttribute("tabindex", "-1");
    banner.focus({ preventScroll: true });
    banner.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function clearResultError() {
  const banner = document.getElementById("result-error");
  if (banner) banner.hidden = true;
}
