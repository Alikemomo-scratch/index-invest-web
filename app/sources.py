"""Narrow, auditable adapters for the public data used by the application."""

from __future__ import annotations

import hashlib
import html
import re
import time
from datetime import date, datetime, timezone
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
    points = []
    for index in range(1, sheet.nrows):
        row = sheet.row_values(index)
        raw_date = str(row[0]).split(".")[0]
        if len(raw_date) != 8:
            continue
        points.append({
            "date": f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}",
            "pe": _number(row[7]),
            "dividend_yield": _number(row[9]),
        })
    if not points:
        raise SourceError("中证官方估值表没有有效数据")
    return sorted(points, key=lambda point: point["date"])


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
