from flask import Flask, jsonify, render_template_string, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from functools import wraps
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cosmic-fx-dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cosmic_fx.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

IST = ZoneInfo("Asia/Kolkata")


# -----------------------------
# DATABASE
# -----------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    trader_type = db.Column(db.String(80), default="Intraday Trader")
    preferred_market = db.Column(db.String(80), default="India")
    timezone = db.Column(db.String(80), default="Asia/Kolkata")
    alexa_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(180), nullable=False)
    message = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(30), default="INFO")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# -----------------------------
# DATA
# -----------------------------
markets = [
    {"name": "Sydney", "country": "Australia", "currency": "AUD", "timezone": "Australia/Sydney", "session": "Pacific", "flag": "🇦🇺", "open_hour": 8, "close_hour": 17, "map_x": 77, "map_y": 66},
    {"name": "Tokyo", "country": "Japan", "currency": "JPY", "timezone": "Asia/Tokyo", "session": "Asia Major", "flag": "🇯🇵", "open_hour": 8, "close_hour": 17, "map_x": 79, "map_y": 36},
    {"name": "Singapore", "country": "Singapore", "currency": "SGD", "timezone": "Asia/Singapore", "session": "Asia Hub", "flag": "🇸🇬", "open_hour": 8, "close_hour": 17, "map_x": 71, "map_y": 53},
    {"name": "Mumbai", "country": "India", "currency": "INR", "timezone": "Asia/Kolkata", "session": "India Equity", "flag": "🇮🇳", "open_hour": 9, "close_hour": 15, "map_x": 63, "map_y": 50},
    {"name": "Dubai", "country": "UAE", "currency": "AED", "timezone": "Asia/Dubai", "session": "Middle East", "flag": "🇦🇪", "open_hour": 8, "close_hour": 16, "map_x": 56, "map_y": 49},
    {"name": "Frankfurt", "country": "Germany", "currency": "EUR", "timezone": "Europe/Berlin", "session": "Europe", "flag": "🇩🇪", "open_hour": 8, "close_hour": 17, "map_x": 48, "map_y": 36},
    {"name": "London", "country": "United Kingdom", "currency": "GBP", "timezone": "Europe/London", "session": "London Major", "flag": "🇬🇧", "open_hour": 8, "close_hour": 17, "map_x": 44, "map_y": 35},
    {"name": "New York", "country": "United States", "currency": "USD", "timezone": "America/New_York", "session": "New York Major", "flag": "🇺🇸", "open_hour": 8, "close_hour": 17, "map_x": 27, "map_y": 41},
]

pairs = [
    {"symbol": "NIFTY", "name": "Nifty 50", "tag": "India Core"},
    {"symbol": "BANKNIFTY", "name": "Bank Nifty", "tag": "Volatility"},
    {"symbol": "XAUUSD", "name": "Gold / US Dollar", "tag": "Safe Haven"},
    {"symbol": "EURUSD", "name": "Euro / US Dollar", "tag": "Most Liquid"},
    {"symbol": "GBPUSD", "name": "Pound / US Dollar", "tag": "London Power"},
    {"symbol": "USDJPY", "name": "US Dollar / Yen", "tag": "Asia Major"},
    {"symbol": "GBPJPY", "name": "Pound / Yen", "tag": "Volatility King"},
    {"symbol": "USDCAD", "name": "US Dollar / Canadian Dollar", "tag": "Oil Linked"},
]

news = [
    {"impact": "HIGH", "currency": "INR", "title": "India Market Opening Bell", "region": "India", "event_time": "09:15 IST"},
    {"impact": "HIGH", "currency": "USD", "title": "US CPI Inflation Data", "region": "United States", "event_time": "18:00 IST"},
    {"impact": "HIGH", "currency": "EUR", "title": "ECB Interest Rate Decision", "region": "Eurozone", "event_time": "17:45 IST"},
    {"impact": "HIGH", "currency": "GBP", "title": "Bank of England Policy Report", "region": "United Kingdom", "event_time": "16:30 IST"},
]


# -----------------------------
# HELPERS
# -----------------------------
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        user = db.session.get(User, session["user_id"])
        if user is None:
            session.clear()
            return redirect(url_for("login"))

        return fn(*args, **kwargs)
    return wrapper


