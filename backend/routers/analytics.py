"""Privacy-conscious first-party analytics and owner reporting.

The public endpoints collect page views and non-PII interaction events. The
authenticated report endpoint keeps the original response fields for backwards
compatibility and adds acquisition, engagement, conversion, and business-outcome
metrics used by the owner dashboard.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Cookie, Header, Query, Request

from auth import verify_session
from config import db
from models import ButtonClick, ButtonClickData, PageView, TrackingData
from rate_limit import limiter

router = APIRouter()

BUSINESS_TIMEZONE = ZoneInfo("America/Chicago")
RETENTION_DAYS = 180
BOT_MARKERS = (
    "bot", "crawler", "spider", "slurp", "headless", "lighthouse",
    "pagespeed", "preview", "facebookexternalhit", "whatsapp",
)
INTERNAL_HOSTS = {
    "lakeviewburgersandseafood.com",
    "www.lakeviewburgersandseafood.com",
    "lakeview-web.onrender.com",
}


def parse_user_agent(user_agent: str) -> tuple[str, str]:
    """Return a coarse device and browser classification without fingerprinting."""
    if not user_agent:
        return "unknown", "unknown"
    ua_lower = user_agent.lower()
    if "ipad" in ua_lower or "tablet" in ua_lower:
        device = "tablet"
    elif "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        device = "mobile"
    else:
        device = "desktop"

    if "edg" in ua_lower:
        browser = "Edge"
    elif "opr" in ua_lower or "opera" in ua_lower:
        browser = "Opera"
    elif "chrome" in ua_lower or "crios" in ua_lower:
        browser = "Chrome"
    elif "firefox" in ua_lower or "fxios" in ua_lower:
        browser = "Firefox"
    elif "safari" in ua_lower:
        browser = "Safari"
    else:
        browser = "Other"
    return device, browser


def is_bot(user_agent: str) -> bool:
    value = (user_agent or "").lower()
    return any(marker in value for marker in BOT_MARKERS)


def referrer_domain(referrer: Optional[str]) -> Optional[str]:
    if not referrer:
        return None
    try:
        host = (urlparse(referrer).hostname or "").lower()
        return host or None
    except ValueError:
        return None


def traffic_source(utm_source: Optional[str], referrer: Optional[str]) -> str:
    if utm_source and utm_source.strip():
        return utm_source.strip().lower()
    domain = referrer_domain(referrer)
    if not domain:
        return "direct"
    if domain in INTERNAL_HOSTS:
        return "internal"
    return domain


def event_category(event_name: str) -> str:
    name = (event_name or "").lower()
    if name.startswith("order_online") or name == "pickup_click" or name.startswith("special_"):
        return "order_pickup"
    if name == "delivery_click":
        return "delivery"
    if name.startswith("call_"):
        return "phone"
    if name.startswith("directions_"):
        return "directions"
    if name.startswith("catering_"):
        return "catering"
    if name.startswith("menu_") or name.startswith("favorite_"):
        return "menu_interest"
    if "review" in name:
        return "reviews"
    if name.startswith("nav_") or name.startswith("footer_") or name.startswith("mobile_nav_"):
        return "navigation"
    return "other"


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Keep analytics context small and scalar; never accept nested payloads."""
    cleaned: Dict[str, Any] = {}
    for raw_key, raw_value in list((metadata or {}).items())[:20]:
        key = str(raw_key)[:80]
        if isinstance(raw_value, bool):
            cleaned[key] = raw_value
        elif isinstance(raw_value, (int, float)):
            cleaned[key] = raw_value
        elif isinstance(raw_value, str):
            cleaned[key] = raw_value[:200]
    return cleaned


def _range_match(start: Optional[datetime] = None, end: Optional[datetime] = None) -> dict:
    query: dict = {"is_bot": {"$ne": True}}
    if start or end:
        timestamp: dict = {}
        if start:
            timestamp["$gte"] = start.astimezone(timezone.utc).isoformat()
        if end:
            timestamp["$lt"] = end.astimezone(timezone.utc).isoformat()
        query["timestamp"] = timestamp
    return query


def _business_boundaries() -> dict[str, datetime]:
    local_now = datetime.now(BUSINESS_TIMEZONE)
    today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    week = today - timedelta(days=today.weekday())
    month = today.replace(day=1)
    previous_month = (month - timedelta(days=1)).replace(day=1)
    return {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "yesterday": today - timedelta(days=1),
        "week": week,
        "previous_week": week - timedelta(days=7),
        "month": month,
        "previous_month": previous_month,
    }


