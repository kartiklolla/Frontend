"""
Seed script — populates ALL 7 collections with sample data.

Collections seeded:
  1. users
  2. clinical_guidelines
  3. prescriptions
  4. audits              (via audit pipeline)
  5. violations          (via audit pipeline, then linked to quality_metrics)
  6. quality_metrics     (computed per doctor per month)
  7. improvements        (linked to violations via TRIGGERS relationship)

Run: python seed.py
"""

import os
import sys
import re
from datetime import datetime, timezone, timedelta
import bcrypt
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "prescription_audit_db")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]


def now():
    return datetime.now(timezone.utc)


def days_ago(n):
    return datetime.now(timezone.utc) - timedelta(days=n)


# ---------------------------------------------------------------------------
# Audit helpers (duplicated here so seed.py is self-contained without Flask)
# ---------------------------------------------------------------------------

REQUIRED_PRESCRIPTION_FIELDS = ["patient_name", "patient_age", "diagnosis", "medications"]
REQUIRED_MEDICATION_FIELDS = ["drug_name", "dosage", "frequency", "duration"]

KNOWN_INTERACTIONS = [
    {"drugs": {"warfarin", "aspirin"}, "severity": "high", "note": "Increased bleeding risk"},
    {"drugs": {"metformin", "alcohol"}, "severity": "high", "note": "Lactic acidosis risk"},
    {"drugs": {"lisinopril", "potassium"}, "severity": "medium", "note": "Hyperkalemia risk"},
    {"drugs": {"simvastatin", "erythromycin"}, "severity": "high", "note": "Rhabdomyolysis risk"},
]


def _extract_number(s):
    match = re.search(r"[\d.]+", str(s))
    return float(match.group()) if match else 0.0


def check_completeness(prescription):
    violations, passed = [], 0
    total_checks = len(REQUIRED_PRESCRIPTION_FIELDS)
    for field in REQUIRED_PRESCRIPTION_FIELDS:
        val = prescription.get(field)
        if val is None or val == "" or val == []:
            violations.append({
                "category": "completeness", "severity": "high",
                "description": f"Missing required field: {field}", "field": field,
                "guideline_reference": "Prescription completeness standard", "penalty_points": 15.0,
            })
        else:
            passed += 1
    meds = prescription.get("medications", [])
    for i, med in enumerate(meds):
        total_checks += len(REQUIRED_MEDICATION_FIELDS)
        for mf in REQUIRED_MEDICATION_FIELDS:
            if not med.get(mf):
                violations.append({
                    "category": "completeness", "severity": "medium",
                    "description": f"Medication #{i+1}: missing '{mf}'",
                    "field": f"medications[{i}].{mf}",
                    "guideline_reference": "Medication completeness standard", "penalty_points": 10.0,
                })
            else:
                passed += 1
    score = (passed / max(total_checks, 1)) * 100
    return round(score, 2), violations


def check_legibility(prescription):
    violations, score = [], 100.0
    if not prescription.get("is_legible", True):
        score = 20.0
        violations.append({
            "category": "legibility", "severity": "critical",
            "description": "Prescription marked as illegible", "field": "is_legible",
            "guideline_reference": "Legibility standard", "penalty_points": 30.0,
        })
    for i, med in enumerate(prescription.get("medications", [])):
        if med.get("drug_name") and len(med["drug_name"]) < 3:
            score -= 15
            violations.append({
                "category": "legibility", "severity": "medium",
                "description": f"Medication #{i+1}: drug name '{med['drug_name']}' may be an unclear abbreviation",
                "field": f"medications[{i}].drug_name",
                "guideline_reference": "Avoid ambiguous abbreviations", "penalty_points": 10.0,
            })
    return max(round(score, 2), 0), violations