def current_user():
    if "user_id" not in session:
        return None
    return db.session.get(User, session["user_id"])


def seconds_until(target_dt, now):
    return max(0, int((target_dt - now).total_seconds()))


def format_duration(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}h {m:02d}m {s:02d}s"


def is_indian_market_holiday(date_obj):
    # MVP placeholder. Add official NSE/BSE holiday API/table later.
    holidays_2026 = {
        "2026-01-26",
        "2026-03-03",
        "2026-03-31",
        "2026-05-28",
        "2026-08-15",
        "2026-10-02",
        "2026-11-09",
        "2026-12-25",
    }
    return date_obj.isoformat() in holidays_2026


def is_indian_trading_day(now_ist):
    return now_ist.weekday() < 5 and not is_indian_market_holiday(now_ist.date())


def get_indian_market_bell_status():
    now = datetime.now(IST)
    trading_day = is_indian_trading_day(now)

    open_dt = now.replace(hour=9, minute=15, second=0, microsecond=0)
    pre_open_dt = now.replace(hour=9, minute=0, second=0, microsecond=0)
    armed_dt = now.replace(hour=9, minute=12, second=0, microsecond=0)
    close_dt = now.replace(hour=15, minute=30, second=0, microsecond=0)

    if not trading_day:
        state = "HOLIDAY_OR_WEEKEND"
        label = "Indian market closed today"
        next_event = "Next valid trading day required"
        bell_now = False
    elif now < pre_open_dt:
        state = "SLEEPING"
        label = "Pre-market not started"
        next_event = f"Pre-market alert in {format_duration(seconds_until(pre_open_dt, now))}"
        bell_now = False
    elif pre_open_dt <= now < armed_dt:
        state = "PRE_MARKET"
        label = "Pre-market alert active"
        next_event = f"Bell arms in {format_duration(seconds_until(armed_dt, now))}"
        bell_now = False
    elif armed_dt <= now < open_dt:
        state = "BELL_ARMED"
        label = "Opening bell armed"
        next_event = f"NSE/BSE opens in {format_duration(seconds_until(open_dt, now))}"
        bell_now = False
    elif open_dt <= now < open_dt + timedelta(seconds=20):
        state = "RING_BELL"
        label = "Indian market open"
        next_event = "Ring opening bell now"
        bell_now = True
    elif open_dt <= now < close_dt:
        state = "MARKET_LIVE"
        label = "Indian market live"
        next_event = f"Market closes in {format_duration(seconds_until(close_dt, now))}"
        bell_now = False
    else:
        state = "MARKET_CLOSED"
        label = "Indian market closed"
        next_event = "Next session tomorrow if trading day"
        bell_now = False

    return {
        "now_ist": now.strftime("%Y-%m-%d %H:%M:%S IST"),
        "is_trading_day": trading_day,
        "state": state,
        "label": label,
        "next_event": next_event,
        "bell_now": bell_now,
        "market_open_time": "09:15 IST",
        "market_close_time": "15:30 IST",
        "disclaimer": "Information only. Not financial advice.",
    }


def get_market_state(market):
    tz = ZoneInfo(market["timezone"])
    now = datetime.now(tz)

    if market["name"] == "Mumbai":
        open_dt = now.replace(hour=9, minute=15, second=0, microsecond=0)
        close_dt = now.replace(hour=15, minute=30, second=0, microsecond=0)
    else:
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
    return [get_market_state(m) for m in markets]


