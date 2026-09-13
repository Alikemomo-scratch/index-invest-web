"""Narrow, auditable adapters for the public data used by the application."""

from __future__ import annotations

import hashlib
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import quote

import httpx


USER_AGENT = "IndexResearchRoom/0.1 (+local personal research)"
CSI_HISTORY_URL = "https://www.csindex.com.cn/csindex-home/perf/index-perf"
CSI_INDICATOR_URL = (
    "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/"
    "file/autofile/indicator/{code}indicator.xls"
)
LEGU_ORIGIN = "https://legulegu.com"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
TENCENT_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
FUNDDB_DIVIDEND_URL = "https://api.jiucaishuo.com/v2/guzhi/newtubiaolinedata"
EASTMONEY_BOND_URL = "https://datacenter.eastmoney.com/api/data/get"
EASTMONEY_BOND_TOKEN = "894050c76af8597a853f5b408b759f5d"
CHINA_TIMEZONE = timezone(timedelta(hours=8))
FUNDDB_SIGNING_SALT = "EWf45rlv#kfsr@k#gfksgkr"
FUNDDB_SIGNATURE_SLICES = {
    "tirgkjfs": (0, 2), "abiokytke": (21, 23), "u54rg5d": (2, 4),
    "kf54ge7": (31, 32), "tiklsktr4": (1, 2), "lksytkjh": (17, 21),
    "sbnoywr": (23, 25), "bgd7h8tyu54": (6, 8), "y654b5fs3tr": (11, 12),
    "bioduytlw": (5, 6), "bd4uy742": (26, 27), "h67456y": (16, 19),
    "bvytikwqjk": (6, 8), "ngd4uy551": (17, 19), "bgiuytkw": (9, 11),
    "nd354uy4752": (30, 31), "ghtoiutkmlg": (11, 14), "bd24y6421f": (24, 26),
    "tbvdiuytk": (16, 17), "ibvytiqjek": (14, 16), "jnhf8u5231": (9, 11),
    "fjlkatj": (2, 5), "hy5641d321t": (25, 27), "iogojti": (25, 26),
    "ngd4yut78": (12, 14), "nkjhrew": (26, 27), "yt447e13f": (8, 9),
    "n3bf4uj7y7": (18, 19), "nbf4uj7y432": (21, 23), "yi854tew": (29, 31),
    "h13ey474": (29, 32), "quikgdky": (27, 29),
}


class SourceError(RuntimeError):
    pass


def _client(timeout: float = 25.0) -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(timeout),
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7"},
    )


def _number(value) -> float | None:
    try:
        result = float(value)
        return result if result == result else None
    except (TypeError, ValueError):
        return None


def fetch_csi_history(code: str, start: str = "20000101", end: str | None = None) -> list[dict]:
    end = end or date.today().strftime("%Y%m%d")
    with _client(35) as client:
        response = client.get(CSI_HISTORY_URL, params={"indexCode": code, "startDate": start, "endDate": end})
        response.raise_for_status()
        payload = response.json()
    if str(payload.get("code")) != "200" or not isinstance(payload.get("data"), list):
        raise SourceError("中证指数历史接口返回了无效响应")
    points = []
    for row in payload["data"]:
        raw_date, close = str(row.get("tradeDate", "")), _number(row.get("close"))
        if len(raw_date) != 8 or close is None or close <= 0:
            continue
        points.append({
            "date": f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}",
            "value": close,
            "pe": _number(row.get("peg")),
        })
    if not points:
        raise SourceError("中证指数历史接口没有返回有效数据")
    return sorted(points, key=lambda point: point["date"])


