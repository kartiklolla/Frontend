"""
Audit Engine — the core processing pipeline.

Implements the flowchart:
  1. Data Ingestion & Pre-Processing  (completeness & legibility check)
  2. Audit Processing Engine          (guideline matcher → adherence → safety check)
  3. Scoring System                   (penalty calculation, violation recording)
  4. Root Cause Analysis & Education Suggestions
  5. Persist to DB (audits, violations, improvements collections)
"""

from datetime import datetime, timezone
from bson import ObjectId

from db import mongo


def now():
    return datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────────────────────
# STEP 1 — Completeness & Legibility Check
# ──────────────────────────────────────────────────────────────────────────────

REQUIRED_PRESCRIPTION_FIELDS = [
    "patient_name", "patient_age", "diagnosis", "medications",
]
REQUIRED_MEDICATION_FIELDS = [
    "drug_name", "dosage", "frequency", "duration",
]


def check_completeness(prescription: dict) -> tuple[float, list[dict]]:
    """
    Returns (score 0-100, list of violation dicts).
    Every missing required field costs points.
    """
    violations = []
    total_checks = len(REQUIRED_PRESCRIPTION_FIELDS)
    passed = 0

    for field in REQUIRED_PRESCRIPTION_FIELDS:
        val = prescription.get(field)
        if val is None or val == "" or val == []:
            violations.append({
                "category": "completeness",
                "severity": "high",
                "description": f"Missing required field: {field}",
                "field": field,
                "guideline_reference": "Prescription completeness standard",
                "penalty_points": 15.0,
            })
        else:
            passed += 1

    # Check each medication entry
    meds = prescription.get("medications", [])
    if meds:
        for i, med in enumerate(meds):
            total_checks += len(REQUIRED_MEDICATION_FIELDS)
            for mf in REQUIRED_MEDICATION_FIELDS:
                if not med.get(mf):
                    violations.append({
                        "category": "completeness",
                        "severity": "medium",
                        "description": f"Medication #{i+1}: missing '{mf}'",
                        "field": f"medications[{i}].{mf}",
                        "guideline_reference": "Medication completeness standard",
                        "penalty_points": 10.0,
                    })
                else:
                    passed += 1

    score = (passed / max(total_checks, 1)) * 100
    return round(score, 2), violations


def check_legibility(prescription: dict) -> tuple[float, list[dict]]:
    """
    Simple legibility check — in production this could use OCR confidence scores.
    Here we rely on the `is_legible` flag and check for very short / suspicious values.
    """
    violations = []
    score = 100.0

    if not prescription.get("is_legible", True):
        score = 20.0
        violations.append({
            "category": "legibility",
            "severity": "critical",
            "description": "Prescription marked as illegible",
            "field": "is_legible",
            "guideline_reference": "Legibility standard",
            "penalty_points": 30.0,
        })

    # Heuristic: flag extremely short drug names (likely abbreviations)
    for i, med in enumerate(prescription.get("medications", [])):
        if med.get("drug_name") and len(med["drug_name"]) < 3:
            score -= 15
            violations.append({
                "category": "legibility",
                "severity": "medium",
                "description": f"Medication #{i+1}: drug name '{med['drug_name']}' may be an unclear abbreviation",
                "field": f"medications[{i}].drug_name",
                "guideline_reference": "Avoid ambiguous abbreviations",
                "penalty_points": 10.0,
            })

    return max(round(score, 2), 0), violations


# ──────────────────────────────────────────────────────────────────────────────
# STEP 2 — Guideline Adherence & Appropriateness
# ──────────────────────────────────────────────────────────────────────────────

