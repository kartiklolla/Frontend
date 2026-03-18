"""
Improvements routes — view and update improvement suggestions.
Maps to DFD Process 6: Generate Improvement Suggestions → Improvement DB.
"""

from flask import Blueprint, request
from bson import ObjectId

from db import mongo
from utils import ok, error, serialize_doc, token_required, now

improvements_bp = Blueprint("improvements", __name__)


@improvements_bp.route("/", methods=["GET"])
@token_required
def list_improvements():
    """List improvement suggestions for a doctor."""
    db = mongo.get_db()
    query = {}

    if request.user["role"] == "doctor":
        query["doctor_id"] = request.user["user_id"]
    elif request.args.get("doctor_id"):
        query["doctor_id"] = request.args["doctor_id"]

    if request.args.get("status"):
        query["status"] = request.args["status"]
    if request.args.get("priority"):
        query["priority"] = request.args["priority"]

    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    skip = (page - 1) * limit

    total = db.improvements.count_documents(query)
    docs = list(
        db.improvements.find(query).sort("created_at", -1).skip(skip).limit(limit)
    )
    return ok({
        "improvements": serialize_doc(docs),
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    })


@improvements_bp.route("/<improvement_id>", methods=["GET"])
@token_required
def get_improvement(improvement_id):
    db = mongo.get_db()
    doc = db.improvements.find_one({"_id": ObjectId(improvement_id)})
    if not doc:
        return error("Improvement not found", 404)
    return ok(serialize_doc(doc))


@improvements_bp.route("/<improvement_id>/status", methods=["PATCH"])
@token_required
def update_status(improvement_id):
    """Update the status of an improvement (pending → acknowledged → resolved)."""
    data = request.get_json()
    new_status = data.get("status")
    if new_status not in ("pending", "acknowledged", "resolved"):
        return error("Status must be: pending, acknowledged, or resolved")

    db = mongo.get_db()
    result = db.improvements.update_one(
        {"_id": ObjectId(improvement_id)},
        {"$set": {"status": new_status, "updated_at": now()}},
    )
    if result.matched_count == 0:
        return error("Improvement not found", 404)

    doc = db.improvements.find_one({"_id": ObjectId(improvement_id)})
    return ok(serialize_doc(doc), "Status updated")
