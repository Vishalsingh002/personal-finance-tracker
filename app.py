import os
import sqlite3
import random
import smtplib
from datetime import datetime
from functools import wraps
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, jsonify, g
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "finance-tracker-ai-secret-key-2026")
DATABASE = os.path.join(os.path.abspath(os.path.dirname(__file__)), "database.db")

# Profile picture upload configuration
UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # Max 5MB file

# Email / SMTP Config for 6-Digit OTP Password Reset
SMTP_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("MAIL_PORT", 587))
MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")

EXPENSE_CATEGORIES = [
    "Food", "Transportation", "Shopping", "Bills",
    "Education", "Entertainment", "Healthcare", "Room rent", "grocery", "Other"
]

INCOME_SOURCES = [
    "Salary", "Freelance", "Business", "Investment", "Gift", "Other"
]


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()

    # Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            monthly_budget REAL DEFAULT 0.0,
            full_name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            occupation TEXT DEFAULT '',
            profile_pic TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Safe migrations for existing databases
    columns = [
        ("monthly_budget", "REAL DEFAULT 0.0"),
        ("full_name", "TEXT DEFAULT ''"),
        ("phone", "TEXT DEFAULT ''"),
        ("occupation", "TEXT DEFAULT ''"),
        ("profile_pic", "TEXT DEFAULT ''"),
    ]
    for col_name, col_def in columns:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass

    # Income Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            source TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    # Expenses Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    # Budgets Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    db.commit()
    db.close()


