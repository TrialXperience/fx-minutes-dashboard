from flask import Flask, jsonify, render_template_string
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

app = Flask(__name__)

# -----------------------------
# CORE MARKET DATA
# -----------------------------
# open_hour / close_hour are local-market hours for the MVP.
# Later we can replace this with broker/session-specific logic and DST rules.
markets = [
    {"name": "Sydney", "country": "Australia", "currency": "AUD", "timezone": "Australia/Sydney", "session": "Pacific Session", "flag": "🇦🇺", "open_hour": 8, "close_hour": 17, "map_x": 77, "map_y": 66},
    {"name": "Tokyo", "country": "Japan", "currency": "JPY", "timezone": "Asia/Tokyo", "session": "Asia Major", "flag": "🇯🇵", "open_hour": 8, "close_hour": 17, "map_x": 79, "map_y": 36},
    {"name": "Singapore", "country": "Singapore", "currency": "SGD", "timezone": "Asia/Singapore", "session": "Asia Hub", "flag": "🇸🇬", "open_hour": 8, "close_hour": 17, "map_x": 71, "map_y": 53},
    {"name": "Shanghai", "country": "China", "currency": "CNY", "timezone": "Asia/Shanghai", "session": "Asia Emerging", "flag": "🇨🇳", "open_hour": 8, "close_hour": 17, "map_x": 74, "map_y": 42},
    {"name": "Mumbai", "country": "India", "currency": "INR", "timezone": "Asia/Kolkata", "session": "Asia Emerging", "flag": "🇮🇳", "open_hour": 9, "close_hour": 17, "map_x": 63, "map_y": 50},
    {"name": "Dubai", "country": "UAE", "currency": "AED", "timezone": "Asia/Dubai", "session": "Middle East", "flag": "🇦🇪", "open_hour": 8, "close_hour": 16, "map_x": 56, "map_y": 49},
    {"name": "Frankfurt", "country": "Germany", "currency": "EUR", "timezone": "Europe/Berlin", "session": "Europe Major", "flag": "🇩🇪", "open_hour": 8, "close_hour": 17, "map_x": 48, "map_y": 36},
    {"name": "Zurich", "country": "Switzerland", "currency": "CHF", "timezone": "Europe/Zurich", "session": "Safe Haven", "flag": "🇨🇭", "open_hour": 8, "close_hour": 17, "map_x": 47, "map_y": 39},
    {"name": "London", "country": "United Kingdom", "currency": "GBP", "timezone": "Europe/London", "session": "London Major", "flag": "🇬🇧", "open_hour": 8, "close_hour": 17, "map_x": 44, "map_y": 35},
    {"name": "Johannesburg", "country": "South Africa", "currency": "ZAR", "timezone": "Africa/Johannesburg", "session": "Africa Emerging", "flag": "🇿🇦", "open_hour": 8, "close_hour": 17, "map_x": 52, "map_y": 75},
    {"name": "Sao Paulo", "country": "Brazil", "currency": "BRL", "timezone": "America/Sao_Paulo", "session": "LatAm Emerging", "flag": "🇧🇷", "open_hour": 9, "close_hour": 18, "map_x": 34, "map_y": 68},
    {"name": "Toronto", "country": "Canada", "currency": "CAD", "timezone": "America/Toronto", "session": "North America", "flag": "🇨🇦", "open_hour": 8, "close_hour": 17, "map_x": 25, "map_y": 34},
    {"name": "New York", "country": "United States", "currency": "USD", "timezone": "America/New_York", "session": "New York Major", "flag": "🇺🇸", "open_hour": 8, "close_hour": 17, "map_x": 27, "map_y": 41},
    {"name": "Mexico City", "country": "Mexico", "currency": "MXN", "timezone": "America/Mexico_City", "session": "LatAm Emerging", "flag": "🇲🇽", "open_hour": 8, "close_hour": 17, "map_x": 20, "map_y": 52},
]

