"""
Budget Coach — Local Web Server
Serves the landing page and the chat app.

Install:  pip install flask ollama
Run:      python server.py

Landing page : http://localhost:5000
Chat app     : http://localhost:5000/app
"""

import json
import uuid
import argparse
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, render_template_string
import ollama

app = Flask(__name__)
app.secret_key = "budget-coach-2025"

DEFAULT_MODEL = "llama3.1:8b"
MODEL = DEFAULT_MODEL
SESSIONS: dict[str, list] = {}

# ── Storage ───────────────────────────────────────────────────────────────────

DATA_FILE = Path("budget_data.json")

def load_data():
    return json.loads(DATA_FILE.read_text()) if DATA_FILE.exists() else {"income": None, "months": {}}

def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2))

def current_month():
    return datetime.now().strftime("%Y-%m")

def last_month():
    now = datetime.now()
    y, m = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    return f"{y}-{m:02d}"

def ensure_month(data, month):
    if month not in data["months"]:
        data["months"][month] = {"expenses": [], "savings": 0}

# ── Tool handlers ─────────────────────────────────────────────────────────────

def handle_set_income(amount):
    data = load_data(); data["income"] = float(amount); save_data(data)
    return f"Income saved: ${float(amount):,.2f}/month."

def handle_add_expense(category, amount, description):
    data = load_data(); month = current_month(); ensure_month(data, month)
    data["months"][month]["expenses"].append({"category": category, "amount": float(amount), "description": description, "date": datetime.now().isoformat()})
    save_data(data)
    total = sum(e["amount"] for e in data["months"][month]["expenses"])
    return f"Added '{description}' (${float(amount):,.2f}) under {category}. Month total: ${total:,.2f}."

def handle_set_savings(amount):
    data = load_data(); month = current_month(); ensure_month(data, month)
    data["months"][month]["savings"] = float(amount); save_data(data)
    return f"Savings for {month} set to ${float(amount):,.2f}."

def handle_get_summary():
    data = load_data(); cm = current_month(); lm = last_month()
    out = {"income": data.get("income"), "current_month": cm}
    if cm in data["months"]:
        cd = data["months"][cm]; expenses = cd.get("expenses", [])
        total_exp = sum(e["amount"] for e in expenses)
        by_cat = {}
        for e in expenses: by_cat[e["category"]] = by_cat.get(e["category"], 0) + e["amount"]
        out.update({"current_expenses_total": total_exp, "current_expenses_by_category": by_cat, "current_savings": cd.get("savings", 0)})
        if data.get("income"): out["current_savings_rate_pct"] = round((out["current_savings"] / data["income"]) * 100, 1)
    if lm in data["months"]:
        ld = data["months"][lm]; last_exp = sum(e["amount"] for e in ld.get("expenses", [])); last_sav = ld.get("savings", 0)
        out.update({"last_month": lm, "last_expenses_total": last_exp, "last_savings": last_sav})
        if "current_expenses_total" in out and last_exp > 0:
            out["expenses_vs_last_month_pct"] = round((out["current_expenses_total"] - last_exp) / last_exp * 100, 1)
        if "current_savings" in out and last_sav > 0:
            out["savings_vs_last_month_pct"] = round((out["current_savings"] - last_sav) / last_sav * 100, 1)
    months = sorted(data["months"].keys())
    if months: out.update({"total_saved_all_time": sum(data["months"][m].get("savings", 0) for m in months), "months_tracked": len(months)})
    return json.dumps(out, indent=2)

def handle_clear_current_month():
    data = load_data(); data["months"].pop(current_month(), None); save_data(data)
    return f"Cleared all data for {current_month()}."