init_db()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        db = get_db()
        user = db.execute("SELECT id FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        if not user:
            session.clear()
            flash("Session expired. Please log in again.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_current_user():
    user_id = session.get("user_id")
    if user_id:
        try:
            db = get_db()
            user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if user:
                return {"current_user": dict(user)}
        except Exception:
            pass
    return {"current_user": None}


def update_auto_budget(user_id, entry_date=None):
    """Automatically updates user's monthly budget based on total income of that month"""
    db = get_db()
    if entry_date and len(entry_date) >= 7:
        month_prefix = entry_date[:7]
    else:
        month_prefix = datetime.now().strftime("%Y-%m")

    row = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM income WHERE user_id = ? AND date LIKE ?",
        (user_id, f"{month_prefix}%")
    ).fetchone()
    total_income_month = float(row["total"]) if row else 0.0

    # Fallback to total all-time income if current month has no entry
    if total_income_month == 0.0:
        row_all = db.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM income WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        total_income_month = float(row_all["total"]) if row_all else 0.0

    db.execute(
        "UPDATE users SET monthly_budget = ? WHERE id = ?",
        (total_income_month, user_id)
    )
    db.commit()
    return total_income_month


def calculate_ai_advisor(total_income, total_expenses, expenses_by_cat):
    """Upgraded 50/30/20 Financial AI Advisor with Smart Warning & Success Status"""
    needs_categories = {"Food", "Transportation", "Room rent", "grocery", "Bills", "Healthcare", "Education"}
    wants_categories = {"Shopping", "Entertainment", "Other"}

    needs_spent = sum(amt for cat, amt in expenses_by_cat.items() if cat in needs_categories)
    wants_spent = sum(amt for cat, amt in expenses_by_cat.items() if cat in wants_categories)
    actual_savings = max(0.0, total_income - total_expenses)

    target_needs = total_income * 0.50
    target_wants = total_income * 0.30
    target_savings = total_income * 0.20

    needs_pct = (needs_spent / total_income * 100) if total_income > 0 else 0
    wants_pct = (wants_spent / total_income * 100) if total_income > 0 else 0
    savings_pct = (actual_savings / total_income * 100) if total_income > 0 else 0

    advice = []
    if total_income == 0:
        advice.append({
            "type": "info",
            "icon": "fa-info-circle",
            "color": "text-primary",
            "badge": "Setup Target",
            "msg": "Add your monthly income to activate personalized 50/30/20 AI financial advice."
        })
    else:
        # Needs Analysis (Target: 50%)
        if needs_spent > target_needs:
            over = needs_spent - target_needs
            advice.append({
                "type": "warning",
                "icon": "fa-exclamation-triangle",
                "color": "text-danger",
                "badge": "Needs Exceeded",
                "msg": f"Needs spending (₹{needs_spent:,.2f}) exceeds the 50% target (₹{target_needs:,.2f}) by ₹{over:,.2f}. Try optimizing rent, utility bills, or grocery."
            })
        else:
            advice.append({
                "type": "success",
                "icon": "fa-check-circle",
                "color": "text-success",
                "badge": "Needs On Track",
                "msg": f"Great work! Needs spending (₹{needs_spent:,.2f}) is safely within your 50% target (₹{target_needs:,.2f})."
            })

        # Wants Analysis (Target: 30%)
        if wants_spent > target_wants:
            over = wants_spent - target_wants
            advice.append({
                "type": "warning",
                "icon": "fa-exclamation-circle",
                "color": "text-warning",
                "badge": "Wants Alert",
                "msg": f"Wants spending (₹{wants_spent:,.2f}) is over the 30% target (₹{target_wants:,.2f}) by ₹{over:,.2f}. Cut back on shopping & entertainment."
            })
        else:
            advice.append({
                "type": "success",
                "icon": "fa-check-circle",
                "color": "text-success",
                "badge": "Wants Controlled",
                "msg": f"Well done! Lifestyle & wants spending (₹{wants_spent:,.2f}) is well controlled under 30% (₹{target_wants:,.2f})."
            })

        # Savings Analysis (Target: 20%)
        if actual_savings >= target_savings:
            advice.append({
                "type": "success",
                "icon": "fa-trophy",
                "color": "text-success",
                "badge": "Target Hit!",
                "msg": f"Superb! You saved ₹{actual_savings:,.2f} ({savings_pct:.1f}%), hitting your 20% savings target (₹{target_savings:,.2f})!"
            })
        else:
            deficit = target_savings - actual_savings
            advice.append({
                "type": "warning",
                "icon": "fa-piggy-bank",
                "color": "text-danger",
                "badge": "Below Target",
                "msg": f"Current savings (₹{actual_savings:,.2f}) are below your 20% target. Aim to save ₹{deficit:,.2f} more this month to stay on track."
            })

    return {
        "needs_spent": needs_spent,
        "wants_spent": wants_spent,
        "actual_savings": actual_savings,
        "target_needs": target_needs,
        "target_wants": target_wants,
        "target_savings": target_savings,
        "needs_pct": round(needs_pct, 1),
        "wants_pct": round(wants_pct, 1),
        "savings_pct": round(savings_pct, 1),
        "advice": advice
    }


def send_otp_email(to_email, otp_code):
    """Sends 6-digit OTP to user's email via SMTP"""
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        print(f"\n==========================================")
        print(f" [DEV MODE] OTP for {to_email} is: {otp_code}")
        print(f"==========================================\n")
        return True

    try:
        msg = MIMEMultipart()
        msg["From"] = f"FinanceTracker AI <{MAIL_USERNAME}>"
        msg["To"] = to_email
        msg["Subject"] = f"{otp_code} is your Password Reset Verification Code"

        body = f"""
        Hello,

        We received a request to reset your password for FinanceTracker AI.

        Your 6-Digit Verification OTP is: {otp_code}

        This code will expire in 10 minutes. If you did not request this, please ignore this email.

        Best regards,
        FinanceTracker AI Team
        """
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


# ================= AUTH & FORGOT PASSWORD ROUTES =================

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("register.html")

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email)).fetchone()
        if existing:
            flash("Username or Email already registered. Please login.", "warning")
            return redirect(url_for("login"))

        password_hash = generate_password_hash(password)
        db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash)
        )
        db.commit()

        user = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        session["user_id"] = user["id"]
        session["username"] = username
        flash("Registration successful! Welcome to Finance Tracker AI.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username.lower())).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Welcome back, {user['full_name'] or user['username']}!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username/email or password.", "danger")

    return render_template("login.html")


