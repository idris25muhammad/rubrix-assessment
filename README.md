# RubriX - Course Rubric Assessment & Portfolio Analytics

RubriX is a web-based course assessment application designed to help lecturers evaluate student performance against hierarchical rubrics (categories and components mapped to CPL/SO-PI codes) and perform detailed course portfolio analytics.

---

## Tech Stack

*   **Backend:** Python, Flask (Application Factory pattern), Flask-SQLAlchemy (SQLAlchemy 2.0+), Flask-Migrate (Alembic)
*   **Database:** MySQL (default, via PyMySQL) or SQLite (configurable via environment variables)
*   **Security:** Argon2 for secure password hashing and session-based authentication
*   **Frontend:** Jinja2 server-rendered templates, Vanilla CSS, Vanilla JavaScript, Chart.js (via CDN for interactive charts), SVG icons
*   **Excel Processing:** openpyxl for Excel import/export of assessment sheets

---

## Core Features

### 1. Authentication & Role-Based Access Control
*   **Roles:** 
    *   `lecturer`: Access limited to their own courses plus courses shared to them.
    *   `tim_kurikulum` (Curriculum Team): Manages their program's users, courses, and SO-PI (each account is scoped to one program).
*   **Credentials:** Default password for all seeded accounts is their email address.
*   **Security Enforcement:** Session expiration and forced login redirect after a password change.

### 2. Courses Dashboard
*   **Search & Filter:** Server-side search filtering by course code and name.
*   **Pagination:** Managed on the backend (10 courses per page).
*   **JSON Rubric Upload:** Import hierarchical rubrics matching CPL, Student Outcomes (SO), and Performance Indicators (PI) structure.
*   **PBL Validation:** Ensures that Project-Based Learning (PBL) courses have a combined weight of Partisipatif + Proyek >= 50%.

### 3. Class Assessment Sheet
*   **Spreadsheet-style Editor:** Live grading sheet with keyboard navigation (arrows/enter/tab), sticky headers, and input clamping (0–100).
*   **Automatic Calculation:** Live updates of total weight-based scores and grades (A–E).
*   **Excel Roundtrip:** Export assessment sheets to Excel and import scores directly from `.xlsx` files with protected columns (Total/Grade).
*   **Inline Rubric View:** Side-by-side rubric criteria checklist mapping directly to the spreadsheet.

### 4. Portfolio Analytics
*   **Interactive Charts:** Visualization of grade distribution, component means, level breakdown, weight vs. std-dev, and PI code aggregates.
*   **Print layout optimization:** Print PDF support for Portfolio and Assessment sheets in landscape A4.
*   **Auto-scaling:** Automatic scaling of tables and charts for assessment sheets to fit within a single page width.

---

## Directory Structure

```text
├── app.py                  # Application entry point
├── config.py               # Config loader for secrets & DB settings
├── requirements.txt        # Backend dependencies
├── migrations/             # Database migrations schema
├── modules/                # Core application package
│   ├── blueprints/         # Flask routes (courses, auth, etc.)
│   ├── auth.py             # Authentication middleware & helpers
│   ├── excel.py            # Excel export/import logic
│   ├── models.py           # SQLAlchemy database models
│   ├── portfolio.py        # Analytics calculations
│   └── seeder.py           # Seeder helper for course data
├── static/                 # Static assets (CSS, JS, fonts, images)
│   ├── css/style.css       # Core stylesheets
│   └── data/so-pi.json     # Seed source for the RKS SO-PI set
└── templates/              # Jinja2 HTML templates
```

---

## Installation & Setup

### 1. Clone the Project & Set Up Virtual Environment
```bash
# Navigate to the project directory
cd rubrikrks

# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows Powershell)
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and adjust the variables (database credentials, application secret key, etc.):
```bash
cp .env.example .env
```

### 4. Initialize Database & Run Migrations
```bash
# Run migrations to update database schema
flask db upgrade
```

### 5. Start the Application
Run the Flask development server:
```bash
flask run --debug
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your web browser.

---

## Seed Accounts
The application automatically seeds one **Tim Kurikulum** account per study program on startup (password = email):
*   `rks@polibatam.ac.id` (RKS)
*   `ti@polibatam.ac.id` (D3-TI)
*   `trm@polibatam.ac.id` (D4-TRM)
*   `tg@polibatam.ac.id` (D3-TG)
*   `anim@polibatam.ac.id` (D4-ANIM)
*   `trpl@polibatam.ac.id` (D4-TRPL)
*   `tp@polibatam.ac.id` (D4-TP)
*   `s2tk@polibatam.ac.id` (S2-TK)

Each manages only its own program's SO-PI and dashboard. **Lecturer** accounts are created later via the **Users** page; courses can be shared to them from the dashboard **Share** button. The RKS SO-PI set is auto-seeded from `static/data/so-pi.json` on first start, then edited via the **SO-PI** page.
