"""
AI Budget Coach — Desktop GUI
Dark chat interface powered by Ollama (100% local)

Install:  pip install customtkinter ollama
Run:      python budget_coach_gui.py
          python budget_coach_gui.py --model llama3.1:8b
"""

import json
import sys
import threading
import argparse
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
import ollama

# ── Appearance ────────────────────────────────────────────────────────────────

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

DEFAULT_MODEL = "llama3.3:70b"

# ── Color palette ─────────────────────────────────────────────────────────────

BG         = "#F2F2F7"   # soft off-white
HEADER_BG  = "#FFFFFF"   # clean white header
CHAT_BG    = "#F2F2F7"   # same as BG
COACH_BG   = "#E5E5EA"   # gray coach bubble
USER_BG    = "#D4E8FF"   # pastel blue user bubble
INPUT_BG   = "#FFFFFF"   # white input
BORDER     = "#D1D1D6"   # light border
ACCENT     = "#4A90D9"   # blue send button
GREEN      = "#34C759"   # green local dot
TEXT       = "#1C1C1E"   # near-black text
TEXT_DIM   = "#8E8E93"   # gray secondary text
TEXT_USER  = "#1C3A6E"   # dark blue for user bubble text
THINKING   = "#FF9500"   # orange thinking indicator

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


# ── Tool schema ───────────────────────────────────────────────────────────────

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
            "description": "Clear all expense and savings data for the current month. Only use if explicitly asked.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def dispatch_tool(name: str, arguments) -> str:
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError:
            args = {}
    else:
        args = arguments or {}

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


# ── App ───────────────────────────────────────────────────────────────────────