# Forgot Password: Step 1 (Send 6-Digit OTP)
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not email:
            flash("Please enter your registered email address.", "danger")
            return render_template("forgot_password.html")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email,)).fetchone()

        if not user:
            flash("No account registered with this email address.", "danger")
            return render_template("forgot_password.html")

        otp = str(random.randint(100000, 999999))
        session["reset_email"] = email
        session["reset_otp"] = otp
        session["reset_otp_time"] = datetime.now().timestamp()
        session["otp_verified"] = False

        send_otp_email(email, otp)
        flash(f"A 6-digit OTP has been sent to {email}. Please check your inbox.", "info")
        return redirect(url_for("verify_otp"))

    return render_template("forgot_password.html")


# Forgot Password: Step 2 (Verify OTP)
@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if "reset_email" not in session or "reset_otp" not in session:
        flash("Please initiate password reset first.", "warning")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        user_otp = request.form.get("otp", "").strip()
        otp_time = session.get("reset_otp_time", 0)

        if datetime.now().timestamp() - otp_time > 600:
            session.pop("reset_otp", None)
            flash("OTP has expired (valid for 10 minutes). Please request a new one.", "danger")
            return redirect(url_for("forgot_password"))

        if user_otp == session.get("reset_otp"):
            session["otp_verified"] = True
            flash("OTP verified successfully! Now create your new password.", "success")
            return redirect(url_for("reset_password"))
        else:
            flash("Invalid OTP code. Please check and try again.", "danger")

    return render_template("verify_otp.html", email=session.get("reset_email"))


@app.route("/resend-otp")
def resend_otp():
    email = session.get("reset_email")
    if not email:
        return redirect(url_for("forgot_password"))

    otp = str(random.randint(100000, 999999))
    session["reset_otp"] = otp
    session["reset_otp_time"] = datetime.now().timestamp()

    send_otp_email(email, otp)
    flash(f"A new 6-digit OTP has been sent to {email}.", "info")
    return redirect(url_for("verify_otp"))


# Forgot Password: Step 3 (Create New Password)
@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if not session.get("otp_verified") or "reset_email" not in session:
        flash("Unauthorized access. Please verify OTP first.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(new_password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("reset_password.html")

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("reset_password.html")

        db = get_db()
        new_hash = generate_password_hash(new_password)
        db.execute("UPDATE users SET password_hash = ? WHERE LOWER(email) = ?", (new_hash, session["reset_email"]))
        db.commit()

        session.pop("reset_email", None)
        session.pop("reset_otp", None)
        session.pop("reset_otp_time", None)
        session.pop("otp_verified", None)

        flash("Your password has been reset successfully! Please log in with your new password.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login"))


# ================= DASHBOARD ROUTE =================
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    db = get_db()
    current_month_prefix = datetime.now().strftime("%Y-%m")

    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    # 1. Total Income (Current month with all-time fallback)
    inc_month = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM income WHERE user_id = ? AND date LIKE ?",
        (user_id, f"{current_month_prefix}%")
    ).fetchone()
    inc_all = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM income WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    month_income = float(inc_month["total"]) if inc_month else 0.0
    all_income = float(inc_all["total"]) if inc_all else 0.0
    total_income = month_income if month_income > 0 else all_income

    # 2. Total Expenses (Current month with all-time fallback)
    exp_month = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE user_id = ? AND date LIKE ?",
        (user_id, f"{current_month_prefix}%")
    ).fetchone()
    exp_all = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    month_expenses = float(exp_month["total"]) if exp_month else 0.0
    all_expenses = float(exp_all["total"]) if exp_all else 0.0
    total_expenses = month_expenses if month_expenses > 0 else all_expenses

    balance = total_income - total_expenses
    monthly_budget = float(user["monthly_budget"]) if user and user["monthly_budget"] else total_income

    # 3. Expenses by Category
    exp_cats = db.execute("""
        SELECT category, COALESCE(SUM(amount), 0) as total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
    """, (user_id,)).fetchall()
    expenses_by_cat = {row["category"]: float(row["total"]) for row in exp_cats}

    # 4. AI Financial Advisor
    ai_advisor = calculate_ai_advisor(total_income, total_expenses, expenses_by_cat)

    # 5. Recent Transactions
    recent_incomes = db.execute(
        "SELECT 'income' as type, id, amount, source as title, date, description FROM income WHERE user_id = ? ORDER BY date DESC LIMIT 10",
        (user_id,)
    ).fetchall()
    recent_expenses = db.execute(
        "SELECT 'expense' as type, id, amount, category as title, date, description FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT 10",
        (user_id,)
    ).fetchall()

    recent_transactions = sorted(
        [dict(r) for r in recent_incomes] + [dict(r) for r in recent_expenses],
        key=lambda x: str(x["date"]),
        reverse=True
    )[:8]

    return render_template(
        "dashboard.html",
        user=user,
        total_income=total_income,
        total_expenses=total_expenses,
        balance=balance,
        monthly_budget=monthly_budget,
        ai_advisor=ai_advisor,
        recent_transactions=recent_transactions,
        categories=EXPENSE_CATEGORIES,
        sources=INCOME_SOURCES,
        current_date=datetime.now().strftime("%Y-%m-%d")
    )