def get_market_intelligence(market_data):
    active = [m for m in market_data if m["status"] == "ACTIVE"]
    names = {m["name"] for m in active}
    currencies = {m["currency"] for m in active}

    if {"London", "New York"}.issubset(names):
        overlap = "LONDON + NEW YORK"
        overlap_sub = "Peak global FX liquidity window"
    elif {"Tokyo", "Singapore"}.issubset(names):
        overlap = "ASIA LIQUIDITY"
        overlap_sub = "Asia institutional flow active"
    elif {"Mumbai"}.issubset(names):
        overlap = "INDIA LIVE"
        overlap_sub = "NSE/BSE trading session active"
    elif active:
        overlap = f"{active[0]['name']} ACTIVE"
        overlap_sub = "Single-session liquidity active"
    else:
        overlap = "MARKET RESET"
        overlap_sub = "Waiting for next liquidity window"

    if {"GBP", "USD"}.issubset(currencies):
        sentiment = "PEAK LIQUIDITY"
        sentiment_class = "hot"
    elif "INR" in currencies:
        sentiment = "INDIA FLOW"
        sentiment_class = "bullish"
    elif active:
        sentiment = "RISK WATCH"
        sentiment_class = "medium"
    else:
        sentiment = "STANDBY"
        sentiment_class = "muted"

    volatility = "HIGH" if len(active) >= 4 else "MEDIUM" if len(active) >= 2 else "LOW"

    return {
        "active_count": len(active),
        "sentiment": sentiment,
        "sentiment_class": sentiment_class,
        "overlap_label": overlap,
        "overlap_sub": overlap_sub,
        "volatility": volatility,
        "safe_haven": "XAU / JPY / CHF WATCH",
    }


# -----------------------------
# AUTH ROUTES
# -----------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        trader_type = request.form.get("trader_type", "Intraday Trader")
        preferred_market = request.form.get("preferred_market", "India")

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("signup"))

        if User.query.filter_by(email=email).first():
            flash("Email already exists. Please login.", "error")
            return redirect(url_for("login"))

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            trader_type=trader_type,
            preferred_market=preferred_market,
        )
        db.session.add(user)
        db.session.commit()

        db.session.add(Notification(
            user_id=user.id,
            title="Welcome to Cosmic Universe FX",
            message="Your trader command center is ready.",
            severity="SUCCESS",
        ))
        db.session.commit()

        session["user_id"] = user.id
        return redirect(url_for("dashboard"))

    return render_template_string(AUTH_TEMPLATE, mode="signup")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        return redirect(url_for("dashboard"))

    return render_template_string(AUTH_TEMPLATE, mode="login")


@app.route("/forgot-password")
def forgot_password():
    return render_template_string(AUTH_TEMPLATE, mode="forgot")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -----------------------------
# PAGE ROUTES
# -----------------------------
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    market_data = build_market_data()
    intelligence = get_market_intelligence(market_data)
    bell = get_indian_market_bell_status()
    notes = Notification.query.filter(
        (Notification.user_id == user.id) | (Notification.user_id.is_(None))
    ).order_by(Notification.created_at.desc()).limit(8).all()

    return render_template_string(
        DASHBOARD_TEMPLATE,
        user=user,
        markets=market_data,
        pairs=pairs,
        news=news,
        intelligence=intelligence,
        bell=bell,
        notifications=notes,
    )


# -----------------------------
# API ROUTES
# -----------------------------
@app.route("/api/markets")
@login_required
def api_markets():
    data = build_market_data()
    return jsonify({
        "server_time_utc": datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "markets": data,
        "intelligence": get_market_intelligence(data),
    })


@app.route("/api/market-bell-status")
@login_required
def api_market_bell_status():
    return jsonify(get_indian_market_bell_status())


@app.route("/api/news")
@login_required
def api_news():
    return jsonify({"news": news})


