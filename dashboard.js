"use strict";

/* =========================================================================
 * dashboard.js —— 今日概览
 * 数据来源：GET /api/v1/dashboard/daily、GET /api/v1/meals?limit=5
 * 这里只做展示与格式化，不做任何营养计算。
 * ========================================================================= */

const DAILY_TARGET_KCAL = 2000;

const dashboardState = {
  date: todayLocalIso(),
  chart: null,
  requestId: 0,
  loading: false,
};

document.addEventListener("DOMContentLoaded", initDashboard);

function initDashboard() {
  const params = new URLSearchParams(window.location.search);
  const saved = params.get("saved");

  if (saved) {
    showToast("这餐已保存，今日合计已更新。", "success");
    params.delete("saved");
    const query = params.toString();
    window.history.replaceState(null, "", window.location.pathname + (query ? `?${query}` : ""));
  }

  const flash = consumeFlash();
  if (flash && flash.message) {
    showToast(flash.message, flash.type || "info", 6500);
  }

  const dateInput = document.getElementById("date-input");
  const maxDate = todayLocalIso();
  if (dateInput) dateInput.max = maxDate;

  const dateParam = params.get("date");
  const initialDate = /^\d{4}-\d{2}-\d{2}$/.test(dateParam || "") && dateParam <= maxDate
    ? dateParam
    : maxDate;

  if (dateInput) {
    dateInput.value = initialDate;
    dateInput.addEventListener("change", () => {
      const value = dateInput.value || maxDate;
      setDashboardDate(value > maxDate ? maxDate : value);
    });
  }

  const prevButton = document.getElementById("prev-day");
  const nextButton = document.getElementById("next-day");
  const todayButton = document.getElementById("today-btn");
  const retryButton = document.getElementById("retry-dashboard");

  if (prevButton) {
    prevButton.addEventListener("click", () => {
      setDashboardDate(shiftLocalDate(dashboardState.date, -1));
    });
  }

  if (nextButton) {
    nextButton.addEventListener("click", () => {
      if (dashboardState.date < maxDate) {
        setDashboardDate(shiftLocalDate(dashboardState.date, 1));
      }
    });
  }

  if (todayButton) {
    todayButton.addEventListener("click", () => setDashboardDate(todayLocalIso()));
  }

  if (retryButton) {
    retryButton.addEventListener("click", () => loadDashboard(dashboardState.date));
  }

  setDashboardDate(initialDate, { updateUrl: false });
}

function setDashboardDate(date, options = {}) {
  const maxDate = todayLocalIso();
  const safeDate = /^\d{4}-\d{2}-\d{2}$/.test(date || "") && date <= maxDate ? date : maxDate;
  dashboardState.date = safeDate;

  const dateInput = document.getElementById("date-input");
  if (dateInput) dateInput.value = safeDate;

  const nextButton = document.getElementById("next-day");
  if (nextButton) nextButton.disabled = safeDate >= maxDate;

  const todayButton = document.getElementById("today-btn");
  if (todayButton) todayButton.disabled = safeDate === maxDate;

  if (options.updateUrl !== false) {
    const url = new URL(window.location.href);
    if (safeDate === maxDate) url.searchParams.delete("date");
    else url.searchParams.set("date", safeDate);
    window.history.replaceState(null, "", url);
  }

  loadDashboard(safeDate);
}

async function loadDashboard(date) {
  const requestId = ++dashboardState.requestId;
  setDashboardLoading(true);
  hidePageError("dashboard-error");

  try {
    const [daily, recent] = await Promise.all([
      apiFetch(`/dashboard/daily?date=${encodeURIComponent(date)}`),
      loadRecentMeals(),
    ]);

    if (requestId !== dashboardState.requestId) return;

    // 先显示容器，再初始化 Chart.js：隐藏容器里的 canvas 宽高为 0，
    // 图表会画不出来或尺寸错误。
    const content = document.getElementById("dashboard-content");
    if (content) content.hidden = false;

    renderDashboard(daily, recent);
  } catch (err) {
    if (requestId !== dashboardState.requestId) return;
    showPageError("dashboard-error", "dashboard-error-text", err);
  } finally {
    if (requestId === dashboardState.requestId) {
      setDashboardLoading(false);
    }
  }
}

async function loadRecentMeals() {
  return apiFetch("/meals?limit=5");
}

function setDashboardLoading(loading) {
  dashboardState.loading = loading;
  const skeleton = document.getElementById("dashboard-loading");
  const content = document.getElementById("dashboard-content");
  if (skeleton) skeleton.hidden = !loading;
  if (content && loading) content.hidden = true;
}

