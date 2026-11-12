## 改了什么

<!-- 一两句话说清，例：新增 app/ai 供应商适配层，把照片变成契约 A 的 JSON -->

## 涉及哪些契约字段

<!-- 期望答案是「没有」。若改了，必须在同一个 PR 里附上 docs/00_MAIN_TECHNICAL_ROUTE.md 的修改 -->

- [ ] 没有改契约（§E / §F / §G 均未变）
- [ ] 改了，已在本 PR 内更新 `docs/00_MAIN_TECHNICAL_ROUTE.md`，并说明影响哪些模块

## 怎么测的

<!-- 单测覆盖了哪些分支、手动验证了哪些场景、真实调用跑了几张图 -->

## 跑了哪些命令

```bash
pytest -q
```

## 已知限制 / 待办

<!-- 还没做的、依赖别人的、暂时绕过的，写清楚，别让 Reviewer 猜 -->

---

## Review 检查清单（`docs/00` §I.5）

- [ ] 字段名与 §E 完全一致（没有 `weight`、没有 `calories`、没有 `protein`）
- [ ] 除 `app/routes/**` 和 `app/__init__.py` 外，没有任何模块 import Flask
- [ ] `app/nutrition/**` 里没有任何 HTTP 调用
- [ ] 只有 `app/ai/client.py` import 了 AI SDK
- [ ] 错误路径抛的是 `ApiError` 子类，不是裸 `Exception`
- [ ] 新行为至少有一个测试
- [ ] 没有重复的计算逻辑
- [ ] 不含 `.env`、`.db`、`uploads/*`、任何密钥

## 合并前自查

- [ ] 本地 `pytest` 全绿（没有失败、没有莫名跳过）
- [ ] `git status` 干净，没有把 `__pycache__` / `uploads/` / 真实照片带进来
