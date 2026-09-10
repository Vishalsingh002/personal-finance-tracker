import os
import sqlite3
from datetime import datetime
from functools import wraps
import pandas as pd
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, jsonify, g
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "finance-tracker-ai-secret-key-2026")
DATABASE = os.path.join(os.path.abspath(os.path.dirname(__file__)), "database.db")

EXPENSE_CATEGORIES = [
    "Food", "Transportation", "Shopping", "Bills",
    "Education", "Entertainment", "Healthcare", "Room rent", "grocery", "Other"
]

INCOME_SOURCES = [
    "Salary", "Freelance", "Investment", "Business", "Gifts", "Pocket Money", "Other"
]

# --- Database Setup & Helpers ---
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                monthly_budget REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Agar purana DB hai toh monthly_budget column add kar dega:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN monthly_budget REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass # Column already exists

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS income (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                source TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                amount REAL NOT NULL,
                UNIQUE(user_id, month),
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        conn.commit()

init_db()

# --- Auth Helpers (Crash-Proof) ---
def get_current_user():
    if "user_id" not in session:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

def login_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        
        # Safe check: agar user DB se delete ho chuka ho
        user = get_current_user()
        if user is None:
            session.clear()
            flash("Session expired or user deleted. Please log in again.", "warning")
            return redirect(url_for("login"))
            
        return func(*args, **kwargs)
    return decorated_view

# --- Pandas Helpers ---
def get_user_dataframes(user_id):
    db = get_db()
    df_income = pd.read_sql_query(
        "SELECT id, amount, source, date, description FROM income WHERE user_id = ?",
        db, params=(user_id,)
    )
    df_expense = pd.read_sql_query(
        "SELECT id, amount, category, date, description FROM expenses WHERE user_id = ?",
        db, params=(user_id,)
    )

    if not df_income.empty:
        df_income["date"] = pd.to_datetime(df_income["date"])
        df_income["month_year"] = df_income["date"].dt.strftime("%Y-%m")
        df_income["month_name"] = df_income["date"].dt.strftime("%b %Y")
    else:
        df_income = pd.DataFrame(columns=["id", "amount", "source", "date", "description", "month_year", "month_name"])

    if not df_expense.empty:
        df_expense["date"] = pd.to_datetime(df_expense["date"])
        df_expense["month_year"] = df_expense["date"].dt.strftime("%Y-%m")
        df_expense["month_name"] = df_expense["date"].dt.strftime("%b %Y")
    else:
        df_expense = pd.DataFrame(columns=["id", "amount", "category", "date", "description", "month_year", "month_name"])

    return df_income, df_expense

# --- 🤖 AI Financial Advisor & Savings Target Engine ---
def ai_financial_advisor(monthly_income, monthly_expense, df_expense_curr):
    advice = {
        "recommended_savings_20": round(monthly_income * 0.20, 2),
        "ideal_savings_30": round(monthly_income * 0.30, 2),
        "max_safe_spending": round(monthly_income * 0.80, 2),
        "current_savings": round(monthly_income - monthly_expense, 2),
        "savings_rate": round(((monthly_income - monthly_expense) / monthly_income * 100), 1) if monthly_income > 0 else 0,
        "emergency_fund_target": round(monthly_expense * 6, 2) if monthly_expense > 0 else round(monthly_income * 3, 2),
        "badge_color": "info",
        "title": "Awaiting Data",
        "summary": "Record your income to unlock your personalized AI Financial Analysis.",
        "tips": []
    }

    if monthly_income <= 0:
        advice["tips"].append("💡 Please record your monthly income first so the AI can compute your savings targets.")
        return advice

    curr_saved = advice["current_savings"]
    rec_saved = advice["recommended_savings_20"]
    rate = advice["savings_rate"]

    if rate >= 30:
        advice["badge_color"] = "success"
        advice["title"] = "🌟 Outstanding Saver!"
        advice["summary"] = f"Excellent! You are saving {rate}% of your income this month, beating the 20% target."
    elif rate >= 20:
        advice["badge_color"] = "success"
        advice["title"] = "✅ 50/30/20 Goal Met"
        advice["summary"] = f"Great work! You are meeting the standard 20% savings rule (${curr_saved:,.2f} saved)."
    elif rate > 0:
        gap = rec_saved - curr_saved
        advice["badge_color"] = "warning"
        advice["title"] = "⚠️ Below Target Savings"
        advice["summary"] = f"You saved {rate}%. To reach the standard 20% target, aim to save an extra ${gap:,.2f}."
    else:
        over = abs(curr_saved)
        advice["badge_color"] = "danger"
        advice["title"] = "🚨 Deficit Spending Alert"
        advice["summary"] = f"Your expenses exceed your income by ${over:,.2f}! High risk of debt."

    # Category Leak Detection
    if not df_expense_curr.empty:
        cat_sums = df_expense_curr.groupby("category")["amount"].sum()
        for cat, val in cat_sums.items():
            pct = (val / monthly_income) * 100
            if cat in ["Shopping", "Entertainment"] and pct > 15:
                advice["tips"].append(f"🛍️ <strong>{cat} Leak</strong>: Consuming {pct:.1f}% (${val:,.2f}) of your monthly income. Consider trimming discretionary items.")
            elif cat in ["Food", "grocery"] and pct > 25:
                advice["tips"].append(f"🍔 <strong>Food/Grocery</strong>: Accounts for {pct:.1f}% of income. Smart meal planning can save an estimated ${(val * 0.15):,.2f}/mo.")
            elif cat == "Room rent" and pct > 40:
                advice["tips"].append(f"🏠 <strong>Rent Heavy</strong>: Rent is taking {pct:.1f}% of your income. Keep fixed lifestyle costs within 50%.")

    if advice["current_savings"] < advice["recommended_savings_20"]:
        daily_cap = advice["max_safe_spending"] / 30
        advice["tips"].append(f"🎯 <strong>Daily Budget Cap</strong>: Limit daily spending to ${daily_cap:,.2f}/day to reach your monthly goal.")
    else:
        advice["tips"].append(f"📈 <strong>Growth Advice</strong>: You have ${curr_saved:,.2f} in savings. Invest in index funds, SIP, or high-yield savings.")

    return advice

# --- Routes ---
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("register.html")

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email)).fetchone()
        if existing:
            flash("Username or Email already registered.", "danger")
            return render_template("register.html")

        hashed_pw = generate_password_hash(password)
        db.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", (username, email, hashed_pw))
        db.commit()
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ? OR email = ?", (identifier, identifier.lower())).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username/email or password.", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    user = get_current_user()
    now = datetime.now()
    current_month = now.strftime("%Y-%m")
    current_month_label = now.strftime("%B %Y")

    db = get_db()
    budget_row = db.execute("SELECT amount FROM budgets WHERE user_id = ? AND month = ?", (user_id, current_month)).fetchone()
    
    # Safe budget handling
    user_budget = user["monthly_budget"] if (user and "monthly_budget" in user.keys() and user["monthly_budget"]) else 0.0
    monthly_budget = budget_row["amount"] if budget_row else user_budget

    df_inc, df_exp = get_user_dataframes(user_id)

    total_income = df_inc["amount"].sum() if not df_inc.empty else 0.0
    total_expense = df_exp["amount"].sum() if not df_exp.empty else 0.0
    current_savings = total_income - total_expense

    curr_inc = df_inc[df_inc["month_year"] == current_month] if not df_inc.empty else pd.DataFrame()
    curr_exp = df_exp[df_exp["month_year"] == current_month] if not df_exp.empty else pd.DataFrame()

    m_income = curr_inc["amount"].sum() if not curr_inc.empty else 0.0
    m_expense = curr_exp["amount"].sum() if not curr_exp.empty else 0.0
    m_savings = m_income - m_expense

    budget_remaining = monthly_budget - m_expense
    budget_pct = min(100.0, round((m_expense / monthly_budget * 100), 1)) if monthly_budget > 0 else 0.0

    recent_transactions = db.execute("""
        SELECT 'income' AS type, id, amount, source AS category_or_source, date, description, created_at
        FROM income WHERE user_id = ?
        UNION ALL
        SELECT 'expense' AS type, id, amount, category AS category_or_source, date, description, created_at
        FROM expenses WHERE user_id = ?
        ORDER BY date DESC, created_at DESC LIMIT 8
    """, (user_id, user_id)).fetchall()

    ai_advice = ai_financial_advisor(m_income, m_expense, curr_exp)

    return render_template(
        "dashboard.html",
        user=user,
        total_income=total_income,
        total_expense=total_expense,
        current_savings=current_savings,
        m_income=m_income,
        m_expense=m_expense,
        m_savings=m_savings,
        monthly_budget=monthly_budget,
        budget_remaining=budget_remaining,
        budget_pct=budget_pct,
        current_month_label=current_month_label,
        recent_transactions=recent_transactions,
        ai_advice=ai_advice,
        categories=EXPENSE_CATEGORIES,
        sources=INCOME_SOURCES,
        today=now.strftime("%Y-%m-%d")
    )