def _parse_csi_indicator_rows(rows: list[list]) -> list[dict]:
    if not rows:
        return []
    headers = [str(value) for value in rows[0]]

    def column(marker: str, fallback: int) -> int:
        return next((index for index, header in enumerate(headers) if marker in header), fallback)

    pe1_index = column("P/E1", 6)
    pe2_index = column("P/E2", 7)
    dp1_index = column("D/P1", 8)
    dp2_index = column("D/P2", 9)
    points = []
    for row in rows[1:]:
        raw_date = str(row[0]).split(".")[0] if row else ""
        if len(raw_date) != 8 or max(pe1_index, pe2_index, dp1_index, dp2_index) >= len(row):
            continue
        pe1, pe2 = _number(row[pe1_index]), _number(row[pe2_index])
        dp1, dp2 = _number(row[dp1_index]), _number(row[dp2_index])
        points.append({
            "date": f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}",
            "pe": pe2,
            "pe_total_share": pe1,
            "pe_calculation_share": pe2,
            "dividend_yield": dp2,
            "dividend_yield_total_share": dp1,
            "dividend_yield_calculation_share": dp2,
        })
    return sorted(points, key=lambda point: point["date"])


def fetch_csi_indicator(code: str) -> list[dict]:
    try:
        import xlrd
    except ImportError as exc:
        raise SourceError("缺少 xlrd，无法读取中证官方估值表") from exc
    with _client() as client:
        response = client.get(CSI_INDICATOR_URL.format(code=code))
        response.raise_for_status()
    try:
        sheet = xlrd.open_workbook(file_contents=response.content).sheet_by_index(0)
    except Exception as exc:
        raise SourceError("中证官方估值表无法解析") from exc
    points = _parse_csi_indicator_rows([sheet.row_values(index) for index in range(sheet.nrows)])
    if not points:
        raise SourceError("中证官方估值表没有有效数据")
    return points


def _funddb_signed_payload(code: str, years: int = 10, timestamp_ms: int | None = None) -> dict:
    payload = {
        "gu_code": code,
        "pe_category": "xilv",
        "year": str(years),
        "ver": "new",
        "type": "pc",
        "version": "2.2.7",
        "authtoken": "",
        "act_time": timestamp_ms if timestamp_ms is not None else int(time.time() * 1000),
    }
    signature_input = "".join(
        str(payload[key]) for key in sorted(payload) if payload[key]
    ) + FUNDDB_SIGNING_SALT
    digest = hashlib.md5(signature_input.encode("utf-8")).hexdigest()
    payload.update({
        field: digest[start:end]
        for field, (start, end) in FUNDDB_SIGNATURE_SLICES.items()
    })
    return payload


def fetch_funddb_dividend_yield(code: str, years: int = 10) -> list[dict]:
    """Return FundDB's public aggregate index-yield series without assigning a CSI methodology."""
    if years not in {3, 5, 10}:
        raise ValueError("FundDB dividend history supports 3, 5, or 10 years")
    with _client(35) as client:
        response = client.post(FUNDDB_DIVIDEND_URL, data=_funddb_signed_payload(code, years))
        response.raise_for_status()
        try:
            payload = response.json()
            series = payload["data"]["tubiao"]["series"]
        except Exception as exc:
            raise SourceError("公共聚合股息率接口返回了无效响应") from exc
    if payload.get("code") != 0 or not isinstance(series, list):
        raise SourceError("公共聚合股息率接口返回了无效响应")
    raw_points = next(
        (item.get("data") for item in series if item.get("name") == "股息率"),
        None,
    )
    if not isinstance(raw_points, list):
        raise SourceError("公共聚合源没有返回该指数的股息率历史")
    points_by_date = {}
    for row in raw_points:
        if not isinstance(row, list) or len(row) < 2:
            continue
        stamp, value = _number(row[0]), _number(row[1])
        if stamp is None or value is None or stamp <= 0 or value <= 0:
            continue
        point_date = datetime.fromtimestamp(stamp / 1000, tz=CHINA_TIMEZONE).date().isoformat()
        points_by_date[point_date] = {"date": point_date, "value": value}
    points = sorted(points_by_date.values(), key=lambda point: point["date"])
    if len(points) < 12:
        raise SourceError("公共聚合源的股息率历史不足 12 个有效观测")
    return points