function renderDashboard(daily, recent) {
  const date = (daily && daily.date) || dashboardState.date;
  const totals = (daily && daily.totals) || {};
  const mealCount = Number(daily && daily.meal_count) || 0;

  const dateLabel = document.getElementById("today-date");
  if (dateLabel) {
    const suffix = date === todayLocalIso() ? " · 今天" : " · 历史记录";
    dateLabel.textContent = formatDateLabel(date) + suffix;
  }

  const mealCountEl = document.getElementById("meal-count");
  if (mealCountEl) mealCountEl.textContent = String(mealCount);

  renderProgress(totals, mealCount);
  renderMacroChart(totals);
  renderMealTypeBreakdown(daily && daily.by_meal_type);

  const recentPayload = recent || {};
  renderRecentList(Array.isArray(recentPayload.meals) ? recentPayload.meals : []);
}

function renderProgress(totals, mealCount) {
  const kcal = Number(totals.calories_kcal) || 0;
  const rawPercent = (kcal / DAILY_TARGET_KCAL) * 100;
  const barPercent = Math.min(rawPercent, 100);

  const valueEl = document.getElementById("calories-value");
  if (valueEl) valueEl.textContent = formatKcal(kcal);

  const targetEl = document.getElementById("calorie-target");
  if (targetEl) targetEl.textContent = formatKcal(DAILY_TARGET_KCAL);

  const percentEl = document.getElementById("calorie-percent");
  if (percentEl) percentEl.textContent = `${Math.round(rawPercent)}%`;

  const bar = document.getElementById("calorie-progress");
  if (bar) {
    bar.style.width = `${barPercent}%`;
    bar.classList.toggle("is-over", kcal > DAILY_TARGET_KCAL);
  }

  const track = document.getElementById("calorie-progress-track");
  if (track) {
    track.setAttribute("aria-valuenow", String(Math.round(barPercent)));
    track.setAttribute(
      "aria-valuetext",
      `已摄入 ${formatKcal(kcal)} 千卡，参考目标 ${formatKcal(DAILY_TARGET_KCAL)} 千卡`
    );
  }

  const remaining = DAILY_TARGET_KCAL - kcal;
  const remainingEl = document.getElementById("remaining-kcal");
  if (remainingEl) {
    if (mealCount === 0 && kcal === 0) {
      remainingEl.textContent = "今天还没有记录，先上传一餐吧。";
      remainingEl.classList.remove("is-over");
    } else if (remaining >= 0) {
      remainingEl.textContent = `距参考目标还可摄入 ${formatKcal(remaining)} kcal`;
      remainingEl.classList.remove("is-over");
    } else {
      remainingEl.textContent = `已超出参考目标 ${formatKcal(-remaining)} kcal`;
      remainingEl.classList.add("is-over");
    }
  }
}

function renderMacroChart(totals) {
  const protein = Number(totals.protein_g) || 0;
  const carbs = Number(totals.carbs_g) || 0;
  const fat = Number(totals.fat_g) || 0;
  const sum = protein + carbs + fat;

  const legendProtein = document.getElementById("legend-protein");
  const legendCarbs = document.getElementById("legend-carbs");
  const legendFat = document.getElementById("legend-fat");
  if (legendProtein) legendProtein.textContent = formatMacro(protein);
  if (legendCarbs) legendCarbs.textContent = formatMacro(carbs);
  if (legendFat) legendFat.textContent = formatMacro(fat);

  const valueProtein = document.getElementById("protein-value");
  const valueCarbs = document.getElementById("carbs-value");
  const valueFat = document.getElementById("fat-value");
  if (valueProtein) valueProtein.textContent = protein.toFixed(1);
  if (valueCarbs) valueCarbs.textContent = carbs.toFixed(1);
  if (valueFat) valueFat.textContent = fat.toFixed(1);

  const canvas = document.getElementById("macro-chart");
  const fallback = document.getElementById("macro-fallback");

  if (sum <= 0) {
    renderMacroFallback({ protein, carbs, fat, empty: true });
    if (canvas) canvas.hidden = true;
    if (fallback) fallback.hidden = false;
    if (dashboardState.chart) {
      dashboardState.chart.destroy();
      dashboardState.chart = null;
    }
    return;
  }

  if (typeof window.Chart === "undefined") {
    renderMacroFallback({ protein, carbs, fat, empty: false });
    if (canvas) canvas.hidden = true;
    if (fallback) fallback.hidden = false;
    return;
  }

  if (canvas) canvas.hidden = false;
  if (fallback) fallback.hidden = true;

  if (dashboardState.chart) dashboardState.chart.destroy();

  dashboardState.chart = new window.Chart(canvas, {
    type: "doughnut",
    data: {
      labels: ["蛋白质", "碳水", "脂肪"],
      datasets: [
        {
          data: [protein, carbs, fat],
          backgroundColor: ["#2563eb", "#d97706", "#dc2626"],
          borderColor: "#ffffff",
          borderWidth: 3,
          hoverOffset: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "68%",
      animation: { duration: 420 },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(20, 33, 29, 0.92)",
          padding: 10,
          displayColors: true,
          callbacks: {
            label(context) {
              const value = Number(context.parsed) || 0;
              return ` ${context.label}：${value.toFixed(1)} g`;
            },
          },
        },
      },
    },
  });
}

