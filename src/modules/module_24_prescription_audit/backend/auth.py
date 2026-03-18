"""
Auth routes: register, login, get profile.
Roles: doctor, admin, hospital_staff
"""

from flask import Blueprint, request
from bson import ObjectId
import bcrypt
import jwt
import os
from datetime import datetime, timezone, timedelta

from db import mongo
from utils import ok, error, serialize_doc, token_required, now

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user (doctor / admin / hospital_staff)."""
    data = request.get_json()
    required = ["name", "email", "password", "role"]
    for field in required:
        if field not in data:
            return error(f"Missing field: {field}")

    if data["role"] not in ("doctor", "admin", "hospital_staff"):
        return error("Role must be doctor, admin, or hospital_staff")

    db = mongo.get_db()
    if db.users.find_one({"email": data["email"]}):
        return error("Email already registered", 409)

    hashed = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt())
    user = {
        "name": data["name"],
        "email": data["email"],
        "password_hash": hashed.decode(),
        "role": data["role"],
        "created_at": now(),
    }
    result = db.users.insert_one(user)
    user["_id"] = result.inserted_id
    user.pop("password_hash")
    return ok(serialize_doc(user), "User registered successfully", 201)


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login and receive a JWT token."""
    data = request.get_json()
    if not data or "email" not in data or "password" not in data:
        return error("Email and password are required")

    db = mongo.get_db()
    user = db.users.find_one({"email": data["email"]})
    if not user:
        return error("Invalid credentials", 401)

    if not bcrypt.checkpw(data["password"].encode(), user["password_hash"].encode()):
        return error("Invalid credentials", 401)

    secret = os.getenv("JWT_SECRET", "change-this-secret")
    token = jwt.encode(
        {
            "user_id": str(user["_id"]),
            "email": user["email"],
            "role": user["role"],
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
        },
        secret,
        algorithm="HS256",
    )
    return ok({"token": token, "role": user["role"], "name": user["name"]}, "Login successful")


@auth_bp.route("/profile", methods=["GET"])
@token_required
def profile():
    """Get the logged-in user's profile."""
    db = mongo.get_db()
    user = db.users.find_one({"_id": ObjectId(request.user["user_id"])}, {"password_hash": 0})
    if not user:
        return error("User not found", 404)
    return ok(serialize_doc(user))
