# rubrikRKS — Project Requirements

Rubric-based course assessment app. Flask + SQLite + Argon2 auth. Courses uploaded as JSON (hierarchical rubric), classes per course, 0–100 scores, and portfolio analytics per class or combined.

## 1. Goal

Let lecturers grade students against a two-level hierarchical rubric (categories + components with `code_pi`/`codes_pi` and weights), map everything to CLO/TP with SO-PI codes (`CLO-1-1a`), and analyze whether the rubric is sound (weight balance, discrimination, score spread).

## 2. Scope / Architecture

- **Backend:** Flask app factory (`modules/`) — blueprints: `auth`, `dashboard`, `users`, `courses`; services: `portfolio`, `excel`, `data`, `helpers`, `validation`, `seeder`, `rubric_builder`.
- **ORM:** SQLAlchemy 2 (`modules/models.py`) — tables: `users`, `courses` (is_pbl, owner_id), `classes` (owner_id, name, lecturer), `categories`, `components` (cpl_pis JSON), `criteria`, `criteria_subjects`, `students`, `scores`, `cpls` (proficiency_level, so_codes).
- **Migrations:** Flask-Migrate / Alembic (`migrations/`) — schema managed via `flask db migrate` / `flask db upgrade`.
- **DB:** MySQL (default, via PyMySQL) or SQLite (set `RKS_DB_ENGINE`), both configured through `SQLALCHEMY_DATABASE_URI` in `.env`.
- **Auth:** Argon2 password hashing; session-based login; default password = email.
- **Frontend:** Server-rendered Jinja2 + vanilla JS, Chart.js via CDN, SVG icons, toast notifications (top-right).
- **Roles:** `tim_kurikulum` (manages users, sees all courses/classes) and `lecturer` (only own courses/classes).

## 3. Features

### 3.1 Auth
- **`/` is the login page.** `/dashboard` is the main app page (requires login).
- Login / logout. Change password.
- Users seeded from https://rks.polibatam.ac.id/#dosen — 13 lecturers + tim_kurikulum account. Email is the username; **default password is the email**.
- `tim_kurikulum` can create/edit/delete users (name, email, role, password).

### 3.2 Dashboard (`/dashboard`)
- 4 summary cards (courses, classes, students, students assessed) scoped to the user.
- Course table (code, name, SKS, semester, components, classes) with **Manage Class**, **edit**, **delete**.
- **Upload Course JSON** (drag & drop modal, structure validation).
- Courses are visible to their owner (lecturer) or all (tim_kurikulum).

### 3.3 Course JSON (hierarchical rubric, CPL-based)
- Course: code, name, SKS, semester, study program, `is_pbl` flag.
- Level 1 categories (`partisipatif`, `tugas`, `kuis`, `ats`, `aas`, `proyek`), Level 2 components with `name`, `weight`, and `cpl_pis` (list of `{cpl, so, pi}` mappings).
- **CPL/TP:** 4–6 per course with `code`, `description`, `proficiency_level` (1–5), and `so_codes` (from `static/data/so-pi.json`). Each component maps to one or more CPL→SO→PI pairs → SO-PI label `CPL{idx}-{pi}` (e.g. `CPL1-1a`).
- PIs offered are only those belonging to the SOs chosen for that CPL. If PBL, Partisipatif + Proyek ≥ 50% (validated).

### 3.4 Manage Classes (`/courses/<id>/classes`)
- Create/edit/delete classes (name + lecturer), 40 student rows each.
- Per class: **Assess**, **Show Portfolio**. Top-right: **Show Combined Portfolio** (all classes of the course).

### 3.5 Assess (per class, spreadsheet)
- No/NIM/Nama columns (royal blue), then category groups → component columns with SO-PI chips, numeric 0–100 cells, Total (unfilled = 0) and Grade (A ≥85 … E) as last columns.
- Keyboard nav, sticky headers/first columns, 40 rows max, Rubric modal (criteria + CLO mapping).
- **Export/Import Excel** with locked Total/Grade columns.

### 3.6 Portfolio (per class and combined)
- Stats + charts: score distribution, component means, level breakdown, weight vs std-dev, PI code means/grades, CLO→indicator mapping.

## 4. API (prefix `/api`, all require auth)

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/login`, `/logout`, `/change-password` | auth |
| GET | `/api/dashboard` | scoped summary stats |
| GET | `/api/courses` | list courses (scoped) |
| POST | `/api/courses/upload` | upload + validate course JSON |
| GET/PUT/DELETE | `/api/courses/<id>` | get / edit / delete course |
| GET/POST | `/api/courses/<id>/classes` | list / create class |
| GET/PUT/DELETE | `/api/classes/<id>` | get / edit / delete class |
| POST | `/api/classes/<id>/save` | save NIM/names + scores |
| GET/POST | `/api/classes/<id>/export` `/import` | Excel roundtrip |
| GET | `/api/classes/<id>/portfolio` | per-class portfolio |
| GET | `/api/courses/<id>/portfolio` | combined portfolio |
| GET/POST/PUT/DELETE | `/users/api/users...` | user management (tim_kurikulum) |

## 5. Non-functional

- App factory in `modules/__init__.py`; entry point `app.py` (`python app.py` or `flask --app app run`).
- **Schema managed by Flask-Migrate**: after changes to models run `flask db migrate -m "..."` then `flask db upgrade`. Initial migration committed.
- Ownership enforced for lecturer role; tim_kurikulum has full visibility.
- Scores clamped 0–100; weights assumed 100%; 40 students/class.
- `.env` holds secrets + DB URI (git-ignored); `.env.example` documents them.

## 6. Out of scope (next steps)

- Real API integration replacing JSON upload.
- Rubric editing UI (currently upload/re-upload).
- Configurable grade thresholds, Excel export of combined portfolio.