@app.route("/api/notifications")
@login_required
def api_notifications():
    user = current_user()
    rows = Notification.query.filter(
        (Notification.user_id == user.id) | (Notification.user_id.is_(None))
    ).order_by(Notification.created_at.desc()).limit(20).all()

    return jsonify({
        "notifications": [
            {
                "title": n.title,
                "message": n.message,
                "severity": n.severity,
                "created_at": n.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for n in rows
        ]
    })


@app.route("/api/alexa/test-bell", methods=["POST"])
@login_required
def api_alexa_test_bell():
    user = current_user()
    db.session.add(Notification(
        user_id=user.id,
        title="Alexa Bell Test",
        message="Alexa-ready bell event generated. Full Alexa Skill integration can consume this endpoint later.",
        severity="VOICE",
    ))
    db.session.commit()

    return jsonify({
        "status": "ok",
        "speak": "Cosmic Universe FX. Market bell test successful. Your trading command center is armed.",
        "ssml": "<speak><audio src='https://example.com/market-bell.mp3'/> Cosmic Universe FX. Market bell test successful.</speak>",
    })


@app.route("/api/alexa/briefing")
@login_required
def api_alexa_briefing():
    market_data = build_market_data()
    intel = get_market_intelligence(market_data)
    bell = get_indian_market_bell_status()

    text = (
        f"Good morning. {bell['label']}. {bell['next_event']}. "
        f"Current global status is {intel['sentiment']}. "
        f"Active overlap is {intel['overlap_label']}. "
        f"Volatility pulse is {intel['volatility']}. "
        "Trade carefully. This is market information only, not financial advice."
    )

    return jsonify({
        "briefing": text,
        "ssml": f"<speak>{text}</speak>",
    })


# -----------------------------
# TEMPLATES
# -----------------------------
AUTH_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Cosmic Universe FX</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            min-height: 100vh;
            font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: #f8fafc;
            background:
                radial-gradient(circle at 10% 10%, rgba(249,115,22,.26), transparent 28%),
                radial-gradient(circle at 90% 20%, rgba(59,130,246,.16), transparent 24%),
                radial-gradient(circle at 50% 100%, rgba(245,158,11,.12), transparent 34%),
                #000;
            display: grid;
            place-items: center;
            padding: 24px;
        }
        body:before {
            content: "";
            position: fixed;
            inset: 0;
            background-image:
                linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px);
            background-size: 44px 44px;
            mask-image: radial-gradient(circle, black, transparent 75%);
            pointer-events: none;
        }
        .auth {
            width: min(1080px, 100%);
            display: grid;
            grid-template-columns: 1fr 430px;
            gap: 28px;
            position: relative;
            z-index: 1;
        }
        .hero, .card {
            border: 1px solid rgba(255,255,255,.09);
            background: linear-gradient(145deg, rgba(15,23,42,.78), rgba(2,6,23,.92));
            backdrop-filter: blur(24px);
            border-radius: 34px;
            box-shadow: 0 40px 120px rgba(0,0,0,.52);
        }
        .hero { padding: 46px; }
        .card { padding: 30px; }
        .eyebrow {
            color: #fb923c;
            font-size: 12px;
            letter-spacing: 4px;
            font-weight: 900;
            text-transform: uppercase;
        }
        h1 {
            font-size: clamp(42px, 6vw, 78px);
            line-height: .95;
            letter-spacing: -3px;
            margin: 22px 0;
        }
        .orange { color: #f97316; }
        p { color: #cbd5e1; line-height: 1.7; font-size: 16px; }
        .pill-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-top: 28px;
        }
        .pill {
            padding: 14px;
            border: 1px solid rgba(249,115,22,.16);
            border-radius: 18px;
            background: rgba(2,6,23,.72);
            color: #e2e8f0;
            font-weight: 800;
            font-size: 13px;
        }
        h2 { margin-top: 0; }
        label { color: #94a3b8; font-size: 12px; font-weight: 900; letter-spacing: 1px; }
        input, select {
            width: 100%;
            margin: 8px 0 16px;
            padding: 14px 15px;
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,.10);
            background: rgba(0,0,0,.45);
            color: white;
            outline: none;
        }
        input:focus, select:focus {
            border-color: #f97316;
            box-shadow: 0 0 0 4px rgba(249,115,22,.12);
        }
        button {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 18px;
            background: linear-gradient(135deg, #f97316, #f59e0b);
            color: #111827;
            font-weight: 950;
            letter-spacing: 1px;
            cursor: pointer;
            box-shadow: 0 18px 50px rgba(249,115,22,.28);
        }
        a { color: #fb923c; text-decoration: none; }
        .muted { color: #94a3b8; font-size: 13px; text-align: center; margin-top: 18px; }
        .flash { color: #fca5a5; font-size: 13px; margin-bottom: 12px; }
        @media(max-width:900px){ .auth { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <main class="auth">
        <section class="hero">
            <div class="eyebrow">Cosmic Universe FX</div>
            <h1>Initialize Your <span class="orange">Trading Command Center</span></h1>
            <p>
                Market bells, global FX sessions, liquidity overlaps, high-impact alerts,
                AI briefings and Alexa-ready voice intelligence in one premium cockpit.
            </p>
            <div class="pill-grid">
                <div class="pill">🇮🇳 NSE/BSE 9:15 Bell</div>
                <div class="pill">🌍 Global FX Sessions</div>
                <div class="pill">🔊 Alexa Voice Layer</div>
                <div class="pill">⚡ Liquidity Intelligence</div>
            </div>
        </section>

        <section class="card">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% for category, message in messages %}
                    <div class="flash">{{ message }}</div>
                {% endfor %}
            {% endwith %}

            {% if mode == "login" %}
                <h2>Login</h2>
                <form method="post">
                    <label>Email</label>
                    <input name="email" type="email" required>
                    <label>Password</label>
                    <input name="password" type="password" required>
                    <button>INITIALIZE SESSION</button>
                </form>
                <div class="muted">
                    New trader? <a href="/signup">Create account</a><br>
                    <a href="/forgot-password">Forgot password?</a>
                </div>
            {% elif mode == "signup" %}
                <h2>Create Account</h2>
                <form method="post">
                    <label>Name</label>
                    <input name="name" required>
                    <label>Email</label>
                    <input name="email" type="email" required>
                    <label>Password</label>
                    <input name="password" type="password" required>
                    <label>Trader Type</label>
                    <select name="trader_type">
                        <option>Intraday Trader</option>
                        <option>Forex Trader</option>
                        <option>Options Trader</option>
                        <option>Swing Trader</option>
                        <option>Beginner Trader</option>
                    </select>
                    <label>Preferred Market</label>
                    <select name="preferred_market">
                        <option>India</option>
                        <option>Forex</option>
                        <option>Commodities</option>
                        <option>Global</option>
                    </select>
                    <button>CREATE COMMAND CENTER</button>
                </form>
                <div class="muted">Already registered? <a href="/login">Login</a></div>
            {% else %}
                <h2>Forgot Password</h2>
                <p>Password reset is placeholder in this MVP. Add email OTP later.</p>
                <div class="muted"><a href="/login">Back to login</a></div>
            {% endif %}
        </section>
    </main>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Cosmic Universe FX Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {
            --void:#000;
            --graphite:#020617;
            --panel:rgba(15,23,42,.82);
            --line:rgba(255,255,255,.09);
            --orange:#f97316;
            --gold:#f59e0b;
            --green:#22c55e;
            --red:#ef4444;
            --blue:#3b82f6;
            --muted:#94a3b8;
            --text:#f8fafc;
        }
        * { box-sizing: border-box; }
        body {
            margin:0;
            color:var(--text);
            font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
            background:
                radial-gradient(circle at 15% 0%, rgba(249,115,22,.24), transparent 28%),
                radial-gradient(circle at 90% 10%, rgba(59,130,246,.13), transparent 26%),
                radial-gradient(circle at 50% 100%, rgba(245,158,11,.12), transparent 28%),
                #000;
            min-height:100vh;
        }
        body:before {
            content:"";
            position:fixed;
            inset:0;
            background-image:
                linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px);
            background-size:48px 48px;
            mask-image:radial-gradient(circle at center, black, transparent 75%);
            pointer-events:none;
        }
        .page { padding:28px; position:relative; z-index:1; }
        .glass {
            background:linear-gradient(145deg, rgba(15,23,42,.82), rgba(2,6,23,.94));
            border:1px solid var(--line);
            border-radius:28px;
            box-shadow:0 30px 90px rgba(0,0,0,.5);
            backdrop-filter:blur(22px);
        }
        .topbar {
            display:flex;
            justify-content:space-between;
            align-items:center;
            gap:18px;
            padding:18px 22px;
            margin-bottom:22px;
        }
        .brand { font-weight:950; letter-spacing:1px; }
        .brand span { color:var(--orange); }
        .user { color:#cbd5e1; font-size:14px; }
        .logout { color:#fb923c; text-decoration:none; font-weight:900; }
        .hero {
            padding:34px;
            margin-bottom:22px;
        }
        .hero-grid {
            display:grid;
            grid-template-columns:1.35fr .85fr;
            gap:22px;
        }
        .eyebrow {
            color:#fb923c;
            font-size:12px;
            letter-spacing:4px;
            text-transform:uppercase;
            font-weight:950;
        }
        h1 {
            font-size:clamp(38px,5vw,68px);
            line-height:.95;
            letter-spacing:-2px;
            margin:16px 0;
        }
        .orange { color:var(--orange); }
        p { color:#cbd5e1; line-height:1.65; }
        .metrics, .intel, .pairs, .main-grid {
            display:grid;
            gap:16px;
        }
        .metrics { grid-template-columns:repeat(4,1fr); margin-top:24px; }
        .metric, .card, .pair, .news, .note {
            background:linear-gradient(145deg, rgba(2,6,23,.96), rgba(15,23,42,.88));
            border:1px solid rgba(249,115,22,.15);
            border-radius:22px;
            padding:18px;
        }
        .metric strong { display:block; font-size:30px; }
        .metric span, .muted { color:var(--muted); font-size:13px; }
        .bell {
            min-height:100%;
            position:relative;
            overflow:hidden;
        }
        .bell:after {
            content:"";
            position:absolute;
            width:260px;
            height:260px;
            right:-110px;
            top:-120px;
            background:radial-gradient(circle, rgba(249,115,22,.35), transparent 65%);
        }
        .bell-icon {
            font-size:64px;
            margin:12px 0;
            filter:drop-shadow(0 0 28px rgba(249,115,22,.8));
        }
        .bell.ring .bell-icon { animation:ring .45s infinite alternate; }
        @keyframes ring {
            from { transform:rotate(-8deg) scale(1); }
            to { transform:rotate(8deg) scale(1.08); }
        }
        .status-pill {
            display:inline-flex;
            padding:8px 12px;
            border-radius:999px;
            font-size:11px;
            font-weight:950;
            letter-spacing:1px;
            background:rgba(249,115,22,.14);
            color:#fb923c;
        }
        .button-row { display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }
        button {
            border:none;
            border-radius:16px;
            padding:12px 14px;
            background:linear-gradient(135deg, var(--orange), var(--gold));
            color:#111827;
            font-weight:950;
            cursor:pointer;
        }
        .secondary {
            background:rgba(255,255,255,.08);
            color:white;
            border:1px solid rgba(255,255,255,.10);
        }
        .intel { grid-template-columns:repeat(4,1fr); margin-bottom:22px; }
        .value { font-size:22px; font-weight:950; margin-top:10px; }
        .hot { color:var(--orange); }
        .bullish,.active { color:var(--green); }
        .medium,.soon { color:var(--gold); }
        .closed,.muted { color:var(--muted); }
        .main-grid {
            grid-template-columns:1.1fr .9fr;
        }
        .market-grid {
            display:grid;
            grid-template-columns:repeat(2,1fr);
            gap:14px;
        }
        .market-top { display:flex; justify-content:space-between; gap:10px; }
        .market-name { font-weight:950; font-size:18px; }
        .time { color:#fb923c; font-weight:900; }
        .progress {
            height:6px;
            background:rgba(148,163,184,.16);
            border-radius:999px;
            overflow:hidden;
            margin-top:12px;
        }
        .fill {
            height:100%;
            width:var(--p);
            background:linear-gradient(90deg, var(--orange), var(--green));
        }
        .pairs { grid-template-columns:repeat(4,1fr); margin-top:22px; }
        .symbol { color:#fb923c; font-size:22px; font-weight:950; }
        .tag { margin-top:10px; font-size:11px; color:#fb923c; }
        .right-stack { display:grid; gap:16px; }
        .impact { color:var(--red); font-size:11px; font-weight:950; letter-spacing:2px; }
        .toast {
            position:fixed;
            right:22px;
            bottom:22px;
            background:#020617;
            border:1px solid rgba(249,115,22,.45);
            padding:16px 18px;
            border-radius:18px;
            box-shadow:0 20px 70px rgba(0,0,0,.55);
            display:none;
            z-index:20;
        }
        .disclaimer {
            margin-top:22px;
            color:#94a3b8;
            font-size:12px;
            text-align:center;
        }
        @media(max-width:1100px){
            .hero-grid,.main-grid,.intel { grid-template-columns:1fr; }
            .metrics,.pairs,.market-grid { grid-template-columns:repeat(2,1fr); }
        }
        @media(max-width:650px){
            .page { padding:14px; }
            .metrics,.pairs,.market-grid { grid-template-columns:1fr; }
            .topbar { align-items:flex-start; flex-direction:column; }
        }
    </style>
</head>
<body>
    <main class="page">
        <nav class="topbar glass">
            <div>
                <div class="brand">COSMIC <span>UNIVERSE FX</span></div>
                <div class="user">Welcome, {{ user.name }} · {{ user.trader_type }} · {{ user.preferred_market }}</div>
            </div>
            <a class="logout" href="/logout">Logout</a>
        </nav>

        <section class="hero glass">
            <div class="hero-grid">
                <div>
                    <div class="eyebrow">Trader Intelligence Operating System</div>
                    <h1>Global FX <span class="orange">Command Cockpit</span></h1>
                    <p>
                        Live session clocks, Indian market bell, liquidity overlaps,
                        high-impact news, Alexa-ready voice briefing and trader alerts.
                    </p>

                    <div class="metrics">
                        <div class="metric"><strong id="activeCount">{{ intelligence.active_count }}</strong><span>Active Markets</span></div>
                        <div class="metric"><strong>{{ pairs|length }}</strong><span>Tracked Instruments</span></div>
                        <div class="metric"><strong>{{ news|length }}</strong><span>High Impact Events</span></div>
                        <div class="metric"><strong id="deviceTime">--:--</strong><span>Device Time</span></div>
                    </div>

                    <div class="pairs">
                        {% for pair in pairs %}
                        <div class="pair">
                            <div class="symbol">{{ pair.symbol }}</div>
                            <div class="muted">{{ pair.name }}</div>
                            <div class="tag">{{ pair.tag }}</div>
                        </div>
                        {% endfor %}
                    </div>
                </div>

                <aside class="card bell" id="bellCard">
                    <div class="eyebrow">Indian Market Bell</div>
                    <div class="bell-icon">🔔</div>
                    <div class="status-pill" id="bellState">{{ bell.state }}</div>
                    <h2 id="bellLabel">{{ bell.label }}</h2>
                    <p id="bellNext">{{ bell.next_event }}</p>
                    <div class="muted" id="bellTime">{{ bell.now_ist }}</div>
                    <div class="button-row">
                        <button onclick="testBell()">TEST BELL</button>
                        <button class="secondary" onclick="getBriefing()">VOICE BRIEFING</button>
                    </div>
                </aside>
            </div>
        </section>

        <section class="intel">
            <div class="card">
                <div class="eyebrow">Global Sentiment</div>
                <div class="value {{ intelligence.sentiment_class }}" id="sentimentValue">{{ intelligence.sentiment }}</div>
            </div>
            <div class="card">
                <div class="eyebrow">Active Overlap</div>
                <div class="value hot" id="overlapValue">{{ intelligence.overlap_label }}</div>
                <div class="muted" id="overlapSub">{{ intelligence.overlap_sub }}</div>
            </div>
            <div class="card">
                <div class="eyebrow">Volatility Pulse</div>
                <div class="value medium" id="volatilityValue">{{ intelligence.volatility }}</div>
            </div>
            <div class="card">
                <div class="eyebrow">Safe Haven Flow</div>
                <div class="value hot">{{ intelligence.safe_haven }}</div>
            </div>
        </section>

        <section class="main-grid">
            <div class="card">
                <h2>Global Market Sessions</h2>
                <div class="market-grid">
                    {% for market in markets %}
                    <div class="note">
                        <div class="market-top">
                            <div>
                                <div class="market-name">{{ market.flag }} {{ market.name }}</div>
                                <div class="muted">{{ market.country }} · {{ market.session }}</div>
                            </div>
                            <div class="time">{{ market.local_time }}</div>
                        </div>
                        <div class="{{ market.status_class }}" style="margin-top:12px;font-weight:950;">{{ market.status }}</div>
                        <div class="progress"><div class="fill" style="--p:{{ market.progress }}%;"></div></div>
                        <div class="muted" style="margin-top:10px;">{{ market.countdown_label }} {{ market.countdown }}</div>
                    </div>
                    {% endfor %}
                </div>
            </div>

            <div class="right-stack">
                <div class="card">
                    <h2>High Impact News</h2>
                    {% for item in news %}
                    <div class="news">
                        <div class="impact">{{ item.impact }} · {{ item.currency }} · {{ item.event_time }}</div>
                        <strong>{{ item.title }}</strong>
                        <div class="muted">{{ item.region }}</div>
                    </div>
                    {% endfor %}
                </div>

                <div class="card">
                    <h2>Alexa Voice Panel</h2>
                    <p id="briefingText">Click “Voice Briefing” to generate an Alexa-ready market briefing.</p>
                    <div class="button-row">
                        <button onclick="getBriefing()">GENERATE BRIEFING</button>
                        <button class="secondary" onclick="testBell()">TEST ALEXA BELL</button>
                    </div>
                </div>

                <div class="card">
                    <h2>Notification Center</h2>
                    {% for n in notifications %}
                    <div class="note">
                        <strong>{{ n.title }}</strong>
                        <div class="muted">{{ n.message }}</div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </section>

        <div class="disclaimer">
            This dashboard is for market information and alerting only. It does not provide financial advice, buy/sell recommendations, or guaranteed outcomes.
        </div>
    </main>

    <div class="toast" id="toast"></div>

    <script>
        let lastBellState = null;

        function playBell() {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const now = ctx.currentTime;

            [0, 0.22, 0.44].forEach((delay) => {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = "sine";
                osc.frequency.setValueAtTime(880, now + delay);
                gain.gain.setValueAtTime(0.001, now + delay);
                gain.gain.exponentialRampToValueAtTime(0.55, now + delay + 0.02);
                gain.gain.exponentialRampToValueAtTime(0.001, now + delay + 0.35);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start(now + delay);
                osc.stop(now + delay + 0.38);
            });
        }

        function toast(message) {
            const el = document.getElementById("toast");
            el.textContent = message;
            el.style.display = "block";
            setTimeout(() => el.style.display = "none", 4200);
        }

        function updateClock() {
            const now = new Date();
            document.getElementById("deviceTime").textContent =
                now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        }

        async function refreshMarkets() {
            const res = await fetch("/api/markets");
            const data = await res.json();

            document.getElementById("activeCount").textContent = data.intelligence.active_count;
            document.getElementById("sentimentValue").textContent = data.intelligence.sentiment;
            document.getElementById("overlapValue").textContent = data.intelligence.overlap_label;
            document.getElementById("overlapSub").textContent = data.intelligence.overlap_sub;
            document.getElementById("volatilityValue").textContent = data.intelligence.volatility;
        }

        async function refreshBell() {
            const res = await fetch("/api/market-bell-status");
            const data = await res.json();

            document.getElementById("bellState").textContent = data.state;
            document.getElementById("bellLabel").textContent = data.label;
            document.getElementById("bellNext").textContent = data.next_event;
            document.getElementById("bellTime").textContent = data.now_ist;

            const bellCard = document.getElementById("bellCard");

            if (data.bell_now && lastBellState !== "RING_BELL") {
                bellCard.classList.add("ring");
                playBell();
                toast("🔔 Indian market opening bell ringing now.");
                setTimeout(() => bellCard.classList.remove("ring"), 7000);
            }

            lastBellState = data.state;
        }

        async function testBell() {
            await fetch("/api/alexa/test-bell", { method: "POST" });
            document.getElementById("bellCard").classList.add("ring");
            playBell();
            toast("🔔 Alexa-ready market bell test successful.");
            setTimeout(() => document.getElementById("bellCard").classList.remove("ring"), 4000);
        }

        async function getBriefing() {
            const res = await fetch("/api/alexa/briefing");
            const data = await res.json();
            document.getElementById("briefingText").textContent = data.briefing;
            toast("Voice briefing generated.");
        }

        updateClock();
        refreshMarkets();
        refreshBell();

        setInterval(updateClock, 1000);
        setInterval(refreshBell, 10000);
        setInterval(refreshMarkets, 30000);
    </script>
</body>
</html>
"""


# -----------------------------
# INIT
# -----------------------------
with app.app_context():
    db.create_all()
    if not Notification.query.first():
        db.session.add(Notification(
            title="System Online",
            message="Cosmic Universe FX intelligence layer initialized.",
            severity="SYSTEM",
        ))
        db.session.commit()


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(debug=False, host="0.0.0.0", port=port)