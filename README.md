# 💰 Smart Personal Finance Tracker with AI Advisor

**Tech Stack:** Python, Flask, SQLite3, Pandas, Chart.js, Bootstrap 5

A full-stack, user-friendly personal finance web application built to help individuals monitor income, manage categorized expenses, track monthly budgets, and receive personalized savings recommendations.

---

## 🌟 Key Features

### 1. 🔐 User Authentication & Security
- User registration and login with encrypted password storage (`werkzeug.security`).
- Session-based access control (`@login_required`) with auto-expiry handling.
- Dedicated user profile for password management and account settings.

### 2. 💵 Income & Expense Management (Full CRUD)
- **Income Tracking**: Record salary, freelance, business, investments, gifts, or pocket money.
- **Categorized Expenses**: Log expenses across 10 custom categories: *Food, Transportation, Shopping, Bills, Education, Entertainment, Healthcare, Room rent, Grocery, and Other*.
- Full support to add, view, edit, and delete transactions with real-time updates.

### 3. 🎯 Monthly Budget Tracking
- Set custom monthly spending targets directly from the dashboard.
- Live progress bar indicating budget utilization:
  - 🟢 **< 75%**: Safe spending range.
  - 🟡 **75% - 99%**: Approaching budget warning.
  - 🔴 **≥ 100%**: Exceeded budget alert.

### 4. 🤖 AI Financial Advisor & Savings Targets
- **Automated Target Calculation**: Calculates exact monthly savings goals based on current income:
  - **Minimum Goal (20%)**: Standard 50/30/20 benchmark.
  - **Pro Goal (30%)**: Aggressive wealth-building target.
  - **Safe Spending Cap (80%)**: Daily and monthly maximum limits.
  - **Emergency Fund Target**: 6 months of living expenses reserve.
- **Spending Leak Detection**: Flags categories taking up abnormal percentages of income (e.g., dining out > 25%, shopping > 15%, rent > 40%).

### 5. 📊 Data Analysis with Pandas
- Real-time aggregation of transaction records.
- Groupby summaries analyzing transaction counts, average expenditure, and category share.
- Daily average burn-rate calculations for the current month.

### 6. 📈 Interactive Visualizations (Chart.js)
- **Cash Flow Comparison Chart**: Grouped bar chart comparing monthly income vs expenses.
- **Category Doughnut Chart**: Visual breakdown of spending by category.
- **Savings Trend Line Chart**: Historical net savings trajectory.

### 7. 🧹 Clean Data & Safety Controls
- **One-Click Clean All Data**: Clear test/dummy income, expense, and budget data while keeping login credentials safe.
- **Permanent Account Deletion**: Self-service option to delete all user records and database entries.

---

## 🛠️ Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Backend** | Python 3, Flask |
| **Database** | SQLite3 |
| **Analytics Engine** | Pandas |
| **Frontend** | HTML5, CSS3, Bootstrap 5, JavaScript |
| **Charts** | Chart.js |
| **Security** | Werkzeug Security (PBKDF2/SHA256 Password Hashing) |

---

## 📁 Project Architecture & Folder Structure

```text
finance-tracker/
│
├── app.py                     # Main Flask app, routes, auth, AI engine & Pandas analytics
├── database.db                # SQLite database (auto-created on first run)
├── requirements.txt           # Python package dependencies
├── README.md                  # Project documentation & user guide
│
├── templates/                 # Jinja2 HTML templates
│   ├── base.html              # Master layout (navbar, alerts, footer, CDN links)
│   ├── index.html             # Landing / welcome page
│   ├── login.html             # User login form
│   ├── register.html          # User registration form
│   ├── dashboard.html         # Main dashboard with AI advisor & metric cards
│   ├── income.html            # Income management table & modals
│   ├── expenses.html          # Expense management table with category filter
│   ├── reports.html           # Pandas reports, category breakdown & charts
│   └── profile.html           # User profile & default budget configuration
│
├── static/                    # Frontend static assets
│   ├── css/
│   │   └── style.css          # Custom styling & card elevation effects
│   └── js/
│       ├── dashboard.js       # Chart.js initialization for dashboard
│       └── reports.js         # Chart.js initialization for reports
│
└── data/                      # Optional folder for CSV exports / data backups