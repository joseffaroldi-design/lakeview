"""Analytics: page view + button click tracking, aggregated dashboard data."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Header, Cookie

from config import db
from auth import verify_session
from models import PageView, TrackingData, ButtonClick, ButtonClickData

router = APIRouter()


def parse_user_agent(user_agent: str) -> tuple:
    """Parse user agent to extract device type and browser."""
    if not user_agent:
        return "unknown", "unknown"

    ua_lower = user_agent.lower()

    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        device = "mobile"
    elif "tablet" in ua_lower or "ipad" in ua_lower:
        device = "tablet"
    else:
        device = "desktop"

    if "chrome" in ua_lower and "edg" not in ua_lower:
        browser = "Chrome"
    elif "firefox" in ua_lower:
        browser = "Firefox"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        browser = "Safari"
    elif "edg" in ua_lower:
        browser = "Edge"
    elif "opera" in ua_lower or "opr" in ua_lower:
        browser = "Opera"
    else:
        browser = "Other"

    return device, browser


@router.post("/analytics/track")
async def track_page_view(data: TrackingData):
    device_type, browser = parse_user_agent(data.user_agent)

    page_view = PageView(
        page=data.page,
        user_agent=data.user_agent,
        device_type=device_type,
        browser=browser,
        referrer=data.referrer,
        session_id=data.session_id,
        screen_width=data.screen_width,
        screen_height=data.screen_height
    )

    doc = page_view.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.page_views.insert_one(doc)
    return {"message": "Page view tracked"}


@router.post("/analytics/button-click")
async def track_button_click(data: ButtonClickData):
    button_click = ButtonClick(
        button_name=data.button_name,
        session_id=data.session_id
    )

    doc = button_click.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.button_clicks.insert_one(doc)
    return {"message": "Button click tracked"}


@router.get("/analytics")
async def get_analytics(authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    total_views = await db.page_views.count_documents({})

    views_today = await db.page_views.count_documents({
        "timestamp": {"$gte": today_start.isoformat()}
    })

    views_this_week = await db.page_views.count_documents({
        "timestamp": {"$gte": week_start.isoformat()}
    })

    views_this_month = await db.page_views.count_documents({
        "timestamp": {"$gte": month_start.isoformat()}
    })

    # Unique sessions (all time)
    unique_sessions_pipeline = [
        {"$match": {"session_id": {"$ne": None}}},
        {"$group": {"_id": "$session_id"}},
        {"$count": "count"}
    ]
    unique_result = await db.page_views.aggregate(unique_sessions_pipeline).to_list(1)
    unique_sessions = unique_result[0]["count"] if unique_result else 0

    # Unique sessions today
    unique_today_pipeline = [
        {"$match": {"session_id": {"$ne": None}, "timestamp": {"$gte": today_start.isoformat()}}},
        {"$group": {"_id": "$session_id"}},
        {"$count": "count"}
    ]
    unique_today_result = await db.page_views.aggregate(unique_today_pipeline).to_list(1)
    unique_sessions_today = unique_today_result[0]["count"] if unique_today_result else 0

    # Page breakdown
    page_pipeline = [
        {"$group": {"_id": "$page", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    page_stats = await db.page_views.aggregate(page_pipeline).to_list(100)
    page_breakdown = {stat["_id"]: stat["count"] for stat in page_stats}

    # Device breakdown
    device_pipeline = [
        {"$match": {"device_type": {"$ne": None}}},
        {"$group": {"_id": "$device_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    device_stats = await db.page_views.aggregate(device_pipeline).to_list(10)
    device_breakdown = {stat["_id"]: stat["count"] for stat in device_stats}

    # Browser breakdown
    browser_pipeline = [
        {"$match": {"browser": {"$ne": None}}},
        {"$group": {"_id": "$browser", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    browser_stats = await db.page_views.aggregate(browser_pipeline).to_list(10)
    browser_breakdown = {stat["_id"]: stat["count"] for stat in browser_stats}

    # Hourly views today (0-23)
    hourly_views_today = {str(h): 0 for h in range(24)}
    hourly_pipeline = [
        {"$match": {"timestamp": {"$gte": today_start.isoformat()}}},
        {"$addFields": {
            "parsed_timestamp": {
                "$cond": {
                    "if": {"$eq": [{"$type": "$timestamp"}, "string"]},
                    "then": {"$dateFromString": {"dateString": "$timestamp"}},
                    "else": "$timestamp"
                }
            }
        }},
        {"$group": {
            "_id": {"$hour": "$parsed_timestamp"},
            "count": {"$sum": 1}
        }}
    ]
    hourly_stats = await db.page_views.aggregate(hourly_pipeline).to_list(24)
    for stat in hourly_stats:
        if stat["_id"] is not None:
            hourly_views_today[str(stat["_id"])] = stat["count"]

    # Daily views this week
    daily_views_week = {}
    daily_pipeline = [
        {"$match": {"timestamp": {"$gte": week_start.isoformat()}}},
        {"$addFields": {
            "parsed_timestamp": {
                "$cond": {
                    "if": {"$eq": [{"$type": "$timestamp"}, "string"]},
                    "then": {"$dateFromString": {"dateString": "$timestamp"}},
                    "else": "$timestamp"
                }
            }
        }},
        {"$group": {
            "_id": {"$dayOfWeek": "$parsed_timestamp"},
            "count": {"$sum": 1}
        }}
    ]
    daily_stats = await db.page_views.aggregate(daily_pipeline).to_list(7)
    day_map = {1: "Sun", 2: "Mon", 3: "Tue", 4: "Wed", 5: "Thu", 6: "Fri", 7: "Sat"}
    for stat in daily_stats:
        if stat["_id"] is not None:
            daily_views_week[day_map.get(stat["_id"], "Unknown")] = stat["count"]
    for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        if day not in daily_views_week:
            daily_views_week[day] = 0

    # Top referrers
    referrer_pipeline = [
        {"$match": {"referrer": {"$nin": [None, "", "null"]}}},
        {"$group": {"_id": "$referrer", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    referrer_stats = await db.page_views.aggregate(referrer_pipeline).to_list(5)
    top_referrers = {stat["_id"]: stat["count"] for stat in referrer_stats}

    # Average pages per session
    if unique_sessions > 0:
        avg_pages_per_session = round(total_views / unique_sessions, 2)
    else:
        avg_pages_per_session = 0

    # Button clicks (all time)
    button_pipeline = [
        {"$group": {"_id": "$button_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    button_stats = await db.button_clicks.aggregate(button_pipeline).to_list(20)
    button_clicks = {stat["_id"]: stat["count"] for stat in button_stats}

    # Button clicks today
    button_today_pipeline = [
        {"$match": {"timestamp": {"$gte": today_start.isoformat()}}},
        {"$group": {"_id": "$button_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    button_today_stats = await db.button_clicks.aggregate(button_today_pipeline).to_list(20)
    button_clicks_today = {stat["_id"]: stat["count"] for stat in button_today_stats}

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
        "avg_pages_per_session": avg_pages_per_session,
        "button_clicks": button_clicks,
        "button_clicks_today": button_clicks_today
    }
