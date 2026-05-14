"""
AI Budget Coach — powered by Claude API
Tracks income, expenses, savings, monthly comparisons, and overall journey.

Install:  pip install anthropic
Run:      python budget_coach.py
"""

import json
import os
from datetime import datetime
from pathlib import Path

import anthropic

# ── Storage ──────────────────────────────────────────────────────────────────

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


# ── Tool schema (what Claude sees) ───────────────────────────────────────────

TOOLS = [
    {
        "name": "set_income",
        "description": "Save the user's monthly income.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Monthly income in dollars."}
            },
            "required": ["amount"],
        },
    },
    {
        "name": "add_expense",
        "description": "Record a single expense for the current month.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Category, e.g. Food, Rent, Transport, Entertainment, Health, Other.",
                },
                "amount": {"type": "number", "description": "Expense amount in dollars."},
                "description": {"type": "string", "description": "Short description of the expense."},
            },
            "required": ["category", "amount", "description"],
        },
    },
    {
        "name": "set_savings",
        "description": "Record how much the user saved this month.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Savings amount in dollars for the current month."}
            },
            "required": ["amount"],
        },
    },
    {
        "name": "get_summary",
        "description": (
            "Retrieve a full budget summary: income, current month expenses (total + by category), "
            "savings, % change vs last month, and all-time savings total. "
            "Always call this before giving financial analysis or advice."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "clear_current_month",
        "description": "Clear all expense and savings data for the current month (use only if user explicitly asks to reset).",
        "input_schema": {"type": "object", "properties": {}},
    },
]

# ── Tool dispatcher ───────────────────────────────────────────────────────────

def dispatch_tool(name: str, inputs: dict) -> str:
    if name == "set_income":
        return handle_set_income(inputs["amount"])
    if name == "add_expense":
        return handle_add_expense(inputs["category"], inputs["amount"], inputs["description"])
    if name == "set_savings":
        return handle_set_savings(inputs["amount"])
    if name == "get_summary":
        return handle_get_summary()
    if name == "clear_current_month":
        return handle_clear_current_month()
    return f"Unknown tool: {name}"


# ── System prompt (cached) ────────────────────────────────────────────────────

SYSTEM = [
    {
        "type": "text",
        "text": f"""You are an empathetic, encouraging AI Budget Coach. Today is {datetime.now().strftime('%B %Y')}.

Your job:
1. Greet new users warmly and ask for their monthly income first if not set.
2. Help them log expenses naturally — extract category, amount, and description from casual messages.
3. Ask about savings at the end of the month or when they mention saving money.
4. Call get_summary before giving any analysis, advice, or progress update.
5. Celebrate wins (savings rate up, spending down). Be honest but kind about overspending.
6. Show % changes vs last month clearly. E.g. "Your food spending is up 12% from last month."
7. Track their overall journey: months tracked, total saved, trends.

Tone: friendly coach, not a stern accountant. Keep responses concise and actionable.
When the user logs an expense, confirm it briefly, then continue the conversation naturally.""",
        "cache_control": {"type": "ephemeral"},  # cache the stable system prompt
    }
]

# ── Main conversation loop ────────────────────────────────────────────────────

def chat_loop() -> None:
    client = anthropic.Anthropic()
    messages: list[dict] = []

    print("\n💰 AI Budget Coach")
    print("─" * 40)
    print("Type your message. 'quit' to exit.\n")

    # Kick things off
    messages.append({
        "role": "user",
        "content": "Hi, I just opened the app.",
    })

    while True:
        # ── Call Claude (streaming) ──
        with client.messages.stream(
            model="claude-opus-4-7",
            max_tokens=1024,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            response = stream.get_final_message()

        # ── Process response ──
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # Collect any tool calls
        tool_results = []
        text_blocks = []

        for block in assistant_content:
            if block.type == "text":
                text_blocks.append(block.text)
            elif block.type == "tool_use":
                result = dispatch_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        # Print any text Claude produced
        if text_blocks:
            print(f"\n🤖 Coach: {''.join(text_blocks)}\n")

        # If there were tool calls, feed results back and get follow-up
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

            with client.messages.stream(
                model="claude-opus-4-7",
                max_tokens=1024,
                system=SYSTEM,
                tools=TOOLS,
                messages=messages,
            ) as stream:
                followup = stream.get_final_message()

            followup_content = followup.content
            messages.append({"role": "assistant", "content": followup_content})

            for block in followup_content:
                if block.type == "text":
                    print(f"\n🤖 Coach: {block.text}\n")

        # ── Get next user input ──
        if response.stop_reason == "end_turn" or not tool_results:
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


if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set.")
        print("Get your key at https://console.anthropic.com/")
        raise SystemExit(1)

    chat_loop()
