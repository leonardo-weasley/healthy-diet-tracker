/* =========================================================================
 * food-options.js —— 标准食物下拉清单
 *
 * 这里只保存“食物 ID + 展示名”，**不包含任何营养数值**。
 * 营养计算全部由服务器端 app/nutrition 完成，前端只负责把用户修正后的
 * food_name 原样放进契约 B 的 items[]。
 *
 * 清单与 03_NUTRITION_ENGINE_DEVELOPER.md §5.2 的 29 条参考食物保持一致。
 * 如果成员 3 增删食物，同步更新本文件即可；未收录的 ID 会由 result.js
 * 自动补一个“未收录”选项，不会导致保存失败。
 * ========================================================================= */

window.FOOD_OPTIONS = Object.freeze([
  { food_name: "cooked_white_rice", label: "白米饭（熟）" },
  { food_name: "brown_rice_cooked", label: "糙米饭（熟）" },
  { food_name: "rice_chicken_bowl", label: "鸡肉饭碗" },
  { food_name: "cooked_noodles", label: "面条（熟）" },
  { food_name: "cooked_pasta", label: "意面（熟）" },
  { food_name: "white_bread", label: "白面包" },
  { food_name: "whole_wheat_bread", label: "全麦面包" },
  { food_name: "oatmeal_cooked", label: "燕麦粥（熟）" },
  { food_name: "grilled_chicken_breast", label: "烤鸡胸肉" },
  { food_name: "beef_stir_fry", label: "炒牛肉" },
  { food_name: "pork_belly_braised", label: "红烧肉" },
  { food_name: "salmon_cooked", label: "三文鱼（熟）" },
  { food_name: "shrimp_cooked", label: "虾（熟）" },
  { food_name: "boiled_egg", label: "水煮蛋" },
  { food_name: "fried_egg", label: "煎蛋" },
  { food_name: "tofu_firm", label: "北豆腐" },
  { food_name: "steamed_broccoli", label: "蒸西兰花" },
  { food_name: "boiled_potato", label: "水煮土豆" },
  { food_name: "french_fries", label: "炸薯条" },
  { food_name: "lettuce", label: "生菜" },
  { food_name: "tomato", label: "番茄" },
  { food_name: "cucumber", label: "黄瓜" },
  { food_name: "milk_whole", label: "全脂牛奶" },
  { food_name: "plain_yogurt", label: "原味酸奶" },
  { food_name: "banana", label: "香蕉" },
  { food_name: "apple", label: "苹果" },
  { food_name: "vegetable_soup", label: "蔬菜汤" },
  { food_name: "milk_tea", label: "奶茶" },
  { food_name: "cola", label: "可乐" },
]);
