# 成员 1 后端交接

本分支基于本地取得的 origin/main（d596b1511de124192c906ef932fc464980776e57），保留已合入的成员 2 AI 代码、团队规范和 PR 模板。

## 本次后端内容

- 应用工厂、配置、6 个业务 API、4 个模板占位页面。
- 上传大小/格式/内容检查、EXIF 修正、缩放和安全路径处理。
- 请求模型、A/C/D/E 边界检查、错误信封、时区和服务编排。
- 明确隔离的演示替身，以及后端测试和六接口演示。
- app/extensions.py 和 tests/conftest.py 提供联调骨架，待成员 5 接管并扩展。

## 与仓库现有内容的关系

不修改 app/ai、AI 测试、scripts 或团队 docs/00–05。保留仓库目前的 OpenAI SDK/DeepSeek 供应商配置，不用早期离线包的 Gemini 配置覆盖它。

BACKEND_MODE=demo 默认使用完整替身。BACKEND_MODE=real 会同时导入 AI、营养、数据库；后两者尚未提供，所以当前不能宣称真实流程已接通。

主路线中营养函数输入使用 estimated_weight_g，确认请求使用 weight_g，本服务层进行字段适配。C 的最后取整 totals 随 meal_data 传给仓储，需成员 3/5 确认取整与保存约定。分页在服务层处理，仓储 get_meals 只接收两个日期参数。

## 验证方式

```text
python -m pytest -q
python demo.py
```

测试使用替身，不要求真实 Key 或联网。真实模块识别、持久化、回滚、级联和浏览器联合验收仍需各成员配合。

## 本次本地验证

2026-11-07：完整仓库测试 140 项通过、1 项跳过；跳过项是原有 AI 白名单对照测试，因成员 3 的 food_database.json 尚未提供。后端 102 项测试通过，六 API 演示通过。未修改或删除任何 AI 测试。
