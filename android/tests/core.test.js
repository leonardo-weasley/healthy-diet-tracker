/* Node tests for the shared domain core (no browser, no Android). */
"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const Core = require("../web/js/core.js");

const ROOT = path.resolve(__dirname, "../..");
const foodDb = JSON.parse(
  fs.readFileSync(path.join(ROOT, "app/nutrition/food_database.json"), "utf8")
);
const fixtures = JSON.parse(fs.readFileSync(path.join(__dirname, "expected.json"), "utf8"));

let passed = 0;
function test(name, fn) {
  try {
    fn();
    passed += 1;
    console.log(`ok - ${name}`);
  } catch (error) {
    console.error(`not ok - ${name}`);
    console.error(error.message);
    process.exitCode = 1;
  }
}

test("nutrition matches Python Decimal ROUND_HALF_UP for all foods", () => {
  fixtures.cases.forEach((item) => {
    const result = Core.calculateMeal(foodDb, [
      {
        food_name: item.food_name,
        display_name: item.food_name,
        estimated_weight_g: item.weight,
      },
    ]);
    assert.strictEqual(result.items.length, 1, `${item.food_name} @ ${item.weight}g`);
    const actual = result.items[0];
    Object.keys(item.expected).forEach((key) => {
      assert.strictEqual(
        actual[key],
        item.expected[key],
        `${item.food_name} @ ${item.weight}g ${key}: ${actual[key]} != ${item.expected[key]}`
      );
    });
  });
});

test("meal totals sum exact values before rounding", () => {
  const foods = fixtures.combo.items.map((item) => ({
    food_name: item.food_name,
    display_name: item.food_name,
    estimated_weight_g: item.weight,
  }));
  const result = Core.calculateMeal(foodDb, foods);
  assert.strictEqual(result.items.length, foods.length);
  Object.keys(fixtures.combo.totals).forEach((key) => {
    assert.strictEqual(result.totals[key], fixtures.combo.totals[key], `${key}`);
  });
});

test("unknown food and missing weight become warnings, not crashes", () => {
  const result = Core.calculateMeal(foodDb, [
    { food_name: "not_a_food", display_name: "神秘料理", estimated_weight_g: 100 },
    { food_name: "banana", display_name: "香蕉", estimated_weight_g: null },
  ]);
  assert.deepStrictEqual(result.items, []);
  assert.deepStrictEqual(result.warnings, [
    "food_not_matched: not_a_food",
    "missing_weight: 香蕉",
  ]);
});

test("AI payload validation accepts contract A", () => {
  const result = Core.validateAnalysis({
    schema_version: "1.0",
    status: "success",
    foods: [
      {
        food_name: "banana",
        display_name: "香蕉",
        estimated_weight_g: 120,
        confidence: 0.9,
        notes: null,
      },
    ],
  });
  assert.strictEqual(result.status, "success");
  assert.deepStrictEqual(result.warnings, []);
  assert.strictEqual(result.foods[0].food_name, "banana");
});

test("AI payload validation rejects bad names and weights", () => {
  assert.throws(
    () =>
      Core.validateAnalysis({
        foods: [{ food_name: "Bad Name", display_name: "x", estimated_weight_g: 10, confidence: 0.5 }],
      }),
    (error) => error.code === "INVALID_AI_RESPONSE"
  );
  assert.throws(
    () =>
      Core.validateAnalysis({
        foods: [{ food_name: null, display_name: "x", estimated_weight_g: 9000, confidence: 0.5 }],
      }),
    (error) => error.code === "INVALID_AI_RESPONSE"
  );
});

test("AI payload derives partial status", () => {
  const result = Core.validateAnalysis({
    foods: [{ food_name: null, display_name: "不明食物", estimated_weight_g: 80, confidence: 0.4 }],
  });
  assert.strictEqual(result.status, "partial");
  assert.deepStrictEqual(result.warnings, ["food_unrecognized: 不明食物"]);
});

test("meal payload normalizes and rejects invalid weight", () => {
  const normalized = Core.validateMealPayload({
    meal_type: "lunch",
    meal_datetime: "2026-11-18T12:30:00+08:00",
    image_path: null,
    items: [{ food_name: "banana", display_name: " 香蕉 ", weight_g: 120 }],
  });
  assert.strictEqual(normalized.items[0].display_name, "香蕉");
  assert.strictEqual(normalized.image_path, null);

  assert.throws(
    () =>
      Core.validateMealPayload({
        meal_type: "lunch",
        meal_datetime: "2026-11-18T12:30:00+08:00",
        items: [{ food_name: "banana", display_name: "香蕉", weight_g: 0 }],
      }),
    (error) => error.code === "INVALID_WEIGHT"
  );
});

test("meal detail and summary mirror repository shapes", () => {
  const record = {
    id: 7,
    meal_type: "dinner",
    meal_datetime_utc: "2026-11-18T10:30:00Z",
    meal_date: "2026-11-18",
    image_path: null,
    created_at: "2026-11-18T10:31:00Z",
    items: [
      {
        food_name: "banana",
        display_name: "香蕉",
        weight_g: 120,
        calories_kcal: 107.5,
        protein_g: 1.3,
        carbs_g: 27.5,
        fat_g: 0.4,
        food_data_source: "USDA",
      },
    ],
  };
  const detail = Core.mealDetail(record);
  assert.strictEqual(detail.meal_id, 7);
  assert.strictEqual(detail.totals.calories_kcal, 107.5);
  assert.strictEqual(detail.meal_datetime.slice(0, 10), "2026-11-18");

  const summary = Core.mealSummary(record);
  assert.strictEqual(summary.display_summary, "香蕉");
  assert.strictEqual(summary.item_count, 1);
  assert.strictEqual(summary.calories_kcal, 107.5);
});

console.log(`\n${passed} tests passed`);
