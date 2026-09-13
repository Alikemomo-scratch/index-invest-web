# 历史收益标准差

## Goal

在历史收益研究器已有平均值、中位数等摘要指标的基础上，增加收益标准差，让用户能直观看到相同买入采样频率、持有年限和收益口径下，完整历史样本的离散程度。

## Requirements

- 后端 `return_summary()` 为当前全部完整持有期样本计算总体标准差（分母为 `N`）。
- 标准差基于当前 `measure` 的样本值直接计算：年化视图对应年化收益标准差，累计视图对应累计收益标准差。
- API `summary` 新增 `standard_deviation`，保留两位小数；空样本返回 `null`。
- 前端历史收益统计区新增标准差卡片，并随年化/累计收益切换更新标签和值。
- 收益读取失败时清空标准差展示，不保留旧值。
- README 的功能与计算口径说明补充标准差定义。

## Acceptance Criteria

- [x] `[1, 2, 6]` 的总体标准差按 `sqrt(sum((x-mean)^2) / N)` 计算并保留两位小数。
- [x] 单一样本标准差为 `0.0`，空样本为 `null`。
- [x] 年化收益视图显示“年化收益标准差”，累计收益视图显示“累计收益标准差”。
- [x] 前端显示 API 的 `summary.standard_deviation`，错误态重置为 `—`。
- [x] 既有收益样本筛选、平均值、中位数和图表行为不变。
- [x] 后端单元测试、前端契约测试与 JavaScript 语法检查通过。

## Definition of Done

- 自动化测试与语法检查通过。
- 后端与前端 Trellis 契约同步更新。
- README 说明更新。
- 不纳入或回退其他进行中的股息率、风险溢价、盈利增长及定投优化改动。

## Technical Approach

复用 `return_summary()` 已得到的有效样本值和算术平均值，在后端一次性计算总体标准差；服务层继续透明返回摘要对象。前端沿用现有统计卡片与 `formatPct()`，仅增加稳定 DOM hook 和标签切换逻辑。

## Decision (ADR-lite)

**Context**: “历史收益标准差”可能指样本收益分布的离散程度，也可能指日/月收益序列的年化波动率。

**Decision**: 本功能计算当前图表所展示的全部完整持有期收益样本的总体标准差，不计算底层日/月收益波动率。

**Consequences**: 数值与当前买入频率、持有年限及年化/累计口径完全一致，易于解释；它不等同于证券常见的年化波动率。

## Out of Scope

- 不新增滚动波动率、下行标准差、夏普比率或置信区间。
- 不改变买入点、持有结束点或完整样本筛选规则。
- 不新增第三方依赖。

## Technical Notes

- 数据流：`app/calculations.py` → `app/service.py` 原样携带摘要 → `static/app.js` → `static/index.html`。
- 相关测试：`tests/test_calculations.py`、`tests/test_frontend_contract.py`。
- 相关契约：`.trellis/spec/backend/index-research-contracts.md`、`.trellis/spec/frontend/chart-interactions.md`。
- 工作区存在其他任务的未提交改动；实现必须使用最小补丁保留它们。
- Obsidian Project Development 未检索到与该项目直接匹配的笔记；仅采用 Trellis 与仓库现有契约。
