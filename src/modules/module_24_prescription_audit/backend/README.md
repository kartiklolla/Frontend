# Automated Prescription Audit System — Backend

**Module 24 | DBMS Course Project**

A Python (Flask) backend with MongoDB that audits prescriptions against clinical guidelines, detects violations, scores compliance, and generates improvement suggestions.

---

## Quick Start

```bash
# 1. Activate the virtual environment
source myvenv/bin/activate

# 2. Install dependencies (skip if venv already has them)
pip install -r requirements.txt

# 3. Configure MongoDB (edit .env if needed — default uses Atlas)
# MONGO_URI and DB_NAME are already set in .env

# 4. Seed all 7 collections with sample data
python seed.py

# 5. Start the server
python app.py
# → http://localhost:5000
```

---

## Project Structure

```
backend/
├── app.py                # Flask entry point, blueprint registration
├── db.py                 # MongoDB singleton + index creation
├── utils.py              # JWT auth decorator, JSON helpers, response utils
├── audit_engine.py       # Core audit pipeline (all processing logic)
├── schemas.py            # Document schema reference (not DB-enforced)
├── seed.py               # Seeds all 7 collections with realistic data
├── requirements.txt
├── .env                  # MONGO_URI, DB_NAME, JWT_SECRET
│
├── auth.py               # POST /api/auth — register, login, profile
├── prescriptions.py      # /api/prescriptions — CRUD
├── audits.py             # /api/audits — trigger & view audits
├── violations.py         # /api/violations — view & filter violations
├── improvements.py       # /api/improvements — suggestions & status updates
├── quality_metrics.py    # /api/quality-metrics — compute & view metrics
├── guidelines.py         # /api/guidelines — admin: manage clinical rules
└── reports.py            # /api/reports — stats, rankings, trend detection
```

> **Note:** All route files live directly in the `backend/` directory (not in a `routes/` subdirectory). `audit_engine.py` is also at the root level (not in `services/`).

---

## ER Diagram → MongoDB Collections

The ER diagram has 5 entities and 4 relationships:

```
Prescription ──(UNDERGOES 1:N)──► PrescriptionAudit ──(GENERATES 1:N)──► Violation
                                                                               │
QualityMetric ──(REFERENCES 1:N)──────────────────────────────────────────────┘
                                                                               │
                                              Improvement ◄──(TRIGGERS N:1)───┘
```

| Collection            | ER Entity          | Primary Key  | Foreign Keys                          |
|-----------------------|--------------------|--------------|---------------------------------------|
| `users`               | (external)         | `_id`        | —                                     |
| `prescriptions`       | Prescription       | `_id`        | `doctor_id` → users                   |
| `audits`              | PrescriptionAudit  | `_id`        | `prescription_id`, `doctor_id`        |
| `violations`          | Violation          | `_id`        | `audit_id` → audits (GENERATES), `metric_id` → quality_metrics (REFERENCES) |
| `quality_metrics`     | QualityMetric      | `_id`        | `doctor_id` → users                   |
| `improvements`        | Improvement        | `_id`        | `violation_id` → violations (TRIGGERS), `audit_id` |
| `clinical_guidelines` | (supporting)       | `_id`        | —                                     |

### Key field names (match these exactly in your frontend)

**audits** — `audit_id` (as `_id`), `audit_date`, `compliance_score` (stored as `overall_score`)

**violations** — `violation_id` (as `_id`), `severity`, `audit_id`, `metric_id`

**quality_metrics** — `metric_id` (as `_id`), `audit_area`, `category`, `error_rate`, `compliance_score`

**improvements** — `improvement_id` (as `_id`), `education_suggestion`, `violation_id`

---

## Seed Data

`seed.py` populates all 7 collections in order and prints a summary:

```
users                     4 documents
clinical_guidelines       5 documents
prescriptions             6 documents
audits                    6 documents   ← runs full audit pipeline per prescription
violations                9 documents   ← metric_id back-filled after quality_metrics
quality_metrics           4 documents   ← 2 doctors × 2 months
improvements             11 documents   ← violation_id linked (TRIGGERS relationship)
```

Test credentials (password for all: `password123`):

| Role           | Email                  |
|----------------|------------------------|
| Admin          | admin@hospital.com     |
| Doctor (Priya) | priya@hospital.com     |
| Doctor (Rahul) | rahul@hospital.com     |
| Hospital Staff | anjali@hospital.com    |

---

## API Reference

All endpoints return:
```json
{ "success": true, "message": "...", "data": { ... } }
```

