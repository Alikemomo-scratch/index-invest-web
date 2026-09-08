"""FastAPI entrypoint for the local-only web application."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .catalog import INDEX_CATALOG
from .service import ResearchService


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
DATA_DIR = Path(os.environ.get("INDEX_INVEST_DATA_DIR", ROOT / "data"))
service = ResearchService(DATA_DIR / "index-invest.sqlite3")

app = FastAPI(
    title="指数研究室",
    description="Local index valuation and holding-period return research",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "local_only": True, "version": app.version}


@app.get("/api/indices")
def indices():
    return {"items": [item.public_dict() for item in INDEX_CATALOG.values()]}


@app.get("/api/indices/{index_id}/research")
def research(
    index_id: str,
    lookback_years: int = Query(10),
    history_frequency: str = Query("monthly"),
):
    try:
        return service.get_research(index_id, lookback_years, history_frequency)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/indices/{index_id}/returns")
def returns(
    index_id: str,
    frequency: str = Query("quarterly"),
    holding_years: int = Query(5),
    measure: str = Query("annualized"),
):
    try:
        return service.get_returns(index_id, frequency, holding_years, measure)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/indices/{index_id}/dca")
def dca(
    index_id: str,
    years: int = Query(10),
    contribution_amount: float = Query(1000),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    cadence: str = Query("monthly"),
    schedule_value: int = Query(1),
):
    try:
        return service.get_dca(
            index_id, years, contribution_amount, start_date, end_date, cadence, schedule_value
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/indices/{index_id}/validation")
def validation(
    index_id: str,
    metric_id: str = Query("pe"),
    reference_value: float = Query(...),
    reference_date: str = Query(...),
    reference_source: str = Query("用户参考"),
    tolerance_pct: float = Query(2.0),
):
    try:
        return service.validate_metric(
            index_id, metric_id, reference_value, reference_date, reference_source, tolerance_pct
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/refresh/{index_id}")
def refresh(
    index_id: str,
    lookback_years: int = Query(10),
    history_frequency: str = Query("monthly"),
    frequency: str = Query("quarterly"),
    holding_years: int = Query(5),
    measure: str = Query("annualized"),
    dca_years: int = Query(10),
    dca_amount: float = Query(1000),
    dca_start_date: Optional[str] = Query(None),
    dca_end_date: Optional[str] = Query(None),
    dca_cadence: str = Query("monthly"),
    dca_schedule_value: int = Query(1),
):
    try:
        research_payload = service.get_research(
            index_id, lookback_years, history_frequency, force=True
        )
        returns_payload = service.get_returns(index_id, frequency, holding_years, measure, force=True)
        dca_payload = service.get_dca(
            index_id, dca_years, dca_amount, dca_start_date, dca_end_date,
            dca_cadence, dca_schedule_value,
        )
        return {
            "status": "ready" if all(
                payload["status"] == "ready"
                for payload in (research_payload, returns_payload, dca_payload)
            ) else "partial",
            "research": research_payload,
            "returns": returns_payload,
            "dca": dca_payload,
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
