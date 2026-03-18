"""
Shared utilities: JSON serialization, auth middleware, response helpers.
"""

from functools import wraps
from datetime import datetime, timezone
from bson import ObjectId
from flask import request, jsonify
import jwt
import os


# ---------------------------------------------------------------------------
# BSON / JSON helpers
# ---------------------------------------------------------------------------

def serialize_doc(doc):
    """Convert a MongoDB document to JSON-safe dict (ObjectId -> str)."""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(d) for d in doc]
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, dict):
            out[k] = serialize_doc(v)
        elif isinstance(v, list):
            out[k] = [serialize_doc(i) if isinstance(i, dict) else str(i) if isinstance(i, ObjectId) else i for i in v]
        else:
            out[k] = v
    return out


def ok(data=None, message="Success", status=200):
    body = {"success": True, "message": message}
    if data is not None:
        body["data"] = data
    return jsonify(body), status


def error(message="Something went wrong", status=400):
    return jsonify({"success": False, "message": message}), status


def now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# JWT auth decorator
# ---------------------------------------------------------------------------

def token_required(f):
    """Decorator that checks for a valid Bearer token in the Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return error("Authorization token is missing", 401)

        try:
            secret = os.getenv("JWT_SECRET", "change-this-secret")
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            request.user = payload  # attach user info to request
        except jwt.ExpiredSignatureError:
            return error("Token has expired", 401)
        except jwt.InvalidTokenError:
            return error("Invalid token", 401)

        return f(*args, **kwargs)

    return decorated
