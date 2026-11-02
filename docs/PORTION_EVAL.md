# 识别与份量回归表

> 由 `scripts/evaluate_portions.py` 生成，模型 `deepseek-flash`，温度 0，思考模式关闭。
> 生成时间：2026-11-02 21:31

| 照片 | 菜品 | 状态 | 复现性 | 耗时 | 识别结果（名称 / food_name 重量） |
|---|---|---|---|---|---|
| first-real-food.jpeg | 红烧肥肠（大肠） | partial | 稳定 | 1452 ms | 红烧猪大肠/null 250g |
| go-believe.jpeg | 未标注 | partial | 波动 | 1327 ms | 小笼包/蒸饺/steamed_bun 300g<br>酱鸭/卤味肉/null 150g<br>生肉/null 80g |
| placeholder.jpg | 纯灰图（负样本） | error | 稳定 | 1182 ms | - |
| red-braised-pork.jpg | 红烧肉 | success | 稳定 | 957 ms | 红烧肉/pork_belly 350g |
| rice steamed-fish stir-fried-greens.jpeg | 米饭 + 清蒸鱼 + 炒青菜 | partial | 波动 | 1288 ms | 清蒸鱼/null 200g<br>清炒小白菜/bok_choy 150g<br>白米饭/cooked_white_rice 150g |
| rice.jpeg | 白米饭 | success | 稳定 | 1100 ms | 白米饭/cooked_white_rice 200g |
| scrambled-egg-with-tomatoes.jpg | 番茄炒蛋 | success | 稳定 | 874 ms | 番茄炒蛋/egg_fried 280g |

## 汇总

- 照片：7 张，调用 14 次
- 识别项：20 项，命中白名单 12 项

## 已知失败类型

- 白名单外菜品（如肥肠、红烧肉做法差异）→ `food_name` 为 null，需人工补
- 多菜品拼盘容易漏项或把配菜当主菜
- 份量估计偏保守，汤/汁类几乎无法估重
