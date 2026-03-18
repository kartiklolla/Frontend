"""
Audit routes — trigger audits and view results.
Maps to DFD Processes 2-5 and the Audit Processing Engine in the flowchart.
"""

from flask import Blueprint, request
from bson import ObjectId

from db import mongo
from utils import ok, error, serialize_doc, token_required
from audit_engine import run_audit

audits_bp = Blueprint("audits", __name__)


@audits_bp.route("/run/<prescription_id>", methods=["POST"])
@token_required
def trigger_audit(prescription_id):
    """
    Run a full audit on a prescription.
    This triggers the entire pipeline: completeness → legibility → guideline
    adherence → safety → scoring → violations → root cause → suggestions.
    """
    try:
        audit_doc = run_audit(prescription_id)
        return ok(serialize_doc(audit_doc), "Audit completed", 201)
    except ValueError as e:
        return error(str(e), 404)
    except Exception as e:
        return error(f"Audit failed: {str(e)}", 500)


@audits_bp.route("/", methods=["GET"])
@token_required
def list_audits():
    """List audits with filters: doctor_id, status, date range, score range."""
    db = mongo.get_db()
    query = {}

    if request.user["role"] == "doctor":
        query["doctor_id"] = request.user["user_id"]
    elif request.args.get("doctor_id"):
        query["doctor_id"] = request.args["doctor_id"]

    if request.args.get("status"):
        query["status"] = request.args["status"]

    if request.args.get("min_score"):
        query["overall_score"] = {"$gte": float(request.args["min_score"])}

    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    skip = (page - 1) * limit

    total = db.audits.count_documents(query)
    docs = list(
        db.audits.find(query).sort("audit_date", -1).skip(skip).limit(limit)
    )
    return ok({
        "audits": serialize_doc(docs),
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    })


@audits_bp.route("/<audit_id>", methods=["GET"])
@token_required
def get_audit(audit_id):
    """Get a single audit with its violations and improvement suggestions."""
    db = mongo.get_db()
    audit = db.audits.find_one({"_id": ObjectId(audit_id)})
    if not audit:
        return error("Audit not found", 404)

    violations = list(db.violations.find({"audit_id": str(audit["_id"])}))
    improvements = list(db.improvements.find({"audit_id": str(audit["_id"])}))

    result = serialize_doc(audit)
    result["violations"] = serialize_doc(violations)
    result["improvements"] = serialize_doc(improvements)
    return ok(result)


@audits_bp.route("/prescription/<prescription_id>", methods=["GET"])
@token_required
def get_audits_for_prescription(prescription_id):
    """Get all audits for a specific prescription (history)."""
    db = mongo.get_db()
    docs = list(
        db.audits.find({"prescription_id": prescription_id}).sort("audit_date", -1)
    )
    return ok(serialize_doc(docs))