All protected endpoints require: `Authorization: Bearer <token>`

---

### Auth — `/api/auth`

| Method | Endpoint            | Auth | Description              |
|--------|---------------------|------|--------------------------|
| POST   | `/register`         | No   | Register a new user      |
| POST   | `/login`            | No   | Login, returns JWT token |
| GET    | `/profile`          | Yes  | Get logged-in user info  |

**Login body:**
```json
{ "email": "priya@hospital.com", "password": "password123" }
```
**Login response `data`:** `{ token, role, name }`

---

### Prescriptions — `/api/prescriptions`

| Method | Endpoint    | Role       | Description             |
|--------|-------------|------------|-------------------------|
| POST   | `/`         | Any        | Create prescription     |
| GET    | `/`         | Any        | List (paginated)        |
| GET    | `/<id>`     | Any        | Get single prescription |
| PUT    | `/<id>`     | Any        | Update prescription     |
| DELETE | `/<id>`     | Admin only | Delete prescription     |

**Query params (GET list):** `doctor_id`, `patient_id`, `page`, `limit`

**Create body:**
```json
{
  "patient_name": "Amit Patel",
  "patient_age": 45,
  "patient_gender": "Male",
  "patient_id": "PAT001",
  "diagnosis": "Bacterial infection",
  "medications": [
    {
      "drug_name": "amoxicillin",
      "dosage": "500mg",
      "frequency": "three times daily",
      "duration": "7 days",
      "route": "oral"
    }
  ],
  "notes": "Follow up in 7 days",
  "is_legible": true
}
```

---

### Audits — `/api/audits`

| Method | Endpoint                            | Role | Description                          |
|--------|-------------------------------------|------|--------------------------------------|
| POST   | `/run/<prescription_id>`            | Any  | **Run full audit on a prescription** |
| GET    | `/`                                 | Any  | List audits (paginated)              |
| GET    | `/<audit_id>`                       | Any  | Get audit + violations + improvements|
| GET    | `/prescription/<prescription_id>`   | Any  | Audit history for a prescription     |

**Query params (GET list):** `doctor_id`, `status` (`pass`/`fail`/`warning`), `min_score`, `page`, `limit`

**Audit pipeline steps** (triggered by `POST /run/<id>`):
1. Completeness check → missing field violations
2. Legibility check → illegible / abbreviation violations
3. Guideline adherence → dosage and required field violations
4. Safety check → drug interactions and contraindications
5. Weighted scoring across all 4 areas
6. Root cause analysis → pattern identification
7. Education suggestions → targeted recommendations
8. Persist to `audits`, `violations`, `improvements` collections

**Scoring weights:**

| Area            | Weight |
|-----------------|--------|
| Completeness    | 25%    |
| Legibility      | 15%    |
| Appropriateness | 30%    |
| Safety          | 30%    |

**Status thresholds:** `pass` ≥ 70 and safety ≥ 50 | `warning` 40–70 | `fail` < 40 or safety < 50

---

### Violations — `/api/violations`

| Method | Endpoint    | Role | Description                        |
|--------|-------------|------|------------------------------------|
| GET    | `/`         | Any  | List violations (paginated)        |
| GET    | `/<id>`     | Any  | Get single violation               |
| GET    | `/summary`  | Any  | Aggregated count by category × severity |

**Query params:** `category` (`completeness`/`legibility`/`appropriateness`/`safety`), `severity` (`low`/`medium`/`high`/`critical`), `audit_id`, `prescription_id`, `page`, `limit`

**Key fields returned:** `violation_id` (as `_id`), `severity`, `audit_id`, `metric_id`, `category`, `description`, `penalty_points`

---

### Improvements — `/api/improvements`

| Method | Endpoint           | Role | Description             |
|--------|--------------------|------|-------------------------|
| GET    | `/`                | Any  | List improvement suggestions |
| GET    | `/<id>`            | Any  | Get single suggestion   |
| PATCH  | `/<id>/status`     | Any  | Update status           |

**Query params (GET list):** `doctor_id`, `status`, `priority`, `page`, `limit`

**Status update body:**
```json
{ "status": "acknowledged" }
```
Valid values: `pending` → `acknowledged` → `resolved`

**Key fields returned:** `improvement_id` (as `_id`), `education_suggestion`, `violation_id`, `audit_id`, `priority`, `status`

---

### Quality Metrics — `/api/quality-metrics`