def check_appropriateness(prescription, guidelines):
    violations, total_rules, rules_passed = [], 0, 0
    meds = prescription.get("medications", [])
    for guideline in guidelines:
        for rule in guideline.get("rules", []):
            matching_meds = (
                [(i, m) for i, m in enumerate(meds)
                 if m.get("drug_name", "").lower() == guideline.get("drug_name", "").lower()]
                if guideline.get("drug_name")
                else [(i, m) for i, m in enumerate(meds)]
            )
            if not matching_meds:
                continue
            for idx, med in matching_meds:
                total_rules += 1
                rule_type = rule.get("rule_type", "")
                params = rule.get("params", {})
                if rule_type == "max_dosage":
                    dosage_num = _extract_number(med.get("dosage", "0"))
                    max_val = params.get("max_mg", float("inf"))
                    if dosage_num > max_val:
                        violations.append({
                            "category": "appropriateness", "severity": "high",
                            "description": f"{med['drug_name']}: dosage {med.get('dosage')} exceeds max {max_val}mg",
                            "field": f"medications[{idx}].dosage",
                            "guideline_reference": guideline["name"], "penalty_points": 20.0,
                        })
                    else:
                        rules_passed += 1
                elif rule_type == "required_field":
                    req_field = params.get("field", "")
                    if not med.get(req_field):
                        violations.append({
                            "category": "appropriateness", "severity": "medium",
                            "description": f"{med['drug_name']}: missing required info '{req_field}'",
                            "field": f"medications[{idx}].{req_field}",
                            "guideline_reference": guideline["name"], "penalty_points": 10.0,
                        })
                    else:
                        rules_passed += 1
                else:
                    rules_passed += 1
    score = (rules_passed / max(total_rules, 1)) * 100
    return round(score, 2), violations


def check_safety(prescription, guidelines):
    violations = []
    drug_names = {m.get("drug_name", "").lower() for m in prescription.get("medications", [])}
    for interaction in KNOWN_INTERACTIONS:
        if interaction["drugs"].issubset(drug_names):
            violations.append({
                "category": "safety", "severity": interaction["severity"],
                "description": f"Drug interaction: {' + '.join(interaction['drugs'])} — {interaction['note']}",
                "field": "medications", "guideline_reference": "Drug interaction database",
                "penalty_points": 25.0 if interaction["severity"] == "high" else 15.0,
            })
    for guideline in guidelines:
        for rule in guideline.get("rules", []):
            if rule.get("rule_type") == "interaction":
                interacting = rule.get("params", {}).get("interacts_with", [])
                target = guideline.get("drug_name", "").lower()
                if target in drug_names:
                    for other in interacting:
                        if other.lower() in drug_names:
                            violations.append({
                                "category": "safety", "severity": "high",
                                "description": f"Guideline-flagged interaction: {target} + {other}",
                                "field": "medications",
                                "guideline_reference": guideline["name"], "penalty_points": 25.0,
                            })
            elif rule.get("rule_type") == "contraindication":
                condition = rule.get("params", {}).get("condition", "").lower()
                target = guideline.get("drug_name", "").lower()
                if target in drug_names and condition in prescription.get("diagnosis", "").lower():
                    violations.append({
                        "category": "safety", "severity": "critical",
                        "description": f"{target} is contraindicated for diagnosis containing '{condition}'",
                        "field": "diagnosis",
                        "guideline_reference": guideline["name"], "penalty_points": 30.0,
                    })
    score = max(100 - len(violations) * 25, 0)
    return round(score, 2), violations


def generate_education_suggestions(violations):
    suggestions = set()
    for v in violations:
        cat, sev = v["category"], v["severity"]
        if cat == "completeness":
            suggestions.add("Complete a refresher on prescription writing standards and required fields.")
        if cat == "legibility":
            suggestions.add("Transition to electronic prescription entry to eliminate legibility concerns.")
        if cat == "appropriateness":
            suggestions.add("Review clinical dosing guidelines for commonly prescribed medications.")
        if cat == "safety" and sev in ("high", "critical"):
            suggestions.add("Mandatory drug interaction awareness module required within 30 days.")
        if cat == "safety":
            suggestions.add("Use a clinical decision support tool to flag interactions at prescribing time.")
    if not suggestions:
        suggestions.add("Continue current practices — all audit areas meet standards.")
    return sorted(suggestions)