# --- Income Routes ---
@app.route("/income", methods=["GET", "POST"])
@login_required
def income():
    user_id = session["user_id"]
    db = get_db()

    if request.method == "POST":
        amount = request.form.get("amount", type=float)
        source = request.form.get("source", "").strip()
        date = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip()

        if not amount or amount <= 0 or not source or not date:
            flash("Please enter valid amount, source, and date.", "danger")
        else:
            db.execute("INSERT INTO income (user_id, amount, source, date, description) VALUES (?, ?, ?, ?, ?)",
                       (user_id, amount, source, date, description))
            db.commit()
            flash("Income recorded successfully!", "success")
        return redirect(url_for("income"))

    incomes = db.execute("SELECT * FROM income WHERE user_id = ? ORDER BY date DESC, id DESC", (user_id,)).fetchall()
    total_income = sum(r["amount"] for r in incomes)

    return render_template("income.html", incomes=incomes, total_income=total_income, sources=INCOME_SOURCES, today=datetime.now().strftime("%Y-%m-%d"))

@app.route("/income/edit/<int:income_id>", methods=["POST"])
@login_required
def edit_income(income_id):
    user_id = session["user_id"]
    amount = request.form.get("amount", type=float)
    source = request.form.get("source", "").strip()
    date = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    if amount and amount > 0 and source and date:
        db = get_db()
        db.execute("UPDATE income SET amount = ?, source = ?, date = ?, description = ? WHERE id = ? AND user_id = ?",
                   (amount, source, date, description, income_id, user_id))
        db.commit()
        flash("Income updated!", "success")
    return redirect(url_for("income"))