pairs = [
    {"symbol": "XAUUSD", "name": "Gold / US Dollar", "tag": "Safe Haven"},
    {"symbol": "EURUSD", "name": "Euro / US Dollar", "tag": "Most Liquid"},
    {"symbol": "GBPUSD", "name": "Pound / US Dollar", "tag": "London Power"},
    {"symbol": "USDJPY", "name": "US Dollar / Yen", "tag": "Asia Major"},
    {"symbol": "GBPJPY", "name": "Pound / Yen", "tag": "Volatility King"},
    {"symbol": "USDCHF", "name": "US Dollar / Swiss Franc", "tag": "Risk Hedge"},
    {"symbol": "AUDUSD", "name": "Australian Dollar / US Dollar", "tag": "Commodity FX"},
    {"symbol": "USDCAD", "name": "US Dollar / Canadian Dollar", "tag": "Oil Linked"},
    {"symbol": "NZDUSD", "name": "New Zealand Dollar / US Dollar", "tag": "Pacific Open"},
    {"symbol": "EURJPY", "name": "Euro / Yen", "tag": "Carry Flow"},
    {"symbol": "EURGBP", "name": "Euro / Pound", "tag": "Europe Spread"},
    {"symbol": "USDCNH", "name": "US Dollar / Offshore Yuan", "tag": "China Risk"},
]

news = [
    {"impact": "HIGH", "currency": "USD", "title": "US CPI Inflation Data", "region": "United States"},
    {"impact": "HIGH", "currency": "JPY", "title": "Bank of Japan Policy Statement", "region": "Japan"},
    {"impact": "HIGH", "currency": "EUR", "title": "ECB Interest Rate Decision", "region": "Eurozone"},
    {"impact": "HIGH", "currency": "GBP", "title": "Bank of England Policy Report", "region": "United Kingdom"},
]

# -----------------------------
# MARKET ENGINE
# -----------------------------
def seconds_until(target_dt, now):
    return max(0, int((target_dt - now).total_seconds()))


def format_duration(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}h {minutes:02d}m {secs:02d}s"


def get_market_state(market):
    tz = ZoneInfo(market["timezone"])
    now = datetime.now(tz)

    open_dt = now.replace(hour=market["open_hour"], minute=0, second=0, microsecond=0)
    close_dt = now.replace(hour=market["close_hour"], minute=0, second=0, microsecond=0)

    if open_dt <= now < close_dt:
        status = "ACTIVE"
        status_class = "active"
        countdown_label = "closes in"
        countdown_seconds = seconds_until(close_dt, now)
        progress = int(((now - open_dt).total_seconds() / (close_dt - open_dt).total_seconds()) * 100)
    elif now < open_dt:
        status = "OPENING SOON" if seconds_until(open_dt, now) <= 7200 else "CLOSED"
        status_class = "soon" if status == "OPENING SOON" else "closed"
        countdown_label = "opens in"
        countdown_seconds = seconds_until(open_dt, now)
        progress = 0
    else:
        next_open = open_dt + timedelta(days=1)
        status = "CLOSED"
        status_class = "closed"
        countdown_label = "opens in"
        countdown_seconds = seconds_until(next_open, now)
        progress = 100

    return {
        **market,
        "local_time": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%a").upper(),
        "status": status,
        "status_class": status_class,
        "countdown_label": countdown_label,
        "countdown": format_duration(countdown_seconds),
        "progress": progress,
    }


def build_market_data():
    return [get_market_state(market) for market in markets]


def get_overlap_data(market_data):
    active = [m for m in market_data if m["status"] == "ACTIVE"]
    active_names = [m["name"] for m in active]

    overlap_rules = [
        ("Sydney + Tokyo", ["Sydney", "Tokyo"], "Pacific-Asia liquidity handoff"),
        ("Tokyo + Singapore + Shanghai", ["Tokyo", "Singapore", "Shanghai"], "Asia institutional flow"),
        ("Frankfurt + London", ["Frankfurt", "London"], "European liquidity build-up"),
        ("London + New York", ["London", "New York"], "Highest global FX liquidity window"),
        ("New York + Toronto", ["New York", "Toronto"], "North America dollar flow"),
    ]

    detected = []
    for label, names, description in overlap_rules:
        matched = [name for name in names if name in active_names]
        if len(matched) >= 2:
            detected.append({"label": label, "description": description, "strength": len(matched)})

    if detected:
        best = sorted(detected, key=lambda item: item["strength"], reverse=True)[0]
    elif active:
        best = {"label": f"{active[0]['name']} ACTIVE", "description": "Single-session liquidity active", "strength": 1}
    else:
        best = {"label": "MARKET RESET", "description": "Liquidity preparing for next session", "strength": 0}

    return best, detected, active