def check_appropriateness(prescription: dict, guidelines: list[dict]) -> tuple[float, list[dict]]:
    """
    Match prescription medications against clinical guidelines.
    Checks dosage limits, contraindications, and required fields.
    """
    violations = []
    total_rules = 0
    rules_passed = 0

    meds = prescription.get("medications", [])

    for guideline in guidelines:
        for rule in guideline.get("rules", []):
            # Match guideline to medications by drug name
            matching_meds = [
                (i, m) for i, m in enumerate(meds)
                if m.get("drug_name", "").lower() == guideline.get("drug_name", "").lower()
            ] if guideline.get("drug_name") else [(i, m) for i, m in enumerate(meds)]

            if not matching_meds:
                continue

            for idx, med in matching_meds:
                total_rules += 1
                rule_type = rule.get("rule_type", "")
                params = rule.get("params", {})

                if rule_type == "max_dosage":
                    # Try to extract numeric dosage
                    dosage_str = med.get("dosage", "0")
                    dosage_num = _extract_number(dosage_str)
                    max_val = params.get("max_mg", float("inf"))
                    if dosage_num > max_val:
                        violations.append({
                            "category": "appropriateness",
                            "severity": "high",
                            "description": f"{med['drug_name']}: dosage {dosage_str} exceeds max {max_val}mg",
                            "field": f"medications[{idx}].dosage",
                            "guideline_reference": guideline["name"],
                            "penalty_points": 20.0,
                        })
                    else:
                        rules_passed += 1

                elif rule_type == "required_field":
                    req_field = params.get("field", "")
                    if not med.get(req_field):
                        violations.append({
                            "category": "appropriateness",
                            "severity": "medium",
                            "description": f"{med['drug_name']}: missing required info '{req_field}'",
                            "field": f"medications[{idx}].{req_field}",
                            "guideline_reference": guideline["name"],
                            "penalty_points": 10.0,
                        })
                    else:
                        rules_passed += 1
                else:
                    rules_passed += 1  # unknown rule type — pass by default

    score = (rules_passed / max(total_rules, 1)) * 100
    return round(score, 2), violations


# ──────────────────────────────────────────────────────────────────────────────
# STEP 3 — Safety Check (drug interactions & contraindications)
# ──────────────────────────────────────────────────────────────────────────────

# Simple built-in interaction database (extend as needed or move to guidelines collection)
KNOWN_INTERACTIONS = [
    {"drugs": {"warfarin", "aspirin"}, "severity": "high", "note": "Increased bleeding risk"},
    {"drugs": {"metformin", "alcohol"}, "severity": "high", "note": "Lactic acidosis risk"},
    {"drugs": {"lisinopril", "potassium"}, "severity": "medium", "note": "Hyperkalemia risk"},
    {"drugs": {"simvastatin", "erythromycin"}, "severity": "high", "note": "Rhabdomyolysis risk"},
]


def check_safety(prescription: dict, guidelines: list[dict]) -> tuple[float, list[dict]]:
    """
    Check for drug-drug interactions and contraindications.
    """
    violations = []
    meds = prescription.get("medications", [])
    drug_names = {m.get("drug_name", "").lower() for m in meds}

    # Check built-in interactions
    for interaction in KNOWN_INTERACTIONS:
        if interaction["drugs"].issubset(drug_names):
            violations.append({
                "category": "safety",
                "severity": interaction["severity"],
                "description": f"Drug interaction: {' + '.join(interaction['drugs'])} — {interaction['note']}",
                "field": "medications",
                "guideline_reference": "Drug interaction database",
                "penalty_points": 25.0 if interaction["severity"] == "high" else 15.0,
            })

    # Check guideline-based contraindications
    for guideline in guidelines:
        for rule in guideline.get("rules", []):
            if rule.get("rule_type") == "interaction":
                interacting = rule.get("params", {}).get("interacts_with", [])
                target = guideline.get("drug_name", "").lower()
                if target in drug_names:
                    for other in interacting:
                        if other.lower() in drug_names:
                            violations.append({
                                "category": "safety",
                                "severity": "high",
                                "description": f"Guideline-flagged interaction: {target} + {other}",
                                "field": "medications",
                                "guideline_reference": guideline["name"],
                                "penalty_points": 25.0,
                            })

            elif rule.get("rule_type") == "contraindication":
                condition = rule.get("params", {}).get("condition", "").lower()
                target = guideline.get("drug_name", "").lower()
                if target in drug_names and condition in prescription.get("diagnosis", "").lower():
                    violations.append({
                        "category": "safety",
                        "severity": "critical",
                        "description": f"{target} is contraindicated for diagnosis containing '{condition}'",
                        "field": "diagnosis",
                        "guideline_reference": guideline["name"],
                        "penalty_points": 30.0,
                    })

    score = max(100 - len(violations) * 25, 0)
    return round(score, 2), violations


