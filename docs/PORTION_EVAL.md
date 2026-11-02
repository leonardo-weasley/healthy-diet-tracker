# 识别与份量回归表

> 由 `scripts/evaluate_portions.py` 生成，模型 `deepseek-flash`，温度 0，思考模式关闭。
> 生成时间：2026-11-02 21:44

| 照片 | 菜品 | 状态 | 复现性 | 耗时 | 识别结果（名称 / food_name 重量） |
|---|---|---|---|---|---|
| first-real-food.jpeg | 红烧肥肠（大肠） | partial | 稳定 | 1643 ms | 红烧猪大肠（肥肠）/null 220g |
| go-believe.jpeg | 未标注 | partial | 稳定 | 1430 ms | 小笼包（蒸饺）/null 300g<br>酱鸭／卤鸭/null 150g<br>生肉（待涮肉片）/null 80g |
| placeholder.jpg | 纯灰图（负样本） | error | 稳定 | 680 ms | - |
| red-braised-pork.jpg | 红烧肉 | success | 稳定 | 900 ms | 红烧肉/pork_belly_braised 350g |
| rice steamed-fish stir-fried-greens.jpeg | 米饭 + 清蒸鱼 + 炒青菜 | partial | 稳定 | 1249 ms | 白米饭/cooked_white_rice 180g<br>清蒸鱼/null 200g<br>蒜蓉炒青菜/null 120g |
| rice.jpeg | 白米饭 | success | 稳定 | 941 ms | 白米饭/cooked_white_rice 200g |
| scrambled-egg-with-tomatoes.jpg | 番茄炒蛋 | success | 波动 | 947 ms | 番茄炒蛋/fried_egg 300g |

## 汇总

- 照片：7 张，调用 14 次
- 识别项：20 项，命中白名单 8 项

## 已知失败类型

- 白名单外菜品（如肥肠、红烧肉做法差异）→ `food_name` 为 null，需人工补
- 多菜品拼盘容易漏项或把配菜当主菜
- 份量估计偏保守，汤/汁类几乎无法估重