# ================= INCOME ROUTES (SMART TEMPLATE CHECK) =================
@app.route("/income", methods=["GET"])
@app.route("/incomes", methods=["GET"])
@login_required
def income():
    user_id = session["user_id"]
    db = get_db()
    incomes = db.execute("SELECT * FROM income WHERE user_id = ? ORDER BY date DESC", (user_id,)).fetchall()
    total = float(sum(r["amount"] for r in incomes)) if incomes else 0.0

    # Auto detect income.html or incomes.html
    tpl = "income.html"
    if not os.path.exists(os.path.join(app.root_path, "templates", "income.html")):
        if os.path.exists(os.path.join(app.root_path, "templates", "incomes.html")):
            tpl = "incomes.html"

    return render_template(
        tpl,
        incomes=incomes,
        total_income=total,
        sources=INCOME_SOURCES,
        current_date=datetime.now().strftime("%Y-%m-%d")
    )


@app.route("/income/add", methods=["POST"])
@app.route("/incomes/add", methods=["POST"])
@login_required
def add_income():
    user_id = session["user_id"]
    raw_amount = str(request.form.get("amount", "0")).replace("₹", "").replace(",", "").strip()
    try:
        amount = float(raw_amount)
    except ValueError:
        amount = 0.0

    source = request.form.get("source", "Other").strip()
    date = request.form.get("date", datetime.now().strftime("%Y-%m-%d")).strip()
    description = request.form.get("description", "").strip()
    from_dashboard = request.form.get("from_dashboard") == "1"

    if amount > 0:
        db = get_db()
        db.execute(
            "INSERT INTO income (user_id, amount, source, date, description) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, source, date, description)
        )
        db.commit()

        update_auto_budget(user_id, date)
        flash(f"₹{amount:,.2f} added to Income successfully!", "success")
    else:
        flash("Please enter a valid amount greater than 0.", "danger")

    if from_dashboard:
        return redirect(url_for("dashboard"))
    return redirect(url_for("income"))


@app.route("/income/delete/<int:id>", methods=["POST"])
@login_required
def delete_income(id):
    user_id = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM income WHERE id = ? AND user_id = ?", (id, user_id))
    db.commit()
    update_auto_budget(user_id)
    flash("Income entry deleted successfully.", "info")
    return redirect(request.referrer or url_for("income"))


# ================= EXPENSE ROUTES (SMART TEMPLATE CHECK) =================
@app.route("/expense", methods=["GET"])
@app.route("/expenses", methods=["GET"])
@login_required
def expense():
    user_id = session["user_id"]
    db = get_db()
    expenses = db.execute("SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC", (user_id,)).fetchall()
    total = float(sum(r["amount"] for r in expenses)) if expenses else 0.0

    # Auto detect expense.html or expenses.html
    tpl = "expense.html"
    if not os.path.exists(os.path.join(app.root_path, "templates", "expense.html")):
        if os.path.exists(os.path.join(app.root_path, "templates", "expenses.html")):
            tpl = "expenses.html"

    return render_template(
        tpl,
        expenses=expenses,
        total_expenses=total,
        categories=EXPENSE_CATEGORIES,
        current_date=datetime.now().strftime("%Y-%m-%d")
    )


