"""
AI Budget Coach — 100% Local (powered by Ollama)
Tracks income, expenses, savings, monthly comparisons, and overall journey.

Install:
    1. Download Ollama from https://ollama.com and install it
    2. In CMD: ollama pull llama3.1:8b
    3. pip install ollama

Run:
    python budget_coach_local.py

Optional — use the smarter 70B model (slower but higher quality):
    python budget_coach_local.py --model llama3.3:70b
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

import ollama

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "llama3.1:8b"

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


# ── Tool schema (what the model sees) ────────────────────────────────────────

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
                    "category": {
                        "type": "string",
                        "description": "Category: Food, Rent, Transport, Entertainment, Health, Utilities, Other.",
                    },
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
            "description": (
                "Retrieve a full budget summary: income, current month expenses (total + by category), "
                "savings, % change vs last month, and all-time savings total. "
                "Always call this before giving any financial analysis or advice."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_current_month",
            "description": "Clear all expense and savings data for the current month. Only use if the user explicitly asks to reset.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# ── Tool dispatcher ───────────────────────────────────────────────────────────

def dispatch_tool(name: str, arguments: str | dict) -> str:
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError:
            args = {}
    else:
        args = arguments

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


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are an empathetic, encouraging AI Budget Coach. Today is {datetime.now().strftime('%B %Y')}.

Your job:
1. Greet new users warmly and ask for their monthly income first if not set.
2. Help them log expenses naturally — extract category, amount, and description from casual messages.
3. Ask about savings at the end of the month or when they mention saving money.
4. Call get_summary before giving any analysis, advice, or progress update.
5. Celebrate wins (savings rate up, spending down). Be honest but kind about overspending.
6. Show % changes vs last month clearly. E.g. "Your food spending is up 12% from last month."
7. Track their overall journey: months tracked, total saved, trends.

Tone: friendly coach, not a stern accountant. Keep responses concise and actionable.
When the user logs an expense, confirm it briefly, then continue the conversation naturally."""


# ── Main conversation loop ────────────────────────────────────────────────────

def chat_loop(model: str) -> None:
    messages: list[dict] = []

    print(f"\n💰 AI Budget Coach  [{model}]")
    print("─" * 45)
    print("Type your message. 'quit' to exit.\n")

    # Kick things off with a silent opener so the model greets the user
    messages.append({"role": "user", "content": "Hi, I just opened the app."})

    while True:
        # ── Call local model ──────────────────────────────────────────────────
        print("⏳ Thinking...", end="\r", flush=True)
        response = ollama.chat(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            tools=TOOLS,
        )
        print("              ", end="\r", flush=True)  # clear the thinking line

        msg = response["message"]
        messages.append(msg)

        tool_calls = msg.get("tool_calls") or []
        text = msg.get("content", "").strip()

        # Print any text the model produced (before or without tool calls)
        if text and not tool_calls:
            print(f"\n🤖 Coach: {text}\n")

        # ── Execute tool calls ────────────────────────────────────────────────
        if tool_calls:
            for call in tool_calls:
                fn = call["function"]
                result = dispatch_tool(fn["name"], fn.get("arguments", {}))
                messages.append({
                    "role": "tool",
                    "content": result,
                })

            # Get the model's follow-up after seeing tool results
            print("⏳ Thinking...", end="\r", flush=True)
            followup = ollama.chat(
                model=model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                tools=TOOLS,
            )
            print("              ", end="\r", flush=True)
            followup_msg = followup["message"]
            messages.append(followup_msg)

            followup_text = followup_msg.get("content", "").strip()
            if followup_text:
                print(f"\n🤖 Coach: {followup_text}\n")

        # ── Get next user input ───────────────────────────────────────────────
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye! Keep saving 💪")
            break

        if user_input.lower() in ("quit", "exit", "bye"):
            print("\nGoodbye! Keep saving 💪\n")
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Budget Coach (local)")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model to use (default: {DEFAULT_MODEL}). Try 'llama3.3:70b' for higher quality.",
    )
    args = parser.parse_args()

    # Check Ollama is running
    try:
        ollama.list()
    except Exception:
        print("Error: Ollama is not running.")
        print("  1. Download it from https://ollama.com")
        print("  2. Install and launch it")
        print(f"  3. In CMD, run: ollama pull {args.model}")
        sys.exit(1)

    chat_loop(args.model)
