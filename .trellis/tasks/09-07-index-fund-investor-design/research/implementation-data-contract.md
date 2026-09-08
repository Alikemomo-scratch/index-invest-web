# 实现阶段数据契约与可得性边界

## 已核验的可用路径

### A 股官方数据

AKShare 当前源码显示，中证指数历史行情来自中证官方接口：

`https://www.csindex.com.cn/csindex-home/perf/index-perf`

该接口可按指数代码与日期范围返回价格、成交和滚动市盈率等字段。中证指数估值文件来自官方对象存储：

`https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/{indexCode}indicator.xls`

文件包含两种市盈率和两种股息率口径，但当前公开结构不含 PB。因此：

* A 股 PE 与股息率可以官方数据为主。
* A 股 PB 当前值可从官方 factsheet 核验，但历史 PB 分位仍需要额外数据供应商。
* 不应把第三方 PB 历史与官方 PE/股息率混合后隐藏来源差异。

源码依据：https://raw.githubusercontent.com/akfamily/akshare/main/akshare/index/index_stock_zh_csindex.py

### 美国指数

S&P DJI 与 Nasdaq 官方页面可以核验指数身份、方法、币种、收益类型和部分当前特征；完整日度成分、历史估值及部分指数数据通常属于订阅数据。公开价格历史可以从二级市场数据源或跟踪 ETF 的复权价格取得，但这不是官方指数全收益序列。

因此：

* 标普 500 与纳斯达克 100 的收益研究可使用明确标注的 ETF 复权价格代理（例如 SPY、QQQ），或用户配置的官方/商业全收益序列。
* 美国指数 PE/PB/股息率的完整可审计历史需要商业数据、用户导入数据，或接受第三方聚合源。
* 不能用当前成分股倒推十年估值历史；这样会产生严重的幸存者偏差。

## 数据源策略选项

### 方案 A：可信优先，允许字段暂不可用

* 中证官方 PE/股息率与价格历史。
* 官方 factsheet 当前 PB。
* 美国官方当前指标与公开价格/ETF 代理。
* 缺少可信历史序列时，PB 或美国估值分位显示“历史数据源未配置”。

优点：来源边界最干净。缺点：不能立即满足所有指数的三项历史分位。

### 方案 B：官方交叉核验 + 公共聚合历史（推荐用于个人本地 MVP）

* 官方源用于指数身份、当前值、方法与更新时间核验。
* 公共聚合源补齐历史 PE/PB/股息率，并在每个字段旁标记 `derived` 或 `aggregated`。
* 本地保存原始响应、抓取时间和数据指纹；若当前值与官方值偏差超过阈值，拒绝更新并显示异常。

优点：功能完整、无需商业订阅、仍可审计。缺点：聚合源稳定性与使用条款需要持续复核。

### 方案 C：商业数据或用户导入

* 提供 CSV 导入和 provider adapter。
* 可连接 Wind、Choice、Bloomberg、FactSet、Refinitiv 或其他用户已有授权的数据。

优点：口径和覆盖最好。缺点：需要用户已有账号、导出文件或 API 权限。

## 统一数据契约

每个时间序列点至少包含：

* `date`: ISO 8601 日期
* `value`: 数值或 null
* `metric`: `pe_ttm | pb | dividend_yield | total_return_index | price_index | adjusted_proxy`
* `source_id` 与 `source_url`
* `source_tier`: `official | licensed | aggregated | proxy`
* `methodology`: 权重、分母、税前/税后、总股本/计算用股本等说明
* `retrieved_at`
* `quality_flags`: stale、methodology-change、cross-check-mismatch、missing 等

API 不返回无来源的裸数字。前端必须能够展示 `as_of_date`、`source_tier`、`return_type`、样本数和缺失原因。

## 分位算法

* 默认回看 10 年，取每月最后一个有效观测。
* 仅在当前值与历史序列口径一致时计算。
* PE/PB/股息率的数值分位统一使用经验分布函数：`count(x <= current) / valid_count`。
* PE 中非正值、null 和明确异常值不纳入样本，并披露剔除数量。
* 分位至少需要 36 个有效月度样本，否则状态为 insufficient-history。
* 股息率的分位仍按数值方向计算，但 UI 文案说明其经济含义与 PE/PB 相反。

## 收益研究算法

* 月、季度、半年均取每个期间最后一个有效交易日作为买入观察点。
* 持有 N 年的结束点取目标周年日当天或之前最近的有效交易日。
* 仅保留具有完整持有窗口的样本。
* 累计收益：`end_value / start_value - 1`。
* 年化收益：`(end_value / start_value) ** (365.2425 / elapsed_days) - 1`。
* 价格指数、全收益指数和 ETF 复权代理绝不混为一个 return type。
* 输出所有样本、样本数、盈利比例、中位数、最差值、最好值，并保留起止日期用于 tooltip。