@app.route("/expense/add", methods=["POST"])
@app.route("/expenses/add", methods=["POST"])
@login_required
def add_expense():
    user_id = session["user_id"]
    raw_amount = str(request.form.get("amount", "0")).replace("₹", "").replace(",", "").strip()
    try:
        amount = float(raw_amount)
    except ValueError:
        amount = 0.0

    category = request.form.get("category", "Other").strip()
    date = request.form.get("date", datetime.now().strftime("%Y-%m-%d")).strip()
    description = request.form.get("description", "").strip()
    from_dashboard = request.form.get("from_dashboard") == "1"

    if amount > 0:
        db = get_db()
        db.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description)
        )
        db.commit()
        flash(f"₹{amount:,.2f} added to Expenses successfully!", "success")
    else:
        flash("Please enter a valid amount greater than 0.", "danger")

    if from_dashboard:
        return redirect(url_for("dashboard"))
    return redirect(url_for("expense"))


@app.route("/expense/delete/<int:id>", methods=["POST"])
@login_required
def delete_expense(id):
    user_id = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (id, user_id))
    db.commit()
    flash("Expense entry deleted.", "info")
    return redirect(request.referrer or url_for("expense"))


# ================= REPORTS ROUTE (SAFE VARIABLES) =================
@app.route("/reports")
@login_required
def reports():
    user_id = session["user_id"]
    db = get_db()

    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    incomes = db.execute("SELECT * FROM income WHERE user_id = ? ORDER BY date DESC", (user_id,)).fetchall()
    expenses = db.execute("SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC", (user_id,)).fetchall()

    total_income = float(sum(r["amount"] for r in incomes)) if incomes else 0.0
    total_expenses = float(sum(r["amount"] for r in expenses)) if expenses else 0.0

    balance = total_income - total_expenses
    net_savings = balance
    net_balance = balance
    savings_rate = round((net_savings / total_income * 100), 1) if total_income > 0 else 0.0
    monthly_budget = float(user["monthly_budget"]) if user and user["monthly_budget"] else total_income

    cat_rows = db.execute("""
        SELECT category, COALESCE(SUM(amount), 0) as total, COUNT(*) as count
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY total DESC
    """, (user_id,)).fetchall()

    return render_template(
        "reports.html",
        user=user,
        total_income=total_income,
        total_expenses=total_expenses,
        balance=balance,
        net_balance=net_balance,
        net_savings=net_savings,
        monthly_budget=monthly_budget,
        savings_rate=savings_rate,
        incomes=incomes,
        expenses=expenses,
        cat_rows=cat_rows
    )


# ================= CLEAN DATA =================
@app.route("/clean-data", methods=["POST"])
@login_required
def clean_data():
    user_id = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM expenses WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM income WHERE user_id = ?", (user_id,))
    db.execute("UPDATE users SET monthly_budget = 0.0 WHERE id = ?", (user_id,))
    db.commit()
    flash("All financial transaction data cleared and budget reset to ₹0.00.", "success")
    return redirect(url_for("dashboard"))