def _parse_government_bond_rows(rows: list[dict]) -> list[dict]:
    points_by_date = {}
    for row in rows:
        raw_date = str(row.get("SOLAR_DATE", ""))[:10]
        china_10y = _number(row.get("EMM00166466"))
        us_10y = _number(row.get("EMG00001310"))
        try:
            date.fromisoformat(raw_date)
        except ValueError:
            continue
        if china_10y is None and us_10y is None:
            continue
        points_by_date[raw_date] = {
            "date": raw_date,
            "china_10y": china_10y,
            "us_10y": us_10y,
        }
    return sorted(points_by_date.values(), key=lambda point: point["date"])


def fetch_government_bond_yields(years: int = 10) -> list[dict]:
    """Return dated China and US 10-year government yields from Eastmoney."""
    if years not in {10, 20}:
        raise ValueError("government bond history supports 10 or 20 years")
    today = date.today()
    try:
        start = today.replace(year=today.year - years)
    except ValueError:
        start = today.replace(year=today.year - years, day=28)
    base_params = {
        "type": "RPTA_WEB_TREASURYYIELD",
        "sty": "ALL",
        "st": "SOLAR_DATE",
        "sr": "-1",
        "token": EASTMONEY_BOND_TOKEN,
        "ps": "500",
        "filter": f"(SOLAR_DATE>='{start.isoformat()}')",
    }

    def fetch_page(client: httpx.Client, page: int) -> tuple[int, list[dict]]:
        response = client.get(
            EASTMONEY_BOND_URL,
            params={**base_params, "p": page, "pageNo": page, "pageNum": page},
        )
        response.raise_for_status()
        try:
            payload = response.json()
            result = payload["result"]
            rows = result["data"]
            pages = int(result["pages"])
        except Exception as exc:
            raise SourceError("中美国债收益率接口返回了无效响应") from exc
        if payload.get("success") is not True or not isinstance(rows, list):
            raise SourceError("中美国债收益率接口返回了无效响应")
        return pages, rows

    with _client(35) as client:
        total_pages, first_rows = fetch_page(client, 1)
        if total_pages < 1 or total_pages > 50:
            raise SourceError("中美国债收益率接口返回了异常分页数量")
        remaining_rows = []
        if total_pages > 1:
            with ThreadPoolExecutor(max_workers=min(6, total_pages - 1)) as executor:
                responses = executor.map(
                    lambda page: fetch_page(client, page), range(2, total_pages + 1)
                )
                for _, rows in responses:
                    remaining_rows.extend(rows)
    points = _parse_government_bond_rows(first_rows + remaining_rows)
    china_count = sum(point["china_10y"] is not None for point in points)
    us_count = sum(point["us_10y"] is not None for point in points)
    if min(china_count, us_count) < 36:
        raise SourceError("中美国债收益率历史不足 36 个有效观测")
    return points


def _csrf_session(client: httpx.Client) -> str:
    page = f"{LEGU_ORIGIN}/stockdata/hs300-ttm-lyr"
    response = client.get(page)
    response.raise_for_status()
    match = re.search(r'<meta[^>]+name=["\']_csrf["\'][^>]+content=["\']([^"\']+)', response.text)
    if not match:
        raise SourceError("乐咕乐股页面未提供 CSRF token")
    return match.group(1)


def fetch_legu_metric(code: str, metric: str) -> list[dict]:
    if metric not in {"pe", "pb"}:
        raise ValueError("Legulegu only supports pe and pb here")
    path = "index-basic-pe" if metric == "pe" else "index-basic-pb"
    token = hashlib.md5(date.today().isoformat().encode("utf-8")).hexdigest()
    with _client(35) as client:
        csrf = _csrf_session(client)
        response = client.get(
            f"{LEGU_ORIGIN}/api/stockdata/{path}",
            params={"token": token, "indexCode": code},
            headers={"X-CSRF-Token": csrf, "Referer": f"{LEGU_ORIGIN}/stockdata/hs300-ttm-lyr"},
        )
        response.raise_for_status()
        try:
            rows = response.json()["data"]
        except Exception as exc:
            raise SourceError("乐咕乐股估值接口返回了无效响应") from exc
    value_key = "addTtmPe" if metric == "pe" else "addPb"
    points = [
        {"date": str(row.get("date"))[:10], "value": value, "close": _number(row.get("close"))}
        for row in rows
        if (value := _number(row.get(value_key))) is not None and value > 0
    ]
    if not points:
        raise SourceError(f"乐咕乐股没有返回有效 {metric.upper()} 数据")
    return sorted(points, key=lambda point: point["date"])


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None


