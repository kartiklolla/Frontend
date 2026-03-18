"""
Automated Prescription Audit System - Backend
Module 24: DBMS Course Project

Entities: PrescriptionAudit, QualityMetric, Violation, Improvement
Audit Areas: Completeness, Legibility, Appropriateness, Safety
"""

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

from db import mongo
from prescriptions import prescriptions_bp
from audits import audits_bp
from violations import violations_bp
from improvements import improvements_bp
from quality_metrics import quality_metrics_bp
from reports import reports_bp
from guidelines import guidelines_bp
from auth import auth_bp

load_dotenv()


def create_app():
    app = Flask(__name__)
    CORS(app)

    app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    app.config["DB_NAME"] = os.getenv("DB_NAME", "prescription_audit_db")
    app.config["JWT_SECRET"] = os.getenv("JWT_SECRET", "change-this-secret")

    # Initialize MongoDB connection
    mongo.init_app(app)

    # Register blueprints (API route groups)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(prescriptions_bp, url_prefix="/api/prescriptions")
    app.register_blueprint(audits_bp, url_prefix="/api/audits")
    app.register_blueprint(violations_bp, url_prefix="/api/violations")
    app.register_blueprint(improvements_bp, url_prefix="/api/improvements")
    app.register_blueprint(quality_metrics_bp, url_prefix="/api/quality-metrics")
    app.register_blueprint(reports_bp, url_prefix="/api/reports")
    app.register_blueprint(guidelines_bp, url_prefix="/api/guidelines")

    # Health check
    @app.route("/api/health", methods=["GET"])
    def health():
        return {"status": "ok", "message": "Prescription Audit System is running"}

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, port=port)
