/**
 * Pure domain logic shared by the Android WebView app and Node tests.
 *
 * Mirrors the Python backend:
 *   app/nutrition/calculator.py  -> calculateMeal / totalsOf
 *   app/ai/schemas.py            -> validateAnalysis
 *   app/services/schemas.py      -> validateMealPayload
 *   app/database/repository.py   -> mealDetail / mealSummary
 *
 * No DOM, no storage, no network: safe to require() from Node.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.HDTCore = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"];
  var MAX_MEAL_ITEMS = 20;
  var MAX_WEIGHT_G = 5000;
  var MAX_FUTURE_MS = 24 * 60 * 60 * 1000;

  var NUTRIENTS = {
    calories_kcal: { per100: "calories_per_100g", places: 1 },
    protein_g: { per100: "protein_per_100g", places: 2 },
    carbs_g: { per100: "carbs_per_100g", places: 2 },
    fat_g: { per100: "fat_per_100g", places: 2 }
  };
  var TOTAL_KEYS = ["calories_kcal", "protein_g", "carbs_g", "fat_g"];

  function CoreError(code, message, status, details) {
    this.name = "CoreError";
    this.code = code;
    this.message = message;
    this.status = status || 400;
    this.details = details === undefined ? null : details;
  }
  CoreError.prototype = Object.create(Error.prototype);
  CoreError.prototype.constructor = CoreError;

  function invalid(message, details) {
    return new CoreError("INVALID_REQUEST", message || "Invalid request parameters.", 400, details);
  }

  // ------------------------------------------------------------- decimals

  function decimalParts(value) {
    var text = String(value).trim();
    var match = /^(\d+)(?:\.(\d+))?$/.exec(text);
    if (!match) {
      return null;
    }
    var fraction = match[2] || "";
    return { digits: BigInt(match[1] + fraction), scale: fraction.length };
  }

  function pow10(exponent) {
    return BigInt(10) ** BigInt(exponent);
  }

  /** Round(value, places) with Decimal ROUND_HALF_UP. */
  function exactScaled(per100, weight, places) {
    var a = decimalParts(per100);
    var b = decimalParts(weight);
    if (!a || !b) {
      return null;
    }
    var numerator = a.digits * b.digits * pow10(places);
    var denominator = BigInt(100) * pow10(a.scale + b.scale);
    var quotient = numerator / denominator;
    var remainder = numerator % denominator;
    if (remainder * BigInt(2) >= denominator) {
      quotient += BigInt(1);
    }
    return quotient;
  }

  function roundScaled(value, fromPlaces, toPlaces) {
    if (toPlaces >= fromPlaces) {
      return value * pow10(toPlaces - fromPlaces);
    }
    var divisor = pow10(fromPlaces - toPlaces);
    var quotient = value / divisor;
    var remainder = value % divisor;
    if (remainder * BigInt(2) >= divisor) {
      quotient += BigInt(1);
    }
    return quotient;
  }

  function scaledToNumber(value, places) {
    return Number(value) / Math.pow(10, places);
  }

  // ---------------------------------------------------------------- foods

  function normalizeFoodName(name) {
    return String(name || "").trim().toLowerCase().replace(/[\s-]+/g, "_");
  }

  var indexCache = typeof WeakMap === "function" ? new WeakMap() : null;

  function foodIndex(foodDb) {
    if (indexCache && indexCache.has(foodDb)) {
      return indexCache.get(foodDb);
    }
    var index = new Map();
    (foodDb.foods || []).forEach(function (food) {
      index.set(food.food_name, food);
      (food.aliases || []).forEach(function (alias) {
        index.set(alias, food);
      });
    });
    if (indexCache) {
      indexCache.set(foodDb, index);
    }
    return index;
  }

  function matchFood(foodDb, name) {
    if (!name) {
      return null;
    }
    var index = foodIndex(foodDb);
    return index.get(name) || index.get(normalizeFoodName(name)) || null;
  }

  function nutrientItem(entry, weight, displayName) {
    var item = {
      food_name: entry.food_name,
      display_name: displayName || entry.display_name || entry.food_name,
      weight_g: weight,
      food_data_source: entry.source || "local",
      _exact: {}
    };
    TOTAL_KEYS.forEach(function (key) {
      var spec = NUTRIENTS[key];
      var scaled = exactScaled(entry[spec.per100], weight, 6);
      if (scaled === null) {
        scaled = BigInt(0);
      }
      item._exact[key] = scaled;
      item[key] = scaledToNumber(roundScaled(scaled, 6, spec.places), spec.places);
    });
    return item;
  }

  function sumExact(items, key) {
    var total = BigInt(0);
    items.forEach(function (item) {
      var parts = decimalParts(item[key]);
      if (parts) {
        total += parts.digits * pow10(Math.max(0, 6 - parts.scale));
      }
    });
    return total;
  }

  function totalsOf(items) {
    var totals = {};
    TOTAL_KEYS.forEach(function (key) {
      var places = NUTRIENTS[key].places;
      totals[key] = scaledToNumber(roundScaled(sumExact(items, key), 6, places), places);
    });
    return totals;
  }

  function calculateMeal(foodDb, foods) {
    var items = [];
    var warnings = [];
    var totalsExact = {};
    TOTAL_KEYS.forEach(function (key) { totalsExact[key] = BigInt(0); });

    (foods || []).forEach(function (food) {
      var name = food.food_name;
      var display = (food.display_name || "unknown").trim();
      var weight = food.estimated_weight_g;

      if (!name) {
        warnings.push("food_not_matched: " + display);
        return;
      }
      if (weight === null || weight === undefined) {
        warnings.push("missing_weight: " + display);
        return;
      }
      if (!(weight > 0) || weight > MAX_WEIGHT_G) {
        warnings.push("invalid_weight: " + display);
        return;
      }
      var entry = matchFood(foodDb, name);
      if (!entry) {
        warnings.push("food_not_matched: " + name);
        return;
      }
      var item = nutrientItem(entry, weight, display);
      TOTAL_KEYS.forEach(function (key) { totalsExact[key] += item._exact[key]; });
      delete item._exact;
      items.push(item);
    });

    var totals = {};
    TOTAL_KEYS.forEach(function (key) {
      var places = NUTRIENTS[key].places;
      totals[key] = scaledToNumber(roundScaled(totalsExact[key], 6, places), places);
    });

    return {
      schema_version: "1.0",
      items: items,
      totals: totals,
      warnings: warnings
    };
  }

  // ------------------------------------------------------------------ ai

  function validateAnalysis(payload) {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new CoreError("INVALID_AI_RESPONSE", "The AI response structure does not match the contract.", 502, {
        reason: "not_object"
      });
    }
    var rawFoods = payload.foods === undefined || payload.foods === null ? [] : payload.foods;
    if (!Array.isArray(rawFoods) || rawFoods.length > MAX_MEAL_ITEMS) {
      throw new CoreError("INVALID_AI_RESPONSE", "The AI response contains an invalid number of foods.", 502, {
        reason: "bad_foods"
      });
    }

    var foods = rawFoods.map(function (food) {
      if (!food || typeof food !== "object" || Array.isArray(food)) {
        throw new CoreError("INVALID_AI_RESPONSE", "The AI response contains an invalid food entry.", 502, {
          reason: "bad_food_item"
        });
      }
      var displayName = typeof food.display_name === "string" ? food.display_name.trim() : "";
      if (!displayName || displayName.length > 100) {
        throw new CoreError("INVALID_AI_RESPONSE", "The AI response contains an invalid food name.", 502, {
          reason: "bad_display_name"
        });
      }

      var foodName = food.food_name;
      if (foodName !== null && foodName !== undefined) {
        if (typeof foodName !== "string" || !/^[a-z0-9_]+$/.test(foodName) || foodName.length > 60) {
          throw new CoreError("INVALID_AI_RESPONSE", "The AI response contains an invalid food identifier.", 502, {
            reason: "bad_food_name"
          });
        }
      } else {
        foodName = null;
      }

      var weight = food.estimated_weight_g;
      if (weight !== null && weight !== undefined) {
        if (typeof weight !== "number" || !isFinite(weight) || weight <= 0 || weight > MAX_WEIGHT_G) {
          throw new CoreError("INVALID_AI_RESPONSE", "The AI response contains an invalid food weight.", 502, {
            reason: "bad_weight"
          });
        }
      } else {
        weight = null;
      }

      var confidence = food.confidence;
      if (typeof confidence !== "number" || !isFinite(confidence) || confidence < 0 || confidence > 1) {
        throw new CoreError("INVALID_AI_RESPONSE", "The AI response contains an invalid confidence value.", 502, {
          reason: "bad_confidence"
        });
      }

      var notes = food.notes === undefined ? null : food.notes;
      if (notes !== null && (typeof notes !== "string" || notes.length > 200)) {
        throw new CoreError("INVALID_AI_RESPONSE", "The AI response contains invalid notes.", 502, {
          reason: "bad_notes"
        });
      }

      return {
        food_name: foodName,
        display_name: displayName,
        estimated_weight_g: weight,
        confidence: confidence,
        notes: notes
      };
    });

    var warnings = [];
    foods.forEach(function (food) {
      if (!food.food_name) {
        warnings.push("food_unrecognized: " + food.display_name);
      }
      if (food.estimated_weight_g === null) {
        warnings.push("missing_weight: " + food.display_name);
      }
    });
    if (foods.length === 0) {
      warnings.push("no_food_detected");
    }

    var status = "success";
    if (foods.length === 0) {
      status = "error";
    } else if (warnings.length > 0) {
      status = "partial";
    }

    return { foods: foods, warnings: warnings, status: status };
  }

  // ------------------------------------------------------------- meals

  function pad2(value) {
    return String(value).padStart(2, "0");
  }

  function todayLocalIso(now) {
    var date = now ? new Date(now) : new Date();
    return date.getFullYear() + "-" + pad2(date.getMonth() + 1) + "-" + pad2(date.getDate());
  }

  function localDateOf(iso) {
    var match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
    if (!match) {
      return todayLocalIso();
    }
    return match[1] + "-" + match[2] + "-" + match[3];
  }

  function toUtcIso(localIso) {
    var date = new Date(localIso);
    if (isNaN(date.getTime())) {
      throw invalid("Invalid meal time format.", { field: "meal_datetime" });
    }
    return date.toISOString().replace(/\.\d{3}Z$/, "Z");
  }

  function toLocalIsoString(utcIso) {
    var date = new Date(utcIso);
    if (isNaN(date.getTime())) {
      return todayLocalIso() + "T00:00:00+00:00";
    }
    var offset = -date.getTimezoneOffset();
    var sign = offset >= 0 ? "+" : "-";
    var abs = Math.abs(offset);
    return (
      date.getFullYear() + "-" + pad2(date.getMonth() + 1) + "-" + pad2(date.getDate()) +
      "T" + pad2(date.getHours()) + ":" + pad2(date.getMinutes()) + ":" + pad2(date.getSeconds()) +
      sign + pad2(Math.floor(abs / 60)) + ":" + pad2(abs % 60)
    );
  }

  function isFutureTooFar(localIso, now) {
    var date = new Date(localIso);
    if (isNaN(date.getTime())) {
      return false;
    }
    var current = now ? new Date(now) : new Date();
    return date.getTime() > current.getTime() + MAX_FUTURE_MS;
  }

  function validateMealPayload(payload) {
    if (!payload || typeof payload !== "object") {
      throw invalid("The request body must be a JSON object.");
    }
    if (MEAL_TYPES.indexOf(payload.meal_type) === -1) {
      throw invalid("meal_type must be breakfast/lunch/dinner/snack.", {
        field: "meal_type"
      });
    }
    var mealDatetime = payload.meal_datetime;
    if (typeof mealDatetime !== "string" || !mealDatetime.trim()) {
      throw invalid("meal_datetime is required.", { field: "meal_datetime" });
    }
    if (isFutureTooFar(mealDatetime)) {
      throw invalid("meal_datetime cannot be more than 24 hours in the future.", { field: "meal_datetime" });
    }

    var imagePath = payload.image_path;
    if (imagePath !== null && imagePath !== undefined) {
      if (typeof imagePath !== "string" || !/^uploads\/[A-Za-z0-9._\-\/]+$/.test(imagePath)) {
        throw invalid("Invalid image_path.", { field: "image_path" });
      }
    } else {
      imagePath = null;
    }

    var rawItems = payload.items;
    if (!Array.isArray(rawItems) || rawItems.length < 1 || rawItems.length > MAX_MEAL_ITEMS) {
      throw invalid("items must contain 1-" + MAX_MEAL_ITEMS + " entries.", { field: "items" });
    }

    var items = rawItems.map(function (item, index) {
      if (!item || typeof item !== "object") {
        throw invalid("items[" + index + "] must be an object.", { field: "items" });
      }
      var displayName = typeof item.display_name === "string" ? item.display_name.trim() : "";
      if (!displayName || displayName.length > 100) {
        throw invalid("items[" + index + "].display_name length must be 1-100.", {
          field: "items"
        });
      }
      var foodName = item.food_name;
      if (foodName !== null && foodName !== undefined) {
        if (typeof foodName !== "string" || !/^[a-z0-9_]+$/.test(foodName) || foodName.length > 60) {
          throw invalid("items[" + index + "].food_name is invalid.", { field: "items" });
        }
      } else {
        foodName = null;
      }
      var weight = item.weight_g;
      if (typeof weight !== "number" || !isFinite(weight) || weight <= 0 || weight > MAX_WEIGHT_G) {
        throw new CoreError("INVALID_WEIGHT", "Food weight must be between 1 and 5000 g.", 400, {
          field: "items",
          index: index
        });
      }
      return {
        food_name: foodName,
        display_name: displayName,
        weight_g: weight
      };
    });

    return {
      meal_type: payload.meal_type,
      meal_datetime: mealDatetime,
      image_path: imagePath,
      items: items
    };
  }

  function mealDetail(record) {
    return {
      meal_id: record.id,
      meal_type: record.meal_type,
      meal_datetime: toLocalIsoString(record.meal_datetime_utc),
      meal_date: record.meal_date,
      image_path: record.image_path || null,
      created_at: record.created_at,
      items: record.items || [],
      totals: totalsOf(record.items || []),
      warnings: []
    };
  }

  function mealSummary(record) {
    var items = record.items || [];
    var names = items.map(function (item) { return item.display_name; });
    var summary = names.slice(0, 3).join(", ");
    if (names.length > 3) {
      summary += " +" + (names.length - 3);
    }
    return {
      meal_id: record.id,
      meal_type: record.meal_type,
      meal_datetime: toLocalIsoString(record.meal_datetime_utc),
      meal_date: record.meal_date,
      display_summary: summary,
      calories_kcal: totalsOf(items).calories_kcal,
      item_count: names.length
    };
  }

  return {
    MEAL_TYPES: MEAL_TYPES,
    MAX_MEAL_ITEMS: MAX_MEAL_ITEMS,
    MAX_WEIGHT_G: MAX_WEIGHT_G,
    NUTRIENTS: NUTRIENTS,
    TOTAL_KEYS: TOTAL_KEYS,
    CoreError: CoreError,
    decimalParts: decimalParts,
    exactScaled: exactScaled,
    roundScaled: roundScaled,
    scaledToNumber: scaledToNumber,
    normalizeFoodName: normalizeFoodName,
    matchFood: matchFood,
    calculateMeal: calculateMeal,
    totalsOf: totalsOf,
    validateAnalysis: validateAnalysis,
    validateMealPayload: validateMealPayload,
    todayLocalIso: todayLocalIso,
    localDateOf: localDateOf,
    toUtcIso: toUtcIso,
    toLocalIsoString: toLocalIsoString,
    isFutureTooFar: isFutureTooFar,
    mealDetail: mealDetail,
    mealSummary: mealSummary
  };
});
