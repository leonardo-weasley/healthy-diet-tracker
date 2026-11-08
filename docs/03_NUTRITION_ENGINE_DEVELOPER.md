# 03 — 营养引擎开发指南（成员 3）

> 上位文档：[`00_MAIN_TECHNICAL_ROUTE.md`](00_MAIN_TECHNICAL_ROUTE.md)。冲突时以主路线为准。
> 你是全项目**唯一**能算营养的人。你的输出必须可复现、可测试、可解释到小数点。

## 1. 角色与目标

### 1.1 你的职责

| 你负责 | 你不负责 |
|---|---|
| 设计 `food_database.json` 的格式 | 识别图片（成员2） |
| 建 20–30 条常见食物参考数据 | 调任何外部 API（**绝对禁止**） |
| 食物名匹配（标准 ID / 别名 / 归一化） | 存数据库（成员5） |
| 按公式算卡路里与三大营养素 | 决定界面怎么显示（成员4） |
| 未匹配、缺重量、非法重量的处理 | 改契约（需全组同意） |
| 纯函数 + 单元测试 | — |

### 1.2 最终交付物（一句话）

> `calculate_meal_nutrition(foods)` 把契约 A 的 `foods` 列表变成契约 C 的 `items` + `totals` + `warnings`，数值可复现到 0.01，未知食物只进 warnings、绝不静默替代。

### 1.3 成功标准

- 180 g `cooked_white_rice` 恒等于 `234.0 kcal / 4.86 g 蛋白 / 50.76 g 碳水 / 0.54 g 脂肪`。
- 同一输入调用 3 次结果完全相同（无随机、无时间、无网络）。
- 一条未匹配不影响其他条目计算。
- 12 条单元测试全绿，不需要 Key、不需要数据库。

---

## 2. 要构建什么

### 2.1 必须实现

1. **数据文件** `food_database.json`：≥20 条，字段固定（§5.1）。
2. **加载与索引** `load_food_index()`：启动读一次，建 `{food_name: entry}` 字典，同时注册 `aliases`。
3. **匹配** `match_food(food_name)`：精确 → 归一化 → 别名，三步，命中即停。
4. **单项计算** `calculate_food_nutrition(food_name, weight_g)`：`weight/100 × per100`。
5. **整餐计算** `calculate_meal_nutrition(foods)`：循环 + 汇总 + 收集 warnings。
6. **取整**：卡路里 1 位、宏量 2 位，合计最后一次性取整。
7. **单元测试**：§9 的 12 条。

### 2.2 明确不做

- ❌ 不调 USDA API（数据是**离线抄好**的，运行时只读本地文件）
- ❌ 不做模糊匹配 / 拼音 / 语义相似度 / "最像的那条"
- ❌ 不做份量推断（那是成员2 的事）
- ❌ 不写数据库（`food` 表由成员5 从你的 JSON 导入）
- ❌ 不在计算里塞业务判断（比如"超过 3000 kcal 就警告"——属 v2）

### 2.3 遇到问题时的判断原则

| 情况 | 正确做法 | 错误做法 |
|---|---|---|
| AI 给的名字库里没有 | 跳过 + `food_not_matched` | 猜一个最像的 |
| 重量是 `null` | 跳过 + `missing_weight` | 默认 100 g |
| 重量是 0 或负数 | 跳过 + `invalid_weight` | 当 0 卡处理 |
| 只认出部分食物 | 算出能算的，warnings 记录其余 | 整单报错 |
| 一条都算不出 | 返回 `items: []`、`totals` 全 0 | 抛异常让接口 500 |

---

## 3. 技术要用的东西

### 3.1 依赖

```bash
pip install "pydantic>=2.6" "pytest>=8.0"
```

> 你不需要 Flask、不需要 requests、不需要数据库驱动。这是本模块最大的优势：**零外部依赖**。

### 3.2 数据来源