MULTPL_PATHS = {
    "pe": "s-p-500-pe-ratio/table/by-month",
    "pb": "s-p-500-price-to-book/table/by-quarter",
    "dividend_yield": "s-p-500-dividend-yield/table/by-month",
}


def fetch_multpl_metric(metric: str) -> list[dict]:
    if metric not in MULTPL_PATHS:
        raise ValueError(f"Unsupported Multpl metric: {metric}")
    url = f"https://www.multpl.com/{MULTPL_PATHS[metric]}"
    with _client(35) as client:
        response = client.get(url)
        response.raise_for_status()
    parser = _TableParser()
    parser.feed(response.text)
    points = []
    for row in parser.rows:
        if len(row) < 2:
            continue
        try:
            parsed_date = datetime.strptime(row[0].strip(), "%b %d, %Y").date()
        except ValueError:
            continue
        match = re.search(r"-?\d+(?:\.\d+)?", html.unescape(row[1]).replace(",", ""))
        if not match:
            continue
        points.append({
            "date": parsed_date.isoformat(), "value": float(match.group()),
            "estimated": "Estimate" in row[1] or "†" in row[1],
        })
    if not points:
        raise SourceError(f"Multpl 没有返回有效 {metric} 表格")
    deduped = {point["date"]: point for point in points}
    return sorted(deduped.values(), key=lambda point: point["date"])


def fetch_yahoo_history(symbol: str) -> list[dict]:
    now = int(time.time())
    url = YAHOO_CHART_URL.format(symbol=quote(symbol, safe=""))
    with _client(35) as client:
        response = client.get(
            url,
            params={"period1": 631152000, "period2": now + 86400, "interval": "1d", "events": "history"},
        )
        response.raise_for_status()
        payload = response.json()
    try:
        result = payload["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
    except Exception as exc:
        raise SourceError("Yahoo Finance 历史接口返回了无效响应") from exc
    points = []
    for stamp, close in zip(timestamps, closes):
        value = _number(close)
        if value is not None and value > 0:
            points.append({
                "date": datetime.fromtimestamp(stamp, tz=timezone.utc).date().isoformat(),
                "value": value,
            })
    if len(points) < 200:
        raise SourceError("Yahoo Finance 日线历史数据不足 200 个观察点")
    return sorted(points, key=lambda point: point["date"])


def fetch_tencent_adjusted_history(symbol: str, start_year: int = 2019) -> list[dict]:
    points_by_date = {}
    with _client(35) as client:
        for window_start in range(start_year, date.today().year + 1, 2):
            window_end = min(window_start + 1, date.today().year)
            response = client.get(
                TENCENT_KLINE_URL,
                params={
                    "param": (
                        f"{symbol},day,{window_start}-01-01,"
                        f"{window_end}-12-31,640,qfq"
                    )
                },
                headers={"Referer": "https://gu.qq.com/"},
            )
            response.raise_for_status()
            try:
                payload = response.json()
                rows = payload["data"][symbol]["qfqday"]
            except Exception as exc:
                raise SourceError("腾讯证券 ETF 前复权日线接口返回了无效响应") from exc
            if payload.get("code") != 0 or not isinstance(rows, list):
                raise SourceError("腾讯证券 ETF 前复权日线响应与请求标的不匹配")
            for row in rows:
                if not isinstance(row, list) or len(row) < 3:
                    continue
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(row[0])):
                    continue
                close = _number(row[2])
                if close is not None and close > 0:
                    points_by_date[str(row[0])] = {"date": str(row[0]), "value": close}
    points = sorted(points_by_date.values(), key=lambda point: point["date"])
    if len(points) < 200:
        raise SourceError("腾讯证券 ETF 前复权日线不足 200 个观察点")
    return points
