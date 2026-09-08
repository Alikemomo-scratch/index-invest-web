# Dividend Low Volatility Index Expansion

Date: 2026-09-08

## Official identities

| Product label | Official name | Display code | Total-return code | Market |
| --- | --- | --- | --- | --- |
| 300 红利低波 | 沪深 300 红利低波动指数 | 930740 | H20740 | China A shares |
| 红利低波 | 中证红利低波动指数 | H30269 | H20269 | China A shares |
| 红利低波 100 | 中证红利低波动 100 指数 | 930955 | H20955 | China A shares |
| 东证红利低波 | 中证东方红红利低波动指数 | 931446 | 921446 | China A shares |
| 标普中国 A 股大盘红利低波 50 | S&P China A-Share LargeCap Low Volatility High Dividend 50 Index | SPCLLHCP | SPCLLHCT | China A shares |

Sources:

- CSI 300 Dividend Low Volatility factsheet: <https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/930740factsheet.pdf>
- CSI Dividend Low Volatility factsheet: <https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/H30269factsheet.pdf>
- CSI Dividend Low Volatility 100 factsheet: <https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/930955factsheet.pdf>
- CSI Dongfanghong Dividend Low Volatility factsheet: <https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/931446factsheet.pdf>
- CSI Dongfanghong Dividend Low Volatility methodology: <https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/20231208180546-931446_Index_Methodology_cn.pdf>
- S&P index page: <https://www.spglobal.com/spdji/zh/indices/dividends-factors/sp-china-a-share-largecap-low-volatility-high-dividend-50-index/>
- S&P Low Volatility High Dividend methodology: <https://www.spglobal.com/spdji/zh/documents/methodologies/methodology-sp-low-volatility-high-dividend-indices-chinese.pdf>

## Live source probes

- The CSI performance API returned daily price-index observations with PE for 930740, H30269, 930955, and 931446.
- The same API returned total-return daily observations for H20740, H20269, H20955, and 921446. The official 931446 factsheet identifies 921446 as the derived total-return index; the old-style inferred code H21446 returned no observations and must not be used.
- The CSI indicator workbooks for all four price codes returned recent PE and dividend-yield observations through 2026-09-08.
- Legulegu returned PB history for H30269.CSI, but no usable PB history for 930740, 930955, or 931446 under their tested public-code forms. Those PB fields must remain unavailable rather than borrowing another index series.

## S&P proxy decision

S&P publishes the official price and total-return identities, but free daily history for SPCLLHCP/SPCLLHCT is not available through the existing public adapters. The linked Southern Asset Management ETF 515450 is therefore used only as a backtest proxy:

- Source: Tencent Securities public K-line adapter for `sh515450`.
- Adjustment: `qfq` forward-adjusted close, which accounts for historical cash distributions in the price series.
- API return type: `adjusted_proxy`, never `total_return`.
- Disclosure: the proxy includes fund fees, tracking difference, market-price effects, and only covers the ETF listing period from 2020 onward.
- Valuation: unavailable unless a separately auditable index valuation source is configured. ETF valuation must not be substituted for index PE/PB/dividend yield.

The Eastmoney endpoint was also probed and returned the expected adjusted series through curl, but repeatedly disconnected from the application's Python HTTP transport. Tencent's dated two-year windows returned successfully through the production transport, so it is the deterministic runtime adapter rather than a shell-dependent workaround.
