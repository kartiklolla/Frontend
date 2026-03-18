"""
Document schemas for all MongoDB collections.
These are used for validation before inserting into the database.
Not enforced at the DB level (MongoDB is schemaless), but keeps the code clean.
"""

# ---------------------------------------------------------------------------
# Collection: users
# ---------------------------------------------------------------------------
USER_SCHEMA = {
    "name": str,           # full name
    "email": str,          # unique login
    "password_hash": str,  # bcrypt hash
    "role": str,           # "doctor" | "admin" | "hospital_staff"
    "created_at": "datetime",
}

# ---------------------------------------------------------------------------
# Collection: prescriptions
# ---------------------------------------------------------------------------
PRESCRIPTION_SCHEMA = {
    "doctor_id": str,
    "patient_id": str,
    "patient_name": str,
    "patient_age": int,
    "patient_gender": str,
    "diagnosis": str,
    "medications": [
        {
            "drug_name": str,
            "dosage": str,        # e.g. "500mg"
            "frequency": str,     # e.g. "twice daily"
            "duration": str,      # e.g. "7 days"
            "route": str,         # e.g. "oral"
        }
    ],
    "notes": str,
    "is_legible": bool,
    "created_at": "datetime",
    "updated_at": "datetime",
}

# ---------------------------------------------------------------------------
# Collection: audits  (PrescriptionAudit entity)
# ---------------------------------------------------------------------------
AUDIT_SCHEMA = {
    "prescription_id": str,
    "doctor_id": str,
    "audit_date": "datetime",
    "completeness_score": float,    # 0-100
    "legibility_score": float,      # 0-100
    "appropriateness_score": float, # 0-100
    "safety_score": float,          # 0-100
    "overall_score": float,         # weighted average
    "status": str,                  # "pass" | "fail" | "warning"
    "guideline_adherence_score": float,
    "violations_count": int,
    "root_cause_analysis": str,
    "education_suggestions": list,
    "created_at": "datetime",
}

# ---------------------------------------------------------------------------
# Collection: violations
# ---------------------------------------------------------------------------
VIOLATION_SCHEMA = {
    "audit_id": str,          # FK → audits._id  (GENERATES relationship)
    "metric_id": str,         # FK → quality_metrics._id  (REFERENCES relationship)
    "prescription_id": str,
    "category": str,          # "completeness" | "legibility" | "appropriateness" | "safety"
    "severity": str,          # "low" | "medium" | "high" | "critical"
    "description": str,
    "field": str,             # which field triggered it, e.g. "dosage"
    "guideline_reference": str,
    "penalty_points": float,
    "created_at": "datetime",
}

# ---------------------------------------------------------------------------
# Collection: improvements
# ---------------------------------------------------------------------------
IMPROVEMENT_SCHEMA = {
    "violation_id": str,      # FK → violations._id  (TRIGGERS relationship)
    "audit_id": str,
    "doctor_id": str,
    "education_suggestion": str,   # matches ER diagram attribute name
    "category": str,
    "priority": str,          # "low" | "medium" | "high"
    "status": str,            # "pending" | "acknowledged" | "resolved"
    "created_at": "datetime",
    "updated_at": "datetime",
}

# ---------------------------------------------------------------------------
# Collection: quality_metrics
# ---------------------------------------------------------------------------
QUALITY_METRIC_SCHEMA = {
    "doctor_id": str,
    "period": str,            # e.g. "2026-03" (monthly)
    "audit_area": str,        # "completeness" | "legibility" | "appropriateness" | "safety" | "overall"
    "category": str,          # grouping label, e.g. "monthly_summary"
    "total_prescriptions": int,
    "total_audits": int,
    "error_rate": float,      # % of failed audits
    "compliance_score": float,
    "avg_completeness": float,
    "avg_legibility": float,
    "avg_appropriateness": float,
    "avg_safety": float,
    "improvement_trend": float,   # positive = improving
    "created_at": "datetime",
    "updated_at": "datetime",
}

# ---------------------------------------------------------------------------
# Collection: clinical_guidelines
# ---------------------------------------------------------------------------
GUIDELINE_SCHEMA = {
    "name": str,
    "category": str,         # "dosage" | "interaction" | "contraindication" | "general"
    "drug_name": str,
    "rules": [
        {
            "rule_type": str,    # "max_dosage" | "interaction" | "contraindication" | "required_field"
            "description": str,
            "params": dict,      # flexible: {"max_mg": 4000, "per": "day"} etc.
        }
    ],
    "is_active": bool,
    "created_at": "datetime",
    "updated_at": "datetime",
}
