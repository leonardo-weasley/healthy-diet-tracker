/* =========================================================================
 * food-options.js — standard food dropdown list
 *
 * This file only stores food IDs and display names; it contains no nutrition values.
 * All nutrition calculations happen in app/nutrition on the server; the frontend only places the user-corrected
 * food_name into contract B items[] unchanged.
 *
 * The list matches the 29 reference foods in 03_NUTRITION_ENGINE_DEVELOPER.md §5.2.
 * When foods are added or removed, update this file; IDs not listed here are handled by result.js
 * with an automatic "not in database" option, so saving does not fail.
 * ========================================================================= */

window.FOOD_OPTIONS = Object.freeze([
  { food_name: "cooked_white_rice", label: "White rice (cooked)" },
  { food_name: "brown_rice_cooked", label: "Brown rice (cooked)" },
  { food_name: "rice_chicken_bowl", label: "Chicken rice bowl" },
  { food_name: "cooked_noodles", label: "Noodles (cooked)" },
  { food_name: "cooked_pasta", label: "Pasta (cooked)" },
  { food_name: "white_bread", label: "White bread" },
  { food_name: "whole_wheat_bread", label: "Whole-wheat bread" },
  { food_name: "oatmeal_cooked", label: "Oatmeal (cooked)" },
  { food_name: "grilled_chicken_breast", label: "Grilled chicken breast" },
  { food_name: "beef_stir_fry", label: "Beef stir-fry" },
  { food_name: "pork_belly_braised", label: "Braised pork belly" },
  { food_name: "salmon_cooked", label: "Salmon (cooked)" },
  { food_name: "shrimp_cooked", label: "Shrimp (cooked)" },
  { food_name: "boiled_egg", label: "Boiled egg" },
  { food_name: "fried_egg", label: "Fried egg" },
  { food_name: "tofu_firm", label: "Firm tofu" },
  { food_name: "steamed_broccoli", label: "Steamed broccoli" },
  { food_name: "boiled_potato", label: "Boiled potato" },
  { food_name: "french_fries", label: "French fries" },
  { food_name: "lettuce", label: "Lettuce" },
  { food_name: "tomato", label: "Tomato" },
  { food_name: "cucumber", label: "Cucumber" },
  { food_name: "milk_whole", label: "Whole milk" },
  { food_name: "plain_yogurt", label: "Plain yogurt" },
  { food_name: "banana", label: "Banana" },
  { food_name: "apple", label: "Apple" },
  { food_name: "vegetable_soup", label: "Vegetable soup" },
  { food_name: "milk_tea", label: "Milk tea" },
  { food_name: "cola", label: "Cola" },
]);
