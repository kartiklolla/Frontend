"""
Quality Metrics routes — compute and retrieve quality metrics per doctor.
Maps to QualityMetric DB in the DFD.
"""

from flask import Blueprint, request
from bson import ObjectId
from datetime import datetime, timezone

from db import mongo
from utils import ok, error, serialize_doc, token_required, now

quality_metrics_bp = Blueprint("quality_metrics", __name__)


@quality_metrics_bp.route("/compute/<doctor_id>", methods=["POST"])
@token_required
def compute_metrics(doctor_id):
    """
    Compute quality metrics for a doctor for a given period (month).
    Aggregates from audits collection.
    """
    if request.user["role"] not in ("admin", "hospital_staff"):
        return error("Admin or hospital staff access required", 403)

    period = request.args.get("period")  # e.g. "2026-03"
    if not period:
        period = datetime.now(timezone.utc).strftime("%Y-%m")

    db = mongo.get_db()

    # Find all audits for this doctor in the period
    start_str = f"{period}-01T00:00:00"
    # Calculate end of month
    year, month = map(int, period.split("-"))
    if month == 12:
        end_str = f"{year+1}-01-01T00:00:00"
    else:
        end_str = f"{year}-{month+1:02d}-01T00:00:00"

    start_dt = datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end_str).replace(tzinfo=timezone.utc)

    audits = list(db.audits.find({
        "doctor_id": doctor_id,
        "audit_date": {"$gte": start_dt, "$lt": end_dt},
    }))

    total_audits = len(audits)
    total_prescriptions = db.prescriptions.count_documents({
        "doctor_id": doctor_id,
        "created_at": {"$gte": start_dt, "$lt": end_dt},
    })

    if total_audits == 0:
        return error("No audits found for this period", 404)

    # Calculate averages
    avg = lambda field: round(sum(a.get(field, 0) for a in audits) / total_audits, 2)
    failed = sum(1 for a in audits if a.get("status") == "fail")
    error_rate = round((failed / total_audits) * 100, 2)

    # Get previous period for trend calculation
    if month == 1:
        prev_period = f"{year-1}-12"
    else:
        prev_period = f"{year}-{month-1:02d}"

    prev_metric = db.quality_metrics.find_one({
        "doctor_id": doctor_id, "period": prev_period
    })
    current_compliance = avg("overall_score")
    improvement_trend = 0.0
    if prev_metric:
        improvement_trend = round(current_compliance - prev_metric.get("compliance_score", 0), 2)

    metric = {
        "doctor_id": doctor_id,
        "period": period,
        "audit_area": "overall",        # ER diagram attribute
        "category": "monthly_summary",  # ER diagram attribute
        "total_prescriptions": total_prescriptions,
        "total_audits": total_audits,
        "error_rate": error_rate,
        "compliance_score": current_compliance,
        "avg_completeness": avg("completeness_score"),
        "avg_legibility": avg("legibility_score"),
        "avg_appropriateness": avg("appropriateness_score"),
        "avg_safety": avg("safety_score"),
        "improvement_trend": improvement_trend,
        "created_at": now(),
        "updated_at": now(),
    }

    # Upsert: update if exists for this doctor+period, else insert
    db.quality_metrics.update_one(
        {"doctor_id": doctor_id, "period": period},
        {"$set": metric},
        upsert=True,
    )

    return ok(serialize_doc(metric), "Quality metrics computed")


@quality_metrics_bp.route("/", methods=["GET"])
@token_required
def list_metrics():
    """List quality metrics with optional doctor and period filters."""
    db = mongo.get_db()
    query = {}

    if request.user["role"] == "doctor":
        query["doctor_id"] = request.user["user_id"]
    elif request.args.get("doctor_id"):
        query["doctor_id"] = request.args["doctor_id"]

    if request.args.get("period"):
        query["period"] = request.args["period"]

    docs = list(db.quality_metrics.find(query).sort("period", -1))
    return ok(serialize_doc(docs))


@quality_metrics_bp.route("/<doctor_id>/trend", methods=["GET"])
@token_required
def get_trend(doctor_id):
    """
    Get quality metric trend for a doctor over multiple periods.
    Returns data suitable for trend charts.
    """
    db = mongo.get_db()
    limit = int(request.args.get("months", 6))
    docs = list(
        db.quality_metrics.find({"doctor_id": doctor_id})
        .sort("period", -1)
        .limit(limit)
    )
    docs.reverse()  # chronological order
    return ok(serialize_doc(docs))
