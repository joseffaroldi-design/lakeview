"""GA4 analytics summary — server-side proxy over Google Analytics Data API.

Reads credentials from environment only. Never exposes secrets to clients.
Returns 503 with a generic "Analytics unavailable" when credentials are missing
or invalid so the dashboard can degrade gracefully.

Approved GA4 events consumed:
  page_view, menu_click, order_pickup_click, order_delivery_click,
  phone_click, directions_click, catering_quote_click, generate_lead
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException, Header, Cookie

from auth import verify_session

logger = logging.getLogger(__name__)
router = APIRouter()

READONLY_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"

APPROVED_EVENTS = (
    "page_view",
    "menu_click",
    "order_pickup_click",
    "order_delivery_click",
    "phone_click",
    "directions_click",
    "catering_quote_click",
    "generate_lead",
)


def _env(key: str) -> str:
    return (os.environ.get(key) or "").strip()


@lru_cache(maxsize=1)
def _get_client():
    """Build a GA4 Data client from env credentials. Cached across requests.

    Raises RuntimeError with a generic message if credentials are missing or
    invalid. Never includes credential contents in the exception.
    """
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.oauth2 import service_account

    json_blob = _env("GOOGLE_SERVICE_ACCOUNT_JSON")
    file_path = _env("GOOGLE_APPLICATION_CREDENTIALS")

    if not json_blob and not file_path:
        raise RuntimeError("GA4 credentials not configured")

    try:
        if json_blob:
            info = json.loads(json_blob)
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=[READONLY_SCOPE]
            )
        else:
            credentials = service_account.Credentials.from_service_account_file(
                file_path, scopes=[READONLY_SCOPE]
            )
        return BetaAnalyticsDataClient(credentials=credentials)
    except Exception:  # noqa: BLE001 — swallow details to avoid leaking secrets
        # Deliberately do not log exception content — the credential JSON can
        # end up inside auth-library exceptions/tracebacks.
        raise RuntimeError("GA4 credentials invalid")


def _run_report(client, property_name, dimensions, metrics, date_ranges,
                dimension_filter=None, limit=100):
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Metric, RunReportRequest,
    )

    request = RunReportRequest(
        property=property_name,
        dimensions=[Dimension(name=n) for n in dimensions],
        metrics=[Metric(name=n) for n in metrics],
        date_ranges=[DateRange(start_date=s, end_date=e) for s, e in date_ranges],
        limit=limit,
    )
    if dimension_filter is not None:
        request.dimension_filter = dimension_filter
    response = client.run_report(request)
    rows = []
    for row in response.rows:
        item = {dimensions[i]: row.dimension_values[i].value for i in range(len(dimensions))}
        for i, name in enumerate(metrics):
            item[name] = row.metric_values[i].value
        rows.append(item)
    return rows


def _event_name_filter(names):
    """Build an OR-filter across event names for a single report call."""
    from google.analytics.data_v1beta.types import Filter, FilterExpression, FilterExpressionList

    expressions = [
        FilterExpression(
            filter=Filter(
                field_name="eventName",
                string_filter=Filter.StringFilter(value=name),
            )
        )
        for name in names
    ]
    return FilterExpression(or_group=FilterExpressionList(expressions=expressions))


@router.get("/ga4/summary")
async def ga4_summary(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
) -> dict[str, Any]:
    """Return today's approved-event counts, top traffic sources, and a 7-day trend.

    All 'today' figures use the GA4 property's own timezone (that's the semantic
    the Data API applies when we pass `today`/`yesterday`).
    """
    await verify_session(authorization, session_token)

    property_id = _env("GA4_PROPERTY_ID")
    if not property_id.isdigit():
        raise HTTPException(status_code=503, detail="Analytics unavailable")

    try:
        client = _get_client()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Analytics unavailable")

    property_name = f"properties/{property_id}"

    try:
        # 1) Today totals — sessions + active users + total pageviews (via screenPageViews)
        today_totals = _run_report(
            client, property_name,
            dimensions=[],
            metrics=["sessions", "activeUsers", "screenPageViews"],
            date_ranges=[("today", "today")],
            limit=1,
        )

        # 2) Today per-approved-event counts — filter down to our 8 events
        today_events = _run_report(
            client, property_name,
            dimensions=["eventName"],
            metrics=["eventCount"],
            date_ranges=[("today", "today")],
            dimension_filter=_event_name_filter(APPROVED_EVENTS),
            limit=50,
        )

        # 3) Top traffic sources (last 7 days, session-based channel grouping)
        traffic = _run_report(
            client, property_name,
            dimensions=["sessionDefaultChannelGroup"],
            metrics=["sessions"],
            date_ranges=[("7daysAgo", "today")],
            limit=10,
        )

        # 4) 7-day trend
        trend = _run_report(
            client, property_name,
            dimensions=["date"],
            metrics=["sessions", "activeUsers", "screenPageViews"],
            date_ranges=[("7daysAgo", "today")],
            limit=8,
        )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        # Never surface GA/Google internals to the client or logs.
        logger.warning("GA4 summary query failed")
        raise HTTPException(status_code=502, detail="Analytics query failed")

    # Normalize today event counts into an object keyed by our 8 event names.
    events_by_name = {name: 0 for name in APPROVED_EVENTS}
    for row in today_events:
        name = row.get("eventName")
        if name in events_by_name:
            try:
                events_by_name[name] = int(row.get("eventCount", "0"))
            except (TypeError, ValueError):
                events_by_name[name] = 0

    totals_row = today_totals[0] if today_totals else {}

    def _int(row, key):
        try:
            return int(row.get(key, "0"))
        except (TypeError, ValueError):
            return 0

    return {
        "property_id": property_id,
        "today": {
            "visitors": _int(totals_row, "activeUsers"),
            "sessions": _int(totals_row, "sessions"),
            "page_views": _int(totals_row, "screenPageViews"),
            "events": events_by_name,
        },
        "traffic_sources": [
            {
                "channel": row.get("sessionDefaultChannelGroup") or "(unassigned)",
                "sessions": _int(row, "sessions"),
            }
            for row in traffic
        ],
        "trend_7d": [
            {
                "date": row.get("date"),
                "sessions": _int(row, "sessions"),
                "visitors": _int(row, "activeUsers"),
                "page_views": _int(row, "screenPageViews"),
            }
            for row in trend
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
