# Prescription Audit System — Frontend

**Module C6 / Module 24 | Streamlit UI**

This package is the Streamlit frontend for the Automated Prescription Audit System. It integrates with the Flask + MongoDB backend located at `../backend/` and is embedded into the main MediCare dashboard.

---

## How to Access the Module

Once the Streamlit app is running, the Prescription Audit module is reachable from two places:

- **Doctor dashboard** — sidebar item **"Prescription Audit"**, or click **→** on module **C6** inside *C — Pharmacy & Medications*
- **Admin dashboard** — sidebar item **"Prescription Audit"**

Both routes call `prescription_audit_module()` from `prescription_audit_main.py`.

---

## Prerequisites

### 1. Backend must be running

```bash
cd src/modules/module_24_prescription_audit/backend
source myvenv/bin/activate
python app.py
# → Flask listens on http://localhost:5000
```

### 2. Frontend dependencies

```bash
pip install -r requirements.txt
# Requires: streamlit, streamlit-option-menu, matplotlib, requests
```

### 3. Run the Streamlit app

```bash
# From the repo root (Frontend/)
streamlit run app.py
# → http://localhost:8501
```

### 4. Log in

Use any of the seeded accounts (password for all: `password123`):

| Role           | Email                   | Access                                      |
|----------------|-------------------------|---------------------------------------------|
| Doctor (Priya) | priya@hospital.com      | Own prescriptions and audits                |
| Doctor (Rahul) | rahul@hospital.com      | Own prescriptions and audits                |
| Admin          | admin@hospital.com      | All data + guidelines management            |
| Hospital Staff | anjali@hospital.com     | Quality metrics + reports (doctor dashboard)|

---

## Package Structure

```
frontend/
├── __init__.py                  # Package marker
├── api_client.py                # HTTP wrapper for all backend endpoints
├── prescription_audit_main.py   # Entry point — nav bar, dashboard overview, router
├── prescription_form.py         # New prescription entry form (write to DB)
├── prescriptions_list.py        # Paginated list + per-prescription detail view
├── audits_list.py               # Paginated list of audit records
├── audit_detail.py              # Full audit report: scores, violations, improvements
├── violations_view.py           # Violations dashboard with charts
├── improvements_view.py         # Improvement suggestions with status controls
├── quality_metrics_view.py      # Monthly compliance metrics and trend chart
├── reports_view.py              # Statistical reports (4 tabs)
├── guidelines_view.py           # Clinical guidelines management (admin only)
└── README.md
```

---

## View Router

All navigation is controlled by `st.session_state.pa_view`. The top nav bar in the module sets this value.

| `pa_view` value       | Page rendered              | Key session state used        |
|-----------------------|----------------------------|-------------------------------|
| `dashboard`           | Overview + KPIs            | —                             |
| `new_prescription`    | Prescription entry form    | —                             |
| `prescriptions`       | Prescriptions list         | —                             |
| `prescription_detail` | Single prescription        | `pa_prescription_id`          |
| `audits`              | Audits list                | —                             |
| `audit_detail`        | Full audit report          | `pa_audit_id`, `pa_audit_prev_view` |
| `violations`          | Violations dashboard       | —                             |
| `improvements`        | Improvement suggestions    | —                             |
| `quality_metrics`     | Quality metrics + trend    | —                             |
| `reports`             | Reports (4 tabs)           | —                             |
| `guidelines`          | Guidelines management      | — (admin only)                |

Navigate programmatically:

```python
st.session_state.pa_view = "audit_detail"
st.session_state.pa_audit_id = "<audit _id string>"
st.session_state.pa_audit_prev_view = "audits"   # where Back button returns to
st.rerun()
```

---

## API Client (`api_client.py`)

A thin wrapper around `requests` that:
- Reads `st.session_state.token` and attaches it as `Authorization: Bearer <token>` on every call
- Unwraps the backend's `{"success": true, "data": ...}` envelope automatically — callers receive the inner payload directly
- Returns `(data, status_code)` tuples