def get_market_intelligence(market_data):
    best_overlap, overlaps, active = get_overlap_data(market_data)
    active_currencies = {m["currency"] for m in active}

    if {"GBP", "USD"}.issubset(active_currencies):
        sentiment = "PEAK LIQUIDITY"
        sentiment_class = "hot"
        sentiment_sub = "London and New York are active together"
    elif {"JPY", "AUD"}.intersection(active_currencies):
        sentiment = "ASIA FLOW"
        sentiment_class = "bullish"
        sentiment_sub = "Pacific and Asia sessions are driving the board"
    elif active:
        sentiment = "RISK WATCH"
        sentiment_class = "medium"
        sentiment_sub = "Liquidity is active but fragmented"
    else:
        sentiment = "STANDBY"
        sentiment_class = "muted"
        sentiment_sub = "Waiting for the next market open"

    volatility = "HIGH" if len(active) >= 4 else "MEDIUM" if len(active) >= 2 else "LOW"
    volatility_class = "hot" if volatility == "HIGH" else "medium" if volatility == "MEDIUM" else "muted"

    return {
        "sentiment": sentiment,
        "sentiment_class": sentiment_class,
        "sentiment_sub": sentiment_sub,
        "overlap_label": best_overlap["label"],
        "overlap_sub": best_overlap["description"],
        "volatility": volatility,
        "volatility_class": volatility_class,
        "safe_haven": "XAU / JPY / CHF WATCH",
        "safe_haven_sub": "Monitor gold, yen and Swiss franc reactions",
        "active_count": len(active),
        "overlap_count": len(overlaps),
    }


@app.route("/api/markets")
def api_markets():
    market_data = build_market_data()
    intelligence = get_market_intelligence(market_data)
    return jsonify({
        "server_time_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "markets": market_data,
        "intelligence": intelligence,
    })


