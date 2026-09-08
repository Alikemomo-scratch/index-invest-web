"""Supported index catalog and deterministic provider routing."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class IndexDefinition:
    id: str
    name: str
    code: str
    market: str
    market_label: str
    currency: str
    valuation_provider: str
    valuation_code: str | None
    price_provider: str
    price_code: str
    fallback_price_code: str | None
    return_type: str
    return_label: str
    valuation_coverage: str

    def public_dict(self) -> dict:
        result = asdict(self)
        result.pop("valuation_code")
        result.pop("price_code")
        result.pop("fallback_price_code")
        result.pop("valuation_provider")
        result.pop("price_provider")
        return result


INDEX_CATALOG = {
    item.id: item
    for item in (
        IndexDefinition(
            "csi300", "沪深 300", "000300", "cn", "A 股", "CNY",
            "csi_legu", "000300.SH", "csi", "H00300", "000300", "total_return",
            "中证全收益指数（含分红再投资）", "PE/PB；股息率仅当前值",
        ),
        IndexDefinition(
            "csi500", "中证 500", "000905", "cn", "A 股", "CNY",
            "csi_legu", "000905.SH", "csi", "H00905", "000905", "total_return",
            "中证全收益指数（含分红再投资）", "PE/PB；股息率仅当前值",
        ),
        IndexDefinition(
            "csi1000", "中证 1000", "000852", "cn", "A 股", "CNY",
            "csi_legu", "000852.SH", "csi", "H00852", "000852", "total_return",
            "中证全收益指数（含分红再投资）", "PE/PB；股息率仅当前值",
        ),
        IndexDefinition(
            "sse50", "上证 50", "000016", "cn", "A 股", "CNY",
            "csi_legu", "000016.SH", "csi", "H00016", "000016", "total_return",
            "中证全收益指数（含分红再投资）", "PE/PB；股息率仅当前值",
        ),
        IndexDefinition(
            "sse_dividend", "上证红利", "000015", "cn", "A 股", "CNY",
            "csi_legu", "000015.SH", "csi", "H00015", "000015", "total_return",
            "中证全收益指数（含分红再投资）", "PE/PB；股息率仅当前值",
        ),
        IndexDefinition(
            "csi300_div_low_vol", "300 红利低波", "930740", "cn", "A 股", "CNY",
            "csi_legu", "930740.CSI", "csi", "H20740", "930740", "total_return",
            "沪深 300 红利低波动全收益指数（含分红再投资）", "官方 PE/股息率；公共 PB 暂不可用",
        ),
        IndexDefinition(
            "csi_div_low_vol", "红利低波", "H30269", "cn", "A 股", "CNY",
            "csi_legu", "H30269.CSI", "csi", "H20269", "H30269", "total_return",
            "中证红利低波动全收益指数（含分红再投资）", "PE/PB；股息率仅近期官方值",
        ),
        IndexDefinition(
            "csi_div_low_vol_100", "红利低波 100", "930955", "cn", "A 股", "CNY",
            "csi_legu", "930955.CSI", "csi", "H20955", "930955", "total_return",
            "中证红利低波动 100 全收益指数（含分红再投资）", "官方 PE/股息率；公共 PB 暂不可用",
        ),
        IndexDefinition(
            "csi_dfh_div_low_vol", "东证红利低波", "931446", "cn", "A 股", "CNY",
            "csi_legu", "931446.CSI", "csi", "921446", "931446", "total_return",
            "中证东方红红利低波动全收益指数（含分红再投资）", "官方 PE/股息率；公共 PB 暂不可用",
        ),
        IndexDefinition(
            "sp_china_a_div_low_vol_50", "标普中国 A 股大盘红利低波 50", "SPCLLHCP",
            "cn", "A 股", "CNY", "unavailable", None, "tencent", "sh515450", None,
            "adjusted_proxy", "515450 ETF 前复权日线代理", "公开历史估值不可用；回测使用 515450 ETF 代理",
        ),
        IndexDefinition(
            "sp500", "标普 500", "SPX", "us", "美股", "USD",
            "multpl", "SPX", "yahoo", "^SP500TR", "^GSPC", "total_return",
            "S&P 500 Total Return Index", "PE/PB/股息率",
        ),
        IndexDefinition(
            "nasdaq100", "纳斯达克 100", "NDX", "us", "美股", "USD",
            "unavailable", None, "yahoo", "^NDX", None, "price_return",
            "价格指数（不含分红）", "公开历史估值暂不可用",
        ),
    )
}


def get_index(index_id: str) -> IndexDefinition:
    try:
        return INDEX_CATALOG[index_id]
    except KeyError as exc:
        raise KeyError(f"Unknown index: {index_id}") from exc
