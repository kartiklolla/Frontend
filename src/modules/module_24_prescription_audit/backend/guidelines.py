"""
Clinical Guidelines routes — manage the rules that audits are scored against.
Maps to DFD Process 5: Score Guideline Adherence (Admin → Clinical Guidelines / Audit Rules).
"""

from flask import Blueprint, request
from bson import ObjectId

from db import mongo
from utils import ok, error, serialize_doc, token_required, now

guidelines_bp = Blueprint("guidelines", __name__)


@guidelines_bp.route("/", methods=["POST"])
@token_required
def create_guideline():
    """Create a new clinical guideline (admin only)."""
    if request.user["role"] != "admin":
        return error("Admin access required", 403)

    data = request.get_json()
    required = ["name", "category", "rules"]
    for f in required:
        if f not in data:
            return error(f"Missing field: {f}")

    guideline = {
        "name": data["name"],
        "category": data["category"],
        "drug_name": data.get("drug_name", ""),
        "rules": data["rules"],
        "is_active": data.get("is_active", True),
        "created_at": now(),
        "updated_at": now(),
    }

    db = mongo.get_db()
    result = db.clinical_guidelines.insert_one(guideline)
    guideline["_id"] = result.inserted_id
    return ok(serialize_doc(guideline), "Guideline created", 201)


@guidelines_bp.route("/", methods=["GET"])
@token_required
def list_guidelines():
    """List all active clinical guidelines."""
    db = mongo.get_db()
    query = {"is_active": True}

    if request.args.get("category"):
        query["category"] = request.args["category"]
    if request.args.get("drug_name"):
        query["drug_name"] = {"$regex": request.args["drug_name"], "$options": "i"}

    docs = list(db.clinical_guidelines.find(query).sort("name", 1))
    return ok(serialize_doc(docs))


@guidelines_bp.route("/<guideline_id>", methods=["GET"])
@token_required
def get_guideline(guideline_id):
    db = mongo.get_db()
    doc = db.clinical_guidelines.find_one({"_id": ObjectId(guideline_id)})
    if not doc:
        return error("Guideline not found", 404)
    return ok(serialize_doc(doc))


@guidelines_bp.route("/<guideline_id>", methods=["PUT"])
@token_required
def update_guideline(guideline_id):
    if request.user["role"] != "admin":
        return error("Admin access required", 403)

    db = mongo.get_db()
    data = request.get_json()
    data["updated_at"] = now()
    data.pop("_id", None)

    result = db.clinical_guidelines.update_one(
        {"_id": ObjectId(guideline_id)}, {"$set": data}
    )
    if result.matched_count == 0:
        return error("Guideline not found", 404)

    doc = db.clinical_guidelines.find_one({"_id": ObjectId(guideline_id)})
    return ok(serialize_doc(doc), "Guideline updated")


@guidelines_bp.route("/<guideline_id>", methods=["DELETE"])
@token_required
def delete_guideline(guideline_id):
    """Soft-delete: deactivate a guideline."""
    if request.user["role"] != "admin":
        return error("Admin access required", 403)

    db = mongo.get_db()
    result = db.clinical_guidelines.update_one(
        {"_id": ObjectId(guideline_id)},
        {"$set": {"is_active": False, "updated_at": now()}},
    )
    if result.matched_count == 0:
        return error("Guideline not found", 404)
    return ok(message="Guideline deactivated")