class BudgetCoachApp(ctk.CTk):
    def __init__(self, model: str):
        super().__init__()
        self.model = model
        self.messages: list[dict] = []
        self.thinking = False
        self._dot_count = 0
        self._think_job = None

        self._build_ui()
        self._add_bubble("coach", "Hey! I'm your Budget Coach 💰 Tell me your monthly income to get started, or just ask me anything.")

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.title("Budget Coach")
        self.geometry("920x720")
        self.minsize(640, 480)
        self.configure(fg_color=BG)

        self._build_header()
        self._build_chat()
        self._build_thinking_bar()
        self._build_input_bar()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=HEADER_BG, corner_radius=0, height=68)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # Icon + title
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", padx=22)

        ctk.CTkLabel(
            left,
            text="💰",
            font=ctk.CTkFont(size=28),
        ).pack(side="left", padx=(0, 10))

        title_stack = ctk.CTkFrame(left, fg_color="transparent")
        title_stack.pack(side="left")

        ctk.CTkLabel(
            title_stack,
            text="Budget Coach",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_stack,
            text="Your personal finance assistant",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_DIM,
        ).pack(anchor="w")

        # Right side badge
        badge = ctk.CTkFrame(header, fg_color="#E8F5E9", corner_radius=12)
        badge.pack(side="right", padx=22)

        ctk.CTkLabel(
            badge,
            text=f"● local  •  {self.model}",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#2E7D32",
        ).pack(padx=12, pady=6)

    def _build_chat(self):
        self.chat_area = ctk.CTkScrollableFrame(
            self,
            fg_color=CHAT_BG,
            corner_radius=0,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=ACCENT,
        )
        self.chat_area.pack(fill="both", expand=True)
        self.chat_area.grid_columnconfigure(0, weight=1)

    def _build_thinking_bar(self):
        self.think_bar = ctk.CTkFrame(self, fg_color=BG, height=30, corner_radius=0)
        self.think_bar.pack(fill="x")
        self.think_bar.pack_propagate(False)

        self.think_label = ctk.CTkLabel(
            self.think_bar,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12, slant="italic"),
            text_color=THINKING,
            anchor="w",
        )
        self.think_label.pack(side="left", padx=22)

    def _build_input_bar(self):
        bar = ctk.CTkFrame(self, fg_color=HEADER_BG, corner_radius=0, height=76)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.input_var = ctk.StringVar()
        self.input_box = ctk.CTkEntry(
            bar,
            textvariable=self.input_var,
            placeholder_text="💬  Message your coach...",
            font=ctk.CTkFont(family="Segoe UI", size=15),
            fg_color=INPUT_BG,
            border_color=BORDER,
            text_color=TEXT,
            corner_radius=28,
            height=48,
            border_width=1,
        )
        self.input_box.pack(side="left", fill="x", expand=True, padx=(18, 10), pady=14)
        self.input_box.bind("<Return>", self._on_send)

        self.send_btn = ctk.CTkButton(
            bar,
            text="Send  ›",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            fg_color=ACCENT,
            hover_color="#3A7FD7",
            text_color="#FFFFFF",
            corner_radius=28,
            width=110,
            height=48,
            command=self._on_send,
        )
        self.send_btn.pack(side="right", padx=(0, 18), pady=14)
        self.input_box.focus()

    # ── Chat bubbles ──────────────────────────────────────────────────────────

    def _add_bubble(self, role: str, text: str):
        is_user = role == "user"

        outer = ctk.CTkFrame(self.chat_area, fg_color="transparent")
        outer.pack(fill="x", padx=22, pady=8)

        # Avatar circle
        avatar = ctk.CTkFrame(
            outer,
            fg_color=ACCENT if is_user else COACH_BG,
            corner_radius=20,
            width=36,
            height=36,
        )
        avatar_label = ctk.CTkLabel(
            avatar,
            text="🧑" if is_user else "🤖",
            font=ctk.CTkFont(size=16),
            width=36,
            height=36,
        )
        avatar_label.pack()

        bubble = ctk.CTkFrame(
            outer,
            fg_color=USER_BG if is_user else COACH_BG,
            corner_radius=18,
            border_width=0,
        )

        label = ctk.CTkLabel(
            bubble,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=TEXT_USER if is_user else TEXT,
            wraplength=560,
            justify="left",
            anchor="w",
        )
        label.pack(padx=18, pady=14)

        if is_user:
            avatar.pack(side="right", padx=(10, 0), anchor="n", pady=(4, 0))
            bubble.pack(side="right")
        else:
            avatar.pack(side="left", padx=(0, 10), anchor="n", pady=(4, 0))
            bubble.pack(side="left")

        self.after(60, self._scroll_bottom)

    def _scroll_bottom(self):
        try:
            self.chat_area._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    # ── Thinking animation ────────────────────────────────────────────────────

    def _set_thinking(self, active: bool):
        self.thinking = active
        state = "disabled" if active else "normal"
        self.send_btn.configure(state=state)
        self.input_box.configure(state=state)

        if active:
            self._dot_count = 0
            self._animate()
        else:
            if self._think_job:
                self.after_cancel(self._think_job)
                self._think_job = None
            self.think_label.configure(text="")

    def _animate(self):
        dots = "." * (self._dot_count % 4)
        self.think_label.configure(text=f"⏳  Coach is thinking{dots}")
        self._dot_count += 1
        self._think_job = self.after(380, self._animate)

    # ── Message handling ──────────────────────────────────────────────────────

    def _on_send(self, _event=None):
        text = self.input_var.get().strip()
        if not text or self.thinking:
            return
        self.input_var.set("")
        self._add_bubble("user", text)
        self.messages.append({"role": "user", "content": text})
        self._set_thinking(True)
        threading.Thread(target=self._call_model, daemon=True).start()

    def _call_model(self):
        try:
            resp = ollama.chat(
                model=self.model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self.messages,
                tools=TOOLS,
            )
            msg = resp["message"]
            self.messages.append(msg)

            tool_calls = msg.get("tool_calls") or []
            text = msg.get("content", "").strip()

            if tool_calls:
                for call in tool_calls:
                    fn = call["function"]
                    result = dispatch_tool(fn["name"], fn.get("arguments", {}))
                    self.messages.append({"role": "tool", "content": result})

                followup = ollama.chat(
                    model=self.model,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self.messages,
                    tools=TOOLS,
                )
                fu_msg = followup["message"]
                self.messages.append(fu_msg)
                text = fu_msg.get("content", "").strip()

            self.after(0, lambda t=text: self._finish(t))
        except Exception as e:
            msg = str(e)
            self.after(0, lambda m=msg: self._finish(f"⚠️  Error: {m}"))

    def _finish(self, text: str):
        self._set_thinking(False)
        if text:
            self._add_bubble("coach", text)



# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Budget Coach — Desktop GUI")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model (default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    try:
        ollama.list()
    except Exception:
        import tkinter as tk
        import tkinter.messagebox as mb
        root = tk.Tk()
        root.withdraw()
        mb.showerror(
            "Ollama not running",
            "Ollama isn't running.\n\n1. Open the Ollama app\n2. Try again",
        )
        sys.exit(1)

    app = BudgetCoachApp(model=args.model)
    app.mainloop()
