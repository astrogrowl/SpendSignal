"""
AI Budget Coach — Web App
Runs locally at http://localhost:5000
Powered by Ollama (100% local, no internet needed)

Install:  pip install flask ollama
Run:      python budget_coach_web.py
"""

import json
import uuid
import argparse
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, session
import ollama

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "llama3.1:8b"
app = Flask(__name__)
app.secret_key = "budget-coach-secret-2025"

# In-memory session store {session_id: [messages]}
SESSIONS: dict[str, list] = {}
MODEL = DEFAULT_MODEL

# ── Storage ───────────────────────────────────────────────────────────────────

DATA_FILE = Path("budget_data.json")


def load_data() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {"income": None, "months": {}}


def save_data(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, indent=2))


def current_month() -> str:
    return datetime.now().strftime("%Y-%m")


def last_month() -> str:
    now = datetime.now()
    year, month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    return f"{year}-{month:02d}"


def ensure_month(data: dict, month: str) -> None:
    if month not in data["months"]:
        data["months"][month] = {"expenses": [], "savings": 0}


# ── Tool handlers ─────────────────────────────────────────────────────────────

def handle_set_income(amount: float) -> str:
    data = load_data()
    data["income"] = amount
    save_data(data)
    return f"Income saved: ${amount:,.2f}/month."


def handle_add_expense(category: str, amount: float, description: str) -> str:
    data = load_data()
    month = current_month()
    ensure_month(data, month)
    data["months"][month]["expenses"].append({
        "category": category,
        "amount": amount,
        "description": description,
        "date": datetime.now().isoformat(),
    })
    save_data(data)
    total = sum(e["amount"] for e in data["months"][month]["expenses"])
    return f"Added '{description}' (${amount:,.2f}) under {category}. Month total: ${total:,.2f}."


def handle_set_savings(amount: float) -> str:
    data = load_data()
    month = current_month()
    ensure_month(data, month)
    data["months"][month]["savings"] = amount
    save_data(data)
    return f"Savings for {month} set to ${amount:,.2f}."


def handle_get_summary() -> str:
    data = load_data()
    cm = current_month()
    lm = last_month()
    out: dict = {"income": data.get("income"), "current_month": cm}

    if cm in data["months"]:
        cd = data["months"][cm]
        expenses = cd.get("expenses", [])
        total_exp = sum(e["amount"] for e in expenses)
        by_cat: dict[str, float] = {}
        for e in expenses:
            by_cat[e["category"]] = by_cat.get(e["category"], 0) + e["amount"]
        out["current_expenses_total"] = total_exp
        out["current_expenses_by_category"] = by_cat
        out["current_savings"] = cd.get("savings", 0)
        if data.get("income"):
            out["current_savings_rate_pct"] = round(
                (out["current_savings"] / data["income"]) * 100, 1
            )

    if lm in data["months"]:
        ld = data["months"][lm]
        last_exp = sum(e["amount"] for e in ld.get("expenses", []))
        last_sav = ld.get("savings", 0)
        out["last_month"] = lm
        out["last_expenses_total"] = last_exp
        out["last_savings"] = last_sav

        if "current_expenses_total" in out and last_exp > 0:
            out["expenses_vs_last_month_pct"] = round(
                (out["current_expenses_total"] - last_exp) / last_exp * 100, 1
            )
        if "current_savings" in out and last_sav > 0:
            out["savings_vs_last_month_pct"] = round(
                (out["current_savings"] - last_sav) / last_sav * 100, 1
            )

    all_months = sorted(data["months"].keys())
    if all_months:
        out["total_saved_all_time"] = sum(
            data["months"][m].get("savings", 0) for m in all_months
        )
        out["months_tracked"] = len(all_months)

    return json.dumps(out, indent=2)


def handle_clear_current_month() -> str:
    data = load_data()
    month = current_month()
    data["months"].pop(month, None)
    save_data(data)
    return f"Cleared all data for {month}."


# ── Tools ─────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_income",
            "description": "Save the user's monthly income.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Monthly income in dollars."}
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_expense",
            "description": "Record a single expense for the current month.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Category: Food, Rent, Transport, Entertainment, Health, Utilities, Other."},
                    "amount": {"type": "number", "description": "Expense amount in dollars."},
                    "description": {"type": "string", "description": "Short description of the expense."},
                },
                "required": ["category", "amount", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_savings",
            "description": "Record how much the user saved this month.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Savings amount in dollars for the current month."}
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_summary",
            "description": "Retrieve full budget summary. Always call before giving analysis or advice.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_current_month",
            "description": "Clear all data for the current month. Only if user explicitly asks.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def dispatch_tool(name: str, arguments) -> str:
    args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
    if name == "set_income":
        return handle_set_income(float(args["amount"]))
    if name == "add_expense":
        return handle_add_expense(args["category"], float(args["amount"]), args["description"])
    if name == "set_savings":
        return handle_set_savings(float(args["amount"]))
    if name == "get_summary":
        return handle_get_summary()
    if name == "clear_current_month":
        return handle_clear_current_month()
    return f"Unknown tool: {name}"