| Method | Endpoint                      | Role         | Description                  |
|--------|-------------------------------|--------------|------------------------------|
| POST   | `/compute/<doctor_id>`        | Admin/Staff  | Compute metrics for a period |
| GET    | `/`                           | Any          | List metrics                 |
| GET    | `/<doctor_id>/trend`          | Any          | Trend data for charts        |

**Query params:** `period` (e.g. `2026-03`), `doctor_id`, `months` (for trend, default 6)

**Key fields returned:** `metric_id` (as `_id`), `audit_area`, `category`, `error_rate`, `compliance_score`, `improvement_trend`

---

### Clinical Guidelines — `/api/guidelines`

| Method | Endpoint    | Role       | Description               |
|--------|-------------|------------|---------------------------|
| POST   | `/`         | Admin only | Create guideline          |
| GET    | `/`         | Any        | List active guidelines    |
| GET    | `/<id>`     | Any        | Get single guideline      |
| PUT    | `/<id>`     | Admin only | Update guideline          |
| DELETE | `/<id>`     | Admin only | Deactivate guideline      |

**Query params (GET list):** `category`, `drug_name`

**Rule types:** `max_dosage`, `interaction`, `contraindication`, `required_field`

---

### Reports — `/api/reports`

| Method | Endpoint              | Role        | Description                         |
|--------|-----------------------|-------------|-------------------------------------|
| GET    | `/audit-summary`      | Admin/Staff | Pass/fail counts, average scores    |
| GET    | `/violation-analysis` | Admin/Staff | Violations by category & severity   |
| GET    | `/doctor-rankings`    | Admin/Staff | Doctors ranked by compliance score  |
| GET    | `/trend-detection`    | Admin/Staff | Improving / declining / stable list |

**Query params:** `period` (e.g. `2026-03`) for rankings

---

## Frontend Integration

### 1. Environment variable
In your React project root, add to `.env`:
```
VITE_API_BASE_URL=http://localhost:5000/api
```
(Use `REACT_APP_API_BASE_URL` for Create React App.)

### 2. Login and store token
```js
const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'priya@hospital.com', password: 'password123' }),
});
const { data } = await res.json();
localStorage.setItem('token', data.token);  // also store data.role, data.name
```

### 3. Authenticated requests
```js
const token = localStorage.getItem('token');

const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/audits/`, {
  headers: { Authorization: `Bearer ${token}` },
});
const { data } = await res.json();
// data.audits — array of audit objects
```

### 4. Run an audit from the UI
```js
// After creating a prescription, trigger its audit:
await fetch(`${import.meta.env.VITE_API_BASE_URL}/audits/run/${prescriptionId}`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${token}` },
});
```

### 5. Field name reference for UI components

| UI label               | API field              | Collection       |
|------------------------|------------------------|------------------|
| Audit Date             | `audit_date`           | audits           |
| Compliance Score       | `overall_score`        | audits           |
| Audit Area             | `audit_area`           | quality_metrics  |
| Category               | `category`             | quality_metrics  |
| Error Rate             | `error_rate`           | quality_metrics  |
| Severity               | `severity`             | violations       |
| Links metric           | `metric_id`            | violations       |
| Education Suggestion   | `education_suggestion` | improvements     |
| Triggered by violation | `violation_id`         | improvements     |

> All MongoDB `_id` values are serialized to strings in every API response.

---

## Quick cURL Tests

```bash
# Login and capture token
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@hospital.com","password":"password123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['token'])")

# Health check
curl http://localhost:5000/api/health

# List prescriptions
curl http://localhost:5000/api/prescriptions/ -H "Authorization: Bearer $TOKEN"

# Run audit on a prescription (replace with real ID from above)
curl -X POST http://localhost:5000/api/audits/run/<PRESCRIPTION_ID> \
  -H "Authorization: Bearer $TOKEN"

# View all audits
curl http://localhost:5000/api/audits/ -H "Authorization: Bearer $TOKEN"

# View violations for an audit
curl "http://localhost:5000/api/violations/?audit_id=<AUDIT_ID>" \
  -H "Authorization: Bearer $TOKEN"

# View improvements (with education_suggestion field)
curl http://localhost:5000/api/improvements/ -H "Authorization: Bearer $TOKEN"

# Compute quality metrics for a doctor
curl -X POST "http://localhost:5000/api/quality-metrics/compute/<DOCTOR_ID>?period=2026-03" \
  -H "Authorization: Bearer $TOKEN"

# Reports
curl http://localhost:5000/api/reports/audit-summary -H "Authorization: Bearer $TOKEN"
curl http://localhost:5000/api/reports/doctor-rankings -H "Authorization: Bearer $TOKEN"
```
