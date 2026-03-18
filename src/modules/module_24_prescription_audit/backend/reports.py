"""
Reports routes — statistical quality analysis and trend detection.
Maps to DFD Process 7: Perform Statistical Trend Analysis and Generate Reports.
Outputs: Audit Report, Compliance Score, Quality Metric Report, Trend Analysis.
"""

from flask import Blueprint, request

from db import mongo
from utils import ok, error, serialize_doc, token_required

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/audit-summary", methods=["GET"])
@token_required
def audit_summary():
    """
    Overall audit summary — pass/fail/warning counts, average scores.
    Accessible by admin and hospital staff.
    """
    if request.user["role"] not in ("admin", "hospital_staff"):
        return error("Admin or hospital staff access required", 403)

    db = mongo.get_db()

    pipeline = [
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1},
            "avg_score": {"$avg": "$overall_score"},
        }},
    ]
    status_stats = {r["_id"]: {"count": r["count"], "avg_score": round(r["avg_score"], 2)}
                    for r in db.audits.aggregate(pipeline)}

    total = sum(s["count"] for s in status_stats.values())

    # Average scores across all audits
    score_pipeline = [
        {"$group": {
            "_id": None,
            "avg_completeness": {"$avg": "$completeness_score"},
            "avg_legibility": {"$avg": "$legibility_score"},
            "avg_appropriateness": {"$avg": "$appropriateness_score"},
            "avg_safety": {"$avg": "$safety_score"},
            "avg_overall": {"$avg": "$overall_score"},
        }},
    ]
    score_result = list(db.audits.aggregate(score_pipeline))
    avg_scores = {}
    if score_result:
        s = score_result[0]
        avg_scores = {k: round(v, 2) for k, v in s.items() if k != "_id" and v is not None}

    return ok({
        "total_audits": total,
        "by_status": status_stats,
        "average_scores": avg_scores,
    })


@reports_bp.route("/violation-analysis", methods=["GET"])
@token_required
def violation_analysis():
    """
    Violation breakdown by category and severity — for dashboards.
    """
    if request.user["role"] not in ("admin", "hospital_staff"):
        return error("Admin or hospital staff access required", 403)

    db = mongo.get_db()

    # By category
    cat_pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}, "avg_penalty": {"$avg": "$penalty_points"}}},
        {"$sort": {"count": -1}},
    ]
    by_category = [
        {"category": r["_id"], "count": r["count"], "avg_penalty": round(r["avg_penalty"], 2)}
        for r in db.violations.aggregate(cat_pipeline)
    ]

    # By severity
    sev_pipeline = [
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    by_severity = [
        {"severity": r["_id"], "count": r["count"]}
        for r in db.violations.aggregate(sev_pipeline)
    ]

    # Top violated fields
    field_pipeline = [
        {"$group": {"_id": "$field", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    top_fields = [
        {"field": r["_id"], "count": r["count"]}
        for r in db.violations.aggregate(field_pipeline)
    ]

    return ok({
        "by_category": by_category,
        "by_severity": by_severity,
        "top_violated_fields": top_fields,
    })


@reports_bp.route("/doctor-rankings", methods=["GET"])
@token_required
def doctor_rankings():
    """
    Rank doctors by compliance score for a given period.
    """
    if request.user["role"] not in ("admin", "hospital_staff"):
        return error("Admin or hospital staff access required", 403)

    db = mongo.get_db()
    period = request.args.get("period")

    query = {}
    if period:
        query["period"] = period

    docs = list(
        db.quality_metrics.find(query).sort("compliance_score", -1)
    )

    # Enrich with doctor names
    rankings = []
    for d in docs:
        from bson import ObjectId as OId
        try:
            user = db.users.find_one({"_id": OId(d["doctor_id"])}, {"name": 1, "email": 1})
        except Exception:
            user = None
        entry = serialize_doc(d)
        entry["doctor_name"] = user["name"] if user else "Unknown"
        rankings.append(entry)

    return ok(rankings)


@reports_bp.route("/trend-detection", methods=["GET"])
@token_required
def trend_detection():
    """
    Detect improvement/degradation trends across all doctors.
    Uses the improvement_trend field from quality_metrics.
    """
    if request.user["role"] not in ("admin", "hospital_staff"):
        return error("Admin or hospital staff access required", 403)

    db = mongo.get_db()

    pipeline = [
        {"$sort": {"period": -1}},
        {"$group": {
            "_id": "$doctor_id",
            "latest_period": {"$first": "$period"},
            "latest_score": {"$first": "$compliance_score"},
            "latest_trend": {"$first": "$improvement_trend"},
            "periods_tracked": {"$sum": 1},
        }},
        {"$sort": {"latest_trend": -1}},
    ]
    results = list(db.quality_metrics.aggregate(pipeline))

    improving = [r for r in results if r.get("latest_trend", 0) > 0]
    declining = [r for r in results if r.get("latest_trend", 0) < 0]
    stable = [r for r in results if r.get("latest_trend", 0) == 0]

    return ok({
        "improving": serialize_doc(improving),
        "declining": serialize_doc(declining),
        "stable": serialize_doc(stable),
        "total_doctors_tracked": len(results),
    })