@app.route("/income/delete/<int:income_id>", methods=["POST"])
@login_required
def delete_income(income_id):
    user_id = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM income WHERE id = ? AND user_id = ?", (income_id, user_id))
    db.commit()
    flash("Income entry deleted.", "info")
    return redirect(url_for("income"))

# --- Set Monthly Budget Route ---
@app.route("/set-budget", methods=["POST"])
@login_required
def set_budget():
    user_id = session["user_id"]
    budget = request.form.get("budget", type=float)
    now = datetime.now()
    current_month = now.strftime("%Y-%m")

    if budget is not None and budget >= 0:
        db = get_db()
        try:
            db.execute("UPDATE users SET monthly_budget = ? WHERE id = ?", (budget, user_id))
        except Exception:
            pass

        db.execute("""
            INSERT INTO budgets (user_id, month, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, month) DO UPDATE SET amount = excluded.amount
        """, (user_id, current_month, budget))
        db.commit()

        flash(f"Monthly Budget ${budget:,.2f} successfully saved!", "success")
    else:
        flash("Please enter a valid budget amount.", "danger")

    return redirect(url_for("dashboard"))

# --- Expense Routes ---
@app.route("/expenses", methods=["GET", "POST"])
@login_required
def expenses():
    user_id = session["user_id"]
    db = get_db()

    if request.method == "POST":
        amount = request.form.get("amount", type=float)
        category = request.form.get("category", "").strip()
        date = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip()

        if not amount or amount <= 0 or not category or not date:
            flash("Please enter valid amount, category, and date.", "danger")
        else:
            db.execute("INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                       (user_id, amount, category, date, description))
            db.commit()
            flash("Expense recorded successfully!", "success")
        return redirect(url_for("expenses"))

    category_filter = request.args.get("category", "")
    if category_filter:
        expense_list = db.execute("SELECT * FROM expenses WHERE user_id = ? AND category = ? ORDER BY date DESC, id DESC", (user_id, category_filter)).fetchall()
    else:
        expense_list = db.execute("SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC, id DESC", (user_id,)).fetchall()

    total_expenses = sum(r["amount"] for r in expense_list)
    return render_template("expenses.html", expenses=expense_list, total_expenses=total_expenses, categories=EXPENSE_CATEGORIES, selected_category=category_filter, today=datetime.now().strftime("%Y-%m-%d"))

@app.route("/expenses/edit/<int:expense_id>", methods=["POST"])
@login_required
def edit_expense(expense_id):
    user_id = session["user_id"]
    amount = request.form.get("amount", type=float)
    category = request.form.get("category", "").strip()
    date = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    if amount and amount > 0 and category and date:
        db = get_db()
        db.execute("UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? WHERE id = ? AND user_id = ?",
                   (amount, category, date, description, expense_id, user_id))
        db.commit()
        flash("Expense updated!", "success")
    return redirect(url_for("expenses"))

@app.route("/expenses/delete/<int:expense_id>", methods=["POST"])
@login_required
def delete_expense(expense_id):
    user_id = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
    db.commit()
    flash("Expense entry deleted.", "info")
    return redirect(url_for("expenses"))

# --- Clean All Data Route (Income, Expenses, Budgets) ---
@app.route("/clear-all-data", methods=["POST"])
@login_required
def clear_all_data():
    user_id = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM income WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM expenses WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM budgets WHERE user_id = ?", (user_id,))
    try:
        db.execute("UPDATE users SET monthly_budget = 0.0 WHERE id = ?", (user_id,))
    except Exception:
        pass
    db.commit()
    flash("All your saved income, expense, and budget data has been cleaned!", "info")
    return redirect(url_for("dashboard"))

# --- Delete Account & Email Route ---
@app.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    user_id = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    session.clear()
    flash("Your account and data have been permanently deleted.", "info")
    return redirect(url_for("register"))

# --- Reports & Analytics ---
@app.route("/reports")
@login_required
def reports():
    user_id = session["user_id"]
    df_inc, df_exp = get_user_dataframes(user_id)

    total_income = df_inc["amount"].sum() if not df_inc.empty else 0.0
    total_expense = df_exp["amount"].sum() if not df_exp.empty else 0.0
    net_savings = total_income - total_expense

    category_summary = []
    if not df_exp.empty:
        cat_df = df_exp.groupby("category")["amount"].agg(["sum", "count", "mean"]).reset_index()
        cat_df.columns = ["category", "total_amount", "count", "avg_amount"]
        cat_df["pct"] = (cat_df["total_amount"] / total_expense * 100).round(1)
        cat_df = cat_df.sort_values(by="total_amount", ascending=False)
        category_summary = cat_df.to_dict(orient="records")

    return render_template("reports.html", total_income=total_income, total_expense=total_expense, net_savings=net_savings, category_summary=category_summary)

# --- Chart Data JSON API ---
@app.route("/api/chart-data")
@login_required
def chart_data():
    user_id = session["user_id"]
    df_inc, df_exp = get_user_dataframes(user_id)

    cat_labels, cat_values = [], []
    if not df_exp.empty:
        cat_series = df_exp.groupby("category")["amount"].sum().sort_values(ascending=False)
        cat_labels = list(cat_series.index)
        cat_values = [round(float(v), 2) for v in cat_series.values]

    all_months = set()
    if not df_inc.empty: all_months.update(df_inc["month_year"].unique())
    if not df_exp.empty: all_months.update(df_exp["month_year"].unique())
    sorted_months = sorted(list(all_months))[-12:]

    monthly_labels, monthly_inc, monthly_exp, monthly_sav = [], [], [], []
    for m in sorted_months:
        i_val = df_inc[df_inc["month_year"] == m]["amount"].sum() if not df_inc.empty else 0.0
        e_val = df_exp[df_exp["month_year"] == m]["amount"].sum() if not df_exp.empty else 0.0
        monthly_inc.append(round(float(i_val), 2))
        monthly_exp.append(round(float(e_val), 2))
        monthly_sav.append(round(float(i_val - e_val), 2))
        monthly_labels.append(datetime.strptime(m, "%Y-%m").strftime("%b %Y"))

    return jsonify({
        "categories": {"labels": cat_labels, "data": cat_values},
        "monthly": {"labels": monthly_labels, "income": monthly_inc, "expenses": monthly_exp, "savings": monthly_sav}
    })

# --- Profile Route ---
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = session["user_id"]
    db = get_db()
    user = get_current_user()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "update_budget":
            budget = request.form.get("monthly_budget", type=float)
            if budget is not None and budget >= 0:
                db.execute("UPDATE users SET monthly_budget = ? WHERE id = ?", (budget, user_id))
                db.commit()
                flash("Default budget updated!", "success")
        elif action == "change_password":
            cur_pw = request.form.get("current_password", "")
            new_pw = request.form.get("new_password", "")
            if not check_password_hash(user["password_hash"], cur_pw):
                flash("Current password incorrect.", "danger")
            elif len(new_pw) < 6:
                flash("Password must be at least 6 characters.", "danger")
            else:
                db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new_pw), user_id))
                db.commit()
                flash("Password changed successfully!", "success")
        return redirect(url_for("profile"))

    inc_cnt = db.execute("SELECT COUNT(*) AS c FROM income WHERE user_id = ?", (user_id,)).fetchone()["c"]
    exp_cnt = db.execute("SELECT COUNT(*) AS c FROM expenses WHERE user_id = ?", (user_id,)).fetchone()["c"]
    return render_template("profile.html", user=user, income_count=inc_cnt, expense_count=exp_cnt)

if __name__ == "__main__":
    app.run(debug=True, port=5000)