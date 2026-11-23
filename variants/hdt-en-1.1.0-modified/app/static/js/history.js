"use strict";

/* =========================================================================
 * history.js — history page
 * Data sources: GET /api/v1/meals, GET /api/v1/meals/{id}, DELETE /api/v1/meals/{id}
 * Contract: 00_MAIN_TECHNICAL_ROUTE.md §E.4, §F.3–§F.5
 * ========================================================================= */

const HISTORY_PAGE_SIZE = 20;
const HISTORY_FILTER_KEY = "hdt.historyFilters";

const historyState = {
  dateFrom: "",
  dateTo: "",
  offset: 0,
  limit: HISTORY_PAGE_SIZE,
  meals: [],
  loading: false,
  requestId: 0,
  details: new Map(),
};

document.addEventListener("DOMContentLoaded", initHistoryPage);

function initHistoryPage() {
  const dateFrom = document.getElementById("date-from");
  const dateTo = document.getElementById("date-to");
  const form = document.getElementById("history-filters");
  const resetButton = document.getElementById("reset-filters");
  const retryButton = document.getElementById("retry-history");
  const emptyAction = document.getElementById("empty-action");
  const prevButton = document.getElementById("prev-page");
  const nextButton = document.getElementById("next-page");

  const maxDate = todayLocalIso();
  if (dateFrom) dateFrom.max = maxDate;
  if (dateTo) dateTo.max = maxDate;

  restoreFilters(dateFrom, dateTo);

  if (form) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      applyFilters();
    });
  }

  document.querySelectorAll("[data-range]").forEach((button) => {
    button.addEventListener("click", () => setQuickRange(button.dataset.range));
  });

  [dateFrom, dateTo].forEach((input) => {
    if (!input) return;
    input.addEventListener("input", () => {
      document.querySelectorAll("[data-range]").forEach((button) => {
        button.classList.remove("is-active");
      });
      hideFilterError();
    });
  });

  if (resetButton) {
    resetButton.addEventListener("click", () => {
      clearFilters();
      loadHistory({ reset: true });
    });
  }

  if (retryButton) {
    retryButton.addEventListener("click", () => loadHistory());
  }

  if (emptyAction) {
    emptyAction.addEventListener("click", () => {
      clearFilters();
      loadHistory({ reset: true });
    });
  }

  if (prevButton) {
    prevButton.addEventListener("click", () => {
      if (historyState.loading || historyState.offset <= 0) return;
      historyState.offset = Math.max(0, historyState.offset - historyState.limit);
      loadHistory();
    });
  }

  if (nextButton) {
    nextButton.addEventListener("click", () => {
      if (historyState.loading) return;
      historyState.offset += historyState.limit;
      loadHistory();
    });
  }

  loadHistory({ reset: true });
}

function restoreFilters(dateFrom, dateTo) {
  const url = new URLSearchParams(window.location.search);
  const urlDate = url.get("date");
  const urlFrom = url.get("date_from");
  const urlTo = url.get("date_to");
  const saved = readJson(HISTORY_FILTER_KEY);

  let from = "";
  let to = "";

  if (isValidIsoDate(urlFrom) && isValidIsoDate(urlTo)) {
    from = urlFrom;
    to = urlTo;
  } else if (isValidIsoDate(urlDate)) {
    from = urlDate;
    to = urlDate;
  } else if (saved && typeof saved === "object") {
    from = isValidIsoDate(saved.from) ? saved.from : "";
    to = isValidIsoDate(saved.to) ? saved.to : "";
  }

  if ((from && !to) || (!from && to) || (from && to && from > to)) {
    from = "";
    to = "";
  }

  historyState.dateFrom = from;
  historyState.dateTo = to;

  if (dateFrom) dateFrom.value = from;
  if (dateTo) dateTo.value = to;

  markActiveQuickRange(from, to);
}

function syncFiltersToUrl() {
  const url = new URL(window.location.href);
  url.searchParams.delete("date");
  url.searchParams.delete("date_from");
  url.searchParams.delete("date_to");

  if (historyState.dateFrom && historyState.dateTo) {
    url.searchParams.set("date_from", historyState.dateFrom);
    url.searchParams.set("date_to", historyState.dateTo);
  }

  window.history.replaceState(null, "", url);
}

