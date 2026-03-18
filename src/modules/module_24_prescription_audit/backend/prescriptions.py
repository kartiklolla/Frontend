"""
Prescription routes — CRUD operations.
Maps to DFD Process 1: Capture Prescription Data → Prescription DB
"""

from flask import Blueprint, request
from bson import ObjectId

from db import mongo
from utils import ok, error, serialize_doc, token_required, now

prescriptions_bp = Blueprint("prescriptions", __name__)


@prescriptions_bp.route("/", methods=["POST"])
@token_required
def create_prescription():
    """
    Create a new prescription.
    This is the entry point — 'Data Ingestion' step from the flowchart.
    """
    data = request.get_json()
    required = ["patient_name", "patient_age", "diagnosis", "medications"]
    for f in required:
        if f not in data:
            return error(f"Missing field: {f}")

    if not isinstance(data.get("medications"), list) or len(data["medications"]) == 0:
        return error("At least one medication is required")

    # Validate each medication entry
    med_fields = ["drug_name", "dosage", "frequency", "duration"]
    for i, med in enumerate(data["medications"]):
        for mf in med_fields:
            if mf not in med:
                return error(f"Medication #{i+1} is missing '{mf}'")

    prescription = {
        "doctor_id": request.user["user_id"],
        "patient_id": data.get("patient_id", ""),
        "patient_name": data["patient_name"],
        "patient_age": data["patient_age"],
        "patient_gender": data.get("patient_gender", ""),
        "diagnosis": data["diagnosis"],
        "medications": data["medications"],
        "notes": data.get("notes", ""),
        "is_legible": data.get("is_legible", True),
        "created_at": now(),
        "updated_at": now(),
    }

    db = mongo.get_db()
    result = db.prescriptions.insert_one(prescription)
    prescription["_id"] = result.inserted_id
    return ok(serialize_doc(prescription), "Prescription created", 201)


@prescriptions_bp.route("/", methods=["GET"])
@token_required
def list_prescriptions():
    """List prescriptions with optional filters: doctor_id, patient_id, date range."""
    db = mongo.get_db()
    query = {}

    # Doctors see only their own; admins see all
    if request.user["role"] == "doctor":
        query["doctor_id"] = request.user["user_id"]
    elif request.args.get("doctor_id"):
        query["doctor_id"] = request.args["doctor_id"]

    if request.args.get("patient_id"):
        query["patient_id"] = request.args["patient_id"]

    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    skip = (page - 1) * limit

    total = db.prescriptions.count_documents(query)
    docs = list(
        db.prescriptions.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return ok({
        "prescriptions": serialize_doc(docs),
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    })


@prescriptions_bp.route("/<prescription_id>", methods=["GET"])
@token_required
def get_prescription(prescription_id):
    """Get a single prescription by ID."""
    db = mongo.get_db()
    doc = db.prescriptions.find_one({"_id": ObjectId(prescription_id)})
    if not doc:
        return error("Prescription not found", 404)
    return ok(serialize_doc(doc))


@prescriptions_bp.route("/<prescription_id>", methods=["PUT"])
@token_required
def update_prescription(prescription_id):
    """Update a prescription (before audit only)."""
    db = mongo.get_db()
    data = request.get_json()
    data["updated_at"] = now()
    data.pop("_id", None)
    data.pop("doctor_id", None)  # don't allow changing ownership

    result = db.prescriptions.update_one(
        {"_id": ObjectId(prescription_id)},
        {"$set": data},
    )
    if result.matched_count == 0:
        return error("Prescription not found", 404)

    doc = db.prescriptions.find_one({"_id": ObjectId(prescription_id)})
    return ok(serialize_doc(doc), "Prescription updated")


@prescriptions_bp.route("/<prescription_id>", methods=["DELETE"])
@token_required
def delete_prescription(prescription_id):
    """Delete a prescription (admin only)."""
    if request.user["role"] != "admin":
        return error("Admin access required", 403)

    db = mongo.get_db()
    result = db.prescriptions.delete_one({"_id": ObjectId(prescription_id)})
    if result.deleted_count == 0:
        return error("Prescription not found", 404)
    return ok(message="Prescription deleted")