```python
from src.modules.module_24_prescription_audit.frontend import api_client

# All functions return (data, http_status_code)
data, status = api_client.list_prescriptions(page=1)
data, status = api_client.create_prescription({...})
data, status = api_client.run_audit(prescription_id)
data, status = api_client.get_audit(audit_id)
data, status = api_client.get_violation_summary()
data, status = api_client.update_improvement_status(imp_id, "acknowledged")
data, status = api_client.list_quality_metrics(doctor_id="...")
data, status = api_client.get_quality_trend(doctor_id)
data, status = api_client.get_audit_summary()
data, status = api_client.get_doctor_rankings()
```

Backend base URL is hardcoded to `http://localhost:5000/api`. Change `BASE_URL` at the top of `api_client.py` if needed.

### Important: some endpoints return a bare list

Several backend `GET` list endpoints return a plain list (not a dict with a named key). Always check the type before calling `.get()`:

```python
# WRONG — crashes if data is a list
metrics = data.get("quality_metrics", [])

# CORRECT
metrics = data if isinstance(data, list) else data.get("quality_metrics", [])
```

Endpoints that return a bare list after unwrapping:

| Function                        | Returns              |
|---------------------------------|----------------------|
| `list_quality_metrics()`        | list of metric docs  |
| `get_quality_trend(doctor_id)`  | list of metric docs  |
| `list_guidelines()`             | list of guideline docs |
| `get_prescription_audits(id)`   | list of audit docs   |

---

## Adding a New Prescription (Data Entry Flow)

1. User fills the form in `prescription_form.py`
2. On submit, `api_client.create_prescription(payload)` sends `POST /api/prescriptions/`
3. The backend saves the document to MongoDB and returns the new `_id`
4. If "Run audit immediately" is checked, `api_client.run_audit(prescription_id)` sends `POST /api/audits/run/<id>`
5. The audit pipeline runs server-side (completeness → legibility → appropriateness → safety) and persists results to `audits`, `violations`, and `improvements` collections
6. The overall score and status are displayed inline; a button navigates to the full audit report

---

## Role-Based Access

`st.session_state.backend_role` (set at login) controls what each user can do:

| Feature                         | `doctor` | `hospital_staff` | `admin` |
|---------------------------------|----------|------------------|---------|
| Create / view own prescriptions | Yes      | —                | Yes     |
| View all prescriptions          | No       | —                | Yes     |
| Run audits                      | Yes      | —                | Yes     |
| View own audits                 | Yes      | —                | Yes     |
| Compute quality metrics         | No       | Yes              | Yes     |
| View reports                    | Yes      | Yes              | Yes     |
| Manage clinical guidelines      | No       | No               | Yes     |

The **Guidelines** nav item is hidden for non-admin users.

---

## Session State Reference

All module-level state keys are prefixed with `pa_` to avoid collisions with the rest of the app.

| Key                    | Type    | Set by                          | Purpose                               |
|------------------------|---------|---------------------------------|---------------------------------------|
| `pa_view`              | str     | nav bar / button clicks         | Current page within the module        |
| `pa_prescription_id`   | str     | prescriptions list              | ID passed to prescription detail page |
| `pa_audit_id`          | str     | audit list / prescription detail| ID passed to audit detail page        |
| `pa_audit_prev_view`   | str     | any page linking to audit detail| Where the Back button returns to      |
| `rx_medications`       | list    | prescription form               | Dynamic medication rows in the form   |
| `new_guideline_rules`  | list    | guidelines view                 | Dynamic rule rows when creating a guideline |

Auth state (set at login, used across the whole app):

| Key            | Type | Description                                    |
|----------------|------|------------------------------------------------|
| `token`        | str  | JWT — sent on every API call                   |
| `user_id`      | str  | MongoDB `_id` of logged-in user                |
| `user_name`    | str  | Display name                                   |
| `backend_role` | str  | `"doctor"` / `"admin"` / `"hospital_staff"`    |