function setQuickRange(range) {
  const today = todayLocalIso();
  const dateFrom = document.getElementById("date-from");
  const dateTo = document.getElementById("date-to");

  if (range === "today") {
    historyState.dateFrom = today;
    historyState.dateTo = today;
  } else if (range === "7d") {
    historyState.dateFrom = shiftLocalDate(today, -6);
    historyState.dateTo = today;
  } else {
    historyState.dateFrom = "";
    historyState.dateTo = "";
  }

  if (dateFrom) dateFrom.value = historyState.dateFrom;
  if (dateTo) dateTo.value = historyState.dateTo;

  markActiveQuickRange(historyState.dateFrom, historyState.dateTo);
  hideFilterError();
  syncFiltersToUrl();
  loadHistory({ reset: true });
}

function markActiveQuickRange(from, to) {
  const today = todayLocalIso();
  let active = "all";

  if (from && to) {
    if (from === today && to === today) active = "today";
    else if (from === shiftLocalDate(today, -6) && to === today) active = "7d";
    else active = "";
  }

  document.querySelectorAll("[data-range]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.range === active);
  });
}

function applyFilters() {
  const fromInput = document.getElementById("date-from");
  const toInput = document.getElementById("date-to");
  const from = fromInput ? fromInput.value : "";
  const to = toInput ? toInput.value : "";

  const message = validateFilters(from, to);
  if (message) {
    showFilterError(message);
    return;
  }

  historyState.dateFrom = from;
  historyState.dateTo = to;
  hideFilterError();
  markActiveQuickRange(from, to);
  syncFiltersToUrl();
  loadHistory({ reset: true });
}

function validateFilters(from, to) {
  if ((from && !to) || (!from && to)) {
    return "Fill in both the start and end date, or leave both empty.";
  }
  if (from && to && from > to) {
    return "The start date cannot be later than the end date.";
  }
  return "";
}

function clearFilters() {
  const dateFrom = document.getElementById("date-from");
  const dateTo = document.getElementById("date-to");
  if (dateFrom) dateFrom.value = "";
  if (dateTo) dateTo.value = "";
  historyState.dateFrom = "";
  historyState.dateTo = "";
  historyState.offset = 0;
  removeStored(HISTORY_FILTER_KEY);
  hideFilterError();
  markActiveQuickRange("", "");
  syncFiltersToUrl();
}

async function loadHistory({ reset = false } = {}) {
  if (reset) historyState.offset = 0;

  const message = validateFilters(historyState.dateFrom, historyState.dateTo);
  if (message) {
    showFilterError(message);
    return;
  }

  const requestId = ++historyState.requestId;
  setHistoryLoading(true);
  hidePageError("history-error");

  const params = new URLSearchParams();
  if (historyState.dateFrom && historyState.dateTo) {
    params.set("date_from", historyState.dateFrom);
    params.set("date_to", historyState.dateTo);
  }
  params.set("limit", String(historyState.limit));
  params.set("offset", String(historyState.offset));

  try {
    const data = await apiFetch(`/meals?${params.toString()}`);
    if (requestId !== historyState.requestId) return;

    const meals = Array.isArray(data.meals) ? data.meals : [];

    // No total count is available: if the user lands on an empty page, step back one page.
    if (meals.length === 0 && historyState.offset > 0) {
      historyState.offset = Math.max(0, historyState.offset - historyState.limit);
      await loadHistory();
      return;
    }

    historyState.meals = meals;
    historyState.offset = Number(data.pagination && data.pagination.offset) || historyState.offset;
    historyState.limit = Number(data.pagination && data.pagination.limit) || HISTORY_PAGE_SIZE;

    storeJson(HISTORY_FILTER_KEY, {
      from: historyState.dateFrom,
      to: historyState.dateTo,
    });

    renderMealList(historyState.meals);
    renderPagination(historyState.meals.length);
  } catch (err) {
    if (requestId !== historyState.requestId) return;
    showPageError("history-error", "history-error-text", err);
  } finally {
    if (requestId === historyState.requestId) {
      setHistoryLoading(false);
    }
  }
}

function setHistoryLoading(loading) {
  historyState.loading = loading;
  const skeleton = document.getElementById("history-loading");
  const list = document.getElementById("history-list");
  const empty = document.getElementById("history-empty");
  const pagination = document.getElementById("pagination");

  if (skeleton) skeleton.hidden = !loading;
  if (loading) {
    if (list) list.hidden = true;
    if (empty) empty.hidden = true;
    if (pagination) pagination.hidden = true;
  }
}