SYSTEM_PROMPT = f"""You are an empathetic, encouraging AI Budget Coach. Today is {datetime.now().strftime('%B %Y')}.

Your job:
1. Greet new users warmly and ask for their monthly income first if not set.
2. Help them log expenses naturally — extract category, amount, and description from casual messages.
3. Ask about savings at the end of the month or when they mention saving money.
4. Call get_summary before giving any analysis, advice, or progress update.
5. Celebrate wins (savings rate up, spending down). Be honest but kind about overspending.
6. Show % changes vs last month clearly. E.g. "Your food spending is up 12% from last month."
7. Track their overall journey: months tracked, total saved, trends.

Tone: friendly coach, not a stern accountant. Keep responses concise and actionable."""


# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return HTML


@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json()
    sid = body.get("session_id") or str(uuid.uuid4())
    user_msg = body.get("message", "").strip()

    if not user_msg:
        return jsonify({"error": "empty message"}), 400

    if sid not in SESSIONS:
        SESSIONS[sid] = []

    messages = SESSIONS[sid]
    messages.append({"role": "user", "content": user_msg})

    try:
        resp = ollama.chat(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            tools=TOOLS,
        )
        msg = resp["message"]
        messages.append(msg)

        tool_calls = msg.get("tool_calls") or []
        text = msg.get("content", "").strip()

        if tool_calls:
            for call in tool_calls:
                fn = call["function"]
                result = dispatch_tool(fn["name"], fn.get("arguments", {}))
                messages.append({"role": "tool", "content": result})

            followup = ollama.chat(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                tools=TOOLS,
            )
            fu = followup["message"]
            messages.append(fu)
            text = fu.get("content", "").strip()

        return jsonify({"reply": text, "session_id": sid})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── HTML / CSS / JS (all-in-one) ──────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Budget Coach</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }

  .card {
    width: 100%;
    max-width: 820px;
    height: 90vh;
    background: #ffffff;
    border-radius: 28px;
    box-shadow: 0 30px 80px rgba(0,0,0,0.4);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* Header */
  .header {
    background: linear-gradient(135deg, #4A90D9 0%, #7B68EE 100%);
    padding: 22px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }
  .header-left { display: flex; align-items: center; gap: 14px; }
  .header-icon {
    width: 48px; height: 48px;
    background: rgba(255,255,255,0.2);
    border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    font-size: 24px;
  }
  .header-title { color: white; font-size: 20px; font-weight: 700; }
  .header-sub { color: rgba(255,255,255,0.75); font-size: 13px; margin-top: 2px; }
  .badge {
    background: rgba(255,255,255,0.2);
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 20px;
    padding: 6px 14px;
    color: white;
    font-size: 12px;
    font-weight: 600;
    display: flex; align-items: center; gap: 6px;
  }
  .dot { width: 8px; height: 8px; background: #4ade80; border-radius: 50%; }

  /* Chat area */
  .chat {
    flex: 1;
    overflow-y: auto;
    padding: 24px 28px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    background: #f8f9fc;
  }
  .chat::-webkit-scrollbar { width: 6px; }
  .chat::-webkit-scrollbar-track { background: transparent; }
  .chat::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 10px; }

  /* Messages */
  .msg { display: flex; align-items: flex-end; gap: 10px; animation: fadeUp 0.3s ease; }
  .msg.user { flex-direction: row-reverse; }

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .avatar {
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; flex-shrink: 0;
  }
  .avatar.coach { background: #e8eaf6; }
  .avatar.user  { background: #dbeafe; }

  .bubble {
    max-width: 68%;
    padding: 14px 18px;
    border-radius: 20px;
    font-size: 15px;
    line-height: 1.6;
    font-weight: 500;
  }
  .bubble.coach {
    background: #ffffff;
    color: #1f2937;
    border: 1px solid #e5e7eb;
    border-bottom-left-radius: 6px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }
  .bubble.user {
    background: linear-gradient(135deg, #4A90D9, #7B68EE);
    color: #ffffff;
    border-bottom-right-radius: 6px;
    box-shadow: 0 4px 12px rgba(74,144,217,0.35);
  }

  /* Typing indicator */
  .typing { display: flex; align-items: flex-end; gap: 10px; }
  .typing-bubble {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 20px;
    border-bottom-left-radius: 6px;
    padding: 14px 20px;
    display: flex; gap: 5px; align-items: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }
  .typing-dot {
    width: 8px; height: 8px;
    background: #9ca3af;
    border-radius: 50%;
    animation: bounce 1.2s infinite;
  }
  .typing-dot:nth-child(2) { animation-delay: 0.2s; }
  .typing-dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes bounce {
    0%, 60%, 100% { transform: translateY(0); }
    30%           { transform: translateY(-6px); }
  }

  /* Input bar */
  .input-bar {
    padding: 16px 22px;
    background: #ffffff;
    border-top: 1px solid #f0f0f0;
    display: flex;
    gap: 12px;
    align-items: center;
    flex-shrink: 0;
  }
  #input {
    flex: 1;
    border: 1.5px solid #e5e7eb;
    border-radius: 28px;
    padding: 14px 22px;
    font-size: 15px;
    font-family: inherit;
    font-weight: 500;
    color: #1f2937;
    outline: none;
    transition: border-color 0.2s;
    background: #f9fafb;
  }
  #input:focus { border-color: #4A90D9; background: #ffffff; }
  #input::placeholder { color: #9ca3af; font-weight: 400; }

  #send {
    width: 52px; height: 52px;
    border-radius: 50%;
    border: none;
    background: linear-gradient(135deg, #4A90D9, #7B68EE);
    color: white;
    font-size: 20px;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    transition: transform 0.15s, box-shadow 0.15s;
    box-shadow: 0 4px 14px rgba(74,144,217,0.4);
  }
  #send:hover  { transform: scale(1.08); box-shadow: 0 6px 18px rgba(74,144,217,0.5); }
  #send:active { transform: scale(0.95); }
  #send:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
</style>
</head>
<body>

<div class="card">
  <!-- Header -->
  <div class="header">
    <div class="header-left">
      <div class="header-icon">💰</div>
      <div>
        <div class="header-title">Budget Coach</div>
        <div class="header-sub">Your personal finance assistant</div>
      </div>
    </div>
    <div class="badge">
      <div class="dot"></div>
      Running locally
    </div>
  </div>

  <!-- Chat -->
  <div class="chat" id="chat">
    <div class="msg">
      <div class="avatar coach">🤖</div>
      <div class="bubble coach">
        Hey! I'm your <strong>Budget Coach</strong> 💰<br>
        Tell me your monthly income to get started, or just ask me anything!
      </div>
    </div>
  </div>

  <!-- Input -->
  <div class="input-bar">
    <input id="input" type="text" placeholder="Message your coach..." autocomplete="off" />
    <button id="send">➤</button>
  </div>
</div>

<script>
  const chat    = document.getElementById('chat');
  const input   = document.getElementById('input');
  const sendBtn = document.getElementById('send');
  let sessionId = null;

  function scrollBottom() {
    chat.scrollTop = chat.scrollHeight;
  }

  function addMessage(role, text) {
    const row = document.createElement('div');
    row.className = `msg ${role}`;

    const avatar = document.createElement('div');
    avatar.className = `avatar ${role}`;
    avatar.textContent = role === 'user' ? '🧑' : '🤖';

    const bubble = document.createElement('div');
    bubble.className = `bubble ${role}`;
    bubble.innerHTML = text.replace(/\\n/g, '<br>');

    row.appendChild(avatar);
    row.appendChild(bubble);
    chat.appendChild(row);
    scrollBottom();
  }

  function showTyping() {
    const row = document.createElement('div');
    row.className = 'typing';
    row.id = 'typing';
    row.innerHTML = `
      <div class="avatar coach">🤖</div>
      <div class="typing-bubble">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>`;
    chat.appendChild(row);
    scrollBottom();
  }

  function hideTyping() {
    const t = document.getElementById('typing');
    if (t) t.remove();
  }

  async function send() {
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    sendBtn.disabled = true;
    input.disabled = true;

    addMessage('user', text);
    showTyping();

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      });
      const data = await res.json();
      hideTyping();

      if (data.error) {
        addMessage('coach', '⚠️ ' + data.error);
      } else {
        sessionId = data.session_id;
        addMessage('coach', data.reply);
      }
    } catch (err) {
      hideTyping();
      addMessage('coach', '⚠️ Could not reach the server. Is Ollama running?');
    }

    sendBtn.disabled = false;
    input.disabled = false;
    input.focus();
  }

  sendBtn.addEventListener('click', send);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });
</script>
</body>
</html>"""


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Budget Coach — Web")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    MODEL = args.model

    try:
        ollama.list()
    except Exception:
        print("Error: Ollama is not running. Open the Ollama app first.")
        raise SystemExit(1)

    print(f"\n💰 Budget Coach Web")
    print(f"   Model : {MODEL}")
    print(f"   Open  : http://localhost:{args.port}\n")

    app.run(host="0.0.0.0", port=args.port, debug=False)
