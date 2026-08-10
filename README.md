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
│   ├── blueprints/         # Flask route blueprints (courses, sopi, etc.)
│   ├── auth.py             # Authentication middleware & helpers
│   ├── excel.py            # Excel export/import logic
│   ├── models.py           # SQLAlchemy database models
│   ├── portfolio.py        # Analytics calculations
│   └── seed.py             # Seeds default accounts & RKS SO-PI set
├── static/                 # Static assets (CSS, JS, fonts, images)
│   ├── css/style.css       # Core stylesheets
│   └── data/so-pi.json     # Seed source for the RKS SO-PI set
└── templates/              # Jinja2 HTML templates
```

---

## Installation & Setup (Development)

### 1. Clone the Project & Set Up Virtual Environment
```bash
git clone https://github.com/idris25muhammad/rubrix-assessment.git
cd rubrix-assessment

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# Linux/macOS:
source venv/bin/activate
# Windows PowerShell:
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
flask db upgrade
```

### 5. Start the Application
Run the Flask development server:
```bash
flask run --debug
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your web browser.

---

## Production Deployment (without Docker)

The app is a plain Python/Flask app, so it can be deployed directly on the server with
`gunicorn` behind nginx — no Docker required. The steps below target an Ubuntu/Debian
server.

### 1. Install System Dependencies
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git nginx mysql-server
```

### 2. Clone the Project & Create a venv
```bash
sudo mkdir -p /opt/rubrix
sudo chown -R $USER:$USER /opt/rubrix
cd /opt/rubrix
git clone https://github.com/idris25muhammad/rubrix-assessment.git .
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/pip install gunicorn
```

### 3. Create the Database
```sql
mysql -u root -p
CREATE DATABASE rubrikrks CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'rubrikrks'@'localhost' IDENTIFIED BY 'your_db_password';
GRANT ALL PRIVILEGES ON rubrikrks.* TO 'rubrikrks'@'localhost';
FLUSH PRIVILEGES;
```

### 4. Configure Environment Variables
Create `/opt/rubrix/.env`:
```env
RKS_SECRET_KEY=your_very_secure_random_key_here
RKS_PORT=5000
RKS_DB_ENGINE=mysql
RKS_MYSQL_HOST=localhost
RKS_MYSQL_PORT=3306
RKS_MYSQL_USER=rubrikrks
RKS_MYSQL_PASSWORD=your_db_password
RKS_MYSQL_DB=rubrikrks
```
Generate a strong secret key with `openssl rand -hex 32`.

### 5. Apply Migrations
```bash
cd /opt/rubrix
venv/bin/flask db upgrade
```

### 6. Create a systemd Service
Create `/etc/systemd/system/rubrix.service`:
```ini
[Unit]
Description=RubriX Gunicorn Server
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/rubrix
EnvironmentFile=/opt/rubrix/.env
ExecStart=/opt/rubrix/venv/bin/gunicorn --workers 4 --bind 127.0.0.1:5000 'app:create_app()'
Restart=always

[Install]
WantedBy=multi-user.target
```
Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rubrix
```

### 7. Configure nginx

**At the domain root:**
```nginx
server {
    listen 80;
    server_name rubrix.example.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Under a sub-path (e.g. `rks.polibatam.ac.id/rubrix`):**
```nginx
server {
    listen 80;
    server_name rks.polibatam.ac.id;

    location /rubrix/ {
        proxy_pass http://127.0.0.1:5000/;
        proxy_set_header Host $host;
        proxy_set_header X-Script-Name /rubrix;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
> **Important:** for the sub-path setup, the app must be wrapped with
> `ProxyFix(..., x_script=1)` in `modules/__init__.py` so Flask honors the
> `X-Script-Name` header and prefixes all `url_for` URLs with `/rubrix`.

Enable the site and reload nginx:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 8. Verify
```bash
sudo systemctl status rubrix
curl -I http://127.0.0.1:5000/login
```

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