function renderMealList(meals) {
  const list = document.getElementById("history-list");
  const empty = document.getElementById("history-empty");
  if (!list || !empty) return;

  list.innerHTML = "";
  list.hidden = false;

  if (!meals.length) {
    list.hidden = true;
    empty.hidden = false;

    const hasFilters = Boolean(historyState.dateFrom || historyState.dateTo);
    const title = document.getElementById("history-empty-title");
    const text = document.getElementById("history-empty-text");
    const action = document.getElementById("empty-action");
    const uploadLink = document.getElementById("empty-upload-link");

    if (title) title.textContent = hasFilters ? "No meals in this range" : "No meals yet";
    if (text) {
      text.textContent = hasFilters
        ? "Try another date range, or clear the filters to see all meals."
        : "Upload a meal photo and it will appear here after you save it.";
    }
    if (action) action.hidden = !hasFilters;
    if (uploadLink) uploadLink.hidden = hasFilters;
    return;
  }

  empty.hidden = true;

  meals.forEach((meal) => {
    list.appendChild(buildMealCard(meal));
  });
}

function buildMealCard(meal) {
  const item = document.createElement("li");
  item.className = "meal-card";
  item.dataset.mealId = String(meal.meal_id);

  const head = document.createElement("div");
  head.className = "meal-card-head";

  const badge = document.createElement("span");
  badge.className = `meal-badge meal-${meal.meal_type || "snack"}`;
  badge.textContent = mealTypeLabel(meal.meal_type);

  const main = document.createElement("div");
  main.className = "meal-card-main";

  const summary = document.createElement("p");
  summary.className = "meal-summary";
  summary.textContent = meal.display_summary || "(Unnamed)";

  const sub = document.createElement("p");
  sub.className = "meal-sub";
  const count = Number(meal.item_count) || 0;
  sub.textContent = `${formatDateTimeShort(meal.meal_datetime)} · ${count} items`;

  main.append(summary, sub);

  const kcal = document.createElement("p");
  kcal.className = "meal-kcal";
  kcal.textContent = formatKcal(meal.calories_kcal);
  const unit = document.createElement("small");
  unit.textContent = " kcal";
  kcal.appendChild(unit);

  const actions = document.createElement("div");
  actions.className = "meal-card-actions";

  const detailButton = document.createElement("button");
  detailButton.type = "button";
  detailButton.className = "btn btn-ghost btn-sm detail-toggle";
  detailButton.textContent = "Details";
  detailButton.setAttribute("aria-expanded", "false");

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.className = "btn btn-danger-ghost btn-sm delete-btn";
  deleteButton.textContent = "Delete";

  actions.append(detailButton, deleteButton);
  head.append(badge, main, kcal, actions);

  const detail = document.createElement("div");
  detail.className = "meal-detail";
  detail.hidden = true;

  detailButton.addEventListener("click", () => {
    openMealDetail(meal.meal_id, item, detail, detailButton);
  });

  deleteButton.addEventListener("click", () => {
    deleteMeal(meal.meal_id, deleteButton);
  });

  item.append(head, detail);
  return item;
}

async function openMealDetail(mealId, card, detailContainer, button) {
  if (!card) {
    card = document.querySelector(`.meal-card[data-meal-id="${mealId}"]`);
  }
  if (!detailContainer && card) {
    detailContainer = card.querySelector(".meal-detail");
  }
  if (!button && card) {
    button = card.querySelector(".detail-toggle");
  }
  if (!card || !detailContainer || !button) return;

  const isOpen = !detailContainer.hidden;

  if (isOpen) {
    detailContainer.hidden = true;
    button.setAttribute("aria-expanded", "false");
    button.textContent = "Details";
    card.classList.remove("is-open");
    return;
  }

  detailContainer.hidden = false;
  card.classList.add("is-open");
  button.setAttribute("aria-expanded", "true");
  button.textContent = "Collapse";

  if (historyState.details.has(mealId)) {
    renderMealDetail(detailContainer, historyState.details.get(mealId));
    return;
  }

  detailContainer.innerHTML = '<p class="detail-loading">Loading details…</p>';

  try {
    const meal = await apiFetch(`/meals/${encodeURIComponent(mealId)}`);
    if (!meal || typeof meal !== "object") {
      throw makeApiError("INTERNAL_ERROR", "Invalid details format.");
    }
    historyState.details.set(mealId, meal);
    renderMealDetail(detailContainer, meal);
  } catch (err) {
    detailContainer.innerHTML = "";
    const error = document.createElement("p");
    error.className = "detail-error";
    error.textContent = errorText(err.code);
    detailContainer.appendChild(error);
  }
}