def generate_root_cause(violations):
    if not violations:
        return "No violations detected."
    categories = {}
    for v in violations:
        cat = v["category"]
        categories[cat] = categories.get(cat, 0) + 1
    worst = max(categories, key=categories.get)
    parts = [f"Primary issue area: {worst} ({categories[worst]} violation(s))."]
    if "safety" in categories:
        parts.append("CRITICAL: Safety violations require immediate attention — review drug interactions and contraindications.")
    if "completeness" in categories:
        parts.append("Incomplete prescriptions suggest rushing or template issues — consider using structured prescription forms.")
    if "legibility" in categories:
        parts.append("Legibility problems indicate handwriting or formatting issues — consider electronic prescriptions.")
    if "appropriateness" in categories:
        parts.append("Appropriateness issues suggest guideline unfamiliarity — targeted training recommended.")
    return " ".join(parts)


def run_audit_for_seed(prescription, guidelines, audit_date):
    """Run audit pipeline and return (audit_doc, all_violations, education_suggestions)."""
    completeness_score, comp_v = check_completeness(prescription)
    legibility_score, leg_v = check_legibility(prescription)
    appropriateness_score, app_v = check_appropriateness(prescription, guidelines)
    safety_score, safety_v = check_safety(prescription, guidelines)

    all_violations = comp_v + leg_v + app_v + safety_v

    overall_score = round(
        completeness_score * 0.25 + legibility_score * 0.15
        + appropriateness_score * 0.30 + safety_score * 0.30, 2
    )
    total_penalty = sum(v["penalty_points"] for v in all_violations)
    guideline_adherence = max(100 - total_penalty, 0)

    if safety_score < 50 or overall_score < 40:
        status = "fail"
    elif overall_score < 70:
        status = "warning"
    else:
        status = "pass"

    root_cause = generate_root_cause(all_violations)
    education = generate_education_suggestions(all_violations)

    audit_doc = {
        "prescription_id": str(prescription["_id"]),
        "doctor_id": prescription.get("doctor_id", ""),
        "audit_date": audit_date,
        "completeness_score": completeness_score,
        "legibility_score": legibility_score,
        "appropriateness_score": appropriateness_score,
        "safety_score": safety_score,
        "overall_score": overall_score,
        "status": status,
        "guideline_adherence_score": round(guideline_adherence, 2),
        "violations_count": len(all_violations),
        "root_cause_analysis": root_cause,
        "education_suggestions": education,
        "created_at": audit_date,
    }
    return audit_doc, all_violations, education


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------