# ================= PROFILE & SETTINGS =================
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = session["user_id"]
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_profile":
            full_name = request.form.get("full_name", "").strip()
            phone = request.form.get("phone", "").strip()
            occupation = request.form.get("occupation", "").strip()
            email = request.form.get("email", "").strip().lower()

            existing = db.execute(
                "SELECT id FROM users WHERE email = ? AND id != ?",
                (email, user_id)
            ).fetchone()
            if existing:
                flash("That email is already in use by another account.", "danger")
                return redirect(url_for("profile"))

            file = request.files.get("profile_pic")
            if file and file.filename and allowed_file(file.filename):
                filename = f"user_{user_id}_{int(datetime.now().timestamp())}_{secure_filename(file.filename)}"
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                db.execute("UPDATE users SET profile_pic = ? WHERE id = ?", (filename, user_id))

            db.execute("""
                UPDATE users
                SET full_name = ?, phone = ?, occupation = ?, email = ?
                WHERE id = ?
            """, (full_name, phone, occupation, email, user_id))
            db.commit()
            flash("Profile details updated successfully!", "success")
            return redirect(url_for("profile"))

    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    inc_sum = db.execute("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM income WHERE user_id = ?", (user_id,)).fetchone()
    exp_sum = db.execute("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM expenses WHERE user_id = ?", (user_id,)).fetchone()

    total_income = float(inc_sum["total"]) if inc_sum else 0.0
    total_expenses = float(exp_sum["total"]) if exp_sum else 0.0
    total_savings = total_income - total_expenses
    total_transactions = (inc_sum["count"] if inc_sum else 0) + (exp_sum["count"] if exp_sum else 0)
    savings_rate = (total_savings / total_income * 100) if total_income > 0 else 0

    return render_template(
        "profile.html",
        user=user,
        total_income=total_income,
        total_expenses=total_expenses,
        total_savings=total_savings,
        savings_rate=round(savings_rate, 1),
        total_transactions=total_transactions
    )


@app.route("/profile/change-password", methods=["POST"])
@login_required
def change_password():
    user_id = session["user_id"]
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    db = get_db()
    user = db.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()

    if not check_password_hash(user["password_hash"], current_password):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for("profile") + "#settings")

    if new_password != confirm_password:
        flash("New password and confirm password do not match.", "danger")
        return redirect(url_for("profile") + "#settings")

    if len(new_password) < 6:
        flash("New password must be at least 6 characters.", "danger")
        return redirect(url_for("profile") + "#settings")

    new_hash = generate_password_hash(new_password)
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    db.commit()
    flash("Password updated successfully!", "success")
    return redirect(url_for("profile") + "#settings")


@app.route("/profile/delete-account", methods=["POST"])
@login_required
def delete_account():
    user_id = session["user_id"]
    confirm_text = request.form.get("confirm_text", "").strip()

    if confirm_text != "DELETE":
        flash("Confirmation text did not match 'DELETE'. Account was not deleted.", "warning")
        return redirect(url_for("profile") + "#settings")

    db = get_db()
    db.execute("DELETE FROM expenses WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM income WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM budgets WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()

    session.clear()
    flash("Your account and all associated financial records have been permanently deleted.", "info")
    return redirect(url_for("register"))


# ================= DASHBOARD CHARTS API =================
@app.route("/api/dashboard-charts")
@login_required
def dashboard_charts():
    user_id = session["user_id"]
    db = get_db()

    cat_rows = db.execute("""
        SELECT category, COALESCE(SUM(amount), 0) as total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
    """, (user_id,)).fetchall()

    cat_labels = [r["category"] for r in cat_rows]
    cat_data = [float(r["total"]) for r in cat_rows]

    expenses = db.execute("""
        SELECT strftime('%Y-%m', date) as month, SUM(amount) as total
        FROM expenses
        WHERE user_id = ?
        GROUP BY month
        ORDER BY month DESC LIMIT 6
    """, (user_id,)).fetchall()

    incomes = db.execute("""
        SELECT strftime('%Y-%m', date) as month, SUM(amount) as total
        FROM income
        WHERE user_id = ?
        GROUP BY month
        ORDER BY month DESC LIMIT 6
    """, (user_id,)).fetchall()

    months = sorted(list(set([r["month"] for r in expenses if r["month"]] + [r["month"] for r in incomes if r["month"]])))
    inc_map = {r["month"]: float(r["total"]) for r in incomes if r["month"]}
    exp_map = {r["month"]: float(r["total"]) for r in expenses if r["month"]}

    trend_labels = months if months else [datetime.now().strftime("%Y-%m")]
    trend_income = [inc_map.get(m, 0.0) for m in trend_labels]
    trend_expenses = [exp_map.get(m, 0.0) for m in trend_labels]

    return jsonify({
        "categories": {"labels": cat_labels, "data": cat_data},
        "trends": {
            "labels": trend_labels,
            "income": trend_income,
            "expenses": trend_expenses
        }
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)