function renderMealDetail(container, meal) {
  container.innerHTML = "";

  const items = Array.isArray(meal.items) ? meal.items : [];

  const header = document.createElement("div");
  header.className = "detail-row detail-row-head";
  ["Food", "Weight", "Calories"].forEach((label) => {
    const cell = document.createElement("span");
    cell.textContent = label;
    header.appendChild(cell);
  });
  container.appendChild(header);

  const list = document.createElement("ul");
  list.className = "detail-items";

  items.forEach((item) => {
    const row = document.createElement("li");
    row.className = "detail-row";

    const name = document.createElement("span");
    name.className = "detail-name";
    name.textContent = item.display_name || "(Unnamed)";

    const weight = document.createElement("span");
    weight.textContent = formatWeight(item.weight_g);

    const calories = document.createElement("span");
    calories.textContent = `${formatKcal(item.calories_kcal)} kcal`;

    row.append(name, weight, calories);
    list.appendChild(row);
  });

  container.appendChild(list);

  const totals = meal.totals || {};
  const footer = document.createElement("div");
  footer.className = "detail-totals";

  const totalKcal = document.createElement("p");
  totalKcal.className = "detail-total-kcal";
  totalKcal.textContent = `${formatKcal(totals.calories_kcal)} kcal`;
  footer.appendChild(totalKcal);

  const macros = document.createElement("p");
  macros.className = "detail-macros";
  macros.textContent =
    `Protein ${formatMacro(totals.protein_g)} · ` +
    `Carbs ${formatMacro(totals.carbs_g)} · ` +
    `Fat ${formatMacro(totals.fat_g)}`;
  footer.appendChild(macros);

  container.appendChild(footer);

  const warnings = Array.isArray(meal.warnings) ? meal.warnings : [];
  if (warnings.length > 0) {
    const warning = document.createElement("p");
    warning.className = "detail-warning";
    warning.textContent = `${warnings.length} notices when saved: ${warnings.join("; ")}`;
    container.appendChild(warning);
  }
}

async function deleteMeal(mealId, button) {
  const confirmed = window.confirm("Delete this record? This cannot be undone.");
  if (!confirmed) return;

  const card = button ? button.closest(".meal-card") : null;
  if (button) {
    button.disabled = true;
    button.textContent = "Deleting…";
  }

  try {
    await apiFetch(`/meals/${encodeURIComponent(mealId)}`, { method: "DELETE" });
    historyState.details.delete(mealId);
    if (card) card.remove();
    showToast("Record deleted.", "success");

    if (historyState.meals.length <= 1 && historyState.offset > 0) {
      historyState.offset = Math.max(0, historyState.offset - historyState.limit);
    }
    await loadHistory();
  } catch (err) {
    if (err.code === "MEAL_NOT_FOUND") {
      historyState.details.delete(mealId);
      if (card) card.remove();
      showToast("This record no longer exists.", "info");
      await loadHistory();
      return;
    }

    if (button) {
      button.disabled = false;
      button.textContent = "Delete";
    }
    showToast(errorText(err.code), "error");
  }
}

function renderPagination(pageCount) {
  const pagination = document.getElementById("pagination");
  const pageInfo = document.getElementById("page-info");
  const prevButton = document.getElementById("prev-page");
  const nextButton = document.getElementById("next-page");

  if (!pagination || !pageInfo || !prevButton || !nextButton) return;

  const hasPrev = historyState.offset > 0;
  const hasNext = pageCount >= historyState.limit;

  if (!hasPrev && !hasNext) {
    pagination.hidden = true;
    return;
  }

  pagination.hidden = false;
  prevButton.disabled = !hasPrev;
  nextButton.disabled = !hasNext;

  const pageNumber = Math.floor(historyState.offset / historyState.limit) + 1;
  pageInfo.textContent = `Page ${pageNumber} · ${pageCount} on this page`;
}

function showFilterError(message) {
  const error = document.getElementById("filter-error");
  if (!error) return;
  error.textContent = message;
  error.hidden = false;
}

function hideFilterError() {
  const error = document.getElementById("filter-error");
  if (error) error.hidden = true;
}

function isValidIsoDate(value) {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

/* Explicit export for documentation and debugging (plain script, attached to window). */
window.loadHistory = loadHistory;
window.openMealDetail = openMealDetail;
window.deleteMeal = deleteMeal;
window.renderMealList = renderMealList;