def seed():
    print("Dropping existing collections...")
    for col in ["users", "prescriptions", "audits", "violations",
                 "improvements", "quality_metrics", "clinical_guidelines"]:
        db[col].drop()

    # ── 1. Users ──────────────────────────────────────────────────────────────
    print("Seeding users...")
    password = bcrypt.hashpw("password123".encode(), bcrypt.gensalt()).decode()

    admin = db.users.insert_one({
        "name": "Dr. Admin Kumar", "email": "admin@hospital.com",
        "password_hash": password, "role": "admin", "created_at": now(),
    })
    doctor1 = db.users.insert_one({
        "name": "Dr. Priya Sharma", "email": "priya@hospital.com",
        "password_hash": password, "role": "doctor", "created_at": now(),
    })
    doctor2 = db.users.insert_one({
        "name": "Dr. Rahul Verma", "email": "rahul@hospital.com",
        "password_hash": password, "role": "doctor", "created_at": now(),
    })
    db.users.insert_one({
        "name": "Nurse Anjali", "email": "anjali@hospital.com",
        "password_hash": password, "role": "hospital_staff", "created_at": now(),
    })
    d1_id = str(doctor1.inserted_id)
    d2_id = str(doctor2.inserted_id)
    print("  Created 4 users (password for all: password123)")

    # ── 2. Clinical Guidelines ────────────────────────────────────────────────
    print("Seeding clinical guidelines...")
    guidelines_data = [
        {
            "name": "Paracetamol Dosing Guidelines", "category": "dosage", "drug_name": "paracetamol",
            "rules": [
                {"rule_type": "max_dosage", "description": "Max 4000mg per day", "params": {"max_mg": 4000, "per": "day"}},
                {"rule_type": "required_field", "description": "Route is required", "params": {"field": "route"}},
            ],
            "is_active": True, "created_at": now(), "updated_at": now(),
        },
        {
            "name": "Amoxicillin Guidelines", "category": "dosage", "drug_name": "amoxicillin",
            "rules": [
                {"rule_type": "max_dosage", "description": "Max 3000mg per day for adults", "params": {"max_mg": 3000, "per": "day"}},
            ],
            "is_active": True, "created_at": now(), "updated_at": now(),
        },
        {
            "name": "Warfarin Safety Rules", "category": "interaction", "drug_name": "warfarin",
            "rules": [
                {"rule_type": "interaction", "description": "Do not combine with aspirin", "params": {"interacts_with": ["aspirin"]}},
                {"rule_type": "required_field", "description": "INR monitoring note required", "params": {"field": "notes"}},
            ],
            "is_active": True, "created_at": now(), "updated_at": now(),
        },
        {
            "name": "Metformin Contraindications", "category": "contraindication", "drug_name": "metformin",
            "rules": [
                {"rule_type": "contraindication", "description": "Contraindicated in renal failure",
                 "params": {"condition": "renal failure"}},
            ],
            "is_active": True, "created_at": now(), "updated_at": now(),
        },
        {
            "name": "General Prescription Standards", "category": "general", "drug_name": "",
            "rules": [
                {"rule_type": "required_field", "description": "Route of administration required",
                 "params": {"field": "route"}},
            ],
            "is_active": True, "created_at": now(), "updated_at": now(),
        },
    ]
    db.clinical_guidelines.insert_many(guidelines_data)
    guidelines = list(db.clinical_guidelines.find({"is_active": True}))
    print(f"  Created {len(guidelines_data)} guidelines")

    # ── 3. Prescriptions ──────────────────────────────────────────────────────
    print("Seeding prescriptions...")
    prescriptions_data = [
        # Doctor 1 — Priya
        {
            "doctor_id": d1_id, "patient_id": "PAT001", "patient_name": "Amit Patel",
            "patient_age": 45, "patient_gender": "Male", "diagnosis": "Bacterial infection",
            "medications": [
                {"drug_name": "amoxicillin", "dosage": "500mg", "frequency": "three times daily", "duration": "7 days", "route": "oral"},
                {"drug_name": "paracetamol", "dosage": "650mg", "frequency": "as needed", "duration": "5 days", "route": "oral"},
            ],
            "notes": "Follow up in 7 days", "is_legible": True,
            "created_at": days_ago(40), "updated_at": days_ago(40),
        },
        {
            "doctor_id": d1_id, "patient_id": "PAT002", "patient_name": "Sunita Devi",
            "patient_age": 62, "patient_gender": "Female", "diagnosis": "Atrial fibrillation",
            "medications": [
                {"drug_name": "warfarin", "dosage": "5mg", "frequency": "once daily", "duration": "ongoing", "route": "oral"},
                {"drug_name": "aspirin", "dosage": "75mg", "frequency": "once daily", "duration": "ongoing", "route": "oral"},
            ],
            "notes": "", "is_legible": True,
            "created_at": days_ago(35), "updated_at": days_ago(35),
        },
        {
            "doctor_id": d1_id, "patient_id": "PAT006", "patient_name": "Vikram Singh",
            "patient_age": 40, "patient_gender": "Male", "diagnosis": "Hypertension",
            "medications": [
                {"drug_name": "amlodipine", "dosage": "5mg", "frequency": "once daily", "duration": "ongoing", "route": "oral"},
            ],
            "notes": "Monitor BP weekly", "is_legible": True,
            "created_at": days_ago(10), "updated_at": days_ago(10),
        },
        # Doctor 2 — Rahul
        {
            "doctor_id": d2_id, "patient_id": "PAT003", "patient_name": "Rajesh Kumar",
            "patient_age": 55, "patient_gender": "Male", "diagnosis": "Type 2 Diabetes with renal failure",
            "medications": [
                {"drug_name": "metformin", "dosage": "1000mg", "frequency": "twice daily", "duration": "ongoing", "route": "oral"},
            ],
            "notes": "Check kidney function", "is_legible": True,
            "created_at": days_ago(38), "updated_at": days_ago(38),
        },
        {
            "doctor_id": d2_id, "patient_id": "PAT004", "patient_name": "Meena Gupta",
            "patient_age": 30, "patient_gender": "Female", "diagnosis": "Fever",
            "medications": [
                {"drug_name": "paracetamol", "dosage": "5000mg", "frequency": "four times daily", "duration": "3 days"},
            ],
            "notes": "", "is_legible": False,
            "created_at": days_ago(33), "updated_at": days_ago(33),
        },
        {
            "doctor_id": d2_id, "patient_id": "PAT005", "patient_name": "Lakshmi Nair",
            "patient_age": 50, "patient_gender": "Female", "diagnosis": "Hypercholesterolemia",
            "medications": [
                {"drug_name": "simvastatin", "dosage": "20mg", "frequency": "once daily", "duration": "ongoing", "route": "oral"},
                {"drug_name": "erythromycin", "dosage": "250mg", "frequency": "twice daily", "duration": "5 days", "route": "oral"},
            ],
            "notes": "Liver function test in 3 months", "is_legible": True,
            "created_at": days_ago(8), "updated_at": days_ago(8),
        },
    ]
    result = db.prescriptions.insert_many(prescriptions_data)
    presc_ids = list(result.inserted_ids)
    for i, pid in enumerate(presc_ids):
        prescriptions_data[i]["_id"] = pid
    print(f"  Created {len(prescriptions_data)} prescriptions")

    # ── 4 & 5. Audits + Violations ────────────────────────────────────────────
    print("Running audits and seeding violations...")
    all_audit_docs = []
    all_violation_docs = []
    all_improvement_docs = []

    audit_offsets = [38, 33, 8, 36, 31, 6]   # days ago each audit ran

    for i, presc in enumerate(prescriptions_data):
        audit_date = days_ago(audit_offsets[i])
        audit_doc, violations, education = run_audit_for_seed(presc, guidelines, audit_date)

        audit_result = db.audits.insert_one(audit_doc)
        audit_id = str(audit_result.inserted_id)
        audit_doc["_id"] = audit_result.inserted_id

        # Insert violations, collect their IDs
        violation_ids = []
        if violations:
            for v in violations:
                v["audit_id"] = audit_id
                v["prescription_id"] = str(presc["_id"])
                v["metric_id"] = ""   # will be filled after quality_metrics insert
                v["created_at"] = audit_date
            v_result = db.violations.insert_many(violations)
            violation_ids = [str(vid) for vid in v_result.inserted_ids]
            for j, v in enumerate(violations):
                v["_id"] = v_result.inserted_ids[j]

        all_audit_docs.append((audit_doc, presc["doctor_id"]))
        all_violation_docs.append((violations, violation_ids))
        all_improvement_docs.append((audit_id, presc["doctor_id"], education, audit_date, violation_ids))

    print(f"  Created {len(all_audit_docs)} audits")

    # ── 6. Quality Metrics ───────────────────────────────────────────────────
    print("Computing quality metrics...")

    def compute_metrics_for(doctor_id, period):
        """Compute and upsert quality_metrics for a doctor+period."""
        year, month = map(int, period.split("-"))
        start_dt = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_dt = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_dt = datetime(year, month + 1, 1, tzinfo=timezone.utc)

        audits_in_period = list(db.audits.find({
            "doctor_id": doctor_id,
            "audit_date": {"$gte": start_dt, "$lt": end_dt},
        }))
        if not audits_in_period:
            return None

        total_audits = len(audits_in_period)
        total_prescriptions = db.prescriptions.count_documents({
            "doctor_id": doctor_id,
            "created_at": {"$gte": start_dt, "$lt": end_dt},
        })
        avg = lambda field: round(sum(a.get(field, 0) for a in audits_in_period) / total_audits, 2)
        failed = sum(1 for a in audits_in_period if a.get("status") == "fail")
        error_rate = round((failed / total_audits) * 100, 2)
        compliance_score = avg("overall_score")

        metric = {
            "doctor_id": doctor_id,
            "period": period,
            "audit_area": "overall",       # ER diagram attribute
            "category": "monthly_summary", # ER diagram attribute
            "total_prescriptions": total_prescriptions,
            "total_audits": total_audits,
            "error_rate": error_rate,
            "compliance_score": compliance_score,
            "avg_completeness": avg("completeness_score"),
            "avg_legibility": avg("legibility_score"),
            "avg_appropriateness": avg("appropriateness_score"),
            "avg_safety": avg("safety_score"),
            "improvement_trend": 0.0,
            "created_at": now(),
            "updated_at": now(),
        }
        res = db.quality_metrics.update_one(
            {"doctor_id": doctor_id, "period": period},
            {"$set": metric},
            upsert=True,
        )
        metric["_id"] = res.upserted_id or db.quality_metrics.find_one(
            {"doctor_id": doctor_id, "period": period})["_id"]
        return metric

    # Periods to compute: last 2 months for each doctor
    current_period = now().strftime("%Y-%m")
    year, month = map(int, current_period.split("-"))
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    prev_period = f"{prev_year}-{prev_month:02d}"

    metric_ids_by_doctor = {}
    for doctor_id in [d1_id, d2_id]:
        for period in [prev_period, current_period]:
            metric = compute_metrics_for(doctor_id, period)
            if metric:
                metric_ids_by_doctor.setdefault(doctor_id, str(metric["_id"]))

    # Back-fill metric_id on violations
    for violations, violation_ids in all_violation_docs:
        for v in violations:
            doctor_id = db.audits.find_one({"_id": ObjectId(v["audit_id"])}, {"doctor_id": 1})["doctor_id"]
            metric_id = metric_ids_by_doctor.get(doctor_id, "")
            db.violations.update_one({"_id": v["_id"]}, {"$set": {"metric_id": metric_id}})

    print(f"  Created quality metrics for {len(metric_ids_by_doctor)} doctors across {prev_period} and {current_period}")

    # ── 7. Improvements (linked to Violations via TRIGGERS) ───────────────────
    print("Seeding improvements...")
    improvement_count = 0
    for audit_id, doctor_id, education, audit_date, violation_ids in all_improvement_docs:
        status = db.audits.find_one({"_id": ObjectId(audit_id)}, {"status": 1})["status"]
        priority = "high" if status == "fail" else ("medium" if status == "warning" else "low")

        for j, suggestion in enumerate(education):
            # Link each improvement to a violation where possible (TRIGGERS: 1 violation → N improvements)
            v_id = violation_ids[j % len(violation_ids)] if violation_ids else ""
            db.improvements.insert_one({
                "violation_id": v_id,           # FK → violations._id (TRIGGERS)
                "audit_id": audit_id,
                "doctor_id": doctor_id,
                "education_suggestion": suggestion,  # ER diagram attribute name
                "category": "education",
                "priority": priority,
                "status": "pending",
                "created_at": audit_date,
                "updated_at": audit_date,
            })
            improvement_count += 1

    print(f"  Created {improvement_count} improvements")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("✅ Seed complete! All 7 collections populated.")
    print("="*60)
    print("\nUser credentials (all passwords: password123):")
    print("  Admin:          admin@hospital.com")
    print("  Doctor (Priya): priya@hospital.com")
    print("  Doctor (Rahul): rahul@hospital.com")
    print("  Staff (Anjali): anjali@hospital.com")
    print("\nMongoDB collections seeded:")
    for col in ["users", "clinical_guidelines", "prescriptions", "audits",
                "violations", "quality_metrics", "improvements"]:
        count = db[col].count_documents({})
        print(f"  {col:<25} {count} documents")
    print("\nStart the Flask server with:")
    print("  cd backend && python app.py")
    print("\nAPI base URL: http://localhost:5000")
    print("Health check: GET http://localhost:5000/api/health")


if __name__ == "__main__":
    seed()
