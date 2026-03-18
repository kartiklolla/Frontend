"""
Violations routes — view and filter violations.
Maps to Violation DB in the DFD.
"""

from flask import Blueprint, request
from bson import ObjectId

from db import mongo
from utils import ok, error, serialize_doc, token_required

violations_bp = Blueprint("violations", __name__)


@violations_bp.route("/", methods=["GET"])
@token_required
def list_violations():
    """List violations with filters: category, severity, audit_id."""
    db = mongo.get_db()
    query = {}

    if request.args.get("category"):
        query["category"] = request.args["category"]
    if request.args.get("severity"):
        query["severity"] = request.args["severity"]
    if request.args.get("audit_id"):
        query["audit_id"] = request.args["audit_id"]
    if request.args.get("prescription_id"):
        query["prescription_id"] = request.args["prescription_id"]

    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))
    skip = (page - 1) * limit

    total = db.violations.count_documents(query)
    docs = list(
        db.violations.find(query).sort("created_at", -1).skip(skip).limit(limit)
    )
    return ok({
        "violations": serialize_doc(docs),
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    })


@violations_bp.route("/<violation_id>", methods=["GET"])
@token_required
def get_violation(violation_id):
    db = mongo.get_db()
    doc = db.violations.find_one({"_id": ObjectId(violation_id)})
    if not doc:
        return error("Violation not found", 404)
    return ok(serialize_doc(doc))


@violations_bp.route("/summary", methods=["GET"])
@token_required
def violation_summary():
    """
    Aggregate violations by category and severity.
    Useful for dashboard charts.
    """
    db = mongo.get_db()
    pipeline = [
        {"$group": {
            "_id": {"category": "$category", "severity": "$severity"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
    ]
    results = list(db.violations.aggregate(pipeline))
    summary = []
    for r in results:
        summary.append({
            "category": r["_id"]["category"],
            "severity": r["_id"]["severity"],
            "count": r["count"],
        })
    return ok(summary)