# ──────────────────────────────────────────────────────────────────────────────
# STEP 4 — Root Cause Analysis & Education Suggestions
# ──────────────────────────────────────────────────────────────────────────────

def generate_root_cause(violations: list[dict]) -> str:
    """Analyze violation patterns to identify the root cause."""
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


def generate_education_suggestions(violations: list[dict]) -> list[str]:
    """Generate targeted education suggestions based on violations found."""
    suggestions = set()

    for v in violations:
        cat = v["category"]
        sev = v["severity"]

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


# ──────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE — run_audit()
# ──────────────────────────────────────────────────────────────────────────────

def run_audit(prescription_id: str) -> dict:
    """
    Execute the full audit pipeline for a prescription.
    Returns the created audit document.
    """
    db = mongo.get_db()
    prescription = db.prescriptions.find_one({"_id": ObjectId(prescription_id)})
    if not prescription:
        raise ValueError("Prescription not found")

    # Fetch active guidelines
    guidelines = list(db.clinical_guidelines.find({"is_active": True}))

    # ── Step 1: Completeness & Legibility ──
    completeness_score, comp_violations = check_completeness(prescription)
    legibility_score, leg_violations = check_legibility(prescription)

    # If completeness or legibility fails hard, the flowchart says "Reject & Return Error"
    # We still record the audit but mark status accordingly.

    # ── Step 2: Appropriateness (guideline adherence) ──
    appropriateness_score, app_violations = check_appropriateness(prescription, guidelines)

    # ── Step 3: Safety ──
    safety_score, safety_violations = check_safety(prescription, guidelines)

    # ── Combine all violations ──
    all_violations = comp_violations + leg_violations + app_violations + safety_violations

    # ── Scoring ──
    overall_score = (
        completeness_score * 0.25
        + legibility_score * 0.15
        + appropriateness_score * 0.30
        + safety_score * 0.30
    )
    overall_score = round(overall_score, 2)

    total_penalty = sum(v["penalty_points"] for v in all_violations)
    guideline_adherence = max(100 - total_penalty, 0)

    # Determine status
    if safety_score < 50 or overall_score < 40:
        status = "fail"
    elif overall_score < 70:
        status = "warning"
    else:
        status = "pass"

    # ── Step 4: Root cause & education ──
    root_cause = generate_root_cause(all_violations)
    education = generate_education_suggestions(all_violations)

    # ── Persist audit ──
    audit_doc = {
        "prescription_id": str(prescription["_id"]),
        "doctor_id": prescription.get("doctor_id", ""),
        "audit_date": now(),
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
        "created_at": now(),
    }
    audit_result = db.audits.insert_one(audit_doc)
    audit_doc["_id"] = audit_result.inserted_id

    # ── Persist violations ──
    violation_ids = []
    if all_violations:
        for v in all_violations:
            v["audit_id"] = str(audit_doc["_id"])
            v["prescription_id"] = str(prescription["_id"])
            v["metric_id"] = ""   # populated when quality_metrics are computed
            v["created_at"] = now()
        v_result = db.violations.insert_many(all_violations)
        violation_ids = [str(vid) for vid in v_result.inserted_ids]

    # ── Persist improvement suggestions (TRIGGERS: violation → improvements) ──
    if education:
        improvements = []
        for j, suggestion in enumerate(education):
            v_id = violation_ids[j % len(violation_ids)] if violation_ids else ""
            improvements.append({
                "violation_id": v_id,                  # FK → violations._id (TRIGGERS)
                "audit_id": str(audit_doc["_id"]),
                "doctor_id": prescription.get("doctor_id", ""),
                "education_suggestion": suggestion,     # ER diagram attribute name
                "category": "education",
                "priority": "high" if status == "fail" else "medium",
                "status": "pending",
                "created_at": now(),
                "updated_at": now(),
            })
        db.improvements.insert_many(improvements)

    return audit_doc


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_number(s: str) -> float:
    """Pull the first number out of a string like '500mg'."""
    import re
    match = re.search(r"[\d.]+", str(s))
    return float(match.group()) if match else 0.0