function renderMacroFallback({ protein, carbs, fat, empty }) {
  const host = document.getElementById("macro-fallback-bars");
  const caption = document.querySelector(".macro-fallback-text");
  if (caption) {
    caption.textContent = empty
      ? "上传一餐后，这里会显示宏量营养素比例。"
      : "图表组件未加载，以下为数值。";
  }
  if (!host) return;
  host.innerHTML = "";

  if (empty) {
    const note = document.createElement("p");
    note.className = "macro-fallback-empty";
    note.textContent = "今天还没有宏量营养素数据。";
    host.appendChild(note);
    return;
  }

  const rows = [
    { label: "蛋白质", value: protein, className: "dot-protein" },
    { label: "碳水", value: carbs, className: "dot-carbs" },
    { label: "脂肪", value: fat, className: "dot-fat" },
  ];
  const max = Math.max(protein, carbs, fat, 1);

  rows.forEach((row) => {
    const wrapper = document.createElement("div");
    wrapper.className = "fallback-row";

    const label = document.createElement("span");
    label.className = "fallback-label";
    label.textContent = row.label;

    const track = document.createElement("span");
    track.className = "fallback-track";
    const fill = document.createElement("span");
    fill.className = `fallback-fill ${row.className}`;
    fill.style.width = `${Math.max((row.value / max) * 100, 2)}%`;
    track.appendChild(fill);

    const value = document.createElement("span");
    value.className = "fallback-value";
    value.textContent = formatMacro(row.value);

    wrapper.append(label, track, value);
    host.appendChild(wrapper);
  });
}

function renderMealTypeBreakdown(byMealType) {
  const host = document.getElementById("meal-type-breakdown");
  const list = document.getElementById("breakdown-list");
  if (!host || !list) return;

  if (!byMealType || typeof byMealType !== "object") {
    host.hidden = true;
    return;
  }

  list.innerHTML = "";
  const total = MEAL_TYPES.reduce((sum, type) => sum + (Number(byMealType[type]) || 0), 0);

  if (total <= 0) {
    host.hidden = true;
    return;
  }

  MEAL_TYPES.forEach((type) => {
    const kcal = Number(byMealType[type]) || 0;

    const item = document.createElement("li");
    item.className = "breakdown-item";

    const label = document.createElement("span");
    label.className = "breakdown-label";
    label.textContent = mealTypeLabel(type);

    const bar = document.createElement("span");
    bar.className = `breakdown-bar meal-${type}`;
    bar.style.width = total > 0 ? `${Math.max((kcal / total) * 100, kcal > 0 ? 4 : 0)}%` : "0%";

    const value = document.createElement("span");
    value.className = "breakdown-value";
    value.textContent = `${formatKcal(kcal)} kcal`;

    item.append(label, bar, value);
    list.appendChild(item);
  });

  host.hidden = false;
}

function renderRecentList(meals) {
  const list = document.getElementById("recent-list");
  const empty = document.getElementById("recent-empty");
  if (!list || !empty) return;

  list.innerHTML = "";
  if (!meals.length) {
    list.hidden = true;
    empty.hidden = false;
    return;
  }

  list.hidden = false;
  empty.hidden = true;

  meals.forEach((meal) => {
    const item = document.createElement("li");
    item.className = "recent-item";

    const link = document.createElement("a");
    link.className = "recent-link";
    link.href = `/history?date=${encodeURIComponent(meal.meal_date || "")}`;

    const badge = document.createElement("span");
    badge.className = `meal-badge meal-${meal.meal_type || "snack"}`;
    badge.textContent = mealTypeLabel(meal.meal_type);

    const main = document.createElement("span");
    main.className = "recent-main";

    const summary = document.createElement("span");
    summary.className = "recent-summary";
    summary.textContent = meal.display_summary || "（无名称）";

    const meta = document.createElement("span");
    meta.className = "recent-sub";
    const count = Number(meal.item_count) || 0;
    meta.textContent = `${formatDateTimeShort(meal.meal_datetime)} · ${count} 项`;

    main.append(summary, meta);

    const kcal = document.createElement("span");
    kcal.className = "recent-kcal";
    kcal.textContent = formatKcal(meal.calories_kcal);
    const unit = document.createElement("small");
    unit.textContent = " kcal";
    kcal.appendChild(unit);

    link.append(badge, main, kcal);
    item.appendChild(link);
    list.appendChild(item);
  });
}

function renderEmptyState() {
  const list = document.getElementById("recent-list");
  const empty = document.getElementById("recent-empty");
  if (list) list.hidden = true;
  if (empty) empty.hidden = false;
}