| 项 | 值 |
|---|---|
| 数据源 | [USDA FoodData Central](https://fdc.nal.usda.gov/) |
| 取哪几个字段 | Energy (kcal)、Protein、Carbohydrate by difference、Total lipid (fat) |
| 基准 | **每 100 g 可食部** |
| 必须记录 | 烹饪状态（生/熟）——白米生熟差约 3 倍 |
| 是否联网 | 查数据时联网一次，之后写进 JSON，**运行时绝不联网** |

### 3.3 需要理解的概念

| 概念 | 用途 |
|---|---|
| 纯函数 | 同样输入永远同样输出，测试才能断言 |
| 线性换算 | `weight/100 * per100`，没有更复杂的公式 |
| 浮点误差 | 用 `Decimal` 做乘加，最后再转 `float` |
| 字典索引 | O(1) 查表，20 条也够快，但写成正确形态 |
| 归一化 | `"Cooked White Rice "` → `cooked_white_rice` |

---

## 4. 你拥有的文件

```text
app/nutrition/__init__.py
app/nutrition/food_database.json     # 你的核心资产（20–30 条）
app/nutrition/food_repository.py     # load_food_index()
app/nutrition/food_matcher.py        # match_food()
app/nutrition/calculator.py          # calculate_food_nutrition / calculate_meal_nutrition
app/nutrition/schemas.py             # NutritionItem / NutritionResult（必须有）
tests/unit/test_calculator.py
tests/unit/test_food_matcher.py
```

### 4.1 别人怎么用你

| 他人 | 用法 | 禁止 |
|---|---|---|
| 成员1 | `calculate_meal_nutrition(foods)`；必要时 `match_food(name)` | 在路由里重写公式 |
| 成员2 | 保证 `food_name` 长成你库里有的样子 | 改你的库 |
| 成员5 | 用 `scripts/seed_foods.py` 把 JSON 导进 `food` 表 | 在 DB 里二次计算 |
| 成员4 | 直接展示 `totals` | 在前端重算 |

**接口边界**：别人只允许 import `calculate_meal_nutrition` 和 `match_food`；不要让他们 import 你的内部函数。

---

## 5. 输入输出契约

### 5.1 你的数据文件格式

```json
{
  "schema_version": "1.0",
  "source_note": "Values per 100 g edible portion. USDA FoodData Central, accessed 2026-11.",
  "foods": [
    {
      "food_name": "cooked_white_rice",
      "display_name": "白米饭（熟）",
      "calories_per_100g": 130,
      "protein_per_100g": 2.7,
      "carbs_per_100g": 28.2,
      "fat_per_100g": 0.3,
      "source": "USDA",
      "aliases": ["white_rice", "rice", "steamed_rice"],
      "is_verified": 1
    }
  ]
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `food_name` | string | 是 | `^[a-z0-9_]+$`，全表唯一，≤60 字符 |
| `display_name` | string | 是 | 1–100 字符，可中文 |
| `calories_per_100g` | number | 是 | `0–900` |
| `protein_per_100g` | number | 是 | `0–100` |
| `carbs_per_100g` | number | 是 | `0–100` |
| `fat_per_100g` | number | 是 | `0–100` |
| `source` | string | 是 | `USDA` / `local` / `custom` |
| `aliases` | array[string] | 否 | 小写，不得与其他 `food_name` 冲突 |
| `is_verified` | 0/1 | 是 | 人工核对过填 1 |

### 5.2 初始 29 条数据（可直接用，核对后把 `is_verified` 改 1）

| food_name | display_name | kcal | protein | carbs | fat | source |
|---|---|---|---|---|---|---|
| cooked_white_rice | 白米饭（熟） | 130 | 2.7 | 28.2 | 0.3 | USDA |
| brown_rice_cooked | 糙米饭（熟） | 123 | 2.7 | 25.6 | 1.0 | USDA |
| rice_chicken_bowl | 鸡肉饭碗 | 180 | 8.0 | 22.0 | 6.0 | local |
| cooked_noodles | 面条（熟） | 138 | 4.5 | 25.0 | 2.1 | local |
| cooked_pasta | 意面（熟） | 158 | 5.8 | 30.9 | 0.9 | USDA |
| white_bread | 白面包 | 265 | 9.0 | 49.0 | 3.2 | USDA |
| whole_wheat_bread | 全麦面包 | 247 | 13.0 | 41.0 | 3.4 | USDA |
| oatmeal_cooked | 燕麦粥（熟） | 71 | 2.5 | 12.0 | 1.5 | USDA |
| grilled_chicken_breast | 烤鸡胸肉 | 165 | 31.0 | 0.0 | 3.6 | USDA |
| beef_stir_fry | 炒牛肉 | 250 | 26.0 | 3.0 | 15.0 | local |
| pork_belly_braised | 红烧肉 | 518 | 9.0 | 3.0 | 53.0 | local |
| salmon_cooked | 三文鱼（熟） | 206 | 22.1 | 0.0 | 12.4 | USDA |
| shrimp_cooked | 虾（熟） | 99 | 24.0 | 0.2 | 0.3 | USDA |
| boiled_egg | 水煮蛋 | 155 | 12.6 | 1.1 | 10.6 | USDA |
| fried_egg | 煎蛋 | 196 | 13.6 | 0.8 | 14.8 | USDA |
| tofu_firm | 北豆腐 | 144 | 17.3 | 2.8 | 8.7 | USDA |
| steamed_broccoli | 蒸西兰花 | 35 | 2.4 | 7.2 | 0.4 | USDA |
| boiled_potato | 水煮土豆 | 87 | 1.9 | 20.1 | 0.1 | USDA |
| french_fries | 炸薯条 | 312 | 3.4 | 41.4 | 14.7 | USDA |
| lettuce | 生菜 | 15 | 1.4 | 2.9 | 0.2 | USDA |
| tomato | 番茄 | 18 | 0.9 | 3.9 | 0.2 | USDA |
| cucumber | 黄瓜 | 15 | 0.7 | 3.6 | 0.1 | USDA |
| milk_whole | 全脂牛奶 | 61 | 3.2 | 4.8 | 3.3 | USDA |
| plain_yogurt | 原味酸奶 | 61 | 3.5 | 4.7 | 3.3 | USDA |
| banana | 香蕉 | 89 | 1.1 | 22.8 | 0.3 | USDA |
| apple | 苹果 | 52 | 0.3 | 13.8 | 0.2 | USDA |
| vegetable_soup | 蔬菜汤 | 30 | 1.5 | 4.0 | 0.8 | local |
| milk_tea | 奶茶 | 90 | 1.0 | 16.0 | 2.5 | local |
| cola | 可乐 | 42 | 0.0 | 10.6 | 0.0 | local |

> 上表是近似值。提交前至少抽查 10 条与 USDA 原文核对并标 `is_verified: 1`；答辩被问"数据哪来的"要答得出。

### 5.3 输入（来自成员2 的契约 A `foods`）

```json
[
  {
    "food_name": "cooked_white_rice",
    "display_name": "White rice",
    "estimated_weight_g": 180.0,
    "confidence": 0.95,
    "notes": null
  },
  {
    "food_name": null,
    "display_name": "某种深色酱汁",
    "estimated_weight_g": null,
    "confidence": 0.42,
    "notes": "Cannot identify"
  }
]
```

**注意**：你读的是 `estimated_weight_g`，不要读 `weight_g`（那是**输出**字段）。

### 5.4 输出（契约 C）

```json
{
  "schema_version": "1.0",
  "items": [
    {
      "food_name": "cooked_white_rice",
      "display_name": "White rice",
      "weight_g": 180.0,
      "calories_kcal": 234.0,
      "protein_g": 4.86,
      "carbs_g": 50.76,
      "fat_g": 0.54,
      "food_data_source": "USDA"
    }
  ],
  "totals": {
    "calories_kcal": 234.0,
    "protein_g": 4.86,
    "carbs_g": 50.76,
    "fat_g": 0.54
  },
  "warnings": ["food_not_matched: 某种深色酱汁", "missing_weight: 某种深色酱汁"]
}
```

### 5.5 错误行为

| 情况 | 行为 |
|---|---|
| 输入不是 list | `ValueError`（这是程序员错误，不是用户错误） |
| 单项未匹配 | 不抛，进 warnings |
| 单项缺重量 | 不抛，进 warnings |
| 全部未匹配 | 返回 `items: []`，`totals` 全 0，warnings 齐全 |
| 重量超过 5000 | 视为非法，进 warnings（`invalid_weight`） |

---

## 6. 必须实现的函数接口

```python
# app/nutrition/food_repository.py
def load_food_index() -> dict[str, dict]:
    """读 food_database.json → {food_name: entry}，并把 aliases 也注册进去。
       只在首次调用时读文件，之后返回缓存。"""

# app/nutrition/food_matcher.py
def match_food(food_name: str) -> dict | None:
    """精确 → 归一化 → 别名。命中返回 entry，否则 None。
       未知输入不抛异常。"""

# app/nutrition/calculator.py
def calculate_food_nutrition(food_name: str, weight_g: float) -> dict:
    """单项计算。返回 items[] 里的一条（不含 schema_version）。
       抛出：FoodNotFound（未匹配）、InvalidWeight（重量不合法）"""

def calculate_meal_nutrition(foods: list[dict]) -> dict:
    """输入契约 A 的 foods 列表，返回契约 C。
       单条失败不中断，全部失败也不抛异常。"""
```

### 6.1 返回条目里必须有的键

`match_food()` 返回的 entry 至少包含：

```text
food_name, display_name, calories_per_100g, protein_per_100g,
carbs_per_100g, fat_per_100g, source, aliases
```

> `match_food()` **不返回**数据库主键。`food_id` 由成员5 在保存时按 `food_name` 解析。

### 6.2 计算顺序（严格按此）

```
for each food in foods:
    name   = food["food_name"]
    weight = food["estimated_weight_g"]

    if name is None          → warning "food_not_matched: {display_name}", continue
    entry = match_food(name) → None 则 warning "food_not_matched: {name}", continue
    if weight is None        → warning "missing_weight: {display_name}", continue
    if not (0 < weight <= 5000) → warning "invalid_weight: {display_name}", continue

    计算四个值，加入 items
合计 = 未取整求和 → 一次性取整
```

---

## 7. 实施步骤

### 7.0 六周交付节奏（你的部分）

| 周 | 你要交付 | 验收 |
|---|---|---|
| 1 | `food_database.json` 骨架 + 10 条数据；`match_food` 骨架；3 条测试 | 能按名字查到条目 |
| 2 | 29 条数据齐；`calculate_food_nutrition`；取整规则；8 条测试 | 180 g 米饭 == 234.0 |
| 3 | `calculate_meal_nutrition` + warnings 全规则；12 条测试 | 用 mock AI 结果能算出整餐 |
| 4 | 配合联调：修正边界（缺重量、非法重量）；性能无关 | 前端改重量后数字跟着变 |
| 5 | 补充测试；核对数据源；标注 `is_verified` | 抽查 10 条与 USDA 一致 |
| 6 | 冻结数据；准备"数据来源"答辩材料 | 能解释每条数值出处 |

### 步骤 1：建数据文件（第 1 周）

1. 照 §5.1 建 `food_database.json`，先填 10 条。
2. 每条都写 `display_name`、`aliases`、`is_verified: 0`。
3. 用编辑器 JSON 校验，确保没有尾逗号。

**完成标准**：`python -c "import json;print(len(json.load(open('app/nutrition/food_database.json'))['foods']))"` 输出 ≥10。

### 步骤 2：加载与匹配（第 1 周末）

1. `load_food_index()`：读文件 → 建字典 → 注册别名 → 缓存。
2. `match_food()`：三步匹配。
3. 写 3 条测试：精确、归一化、未匹配。

**完成标准**：`match_food("Cooked White Rice")` 返回 `cooked_white_rice` 的条目。

### 步骤 3：单项计算（第 2 周）

1. `calculate_food_nutrition()`：`weight/100 × per100`，用 `Decimal`。
2. 按 §8.3 取整。
3. 写 4 条测试：米饭、鸡胸、零卡食物、精度。

**完成标准**：`calculate_food_nutrition("cooked_white_rice", 180)["calories_kcal"] == 234.0`。

### 步骤 4：整餐计算（第 3 周）

1. 按 §6.2 的循环实现。
2. 实现三种 warning 前缀。
3. 实现"全部失败不抛异常"。
4. 写 5 条测试：合计、部分失败、全部失败、空列表、不中断。

**完成标准**：契约 A 的 `mock_ai_result.json` 直接喂进去得到契约 C。

### 步骤 5：与上下游对齐（第 3–4 周）

1. 与成员2 确认：他的 `food_name` 至少 10 个能命中你的库。
2. 与成员5 确认：他导入 JSON 时字段名一致。
3. 与成员1 确认：`items` 里没有 `food_id` 也没问题（他自己不补，仓储层解析）。

### 步骤 6：数据核对（第 5 周）

1. 抽查 10 条与 USDA 页面比对，改 `is_verified: 1`。
2. 记录每条数据的访问日期（写在 `source_note`）。
3. 把差异超过 5% 的条目修正。

---

## 8. 代码示例

### 8.0 Pydantic 模型（`app/nutrition/schemas.py`，**必须有**）

```python
from typing import Literal

from pydantic import BaseModel, Field


class NutritionItem(BaseModel):
    """契约 C 的 items[] 里的一条。"""
    food_name: str = Field(min_length=1, max_length=60)
    display_name: str = Field(min_length=1, max_length=100)
    weight_g: float = Field(gt=0, le=5000)
    calories_kcal: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    food_data_source: str = Field(default="local")


class NutritionResult(BaseModel):
    """契约 C 的完整返回值。"""
    schema_version: Literal["1.0"] = "1.0"
    items: list[NutritionItem] = Field(default_factory=list, max_length=20)
    totals: dict
    warnings: list[str] = Field(default_factory=list)
```

> 这个模型用于**运行时自检**：`1` 计算完成后用 `NutritionResult.model_validate(result)` 确认形状正确；2 在测试中代替手工断言逐个字段。与 `ai/schemas.py` 的 `AIAnalysis` 对应，保证两端 Pydantic 校验风格一致。

### 8.1 加载与索引

```python
# app/nutrition/food_repository.py
import json
from pathlib import Path

_DATA_PATH = Path(__file__).with_name("food_database.json")
_CACHE: dict[str, dict] | None = None


def load_food_index() -> dict[str, dict]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    index: dict[str, dict] = {}
    for entry in raw["foods"]:
        index[entry["food_name"]] = entry
    for entry in raw["foods"]:
        for alias in entry.get("aliases") or []:
            index.setdefault(alias.lower(), entry)

    _CACHE = index
    return _CACHE


def reset_cache() -> None:
    """仅供测试使用。"""
    global _CACHE
    _CACHE = None
```

### 8.2 匹配

```python
# app/nutrition/food_matcher.py
import re

from .food_repository import load_food_index


def _normalize(name: str) -> str:
    return re.sub(r"[\s\-]+", "_", name.strip().lower())


def match_food(food_name: str) -> dict | None:
    if not food_name:
        return None
    index = load_food_index()

    if food_name in index:                     # 1. 精确
        return index[food_name]

    normalized = _normalize(food_name)         # 2. 归一化
    if normalized in index:
        return index[normalized]

    return None                                # 3. 别名已在 index 里注册
```

> 别名之所以"免费"，是因为 `load_food_index()` 已经把 `aliases` 放进了同一个字典。这样匹配只有一次查表，没有额外分支。

### 8.3 单项计算与取整

```python
# app/nutrition/calculator.py
from decimal import Decimal, ROUND_HALF_UP

from ..utils.errors import FoodNotFound, InvalidWeight
from .food_matcher import match_food

MAX_WEIGHT_G = 5000


def _round(value: Decimal, places: int) -> float:
    quant = Decimal(1).scaleb(-places)
    return float(value.quantize(quant, rounding=ROUND_HALF_UP))


def calculate_food_nutrition(food_name: str, weight_g: float) -> dict:
    entry = match_food(food_name)
    if entry is None:
        raise FoodNotFound(f"Food not found: {food_name}",
                           details={"food_name": food_name})
    if not isinstance(weight_g, (int, float)) or not (0 < weight_g <= MAX_WEIGHT_G):
        raise InvalidWeight(f"Invalid weight: {weight_g}",
                            details={"weight_g": weight_g})

    ratio = Decimal(str(weight_g)) / Decimal(100)
    return {
        "food_name": entry["food_name"],
        "display_name": entry["display_name"],     # 单独调用时用库里的名字；
                                                   # 整餐计算时会被用户的 display_name 覆盖
        "weight_g": float(weight_g),
        "calories_kcal": _round(ratio * Decimal(str(entry["calories_per_100g"])), 1),
        "protein_g": _round(ratio * Decimal(str(entry["protein_per_100g"])), 2),
        "carbs_g": _round(ratio * Decimal(str(entry["carbs_per_100g"])), 2),
        "fat_g": _round(ratio * Decimal(str(entry["fat_per_100g"])), 2),
        "food_data_source": entry.get("source", "local"),
    }
```

> **注意 `display_name` 的来源**：契约 C 里 `items[].display_name` 是"用户看到的那个名字"（用户可能改过），所以 `calculate_meal_nutrition()` 用的是**输入里的** `display_name`，不是库里的。上面这个单项函数是给"按食物名直接查"的场景用的（比如测试或未来的手动录入），两者不要混。

### 8.4 整餐计算

```python
# app/nutrition/calculator.py（续）
_TOTAL_KEYS = ("calories_kcal", "protein_g", "carbs_g", "fat_g")


def calculate_meal_nutrition(foods: list[dict]) -> dict:
    if not isinstance(foods, list):
        raise ValueError("foods must be a list")

    items: list[dict] = []
    warnings: list[str] = []
    exact = {key: Decimal(0) for key in _TOTAL_KEYS}

    for food in foods:
        name = food.get("food_name")
        display = food.get("display_name") or "unknown"
        weight = food.get("estimated_weight_g")

        if not name:
            warnings.append(f"food_not_matched: {display}")
            continue
        if weight is None:
            warnings.append(f"missing_weight: {display}")
            continue
        if not isinstance(weight, (int, float)) or not (0 < weight <= MAX_WEIGHT_G):
            warnings.append(f"invalid_weight: {display}")
            continue

        entry = match_food(name)
        if entry is None:
            warnings.append(f"food_not_matched: {name}")
            continue

        ratio = Decimal(str(weight)) / Decimal(100)
        item = {
            "food_name": entry["food_name"],
            "display_name": display,
            "weight_g": float(weight),
            "calories_kcal": ratio * Decimal(str(entry["calories_per_100g"])),
            "protein_g": ratio * Decimal(str(entry["protein_per_100g"])),
            "carbs_g": ratio * Decimal(str(entry["carbs_per_100g"])),
            "fat_g": ratio * Decimal(str(entry["fat_per_100g"])),
            "food_data_source": entry.get("source", "local"),
        }
        for key in _TOTAL_KEYS:
            exact[key] += item[key]

        items.append({
            **item,
            "calories_kcal": _round(item["calories_kcal"], 1),
            "protein_g": _round(item["protein_g"], 2),
            "carbs_g": _round(item["carbs_g"], 2),
            "fat_g": _round(item["fat_g"], 2),
        })

    totals = {key: _round(exact[key], 1 if key == "calories_kcal" else 2)
              for key in _TOTAL_KEYS}

    return {
        "schema_version": "1.0",
        "items": items,
        "totals": totals,
        "warnings": warnings,
    }
```

**关键点**：`exact` 累加的是未取整的 `Decimal`，`items` 里放的是取整后的值——所以 `totals` 不会因为多次取整而漂移。

---

## 9. 测试要求

### 9.1 12 条用例

| # | 用例 | 输入 | 期望 |
|---|---|---|---|
| N1 | 米饭单项 | `cooked_white_rice`, 180 | `calories_kcal == 234.0`, `protein_g == 4.86` |
| N2 | 碳水精度 | 同上 | `carbs_g == 50.76`（`approx`） |
| N3 | 两项合计 | 米饭 180 + 鸡胸 120 | `totals.calories_kcal == 432.0` |
| N4 | 合计蛋白 | 同上 | `totals.protein_g == 42.06` |
| N5 | 零卡食物 | `cola`, 330 | `calories_kcal == 138.6` |
| N6 | 精确匹配 | `cooked_white_rice` | 命中 |
| N7 | 归一化匹配 | `"Cooked White Rice"` | 命中 |
| N8 | 别名匹配 | `"white_rice"` | 命中 `cooked_white_rice` |
| N9 | 未匹配 | `"dragon_fruit"` | `match_food` 返回 None；整餐进 warnings |
| N10 | 缺重量 | `estimated_weight_g: null` | 跳过 + `missing_weight`，`items` 不含该项 |
| N11 | 非法重量 | `weight_g: -10` / `0` / `6000` | 跳过 + `invalid_weight` |
| N12 | 纯函数 | 同输入跑 3 次 | 三次 `json.dumps` 完全相同 |

### 9.2 测试示例

```python
# tests/unit/test_calculator.py
import json

import pytest

from app.nutrition.calculator import calculate_food_nutrition, calculate_meal_nutrition


def test_rice_180g():
    result = calculate_food_nutrition("cooked_white_rice", 180)
    assert result["calories_kcal"] == pytest.approx(234.0, abs=0.01)
    assert result["protein_g"] == pytest.approx(4.86, abs=0.01)
    assert result["carbs_g"] == pytest.approx(50.76, abs=0.01)
    assert result["fat_g"] == pytest.approx(0.54, abs=0.01)


def test_meal_totals_and_partial_failure():
    foods = [
        {"food_name": "cooked_white_rice", "display_name": "White rice",
         "estimated_weight_g": 180.0},
        {"food_name": "grilled_chicken_breast", "display_name": "Chicken",
         "estimated_weight_g": 120.0},
        {"food_name": None, "display_name": "酱汁", "estimated_weight_g": None},
    ]
    result = calculate_meal_nutrition(foods)

    assert len(result["items"]) == 2
    assert result["totals"]["calories_kcal"] == pytest.approx(432.0, abs=0.01)
    assert any(w.startswith("food_not_matched:") for w in result["warnings"])


def test_unknown_food_does_not_raise():
    result = calculate_meal_nutrition(
        [{"food_name": "dragon_fruit", "display_name": "火龙果",
          "estimated_weight_g": 100.0}]
    )
    assert result["items"] == []
    assert result["totals"]["calories_kcal"] == 0.0
```

### 9.3 判定标准

- 12 条全绿。
- `grep -rn "requests\|google\|openai\|urllib" app/nutrition` **零命中**。
- 不需要 `.env`、不需要数据库就能跑。

---

## 10. 集成说明

### 10.1 你的依赖

| 依赖 | 提供者 | 没完成时 |
|---|---|---|
| 契约 A 的 `foods` 结构 | 成员2 | 用 `mock_ai_result.json` 自己造 |
| `FoodNotFound` / `InvalidWeight` 异常类 | 成员1 | 按 `00` §G.2 签名先建，最终以他的为准 |

**你不依赖**：数据库、Flask、任何网络。

### 10.2 依赖你的

| 模块 | 用你什么 | 注意 |
|---|---|---|
| 成员1 | `calculate_meal_nutrition()` | 你要保证"全失败时不抛异常"，让他统一抛 `FOOD_NOT_FOUND` |
| 成员5 | 用 `seed_foods.py` 读你的 JSON 导入 `food` 表 | 你的 `food_name` 是他表里的唯一键 |
| 成员4 | 间接：通过 API 拿 `totals` | 不需要知道你的存在 |

### 10.3 什么时候合并

| 时机 | 内容 |
|---|---|
| 第 1 周末 | JSON 骨架 + 10 条数据 + `match_food` |
| 第 2 周末 | 单项计算 + 取整 + 8 条测试 |
| 第 3 周末 | 整餐计算 + warnings + 12 条测试 |
| 第 5 周 | 数据核对与 `is_verified` 标注 |

### 10.4 接口要变怎么办

- **改 `food_database.json` 字段名**：等同契约变更，先改 `00` §E.3（`food_data_source`）与 §C，再通知成员5（导入脚本）与成员1。
- **新增食物**：直接提 PR，不需要契约变更。
- **改某条数值**：必须写明理由与来源链接；历史餐食不受影响（快照），但新数据会变。

---

## 11. GitHub 工作流

```bash
git checkout develop && git pull
git checkout -b feature/nutrition
git add app/nutrition tests/unit/test_calculator.py tests/unit/test_food_matcher.py
git commit -m "feat(nutrition): add 29 reference foods and meal calculator"
git push -u origin feature/nutrition
```

提交示例：
- `feat(nutrition): add food database with 29 entries`
- `feat(nutrition): implement per-100g calculation with decimal rounding`
- `fix(nutrition): treat zero weight as invalid instead of zero calories`
- `test(nutrition): cover unmatched and missing weight paths`

PR 描述必须包含：
1. 数据来源链接（新增/修改条目时）；
2. 受影响的字段（预期"没有"）；
3. `pytest tests/unit -q` 输出。

---

## 12. 最终交付清单

### 12.1 代码

- [ ] `food_database.json` ≥20 条（建议 29），每条字段齐全、`food_name` 唯一
- [ ] `load_food_index()` 带缓存，`aliases` 已注册
- [ ] `match_food()` 三步匹配，未知返回 `None`
- [ ] `calculate_food_nutrition()` 用 `Decimal`，取整符合 §8.3
- [ ] `calculate_meal_nutrition()` 按 §6.2 顺序，三种 warning 前缀正确
- [ ] 合计用未取整值累加后一次性取整

### 12.2 测试

- [ ] 12 条用例全绿
- [ ] 无需 Key / 网络 / 数据库
- [ ] `grep` 确认无外部调用

### 12.3 数据

- [ ] 抽查 10 条与 USDA 一致，标 `is_verified: 1`
- [ ] `source_note` 写访问日期
- [ ] 每条 `display_name` 带烹饪状态（能带则带）

### 12.4 自检问题

1. 为什么不能用已取整的单项值相加得到 `totals`？
2. `estimated_weight_g` 为 `null` 时，你的 `items` 里会多一条吗？（不会）
3. `food_name` 有值但库里没有，返回什么？整单会失败吗？（不会）
4. 你的模块能不能在没有任何网络的情况下跑测试？（必须能）
5. 如果把米饭数值从 130 改成 140，历史餐食的总热量会变吗？（不会，是快照）