async def _unique_count(collection, field: str, match: dict) -> int:
    rows = await collection.aggregate([
        {"$match": {**match, field: {"$nin": [None, ""]}}},
        {"$group": {"_id": f"${field}"}},
        {"$count": "count"},
    ]).to_list(1)
    return rows[0]["count"] if rows else 0


async def _visitor_count(match: dict) -> int:
    rows = await db.page_views.aggregate([
        {"$match": match},
        {"$project": {"key": {"$ifNull": ["$visitor_id", "$session_id"]}}},
        {"$match": {"key": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$key"}},
        {"$count": "count"},
    ]).to_list(1)
    return rows[0]["count"] if rows else 0


async def _breakdown(collection, field: str, match: dict, limit: int = 20) -> dict[str, int]:
    rows = await collection.aggregate([
        {"$match": {**match, field: {"$nin": [None, "", "null"]}}},
        {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]).to_list(limit)
    return {str(row["_id"]): row["count"] for row in rows if row.get("_id") is not None}


async def _session_summary(match: dict) -> dict[str, float]:
    rows = await db.page_views.aggregate([
        {"$match": {**match, "session_id": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$session_id", "pages": {"$sum": 1}}},
        {"$group": {
            "_id": None,
            "sessions": {"$sum": 1},
            "single_page_sessions": {"$sum": {"$cond": [{"$eq": ["$pages", 1]}, 1, 0]}},
            "total_pages": {"$sum": "$pages"},
        }},
    ]).to_list(1)
    if not rows:
        return {"sessions": 0, "single_page_sessions": 0, "avg_pages": 0, "bounce_rate": 0}
    row = rows[0]
    sessions = row.get("sessions", 0)
    singles = row.get("single_page_sessions", 0)
    return {
        "sessions": sessions,
        "single_page_sessions": singles,
        "avg_pages": round(row.get("total_pages", 0) / sessions, 2) if sessions else 0,
        "bounce_rate": round(singles * 100 / sessions, 1) if sessions else 0,
    }


def _trend(current: int, previous: int) -> float:
    if previous == 0:
        return 100.0 if current else 0.0
    return round((current - previous) * 100 / previous, 1)


@router.post("/analytics/track")
@limiter.limit("60/minute")
async def track_page_view(request: Request, data: TrackingData):
    user_agent = data.user_agent or request.headers.get("user-agent", "")
    device_type, browser = parse_user_agent(user_agent)
    page_view = PageView(
        page=data.page,
        user_agent=user_agent,
        device_type=device_type,
        browser=browser,
        # Store only the referring host. Query strings can contain personal or
        # campaign-specific values and are not needed for owner reporting.
        referrer=referrer_domain(data.referrer),
        referrer_domain=referrer_domain(data.referrer),
        source=traffic_source(data.utm_source, data.referrer),
        session_id=data.session_id,
        visitor_id=data.visitor_id,
        screen_width=data.screen_width,
        screen_height=data.screen_height,
        page_title=data.page_title,
        language=data.language,
        timezone=data.timezone,
        utm_source=data.utm_source,
        utm_medium=data.utm_medium,
        utm_campaign=data.utm_campaign,
        utm_content=data.utm_content,
        utm_term=data.utm_term,
        is_bot=is_bot(user_agent),
    )
    doc = page_view.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    doc["expires_at"] = datetime.now(timezone.utc) + timedelta(days=RETENTION_DAYS)
    await db.page_views.insert_one(doc)
    return {"message": "Page view tracked"}


async def _store_event(data: ButtonClickData) -> dict:
    category = data.event_category or event_category(data.button_name)
    event = ButtonClick(
        button_name=data.button_name,
        session_id=data.session_id,
        visitor_id=data.visitor_id,
        page=data.page,
        event_category=category,
        metadata=sanitize_metadata(data.metadata),
    )
    doc = event.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    doc["expires_at"] = datetime.now(timezone.utc) + timedelta(days=RETENTION_DAYS)
    await db.button_clicks.insert_one(doc)
    return {"message": "Analytics event tracked", "category": category}


@router.post("/analytics/button-click")
@limiter.limit("60/minute")
async def track_button_click(request: Request, data: ButtonClickData):
    return await _store_event(data)


@router.post("/analytics/event")
@limiter.limit("120/minute")
async def track_event(request: Request, data: ButtonClickData):
    """Generic non-PII event endpoint used by the public site."""
    return await _store_event(data)


@router.get("/analytics")
async def get_analytics(
    authorization: str = Header(None),
    session_token: str = Cookie(None),
    days: int = Query(30, ge=1, le=RETENTION_DAYS),
):
    await verify_session(authorization, session_token)
    bounds = _business_boundaries()
    today_match = _range_match(bounds["today"], bounds["tomorrow"])
    yesterday_match = _range_match(bounds["yesterday"], bounds["today"])
    week_match = _range_match(bounds["week"], bounds["tomorrow"])
    previous_week_match = _range_match(bounds["previous_week"], bounds["week"])
    month_match = _range_match(bounds["month"], bounds["tomorrow"])
    previous_month_match = _range_match(bounds["previous_month"], bounds["month"])
    range_start = bounds["today"] - timedelta(days=days - 1)
    selected_match = _range_match(range_start, bounds["tomorrow"])
    all_match = _range_match()

    total_views = await db.page_views.count_documents(all_match)
    views_today = await db.page_views.count_documents(today_match)
    views_yesterday = await db.page_views.count_documents(yesterday_match)
    views_this_week = await db.page_views.count_documents(week_match)
    views_previous_week = await db.page_views.count_documents(previous_week_match)
    views_this_month = await db.page_views.count_documents(month_match)
    views_previous_month = await db.page_views.count_documents(previous_month_match)
    unique_sessions = await _unique_count(db.page_views, "session_id", all_match)
    unique_sessions_today = await _unique_count(db.page_views, "session_id", today_match)
    unique_sessions_week = await _unique_count(db.page_views, "session_id", week_match)
    unique_sessions_month = await _unique_count(db.page_views, "session_id", month_match)
    unique_visitors = await _visitor_count(all_match)
    unique_visitors_range = await _visitor_count(selected_match)

    page_breakdown = await _breakdown(db.page_views, "page", all_match, 100)
    page_breakdown_range = await _breakdown(db.page_views, "page", selected_match, 100)
    device_breakdown = await _breakdown(db.page_views, "device_type", selected_match, 10)
    browser_breakdown = await _breakdown(db.page_views, "browser", selected_match, 10)
    source_breakdown = await _breakdown(db.page_views, "source", selected_match, 20)
    campaign_breakdown = await _breakdown(db.page_views, "utm_campaign", selected_match, 20)
    language_breakdown = await _breakdown(db.page_views, "language", selected_match, 10)
    timezone_breakdown = await _breakdown(db.page_views, "timezone", selected_match, 10)
    top_referrers = await _breakdown(db.page_views, "referrer_domain", selected_match, 10)
    button_clicks = await _breakdown(db.button_clicks, "button_name", all_match, 100)
    button_clicks_today = await _breakdown(db.button_clicks, "button_name", today_match, 100)
    events_range = await _breakdown(db.button_clicks, "button_name", selected_match, 100)
    event_category_breakdown = await _breakdown(db.button_clicks, "event_category", selected_match, 20)

    legacy_events = await db.button_clicks.aggregate([
        {"$match": {**selected_match, "$or": [
            {"event_category": {"$exists": False}},
            {"event_category": None},
            {"event_category": ""},
        ]}},
        {"$group": {"_id": "$button_name", "count": {"$sum": 1}}},
    ]).to_list(100)
    for row in legacy_events:
        category = event_category(str(row.get("_id") or ""))
        event_category_breakdown[category] = event_category_breakdown.get(category, 0) + row.get("count", 0)

    session_summary = await _session_summary(selected_match)

    daily_views = {
        (range_start + timedelta(days=offset)).strftime("%Y-%m-%d"): 0
        for offset in range(days)
    }
    daily_rows = await db.page_views.aggregate([
        {"$match": selected_match},
        {"$addFields": {"parsed_timestamp": {"$cond": {
            "if": {"$eq": [{"$type": "$timestamp"}, "string"]},
            "then": {"$dateFromString": {"dateString": "$timestamp"}},
            "else": "$timestamp",
        }}}},
        {"$group": {"_id": {"$dateToString": {
            "format": "%Y-%m-%d", "date": "$parsed_timestamp", "timezone": "America/Chicago",
        }}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]).to_list(days)
    for row in daily_rows:
        if row.get("_id") in daily_views:
            daily_views[row["_id"]] = row["count"]

    hourly_views_today = {str(hour): 0 for hour in range(24)}
    hourly_rows = await db.page_views.aggregate([
        {"$match": today_match},
        {"$addFields": {"parsed_timestamp": {"$cond": {
            "if": {"$eq": [{"$type": "$timestamp"}, "string"]},
            "then": {"$dateFromString": {"dateString": "$timestamp"}},
            "else": "$timestamp",
        }}}},
        {"$group": {"_id": {"$hour": {
            "date": "$parsed_timestamp", "timezone": "America/Chicago",
        }}, "count": {"$sum": 1}}},
    ]).to_list(24)
    for row in hourly_rows:
        if row.get("_id") is not None:
            hourly_views_today[str(row["_id"])] = row["count"]

    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    daily_views_week = {day: 0 for day in day_order}
    week_rows = await db.page_views.aggregate([
        {"$match": week_match},
        {"$addFields": {"parsed_timestamp": {"$cond": {
            "if": {"$eq": [{"$type": "$timestamp"}, "string"]},
            "then": {"$dateFromString": {"dateString": "$timestamp"}},
            "else": "$timestamp",
        }}}},
        {"$group": {"_id": {"$dayOfWeek": {
            "date": "$parsed_timestamp", "timezone": "America/Chicago",
        }}, "count": {"$sum": 1}}},
    ]).to_list(7)
    day_map = {1: "Sun", 2: "Mon", 3: "Tue", 4: "Wed", 5: "Thu", 6: "Fri", 7: "Sat"}
    for row in week_rows:
        if row.get("_id") in day_map:
            daily_views_week[day_map[row["_id"]]] = row["count"]

    async def _entry_pages(first: bool) -> dict[str, int]:
        rows = await db.page_views.aggregate([
            {"$match": {**selected_match, "session_id": {"$nin": [None, ""]}}},
            {"$sort": {"timestamp": 1 if first else -1}},
            {"$group": {"_id": "$session_id", "page": {"$first": "$page"}}},
            {"$group": {"_id": "$page", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]).to_list(10)
        return {str(row["_id"]): row["count"] for row in rows if row.get("_id")}

    landing_pages = await _entry_pages(True)
    exit_pages = await _entry_pages(False)

    viewport_rows = await db.page_views.aggregate([
        {"$match": {**selected_match, "screen_width": {"$type": "number"}}},
        {"$project": {"bucket": {"$switch": {
            "branches": [
                {"case": {"$lte": ["$screen_width", 479]}, "then": "Small phone"},
                {"case": {"$lte": ["$screen_width", 767]}, "then": "Large phone"},
                {"case": {"$lte": ["$screen_width", 1024]}, "then": "Tablet"},
                {"case": {"$lte": ["$screen_width", 1439]}, "then": "Desktop"},
            ],
            "default": "Large desktop",
        }}}},
        {"$group": {"_id": "$bucket", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]).to_list(10)
    viewport_breakdown = {row["_id"]: row["count"] for row in viewport_rows}

    returning_rows = await db.page_views.aggregate([
        {"$match": {**all_match, "visitor_id": {"$nin": [None, ""]}, "session_id": {"$nin": [None, ""]}}},
        {"$group": {"_id": {"visitor": "$visitor_id", "session": "$session_id"}}},
        {"$group": {"_id": "$_id.visitor", "sessions": {"$sum": 1}}},
        {"$group": {
            "_id": None,
            "identified": {"$sum": 1},
            "returning": {"$sum": {"$cond": [{"$gt": ["$sessions", 1]}, 1, 0]}},
        }},
    ]).to_list(1)
    identified_visitors = returning_rows[0].get("identified", 0) if returning_rows else 0
    returning_visitors = returning_rows[0].get("returning", 0) if returning_rows else 0

    event_sessions = await db.button_clicks.aggregate([
        {"$match": {**selected_match, "session_id": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$session_id", "events": {"$addToSet": "$button_name"}}},
    ]).to_list(10000)
    order_intent_sessions = sum(
        1 for row in event_sessions
        if any(event_category(name) in {"order_pickup", "delivery", "phone"} for name in row.get("events", []))
    )
    menu_interest_sessions = sum(
        1 for row in event_sessions
        if any(event_category(name) == "menu_interest" for name in row.get("events", []))
    )
    sessions_range = int(session_summary["sessions"])
    order_intent_rate = round(order_intent_sessions * 100 / sessions_range, 1) if sessions_range else 0
    menu_interest_rate = round(menu_interest_sessions * 100 / sessions_range, 1) if sessions_range else 0

    engagement_rows = await db.button_clicks.aggregate([
        {"$match": {
            **selected_match,
            "button_name": "page_engagement",
            "metadata.duration_seconds": {"$type": "number"},
        }},
        {"$group": {
            "_id": None,
            "reports": {"$sum": 1},
            "average_seconds": {"$avg": "$metadata.duration_seconds"},
            "average_scroll_depth": {"$avg": "$metadata.scroll_depth"},
        }},
    ]).to_list(1)
    engagement = engagement_rows[0] if engagement_rows else {}

    range_iso = range_start.astimezone(timezone.utc).isoformat()
    catering_total = await db.catering_inquiries.count_documents({})
    catering_range = await db.catering_inquiries.count_documents({"submitted_at": {"$gte": range_iso}})
    newsletter_total = await db.newsletter_subscribers.count_documents({})
    newsletter_range = await db.newsletter_subscribers.count_documents({"subscribed_at": {"$gte": range_iso}})
    loyalty_total = await db.loyalty_members.count_documents({})
    loyalty_range = await db.loyalty_members.count_documents({"joined_at": {"$gte": range_iso}})

    return {
        "total_views": total_views,
        "views_today": views_today,
        "views_this_week": views_this_week,
        "views_this_month": views_this_month,
        "unique_sessions": unique_sessions,
        "unique_sessions_today": unique_sessions_today,
        "page_breakdown": page_breakdown,
        "device_breakdown": device_breakdown,
        "browser_breakdown": browser_breakdown,
        "hourly_views_today": hourly_views_today,
        "daily_views_week": daily_views_week,
        "top_referrers": top_referrers,
        "avg_pages_per_session": session_summary["avg_pages"],
        "button_clicks": button_clicks,
        "button_clicks_today": button_clicks_today,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "business_timezone": "America/Chicago",
        "selected_days": days,
        "range_start": range_start.date().isoformat(),
        "range_end": bounds["today"].date().isoformat(),
        "views_yesterday": views_yesterday,
        "views_previous_week": views_previous_week,
        "views_previous_month": views_previous_month,
        "unique_sessions_week": unique_sessions_week,
        "unique_sessions_month": unique_sessions_month,
        "unique_visitors": unique_visitors,
        "unique_visitors_range": unique_visitors_range,
        "returning_visitors": returning_visitors,
        "new_visitors": max(identified_visitors - returning_visitors, 0),
        "bounce_rate": session_summary["bounce_rate"],
        "sessions_range": sessions_range,
        "single_page_sessions": session_summary["single_page_sessions"],
        "trends": {
            "today_vs_yesterday": _trend(views_today, views_yesterday),
            "week_vs_previous": _trend(views_this_week, views_previous_week),
            "month_vs_previous": _trend(views_this_month, views_previous_month),
        },
        "daily_views": daily_views,
        "page_breakdown_range": page_breakdown_range,
        "landing_pages": landing_pages,
        "exit_pages": exit_pages,
        "source_breakdown": source_breakdown,
        "campaign_breakdown": campaign_breakdown,
        "language_breakdown": language_breakdown,
        "timezone_breakdown": timezone_breakdown,
        "viewport_breakdown": viewport_breakdown,
        "events_range": events_range,
        "event_category_breakdown": event_category_breakdown,
        "conversion_funnel": {
            "website_sessions": sessions_range,
            "menu_interest_sessions": menu_interest_sessions,
            "order_intent_sessions": order_intent_sessions,
            "order_pickup_events": event_category_breakdown.get("order_pickup", 0),
            "delivery_events": event_category_breakdown.get("delivery", 0),
            "phone_events": event_category_breakdown.get("phone", 0),
            "directions_events": event_category_breakdown.get("directions", 0),
            "catering_events": event_category_breakdown.get("catering", 0),
        },
        "conversion_rates": {
            "menu_interest_rate": menu_interest_rate,
            "order_intent_rate": order_intent_rate,
        },
        "engagement": {
            "reports": engagement.get("reports", 0),
            "average_seconds": round(engagement.get("average_seconds", 0) or 0, 1),
            "average_scroll_depth": round(engagement.get("average_scroll_depth", 0) or 0, 1),
        },
        "business_outcomes": {
            "catering_inquiries_total": catering_total,
            "catering_inquiries_range": catering_range,
            "newsletter_subscribers_total": newsletter_total,
            "newsletter_subscribers_range": newsletter_range,
            "loyalty_members_total": loyalty_total,
            "loyalty_members_range": loyalty_range,
        },
    }