TOOLS = [
    {"type":"function","function":{"name":"set_income","description":"Save the user's monthly income.","parameters":{"type":"object","properties":{"amount":{"type":"number"}},"required":["amount"]}}},
    {"type":"function","function":{"name":"add_expense","description":"Record a single expense for the current month.","parameters":{"type":"object","properties":{"category":{"type":"string"},"amount":{"type":"number"},"description":{"type":"string"}},"required":["category","amount","description"]}}},
    {"type":"function","function":{"name":"set_savings","description":"Record how much the user saved this month.","parameters":{"type":"object","properties":{"amount":{"type":"number"}},"required":["amount"]}}},
    {"type":"function","function":{"name":"get_summary","description":"Retrieve full budget summary. Always call before giving analysis or advice.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"clear_current_month","description":"Clear all data for the current month. Only if user explicitly asks.","parameters":{"type":"object","properties":{}}}},
]

def dispatch_tool(name, arguments):
    args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
    if name == "set_income":         return handle_set_income(args["amount"])
    if name == "add_expense":        return handle_add_expense(args["category"], args["amount"], args["description"])
    if name == "set_savings":        return handle_set_savings(args["amount"])
    if name == "get_summary":        return handle_get_summary()
    if name == "clear_current_month":return handle_clear_current_month()
    return f"Unknown tool: {name}"

SYSTEM_PROMPT = f"""You are an empathetic, encouraging AI Budget Coach. Today is {datetime.now().strftime('%B %Y')}.
1. Greet new users warmly and ask for their monthly income first if not set.
2. Help them log expenses naturally — extract category, amount, and description from casual messages.
3. Ask about savings at the end of the month or when they mention saving money.
4. Call get_summary before giving any analysis, advice, or progress update.
5. Celebrate wins. Be honest but kind about overspending.
6. Show % changes vs last month clearly.
Tone: friendly coach, not a stern accountant. Keep responses concise and actionable."""

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def landing():
    return LANDING_HTML

@app.route("/app")
def chat_app():
    return CHAT_HTML

@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json()
    sid = body.get("session_id") or str(uuid.uuid4())
    user_msg = body.get("message", "").strip()
    if not user_msg: return jsonify({"error": "empty message"}), 400
    if sid not in SESSIONS: SESSIONS[sid] = []
    messages = SESSIONS[sid]
    messages.append({"role": "user", "content": user_msg})
    try:
        resp = ollama.chat(model=MODEL, messages=[{"role":"system","content":SYSTEM_PROMPT}] + messages, tools=TOOLS)
        msg = resp["message"]; messages.append(msg)
        tool_calls = msg.get("tool_calls") or []; text = msg.get("content","").strip()
        if tool_calls:
            for call in tool_calls:
                fn = call["function"]; result = dispatch_tool(fn["name"], fn.get("arguments",{}))
                messages.append({"role":"tool","content":result})
            fu = ollama.chat(model=MODEL, messages=[{"role":"system","content":SYSTEM_PROMPT}] + messages, tools=TOOLS)
            fu_msg = fu["message"]; messages.append(fu_msg); text = fu_msg.get("content","").strip()
        return jsonify({"reply": text, "session_id": sid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Landing page HTML ─────────────────────────────────────────────────────────

LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Budget Coach — Your AI Financial Coach</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet"/>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }

body {
  font-family: 'Inter', sans-serif;
  background: linear-gradient(160deg, #eef2ff 0%, #f5f3ff 50%, #fdf4ff 100%);
  color: #0f172a;
  overflow-x: hidden;
  min-height: 100vh;
}

/* ── Waves ──────────────────────────────────────────────── */
.wave-bg {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  height: 60vh;
  pointer-events: none;
  z-index: 0;
}
.wave-svg {
  position: absolute;
  bottom: 0; left: 0;
  width: 200%;
  will-change: transform;
  transform: translate3d(0,0,0);
}
.w1 { animation: wv 18s linear infinite;         opacity: 0.25; bottom: 0;    }
.w2 { animation: wv 26s linear infinite reverse; opacity: 0.20; bottom: 50px; }
.w3 { animation: wv 22s linear infinite;         opacity: 0.18; bottom: 110px;}
.w4 { animation: wv 30s linear infinite reverse; opacity: 0.15; bottom: 170px;}

@keyframes wv {
  from { transform: translate3d(0,0,0); }
  to   { transform: translate3d(-50%,0,0); }
}

/* ── Navbar ─────────────────────────────────────────────── */
nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  padding: 18px 60px;
  display: flex; align-items: center; justify-content: space-between;
  background: rgba(255,255,255,0.72);
  backdrop-filter: blur(18px);
  border-bottom: 1px solid rgba(255,255,255,0.8);
}
.nav-logo {
  font-size: 20px; font-weight: 800;
  background: linear-gradient(135deg,#7c3aed,#3b82f6);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.nav-links { display: flex; gap: 36px; }
.nav-links a { text-decoration: none; color: #64748b; font-size: 15px; font-weight: 500; transition: color .2s; }
.nav-links a:hover { color: #0f172a; }
.nav-cta {
  background: linear-gradient(135deg,#7c3aed,#3b82f6); color: white;
  border: none; padding: 11px 26px; border-radius: 50px;
  font-size: 14px; font-weight: 700; cursor: pointer; font-family: inherit;
  box-shadow: 0 4px 20px rgba(124,58,237,.3); transition: transform .2s, box-shadow .2s;
}
.nav-cta:hover { transform: translateY(-2px); box-shadow: 0 8px 28px rgba(124,58,237,.4); }

/* ── Hero ───────────────────────────────────────────────── */
.hero {
  position: relative; z-index: 1;
  min-height: 100vh;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; padding: 140px 24px 80px;
}
.hero-badge {
  display: inline-flex; align-items: center; gap: 8px;
  background: rgba(255,255,255,.85); border: 1px solid rgba(167,139,250,.4);
  border-radius: 50px; padding: 8px 18px;
  font-size: 13px; font-weight: 600; color: #7c3aed;
  margin-bottom: 32px; backdrop-filter: blur(10px);
  animation: fadeDown .8s ease both;
}
.badge-dot { width:7px;height:7px;background:#7c3aed;border-radius:50%;animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(1.4)} }
.hero h1 {
  font-size: clamp(48px,7vw,88px); font-weight: 900;
  line-height: 1.05; letter-spacing: -2px; margin-bottom: 24px;
  animation: fadeDown .8s .1s ease both;
}
.grad { background: linear-gradient(135deg,#7c3aed,#3b82f6,#06b6d4); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
.hero p {
  font-size: clamp(17px,2vw,21px); color: #64748b;
  max-width: 560px; line-height: 1.65; margin-bottom: 44px; font-weight: 400;
  animation: fadeDown .8s .2s ease both;
}
.hero-btns { display:flex; gap:14px; justify-content:center; margin-bottom:70px; animation: fadeDown .8s .3s ease both; }
.btn-primary {
  background: linear-gradient(135deg,#7c3aed,#3b82f6); color: white;
  border: none; padding: 16px 36px; border-radius: 50px;
  font-size: 16px; font-weight: 700; cursor: pointer; font-family: inherit;
  box-shadow: 0 8px 30px rgba(124,58,237,.35); transition: transform .2s, box-shadow .2s;
}
.btn-primary:hover { transform: translateY(-3px); box-shadow: 0 14px 40px rgba(124,58,237,.45); }
.btn-secondary {
  background: rgba(255,255,255,.85); color: #0f172a;
  border: 1.5px solid rgba(0,0,0,.1); padding: 16px 36px; border-radius: 50px;
  font-size: 16px; font-weight: 600; cursor: pointer; font-family: inherit;
  backdrop-filter: blur(10px); transition: transform .2s, box-shadow .2s;
}
.btn-secondary:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,.1); }

/* Floating card */
.hero-card {
  animation: fadeDown .9s .4s ease both, float 5s 1.5s ease-in-out infinite;
  background: rgba(255,255,255,.78); backdrop-filter: blur(30px);
  border: 1px solid rgba(255,255,255,.9); border-radius: 28px;
  padding: 30px 36px; max-width: 500px; width: 100%;
  box-shadow: 0 30px 80px rgba(0,0,0,.1), 0 0 0 1px rgba(255,255,255,.5);
}
@keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-12px)} }
.card-row { display:flex; align-items:center; justify-content:space-between; margin-bottom:24px; }
.card-title { font-size:15px; font-weight:700; color:#64748b; }
.card-chip { background:linear-gradient(135deg,#ede9fe,#dbeafe); color:#7c3aed; font-size:12px; font-weight:700; padding:5px 12px; border-radius:20px; }
.balance { font-size:38px; font-weight:900; letter-spacing:-1px; margin-bottom:6px; }
.balance-sub { font-size:13px; color:#64748b; margin-bottom:24px; }
.bars { display:flex; flex-direction:column; gap:12px; }
.bar-row { display:flex; align-items:center; gap:12px; }
.bar-lbl { font-size:13px; font-weight:600; color:#64748b; width:90px; text-align:left; }
.bar-track { flex:1; height:8px; background:#f1f5f9; border-radius:10px; overflow:hidden; }
.bar-fill { height:100%; border-radius:10px; animation: barGrow 1.5s 1s ease both; }
@keyframes barGrow { from{width:0!important} }
.bar-val { font-size:13px; font-weight:700; width:50px; text-align:right; }
.chips { display:flex; gap:8px; margin-top:20px; flex-wrap:wrap; }
.chip { padding:6px 14px; border-radius:20px; font-size:12px; font-weight:700; }

@keyframes fadeDown { from{opacity:0;transform:translateY(-20px)} to{opacity:1;transform:translateY(0)} }

/* ── Sections ───────────────────────────────────────────── */
section { position:relative; z-index:1; padding:120px 24px; }
.sec-label { font-size:13px; font-weight:700; letter-spacing:2px; text-transform:uppercase; color:#7c3aed; margin-bottom:16px; text-align:center; }
.sec-title { font-size:clamp(32px,4vw,52px); font-weight:900; letter-spacing:-1.5px; text-align:center; margin-bottom:16px; line-height:1.1; }
.sec-sub { font-size:18px; color:#64748b; text-align:center; max-width:520px; margin:0 auto 64px; line-height:1.6; }

/* Features */
.features { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:24px; max-width:1100px; margin:0 auto; }
.f-card {
  background: rgba(255,255,255,.75); backdrop-filter:blur(20px);
  border: 1px solid rgba(255,255,255,.9); border-radius:24px; padding:36px 32px;
  transition: transform .3s, box-shadow .3s; box-shadow:0 4px 24px rgba(0,0,0,.06);
  opacity:0; transform:translateY(30px);
}
.f-card.show { animation: revealUp .6s ease forwards; }
@keyframes revealUp { to{opacity:1;transform:translateY(0)} }
.f-card:hover { transform:translateY(-8px); box-shadow:0 20px 50px rgba(0,0,0,.12); }
.f-icon { width:58px;height:58px;border-radius:18px;display:flex;align-items:center;justify-content:center;font-size:26px;margin-bottom:22px; }
.f-card h3 { font-size:19px; font-weight:800; margin-bottom:10px; letter-spacing:-.5px; }
.f-card p { font-size:15px; color:#64748b; line-height:1.65; }

/* Steps */
.steps-box {
  background:rgba(255,255,255,.6); backdrop-filter:blur(20px);
  border:1px solid rgba(255,255,255,.9); border-radius:32px;
  padding:64px; max-width:900px; margin:0 auto;
  box-shadow:0 8px 40px rgba(0,0,0,.07);
}
.step { display:flex; align-items:flex-start; gap:28px; padding:28px 0; border-bottom:1px solid rgba(0,0,0,.06); opacity:0; transform:translateX(-20px); }
.step.show { animation: revealLeft .6s ease forwards; }
@keyframes revealLeft { to{opacity:1;transform:translateX(0)} }
.step:last-child { border-bottom:none; }
.step-num { width:52px;height:52px;border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:900;flex-shrink:0;color:white; }
.step-body h3 { font-size:18px; font-weight:800; margin-bottom:6px; letter-spacing:-.4px; }
.step-body p  { font-size:15px; color:#64748b; line-height:1.6; }

/* Stats */
.stats { display:flex; justify-content:center; gap:48px; flex-wrap:wrap; max-width:900px; margin:0 auto; }
.stat { text-align:center; opacity:0; transform:translateY(20px); }
.stat.show { animation: revealUp .6s ease forwards; }
.stat-n { font-size:52px; font-weight:900; letter-spacing:-2px; background:linear-gradient(135deg,#7c3aed,#3b82f6); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
.stat-l { font-size:15px; color:#64748b; font-weight:500; margin-top:4px; }

/* CTA */
.cta-box {
  max-width:780px; margin:0 auto;
  background:linear-gradient(135deg,#7c3aed,#3b82f6); border-radius:32px;
  padding:80px 60px; text-align:center; position:relative; overflow:hidden;
  box-shadow:0 30px 80px rgba(124,58,237,.35);
}
.cta-glow  { position:absolute;width:400px;height:400px;background:rgba(255,255,255,.1);border-radius:50%;top:-100px;right:-100px;animation:float 6s ease-in-out infinite; }
.cta-glow2 { position:absolute;width:300px;height:300px;background:rgba(255,255,255,.07);border-radius:50%;bottom:-80px;left:-60px;animation:float 8s 1s ease-in-out infinite; }
.cta-box h2 { font-size:clamp(28px,4vw,46px); font-weight:900; color:white; letter-spacing:-1.5px; margin-bottom:16px; position:relative; }
.cta-box p  { font-size:18px; color:rgba(255,255,255,.8); margin-bottom:40px; position:relative; }
.btn-white { background:white; color:#7c3aed; border:none; padding:18px 44px; border-radius:50px; font-size:17px; font-weight:800; cursor:pointer; font-family:inherit; position:relative; box-shadow:0 8px 30px rgba(0,0,0,.15); transition:transform .2s, box-shadow .2s; }
.btn-white:hover { transform:translateY(-3px); box-shadow:0 16px 40px rgba(0,0,0,.2); }

/* Footer */
footer { position:relative;z-index:1;padding:40px 60px;display:flex;align-items:center;justify-content:space-between;border-top:1px solid rgba(0,0,0,.07);background:rgba(255,255,255,.5);backdrop-filter:blur(10px); }
.f-logo { font-size:17px;font-weight:800;background:linear-gradient(135deg,#7c3aed,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text; }
footer p { font-size:13px; color:#94a3b8; }
</style>
</head>
<body>

<!-- Waves -->
<div class="wave-bg">
  <svg class="wave-svg w1" viewBox="0 0 1440 120" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M0,60 C360,120 720,0 1080,60 C1260,90 1350,30 1440,60 L1440,120 L0,120Z" fill="#c4b5fd"/>
    <path d="M1440,60 C1800,120 2160,0 2520,60 C2700,90 2790,30 2880,60 L2880,120 L1440,120Z" fill="#c4b5fd"/>
  </svg>
  <svg class="wave-svg w2" viewBox="0 0 1440 120" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M0,50 C240,110 480,10 720,55 C960,100 1200,15 1440,50 L1440,120 L0,120Z" fill="#93c5fd"/>
    <path d="M1440,50 C1680,110 1920,10 2160,55 C2400,100 2640,15 2880,50 L2880,120 L1440,120Z" fill="#93c5fd"/>
  </svg>
  <svg class="wave-svg w3" viewBox="0 0 1440 120" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M0,70 C300,20 600,110 900,65 C1100,35 1300,95 1440,70 L1440,120 L0,120Z" fill="#6ee7b7"/>
    <path d="M1440,70 C1740,20 2040,110 2340,65 C2540,35 2740,95 2880,70 L2880,120 L1440,120Z" fill="#6ee7b7"/>
  </svg>
  <svg class="wave-svg w4" viewBox="0 0 1440 120" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M0,55 C360,5 720,110 1080,55 C1260,28 1380,80 1440,55 L1440,120 L0,120Z" fill="#f9a8d4"/>
    <path d="M1440,55 C1800,5 2160,110 2520,55 C2700,28 2820,80 2880,55 L2880,120 L1440,120Z" fill="#f9a8d4"/>
  </svg>
</div>

<!-- Navbar -->
<nav>
  <div class="nav-logo">💰 Budget Coach</div>
  <div class="nav-links">
    <a href="#features">Features</a>
    <a href="#how">How it works</a>
    <a href="/app">Launch App</a>
  </div>
  <button class="nav-cta" onclick="location.href='/app'">Launch App →</button>
</nav>

<!-- Hero -->
<div class="hero">
  <div class="hero-badge"><div class="badge-dot"></div> 100% Private &amp; Local — No Cloud, No Fees</div>
  <h1>Your money.<br><span class="grad">Finally under control.</span></h1>
  <p>An AI coach that understands your spending, celebrates your wins, and helps you save more — running entirely on your own machine.</p>
  <div class="hero-btns">
    <button class="btn-primary" onclick="location.href='/app'">Get Started Free →</button>
    <button class="btn-secondary" onclick="document.getElementById('how').scrollIntoView({behavior:'smooth'})">See how it works</button>
  </div>
  <div class="hero-card">
    <div class="card-row"><span class="card-title">Monthly Overview</span><span class="card-chip">May 2025</span></div>
    <div class="balance">$1,240<span style="font-size:22px;color:#94a3b8">.00</span></div>
    <div class="balance-sub">saved this month · <span style="color:#22c55e;font-weight:700">↑ 18% vs last month</span></div>
    <div class="bars">
      <div class="bar-row"><span class="bar-lbl">🍕 Food</span><div class="bar-track"><div class="bar-fill" style="width:62%;background:linear-gradient(90deg,#a78bfa,#818cf8)"></div></div><span class="bar-val">$620</span></div>
      <div class="bar-row"><span class="bar-lbl">🏠 Rent</span><div class="bar-track"><div class="bar-fill" style="width:85%;background:linear-gradient(90deg,#60a5fa,#38bdf8)"></div></div><span class="bar-val">$850</span></div>
      <div class="bar-row"><span class="bar-lbl">🚗 Transport</span><div class="bar-track"><div class="bar-fill" style="width:28%;background:linear-gradient(90deg,#6ee7b7,#34d399)"></div></div><span class="bar-val">$280</span></div>
      <div class="bar-row"><span class="bar-lbl">🎮 Fun</span><div class="bar-track"><div class="bar-fill" style="width:18%;background:linear-gradient(90deg,#fca5a5,#f472b6)"></div></div><span class="bar-val">$180</span></div>
    </div>
    <div class="chips">
      <span class="chip" style="background:#ede9fe;color:#7c3aed">💡 Spend less on food</span>
      <span class="chip" style="background:#dcfce7;color:#16a34a">🎯 Goal: 20% savings</span>
      <span class="chip" style="background:#dbeafe;color:#2563eb">📊 4 months tracked</span>
    </div>
  </div>
</div>

<!-- Features -->
<section id="features">
  <div class="sec-label">Features</div>
  <h2 class="sec-title">Everything you need.<br><span class="grad">Nothing you don't.</span></h2>
  <p class="sec-sub">No subscriptions. No data shared. Just a smart coach living on your computer.</p>
  <div class="features">
    <div class="f-card"><div class="f-icon" style="background:#ede9fe">💬</div><h3>Talk naturally</h3><p>Say "I spent $45 on groceries" and it logs it. No forms, no spreadsheets.</p></div>
    <div class="f-card"><div class="f-icon" style="background:#dbeafe">📊</div><h3>Smart comparisons</h3><p>See how this month stacks up. Clear, honest % changes vs last month.</p></div>
    <div class="f-card"><div class="f-icon" style="background:#dcfce7">🎯</div><h3>Track your journey</h3><p>Total saved all-time, savings rate, monthly trends — watch yourself improve.</p></div>
    <div class="f-card"><div class="f-icon" style="background:#fce7f3">🔒</div><h3>100% private</h3><p>Runs entirely on your machine. Your financial data never leaves. Ever.</p></div>
    <div class="f-card"><div class="f-icon" style="background:#fef3c7">⚡</div><h3>Instant responses</h3><p>Powered by a local AI model. No cloud servers. Fast, works offline.</p></div>
    <div class="f-card"><div class="f-icon" style="background:#f0fdf4">🌱</div><h3>Encouraging tone</h3><p>A coach who celebrates wins and helps you get back on track — kindly.</p></div>
  </div>
</section>

<!-- Stats -->
<section style="padding:60px 24px">
  <div class="stats">
    <div class="stat"><div class="stat-n">$0</div><div class="stat-l">Monthly fees</div></div>
    <div class="stat"><div class="stat-n">100%</div><div class="stat-l">Private &amp; local</div></div>
    <div class="stat"><div class="stat-n">5</div><div class="stat-l">Smart tools built in</div></div>
    <div class="stat"><div class="stat-n">∞</div><div class="stat-l">Months of tracking</div></div>
  </div>
</section>

<!-- How it works -->
<section id="how">
  <div class="sec-label">How it works</div>
  <h2 class="sec-title">Up and running in<br><span class="grad">three steps.</span></h2>
  <p class="sec-sub">No accounts, no setup wizard. Just open it and start talking.</p>
  <div class="steps-box">
    <div class="step"><div class="step-num" style="background:linear-gradient(135deg,#a78bfa,#818cf8)">1</div><div class="step-body"><h3>Tell it your income</h3><p>Type your monthly income and Budget Coach saves it. That's your baseline — everything is measured against it.</p></div></div>
    <div class="step"><div class="step-num" style="background:linear-gradient(135deg,#60a5fa,#38bdf8)">2</div><div class="step-body"><h3>Log expenses by chatting</h3><p>Say "I spent $12 on lunch." The AI figures out category, amount, and description automatically.</p></div></div>
    <div class="step"><div class="step-num" style="background:linear-gradient(135deg,#6ee7b7,#34d399)">3</div><div class="step-body"><h3>Get personalized advice</h3><p>Ask "how am I doing?" and get a full summary — spending by category, % changes, savings rate, and honest advice.</p></div></div>
  </div>
</section>

<!-- CTA -->
<section style="padding:80px 24px 140px">
  <div class="cta-box">
    <div class="cta-glow"></div><div class="cta-glow2"></div>
    <h2>Start your financial journey today.</h2>
    <p>Free forever. Runs locally. Takes 2 minutes to set up.</p>
    <button class="btn-white" onclick="location.href='/app'">Launch Budget Coach →</button>
  </div>
</section>

<!-- Footer -->
<footer>
  <div class="f-logo">💰 Budget Coach</div>
  <p>Built with ❤️ · Runs 100% locally · Your data stays yours</p>
  <p>Powered by Ollama</p>
</footer>

<script>
const io = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('show'); io.unobserve(e.target); }
  });
}, { threshold: 0.15 });
document.querySelectorAll('.f-card, .step, .stat').forEach(el => io.observe(el));
</script>
</body>
</html>"""

# ── Chat app HTML ─────────────────────────────────────────────────────────────

CHAT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Budget Coach — Chat</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter', sans-serif; background: #f2f2f7; height: 100vh; display: flex; flex-direction: column; }
nav {
  background: white; padding: 14px 24px;
  display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid #f0f0f0; flex-shrink: 0;
}
.nav-logo { font-size:18px; font-weight:800; background:linear-gradient(135deg,#7c3aed,#3b82f6); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
.nav-back { font-size:14px; color:#64748b; text-decoration:none; font-weight:500; }
.nav-back:hover { color:#0f172a; }
.badge { background:#e8f5e9; color:#2e7d32; font-size:12px; font-weight:700; padding:5px 12px; border-radius:12px; }
.chat { flex:1; overflow-y:auto; padding:24px 20px; display:flex; flex-direction:column; gap:16px; }
.chat::-webkit-scrollbar { width:5px; }
.chat::-webkit-scrollbar-thumb { background:#d1d5db; border-radius:10px; }
.msg { display:flex; align-items:flex-end; gap:10px; animation:fadeUp .3s ease; }
.msg.user { flex-direction:row-reverse; }
@keyframes fadeUp { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
.av { width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0; }
.av.coach{background:#ede9fe;} .av.user{background:#dbeafe;}
.bubble { max-width:70%; padding:13px 17px; border-radius:20px; font-size:15px; line-height:1.6; font-weight:500; }
.bubble.coach { background:white; color:#1f2937; border:1px solid #e5e7eb; border-bottom-left-radius:5px; box-shadow:0 2px 8px rgba(0,0,0,.06); }
.bubble.user  { background:linear-gradient(135deg,#7c3aed,#3b82f6); color:white; border-bottom-right-radius:5px; box-shadow:0 4px 12px rgba(124,58,237,.3); }
.typing-bubble { background:white;border:1px solid #e5e7eb;border-radius:20px;border-bottom-left-radius:5px;padding:14px 18px;display:flex;gap:5px;align-items:center;box-shadow:0 2px 8px rgba(0,0,0,.06); }
.dot { width:7px;height:7px;background:#9ca3af;border-radius:50%;animation:bounce 1.2s infinite; }
.dot:nth-child(2){animation-delay:.2s} .dot:nth-child(3){animation-delay:.4s}
@keyframes bounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-6px)} }
.input-bar { padding:14px 18px; background:white; border-top:1px solid #f0f0f0; display:flex; gap:10px; align-items:center; flex-shrink:0; }
#inp { flex:1;border:1.5px solid #e5e7eb;border-radius:26px;padding:13px 20px;font-size:15px;font-family:inherit;font-weight:500;color:#1f2937;outline:none;transition:border-color .2s;background:#f9fafb; }
#inp:focus { border-color:#7c3aed; background:white; }
#inp::placeholder { color:#9ca3af; font-weight:400; }
#send { width:48px;height:48px;border-radius:50%;border:none;background:linear-gradient(135deg,#7c3aed,#3b82f6);color:white;font-size:18px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:transform .15s;box-shadow:0 4px 14px rgba(124,58,237,.35); }
#send:hover{transform:scale(1.08)} #send:active{transform:scale(.95)} #send:disabled{opacity:.5;cursor:not-allowed;transform:none}
</style>
</head>
<body>
<nav>
  <div style="display:flex;align-items:center;gap:12px">
    <a class="nav-back" href="/">← Back</a>
    <div class="nav-logo">💰 Budget Coach</div>
  </div>
  <div class="badge">● Running locally</div>
</nav>
<div class="chat" id="chat">
  <div class="msg">
    <div class="av coach">🤖</div>
    <div class="bubble coach">Hey! I'm your <strong>Budget Coach</strong> 💰<br>Tell me your monthly income to get started, or just ask me anything!</div>
  </div>
</div>
<div class="input-bar">
  <input id="inp" type="text" placeholder="Message your coach..." autocomplete="off"/>
  <button id="send">➤</button>
</div>
<script>
const chat=document.getElementById('chat'),inp=document.getElementById('inp'),btn=document.getElementById('send');
let sid=null;
function scrollBottom(){chat.scrollTop=chat.scrollHeight;}
function addMsg(role,text){
  const row=document.createElement('div');row.className=`msg ${role}`;
  const av=document.createElement('div');av.className=`av ${role}`;av.textContent=role==='user'?'🧑':'🤖';
  const b=document.createElement('div');b.className=`bubble ${role}`;b.innerHTML=text.replace(/\\n/g,'<br>');
  row.appendChild(av);row.appendChild(b);chat.appendChild(row);scrollBottom();
}
function showTyping(){const r=document.createElement('div');r.className='msg';r.id='typing';r.innerHTML='<div class="av coach">🤖</div><div class="typing-bubble"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>';chat.appendChild(r);scrollBottom();}
function hideTyping(){const t=document.getElementById('typing');if(t)t.remove();}
async function send(){
  const text=inp.value.trim();if(!text)return;
  inp.value='';btn.disabled=true;inp.disabled=true;
  addMsg('user',text);showTyping();
  try{
    const res=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,session_id:sid})});
    const data=await res.json();hideTyping();
    if(data.error){addMsg('coach','⚠️ '+data.error);}else{sid=data.session_id;addMsg('coach',data.reply);}
  }catch(e){hideTyping();addMsg('coach','⚠️ Could not reach the server.');}
  btn.disabled=false;inp.disabled=false;inp.focus();
}
btn.addEventListener('click',send);
inp.addEventListener('keydown',e=>{if(e.key==='Enter')send();});
</script>
</body>
</html>"""

# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    MODEL = args.model

    try: ollama.list()
    except: print("Error: Ollama is not running."); raise SystemExit(1)

    print(f"\n💰 Budget Coach")
    print(f"   Landing : http://localhost:{args.port}")
    print(f"   Chat app: http://localhost:{args.port}/app")
    print(f"   Model   : {MODEL}\n")

    app.run(host="0.0.0.0", port=args.port, debug=False)