@app.route("/")
def home():
    market_data = build_market_data()
    intelligence = get_market_intelligence(market_data)
    active_count = sum(1 for m in market_data if m["status"] == "ACTIVE")
    soon_count = sum(1 for m in market_data if m["status"] == "OPENING SOON")
    high_news_count = sum(1 for item in news if item["impact"] == "HIGH")

    html = """
<!DOCTYPE html>
<html>
<head>
    <title>FX Minutes | Global FX Command Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <style>
        :root {
            --void: #000000;
            --graphite: #020617;
            --panel: rgba(15, 23, 42, 0.78);
            --panel-deep: rgba(2, 6, 23, 0.92);
            --line: rgba(255, 255, 255, 0.08);
            --orange: #f97316;
            --orange-2: #fb923c;
            --green: #22c55e;
            --red: #ef4444;
            --amber: #f59e0b;
            --blue: #3b82f6;
            --muted: #94a3b8;
            --text: #f8fafc;
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            min-height: 100vh;
            background:
                radial-gradient(circle at 15% 0%, rgba(249,115,22,0.25), transparent 28%),
                radial-gradient(circle at 90% 15%, rgba(59,130,246,0.12), transparent 25%),
                radial-gradient(circle at 70% 90%, rgba(249,115,22,0.12), transparent 24%),
                #000;
            overflow-x: hidden;
        }

        body::before {
            content: "";
            position: fixed;
            inset: 0;
            background-image:
                linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
            background-size: 48px 48px;
            mask-image: radial-gradient(circle at center, black, transparent 75%);
            pointer-events: none;
        }

        .page { padding: 34px; position: relative; z-index: 1; }

        .glass {
            background: linear-gradient(145deg, rgba(15,23,42,0.82), rgba(2,6,23,0.88));
            border: 1px solid var(--line);
            border-radius: 32px;
            box-shadow: 0 34px 90px rgba(0, 0, 0, 0.48);
            backdrop-filter: blur(22px);
        }

        .hero-card {
            padding: 38px;
            margin-bottom: 28px;
            overflow: hidden;
            position: relative;
        }

        .hero-card::after {
            content: "";
            position: absolute;
            width: 520px;
            height: 520px;
            right: -220px;
            top: -260px;
            background: radial-gradient(circle, rgba(249,115,22,0.24), transparent 62%);
            filter: blur(8px);
            pointer-events: none;
        }

        .top-layout {
            display: grid;
            grid-template-columns: 1.6fr 0.9fr;
            gap: 28px;
            align-items: stretch;
        }

        .eyebrow {
            color: var(--orange-2);
            font-size: 12px;
            letter-spacing: 4px;
            text-transform: uppercase;
            font-weight: 900;
        }

        h1 {
            font-size: clamp(44px, 5vw, 76px);
            line-height: 0.95;
            margin: 18px 0 18px;
            letter-spacing: -3px;
        }

        .orange { color: var(--orange); }

        .subtitle {
            color: #cbd5e1;
            font-size: 18px;
            line-height: 1.65;
            max-width: 950px;
        }

        .metrics, .pair-grid, .intel-grid { display: grid; gap: 16px; }

        .metrics {
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin-top: 30px;
        }

        .metric, .pair-card, .intel-card, .market-card, .alert-card {
            background: linear-gradient(145deg, rgba(2,6,23,0.96), rgba(15,23,42,0.92));
            border: 1px solid rgba(249,115,22,0.14);
            border-radius: 22px;
            transition: 0.25s ease;
        }

        .metric:hover, .pair-card:hover, .intel-card:hover, .market-card:hover, .alert-card:hover {
            transform: translateY(-3px);
            border-color: rgba(249,115,22,0.58);
            box-shadow: 0 18px 50px rgba(249,115,22,0.13);
        }

        .metric { padding: 18px 20px; }
        .metric strong { display: block; font-size: 32px; line-height: 1; }
        .metric span { color: var(--muted); font-size: 13px; }

        .pair-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin-top: 28px;
        }

        .pair-card { padding: 18px; min-height: 112px; }
        .pair-symbol { color: var(--orange); font-weight: 950; font-size: 24px; letter-spacing: 1px; }
        .pair-name { color: #cbd5e1; margin-top: 8px; font-size: 14px; }
        .pair-tag { display: inline-flex; margin-top: 14px; padding: 6px 10px; border-radius: 999px; background: rgba(249,115,22,0.13); color: var(--orange-2); font-size: 11px; font-weight: 900; letter-spacing: 1px; }

        .map-widget {
            padding: 24px;
            min-height: 100%;
            position: relative;
            overflow: hidden;
        }

        .map-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
        }

        .map-title { color: var(--orange-2); letter-spacing: 3px; font-weight: 950; font-size: 13px; }
        .server-time { color: var(--muted); font-size: 12px; }

        .world-map {
            position: relative;
            height: 380px;
            border-radius: 24px;
            overflow: hidden;
            background:
                radial-gradient(circle at 50% 45%, rgba(59,130,246,0.12), transparent 40%),
                linear-gradient(180deg, rgba(15,23,42,0.98), rgba(2,6,23,0.98));
            border: 1px solid rgba(255,255,255,0.07);
        }

        .world-map::before {
            content: "";
            position: absolute;
            inset: 0;
            opacity: 0.24;
            background:
                radial-gradient(ellipse at 24% 38%, #64748b 0 8%, transparent 9%),
                radial-gradient(ellipse at 34% 62%, #64748b 0 7%, transparent 8%),
                radial-gradient(ellipse at 48% 36%, #64748b 0 8%, transparent 9%),
                radial-gradient(ellipse at 56% 54%, #64748b 0 9%, transparent 10%),
                radial-gradient(ellipse at 72% 42%, #64748b 0 12%, transparent 13%),
                radial-gradient(ellipse at 80% 69%, #64748b 0 8%, transparent 9%);
            filter: blur(0.2px);
        }

        .time-ruler {
            display: grid;
            grid-template-columns: repeat(12, 1fr);
            gap: 4px;
            color: #e5e7eb;
            font-weight: 800;
            font-size: 12px;
            padding: 4px 10px 14px;
            position: relative;
            z-index: 3;
        }

        .time-ruler span { text-align: center; opacity: 0.72; }

        .now-line {
            position: absolute;
            top: 36px;
            bottom: 72px;
            left: 50%;
            width: 3px;
            border-radius: 999px;
            background: linear-gradient(var(--blue), #60a5fa, var(--blue));
            box-shadow: 0 0 22px rgba(59,130,246,0.8);
            z-index: 6;
            animation: scanPulse 2s ease-in-out infinite;
        }

        @keyframes scanPulse { 0%,100%{opacity:.8} 50%{opacity:1} }

        .session-bar {
            position: absolute;
            min-width: 250px;
            z-index: 5;
            border-radius: 16px;
            background: rgba(148,163,184,0.66);
            border: 1px solid rgba(255,255,255,0.08);
            color: #0f172a;
            backdrop-filter: blur(8px);
            box-shadow: 0 16px 44px rgba(0,0,0,0.25);
            overflow: hidden;
        }

        .session-bar.active { background: linear-gradient(90deg, rgba(34,197,94,0.92), rgba(20,184,166,0.72)); color: #ecfeff; box-shadow: 0 0 35px rgba(34,197,94,0.28); }
        .session-bar.soon { background: linear-gradient(90deg, rgba(245,158,11,0.9), rgba(249,115,22,0.64)); color: #fff7ed; box-shadow: 0 0 35px rgba(245,158,11,0.24); }
        .session-bar.closed { background: rgba(148,163,184,0.42); color: #e2e8f0; }

        .bar-fill { height: 5px; background: rgba(255,255,255,0.75); width: var(--progress); }
        .bar-body { padding: 10px 14px 12px 58px; position: relative; }
        .flag-badge { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); width: 42px; height: 42px; display: grid; place-items: center; border-radius: 999px; background: #f8fafc; color: #0f172a; font-size: 25px; box-shadow: 0 0 0 5px rgba(15,23,42,0.55); }
        .bar-title { font-weight: 950; letter-spacing: 1px; }
        .bar-sub { font-size: 12px; opacity: 0.9; margin-top: 3px; }

        .s-london { left: 37%; top: 78px; }
        .s-newyork { left: 14%; top: 150px; }
        .s-frankfurt { left: 42%; top: 172px; }
        .s-tokyo { left: 63%; top: 150px; }
        .s-sydney { left: 70%; top: 250px; }

        .map-pin {
            position: absolute;
            left: var(--x);
            top: var(--y);
            width: 10px;
            height: 10px;
            border-radius: 999px;
            background: var(--muted);
            z-index: 4;
            box-shadow: 0 0 16px rgba(148,163,184,0.6);
        }
        .map-pin.active { background: var(--green); box-shadow: 0 0 24px rgba(34,197,94,0.85); }
        .map-pin.soon { background: var(--amber); box-shadow: 0 0 24px rgba(245,158,11,0.75); }

        .session-dock {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 10px;
            margin-top: 14px;
        }

        .dock-card {
            padding: 13px;
            border-radius: 18px;
            background: rgba(2,6,23,0.78);
            border: 1px solid rgba(255,255,255,0.08);
        }
        .dock-title { font-weight: 900; font-size: 13px; }
        .dock-time { color: #cbd5e1; margin-top: 5px; font-size: 13px; }
        .dock-day { color: #60a5fa; margin-top: 5px; font-size: 11px; font-weight: 900; }

        .market-state {
            margin-top: 14px;
            padding: 18px;
            border-radius: 22px;
            background: rgba(2,6,23,0.86);
            border: 1px solid rgba(255,255,255,0.08);
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: center;
        }
        .market-open-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--green); display: inline-block; margin-right: 8px; box-shadow: 0 0 14px var(--green); }
        .device-time { font-size: 34px; font-weight: 200; letter-spacing: -1px; }

        .intel-grid { grid-template-columns: repeat(4, 1fr); margin: 28px 0; }
        .intel-card { padding: 20px; }
        .intel-label { color: var(--muted); font-size: 11px; letter-spacing: 3px; font-weight: 950; }
        .intel-value { margin-top: 12px; font-size: 22px; font-weight: 950; }
        .intel-sub { margin-top: 10px; color: #cbd5e1; font-size: 13px; line-height: 1.5; }
        .bullish { color: var(--green); }
        .bearish { color: var(--red); }
        .medium { color: var(--amber); }
        .hot { color: var(--orange); }
        .muted { color: var(--muted); }

        .ticker-wrap {
            margin-top: 24px;
            overflow: hidden;
            border-radius: 22px;
            background: #020617;
            border: 1px solid rgba(255,255,255,0.08);
            padding: 10px;
        }

        .grid { display: grid; grid-template-columns: 1.35fr 0.85fr; gap: 28px; }
        .section { padding: 30px; }
        .section h2 { margin-top: 0; font-size: 24px; }

        .market-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 16px;
            max-height: 720px;
            overflow-y: auto;
            padding-right: 6px;
        }

        .market-card, .alert-card { padding: 20px; margin-bottom: 0; }
        .market-top { display: flex; justify-content: space-between; gap: 14px; align-items: center; }
        .market-name { font-size: 19px; font-weight: 900; }
        .time { color: var(--orange); font-weight: 900; }
        .country { color: var(--muted); margin: 8px 0 14px; }
        .currency { color: var(--orange-2); font-weight: 900; font-size: 12px; letter-spacing: 2px; }
        .status { display: inline-flex; padding: 8px 12px; border-radius: 999px; font-size: 11px; font-weight: 950; letter-spacing: 1px; }
        .active { color: var(--green); background: rgba(34,197,94,0.12); }
        .soon { color: var(--amber); background: rgba(245,158,11,0.12); }
        .closed { color: var(--muted); background: rgba(148,163,184,0.12); }

        .progress-track { height: 6px; margin-top: 14px; border-radius: 999px; background: rgba(148,163,184,0.15); overflow: hidden; }
        .progress-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--orange), var(--green)); width: var(--progress); }
        .countdown { color: #cbd5e1; font-size: 12px; margin-top: 10px; }

        .impact { font-size: 11px; font-weight: 950; letter-spacing: 3px; }
        .HIGH { color: var(--red); }
        .news-title { margin: 8px 0 5px; font-weight: 900; font-size: 16px; }
        .region { color: var(--muted); font-size: 13px; }

        @media (max-width: 1250px) {
            .top-layout, .grid { grid-template-columns: 1fr; }
            .pair-grid, .intel-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }

        @media (max-width: 760px) {
            .page { padding: 16px; }
            .hero-card, .section { padding: 22px; }
            h1 { letter-spacing: -1px; }
            .metrics, .pair-grid, .intel-grid, .market-grid, .session-dock { grid-template-columns: 1fr; }
            .world-map { height: 520px; }
            .session-bar { left: 5% !important; right: 5%; min-width: auto; }
            .s-london { top: 70px; }
            .s-newyork { top: 145px; }
            .s-frankfurt { top: 220px; }
            .s-tokyo { top: 295px; }
            .s-sydney { top: 370px; }
        }
    </style>
</head>

<body>
    <main class="page">
        <section class="hero-card glass">
            <div class="top-layout">
                <div>
                    <div class="eyebrow">FX Minutes Intelligence System</div>
                    <h1>Global FX <span class="orange">Command Dashboard</span></h1>
                    <p class="subtitle">
                        A premium command cockpit for pro traders: live TradingView-powered FX instruments,
                        global market sessions, overlap intelligence, priority macro news, and liquid currency-pair focus.
                    </p>

                    <div class="metrics">
                        <div class="metric"><strong id="activeCount">{{ active_count }}</strong><span>Active Markets</span></div>
                        <div class="metric"><strong id="soonCount">{{ soon_count }}</strong><span>Opening Soon</span></div>
                        <div class="metric"><strong>{{ high_news_count }}</strong><span>High Priority News</span></div>
                        <div class="metric"><strong>{{ pairs|length }}</strong><span>Tracked Instruments</span></div>
                    </div>

                    <div class="pair-grid">
                        {% for pair in pairs[:8] %}
                        <div class="pair-card">
                            <div class="pair-symbol">{{ pair.symbol }}</div>
                            <div class="pair-name">{{ pair.name }}</div>
                            <div class="pair-tag">{{ pair.tag }}</div>
                        </div>
                        {% endfor %}
                    </div>
                </div>

                <aside class="map-widget glass">
                    <div class="map-head">
                        <div class="map-title">GLOBAL SESSION MAP</div>
                        <div class="server-time" id="serverTime">Server Sync</div>
                    </div>

                    <div class="world-map">
                        <div class="time-ruler">
                            <span>12</span><span>2</span><span>4</span><span>6</span><span>8</span><span>10</span><span>12</span><span>2</span><span>4</span><span>6</span><span>8</span><span>10</span>
                        </div>
                        <div class="now-line"></div>

                        {% for market in markets %}
                        <div class="map-pin {{ market.status_class }}" style="--x: {{ market.map_x }}%; --y: {{ market.map_y }}%;" title="{{ market.name }} {{ market.status }}"></div>
                        {% endfor %}

                        {% for market in markets %}
                            {% if market.name in ["London", "New York", "Frankfurt", "Tokyo", "Sydney"] %}
                            <div class="session-bar {{ market.status_class }} s-{{ market.name|lower|replace(' ', '') }}">
                                <div class="bar-fill" style="--progress: {{ market.progress }}%;"></div>
                                <div class="bar-body">
                                    <div class="flag-badge">{{ market.flag }}</div>
                                    <div class="bar-title">{{ market.name|upper }}</div>
                                    <div class="bar-sub">{{ market.countdown }} · {{ market.countdown_label }}</div>
                                </div>
                            </div>
                            {% endif %}
                        {% endfor %}
                    </div>

                    <div class="session-dock">
                        {% for market in markets %}
                            {% if market.name in ["New York", "London", "Frankfurt", "Tokyo", "Sydney"] %}
                            <div class="dock-card">
                                <div class="dock-title">{{ market.flag }} {{ market.name }}</div>
                                <div class="dock-time" data-tz="{{ market.timezone }}">{{ market.local_time }}</div>
                                <div class="dock-day">{{ market.weekday }}</div>
                            </div>
                            {% endif %}
                        {% endfor %}
                    </div>

                    <div class="market-state">
                        <div>
                            <div><span class="market-open-dot"></span><strong id="marketState">MARKET: {{ 'OPEN' if active_count > 0 else 'CLOSED' }}</strong></div>
                            <div class="server-time" id="overlapState">{{ intelligence.overlap_label }}</div>
                        </div>
                        <div class="device-time" id="deviceTime">--:--</div>
                    </div>
                </aside>
            </div>

            <div class="intel-grid">
                <div class="intel-card">
                    <div class="intel-label">GLOBAL SENTIMENT</div>
                    <div class="intel-value {{ intelligence.sentiment_class }}" id="sentimentValue">{{ intelligence.sentiment }}</div>
                    <div class="intel-sub" id="sentimentSub">{{ intelligence.sentiment_sub }}</div>
                </div>

                <div class="intel-card">
                    <div class="intel-label">ACTIVE OVERLAP</div>
                    <div class="intel-value hot" id="overlapValue">{{ intelligence.overlap_label }}</div>
                    <div class="intel-sub" id="overlapSub">{{ intelligence.overlap_sub }}</div>
                </div>

                <div class="intel-card">
                    <div class="intel-label">VOLATILITY PULSE</div>
                    <div class="intel-value {{ intelligence.volatility_class }}" id="volatilityValue">{{ intelligence.volatility }}</div>
                    <div class="intel-sub">Driven by active-session density and overlap strength</div>
                </div>

                <div class="intel-card">
                    <div class="intel-label">SAFE HAVEN FLOW</div>
                    <div class="intel-value bearish">{{ intelligence.safe_haven }}</div>
                    <div class="intel-sub">{{ intelligence.safe_haven_sub }}</div>
                </div>
            </div>

            <div class="ticker-wrap">
                <div class="tradingview-widget-container">
                    <div class="tradingview-widget-container__widget"></div>
                    <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
                    {
                        "symbols": [
                            {"proName": "OANDA:XAUUSD", "title": "XAU/USD"},
                            {"proName": "FX:EURUSD", "title": "EUR/USD"},
                            {"proName": "FX:GBPUSD", "title": "GBP/USD"},
                            {"proName": "FX:USDJPY", "title": "USD/JPY"},
                            {"proName": "FX:GBPJPY", "title": "GBP/JPY"},
                            {"proName": "FX:USDCHF", "title": "USD/CHF"},
                            {"proName": "FX:AUDUSD", "title": "AUD/USD"},
                            {"proName": "FX:USDCAD", "title": "USD/CAD"},
                            {"proName": "FX:NZDUSD", "title": "NZD/USD"},
                            {"proName": "FX:USDCNH", "title": "USD/CNH"}
                        ],
                        "showSymbolLogo": true,
                        "isTransparent": true,
                        "displayMode": "adaptive",
                        "colorTheme": "dark",
                        "locale": "en"
                    }
                    </script>
                </div>
            </div>
        </section>

        <section class="grid">
            <div class="section glass">
                <h2>Financial Market Countries</h2>
                <div class="market-grid" id="marketGrid">
                    {% for market in markets %}
                    <div class="market-card">
                        <div class="market-top">
                            <div>
                                <div class="market-name">{{ market.flag }} {{ market.name }}</div>
                                <div class="currency">{{ market.currency }}</div>
                            </div>
                            <div class="time">{{ market.local_time }}</div>
                        </div>
                        <div class="country">{{ market.country }} · {{ market.session }}</div>
                        <span class="status {{ market.status_class }}">{{ market.status }}</span>
                        <div class="progress-track"><div class="progress-fill" style="--progress: {{ market.progress }}%;"></div></div>
                        <div class="countdown">{{ market.countdown_label }} {{ market.countdown }}</div>
                    </div>
                    {% endfor %}
                </div>
            </div>

            <div class="section glass">
                <h2>High Priority News</h2>
                {% for item in news %}
                <div class="alert-card">
                    <div class="impact HIGH">{{ item.impact }} · {{ item.currency }}</div>
                    <div class="news-title">{{ item.title }}</div>
                    <div class="region">{{ item.region }}</div>
                </div>
                {% endfor %}
            </div>
        </section>
    </main>

    <script>
        function updateDeviceClock() {
            const now = new Date();
            const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const deviceTime = document.getElementById('deviceTime');
            if (deviceTime) deviceTime.textContent = time;

            document.querySelectorAll('[data-tz]').forEach(el => {
                const tz = el.getAttribute('data-tz');
                el.textContent = new Intl.DateTimeFormat('en-GB', {
                    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: tz
                }).format(now);
            });
        }

        async function refreshMarketData() {
            try {
                const res = await fetch('/api/markets');
                const data = await res.json();

                document.getElementById('serverTime').textContent = data.server_time_utc;
                document.getElementById('activeCount').textContent = data.intelligence.active_count;
                document.getElementById('marketState').textContent = data.intelligence.active_count > 0 ? 'MARKET: OPEN' : 'MARKET: CLOSED';
                document.getElementById('overlapState').textContent = data.intelligence.overlap_label;
                document.getElementById('sentimentValue').textContent = data.intelligence.sentiment;
                document.getElementById('sentimentSub').textContent = data.intelligence.sentiment_sub;
                document.getElementById('overlapValue').textContent = data.intelligence.overlap_label;
                document.getElementById('overlapSub').textContent = data.intelligence.overlap_sub;
                document.getElementById('volatilityValue').textContent = data.intelligence.volatility;
            } catch (error) {
                console.error('Market refresh failed:', error);
            }
        }

        updateDeviceClock();
        refreshMarketData();
        setInterval(updateDeviceClock, 1000);
        setInterval(refreshMarketData, 30000);
    </script>
</body>
</html>
    """

    return render_template_string(
        html,
        markets=market_data,
        news=news,
        pairs=pairs,
        active_count=active_count,
        soon_count=soon_count,
        high_news_count=high_news_count,
        intelligence=intelligence,
    )


if __name__ == "__main__":
    app.run(debug=True)
