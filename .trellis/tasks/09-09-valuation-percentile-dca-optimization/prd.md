# brainstorm: 估值分位触发的分散定投优化

## Goal

通过历史滚动回测寻找稳健的估值分位触发阈值，同时保留持续、分散的基础定投，避免把策略退化为等待单一买点或一次性集中投入。

## What I Already Know

- 用户希望回测出一个合适的历史估值分位点。
- 风险约束是资金仍应分散定投，而不是低估时一次性投入。
- 项目已有月/周定投、逐笔现金流 XIRR、估值月末分位和滚动持有收益基础能力。
- 当前固定定投模型没有现金储备、估值信号或阈值优化。

## Assumptions (Temporary)

- 分位信号用于调整投入强度，不用于完全停止基础定投。
- MVP 优化一个阈值参数，其他参数先固定，避免过拟合。
- 普通月度定投是基准策略，比较时两者外部现金流完全一致。

## Open Questions

- 采用“基础定投不断档、低估时加码”，还是“达到阈值后才启动一段定投计划”？

## Requirements (Evolving)

- 使用随时间扩展的历史窗口计算当期分位，禁止使用未来数据。
- 候选阈值使用可解释的小网格搜索，不追逐连续参数的样本内极值。
- 使用多个滚动起始窗口，并保留一个时间上靠后的样本外区间。
- 所有策略与普通定投拥有相同的外部现金流、回测区间和收益指数。
- 结果报告稳健阈值区间，而不只报告单一最优点。

## Recommended Objective

最大化样本外 `策略 XIRR - 普通定投 XIRR` 的中位数，同时约束最差 20% 样本的下行表现不显著差于普通定投。

## Recommended DCA Constraints

- 每月固定投入当月预算的 70%，不得跳过。
- 剩余 30% 进入现金储备，仅在达到便宜分位时加码。
- 单月股票投入不超过正常月预算的 2 倍。
- 期末未投入现金计入总资产，不能从结果中消失。
- 至少需要 24 个完整滚动回测窗口。

## Acceptance Criteria (Evolving)

- [ ] 历史信号没有前视偏差。
- [ ] 候选阈值逐个给出样本外中位超额 XIRR、20% 分位、CVaR、最差值和胜率。
- [ ] 普通定投与优化策略的外部现金流完全相同。
- [ ] 基础定投不断档，单月投入不超过配置上限。
- [ ] 样本不足时不输出“最优阈值”。
- [ ] 返回稳健阈值区间及推荐值，并披露过拟合和数据覆盖风险。

## Definition of Done

- Calculation and service tests cover cash reserve, trigger direction, no-lookahead percentile, rolling windows, and sample insufficiency.
- Relevant syntax, unit, API, and browser smoke checks pass.
- UI explains objective, constraints, baseline, sample period, and source methodology.
- Existing fixed DCA remains available and unchanged as a baseline.

## Out of Scope

- 强化学习、遗传算法或逐日自由仓位优化。
- 多指数之间的资产配置权重优化。
- 交易税费、滑点和融资杠杆，除非后续明确纳入。
- 用全历史分位回填过去信号。

## Research References

- [`research/optimization-formulation.md`](research/optimization-formulation.md) — 优化问题分类、策略形式、目标函数、约束和样本外验证协议。

## Technical Notes

- Likely backend files: `app/calculations.py`, `app/service.py`, `app/main.py`.
- Likely frontend files: `static/index.html`, `static/app.js`, and DCA styles.
- The prior EPS planning task is not being implemented; this is a separate
  planning task.
