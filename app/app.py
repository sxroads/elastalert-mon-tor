"""Error dashboard: one page showing today's failing services from Elasticsearch."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from flask import Flask, render_template

ES_URL = os.environ.get("ES_URL", "http://localhost:9200").rstrip("/")
ES_USERNAME = os.environ.get("ES_USERNAME", "")
ES_PASSWORD = os.environ.get("ES_PASSWORD", "")
ES_CA_CERT = os.environ.get("ES_CA_CERT", "")
ES_VERIFY_CERTS = os.environ.get("ES_VERIFY_CERTS", "true").lower() == "true"

ES_INDEX = os.environ.get("ES_INDEX", "logs-*")
SERVICE_FIELD = os.environ.get("SERVICE_FIELD", "service.name")
TIMESTAMP_FIELD = os.environ.get("TIMESTAMP_FIELD", "@timestamp")
ERROR_FIELD = os.environ.get("ERROR_FIELD", "isError")
TIMEZONE = os.environ.get("TIMEZONE", "UTC")

TOP_N = int(os.environ.get("TOP_N", "15"))
DAILY_THRESHOLD = int(os.environ.get("DAILY_THRESHOLD", "15"))
REFRESH_SECONDS = int(os.environ.get("REFRESH_SECONDS", "60"))
MAX_SERVICES = 1000  # upper bound on distinct services counted per query

app = Flask(__name__)


def es_search(body):
    verify = ES_CA_CERT or ES_VERIFY_CERTS
    auth = (ES_USERNAME, ES_PASSWORD) if ES_USERNAME else None
    resp = requests.post(f"{ES_URL}/{ES_INDEX}/_search", json=body, auth=auth, verify=verify, timeout=30)
    resp.raise_for_status()
    return resp.json()


def build_query():
    # Errors since local midnight, counted per service and per hour
    return {
        "size": 0,
        "track_total_hits": True,
        "query": {
            "bool": {
                "filter": [
                    {"term": {ERROR_FIELD: True}},
                    {"range": {TIMESTAMP_FIELD: {"gte": "now/d", "lte": "now", "time_zone": TIMEZONE}}},
                ]
            }
        },
        "aggs": {
            "services": {"terms": {"field": SERVICE_FIELD, "size": MAX_SERVICES}},
            "per_hour": {
                "date_histogram": {
                    "field": TIMESTAMP_FIELD,
                    "calendar_interval": "1h",
                    "time_zone": TIMEZONE,
                    "format": "HH:mm",
                    "min_doc_count": 0,
                    "extended_bounds": {"min": "now/d", "max": "now/d+23h"},
                }
            },
        },
    }


def fetch_report():
    result = es_search(build_query())
    aggs = result["aggregations"]
    now_ms = datetime.now().timestamp() * 1000

    services = [{"name": b["key"], "count": b["doc_count"]} for b in aggs["services"]["buckets"]]
    hours = [
        # Hours that haven't started yet are None, so the chart leaves them blank instead of showing 0
        {"label": b["key_as_string"], "count": b["doc_count"] if b["key"] <= now_ms else None}
        for b in aggs["per_hour"]["buckets"]
    ]
    return {
        "total": result["hits"]["total"]["value"],
        "service_count": len(services),
        "truncated": aggs["services"]["sum_other_doc_count"] > 0,
        "top": services[:TOP_N],
        "over_threshold": [s for s in services if s["count"] > DAILY_THRESHOLD],
        "hours": hours,
    }


@app.route("/")
def index():
    report, error = None, None
    try:
        report = fetch_report()
    except Exception as exc:  # show the problem on the page instead of a blank 500
        error = f"{type(exc).__name__}: {exc}"
    return render_template(
        "index.html",
        report=report,
        error=error,
        top_n=TOP_N,
        threshold=DAILY_THRESHOLD,
        refresh=REFRESH_SECONDS,
        generated=datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d %H:%M"),
        timezone=TIMEZONE,
    )


@app.route("/healthz")
def healthz():
    return {"status": "ok"}
