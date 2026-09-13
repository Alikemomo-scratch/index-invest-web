# brainstorm: 指数盈利增长追踪

## Goal

为当前指数研究器增加一个单一、可比较的核心数据，用来观察指数所代表公司的整体盈利增长，而不是用指数涨跌或估值变化替代盈利变化。

## What I Already Know

- 用户希望用一个数据追踪这些指数对应公司的盈利增长。
- 当前项目已经拥有中证价格指数与历史 PE，可计算指数层隐含 EPS。
- 当前项目的数据契约要求来源、观察日、口径、覆盖和降级状态可追溯。
- 300 红利低波的完整月末样例可计算出 2026-08 隐含 EPS TTM 同比为 -5.71%。

## Assumptions (Temporary)

- 首要目标是观察“指数作为当前投资组合”的盈利周期，而不是逐家公司的盈利归因。
- MVP 使用已实现的数据源，不新增付费 Wind/Bloomberg 依赖。

## Open Questions

- 核心指标应追踪指数整体盈利，还是固定公司样本的同口径盈利？

## Requirements (Evolving)

- 主指标候选为“指数盈利增长（隐含 EPS TTM 同比）”。
- 隐含 EPS 使用价格指数收盘点位除以同日 PE TTM。
- 同比仅使用完整月末并与上年同月末比较。
- 不使用全收益指数计算 EPS，不拼接不同 PE 口径。
- 页面必须披露换仓、权重变化和数据缺口的影响。

## Acceptance Criteria (Evolving)

- [ ] 支持的指数展示最新完整月末盈利同比、观察日、来源和方法标签。
- [ ] 历史图同时支持隐含 EPS 水平和同比增速。
- [ ] PE 缺失、为零或为负时返回不可用，不生成伪数据。
- [ ] 价格、PE 的指数身份和日期不一致时拒绝计算。
- [ ] 300 红利低波固定样例的公式与同比结果有单元测试。

## Definition of Done

- Tests added or updated for calculations and source contracts.
- Relevant lint, syntax, unit, API, and browser smoke checks pass.
- Methodology and coverage disclosure is documented.
- No source is labeled official unless both calculation inputs are official and matched.

## Out of Scope

- 成分股级利润贡献拆解。
- 固定成分股篮子的幸存者偏差校正。
- 分析师一致预期和付费数据源。
- 将隐含 EPS 声称为中证官方直接发布的 EPS。

## Research References

- [`research/index-earnings-growth-options.md`](research/index-earnings-growth-options.md) — 比较隐含 EPS、成分股底层聚合和前瞻一致预期三种方案。

## Technical Notes

- Likely files: `app/calculations.py`, `app/service.py`, `static/app.js`,
  `static/index.html`, and their existing contract tests.
- New planning task is separate from the active dividend-yield coverage task;
  no product code has been changed.
