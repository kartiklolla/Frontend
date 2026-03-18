"""
API Client for Prescription Audit System Backend (Module 24)
Base URL: http://localhost:5000

All backend success responses are wrapped:
  {"success": true, "data": <actual payload>, "message": "..."}
All error responses:
  {"success": false, "message": "..."}

_unwrap() strips the wrapper so callers work with the actual payload directly.
"""

import requests
import streamlit as st

BASE_URL = "http://localhost:5000/api"


def _headers():
    token = st.session_state.get("token", "")
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _unwrap(body, status):
    """
    If the backend returned a success wrapper, return just the inner data.
    On error (or non-standard response) return the body as-is so callers can
    read body.get("message") for the error text.
    """
    if isinstance(body, dict) and body.get("success") is True and "data" in body:
        return body["data"], status
    return body, status


def _get(path, params=None):
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=_headers(), params=params, timeout=10)
        return _unwrap(r.json(), r.status_code)
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to backend. Make sure the server is running on port 5000."}, 503
    except Exception as e:
        return {"error": str(e)}, 500


def _post(path, data):
    try:
        r = requests.post(f"{BASE_URL}{path}", headers=_headers(), json=data, timeout=10)
        return _unwrap(r.json(), r.status_code)
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to backend. Make sure the server is running on port 5000."}, 503
    except Exception as e:
        return {"error": str(e)}, 500


def _put(path, data):
    try:
        r = requests.put(f"{BASE_URL}{path}", headers=_headers(), json=data, timeout=10)
        return _unwrap(r.json(), r.status_code)
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to backend."}, 503
    except Exception as e:
        return {"error": str(e)}, 500


def _patch(path, data):
    try:
        r = requests.patch(f"{BASE_URL}{path}", headers=_headers(), json=data, timeout=10)
        return _unwrap(r.json(), r.status_code)
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to backend."}, 503
    except Exception as e:
        return {"error": str(e)}, 500


def _delete(path):
    try:
        r = requests.delete(f"{BASE_URL}{path}", headers=_headers(), timeout=10)
        return _unwrap(r.json(), r.status_code)
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to backend."}, 503
    except Exception as e:
        return {"error": str(e)}, 500


# ── Auth ──────────────────────────────────────────────────────────────────────

def login(email, password):
    return _post("/auth/login", {"email": email, "password": password})


def register(name, email, password, role):
    return _post("/auth/register", {"name": name, "email": email, "password": password, "role": role})


def get_profile():
    return _get("/auth/profile")


# ── Prescriptions ─────────────────────────────────────────────────────────────

def create_prescription(data):
    return _post("/prescriptions/", data)


def list_prescriptions(doctor_id=None, patient_id=None, page=1, per_page=10):
    params = {"page": page, "per_page": per_page}
    if doctor_id:
        params["doctor_id"] = doctor_id
    if patient_id:
        params["patient_id"] = patient_id
    return _get("/prescriptions/", params)


def get_prescription(prescription_id):
    return _get(f"/prescriptions/{prescription_id}")


def update_prescription(prescription_id, data):
    return _put(f"/prescriptions/{prescription_id}", data)


def delete_prescription(prescription_id):
    return _delete(f"/prescriptions/{prescription_id}")


# ── Audits ────────────────────────────────────────────────────────────────────

def run_audit(prescription_id):
    return _post(f"/audits/run/{prescription_id}", {})


def list_audits(doctor_id=None, status=None, page=1, per_page=10):
    params = {"page": page, "per_page": per_page}
    if doctor_id:
        params["doctor_id"] = doctor_id
    if status:
        params["status"] = status
    return _get("/audits/", params)


def get_audit(audit_id):
    return _get(f"/audits/{audit_id}")


def get_prescription_audits(prescription_id):
    return _get(f"/audits/prescription/{prescription_id}")


# ── Violations ────────────────────────────────────────────────────────────────

def list_violations(audit_id=None, category=None, severity=None):
    params = {}
    if audit_id:
        params["audit_id"] = audit_id
    if category:
        params["category"] = category
    if severity:
        params["severity"] = severity
    return _get("/violations/", params)


def get_violation_summary():
    return _get("/violations/summary")


# ── Improvements ──────────────────────────────────────────────────────────────

def list_improvements(audit_id=None, doctor_id=None, status=None):
    params = {}
    if audit_id:
        params["audit_id"] = audit_id
    if doctor_id:
        params["doctor_id"] = doctor_id
    if status:
        params["status"] = status
    return _get("/improvements/", params)


def update_improvement_status(improvement_id, status):
    return _patch(f"/improvements/{improvement_id}/status", {"status": status})


# ── Quality Metrics ───────────────────────────────────────────────────────────

def compute_quality_metrics(doctor_id, period=None):
    data = {}
    if period:
        data["period"] = period
    return _post(f"/quality-metrics/compute/{doctor_id}", data)


def list_quality_metrics(doctor_id=None, period=None):
    params = {}
    if doctor_id:
        params["doctor_id"] = doctor_id
    if period:
        params["period"] = period
    return _get("/quality-metrics/", params)


def get_quality_trend(doctor_id):
    return _get(f"/quality-metrics/{doctor_id}/trend")


# ── Guidelines ────────────────────────────────────────────────────────────────

def list_guidelines(category=None):
    params = {}
    if category:
        params["category"] = category
    return _get("/guidelines/", params)


def get_guideline(guideline_id):
    return _get(f"/guidelines/{guideline_id}")


def create_guideline(data):
    return _post("/guidelines/", data)


def update_guideline(guideline_id, data):
    return _put(f"/guidelines/{guideline_id}", data)


def delete_guideline(guideline_id):
    return _delete(f"/guidelines/{guideline_id}")


# ── Reports ───────────────────────────────────────────────────────────────────

def get_audit_summary():
    return _get("/reports/audit-summary")


def get_violation_analysis():
    return _get("/reports/violation-analysis")


def get_doctor_rankings():
    return _get("/reports/doctor-rankings")


def get_trend_detection():
    return _get("/reports/trend-detection")


# ── Health ────────────────────────────────────────────────────────────────────

def health_check():
    return _get("/health")
