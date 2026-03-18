"""
MongoDB connection manager.
Provides a singleton-like db reference used across all routes.
"""

from pymongo import MongoClient


class Mongo:
    def __init__(self):
        self.client = None
        self.db = None

    def init_app(self, app):
        uri = app.config["MONGO_URI"]
        db_name = app.config["DB_NAME"]
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

        # Create indexes for performance
        self._create_indexes()

    def _create_indexes(self):
        """Create MongoDB indexes for common query patterns."""
        # Prescriptions
        self.db.prescriptions.create_index("doctor_id")
        self.db.prescriptions.create_index("patient_id")
        self.db.prescriptions.create_index("created_at")

        # Audits
        self.db.audits.create_index("prescription_id")
        self.db.audits.create_index("audit_date")
        self.db.audits.create_index("overall_score")

        # Violations
        self.db.violations.create_index("audit_id")
        self.db.violations.create_index("metric_id")
        self.db.violations.create_index("severity")
        self.db.violations.create_index("category")

        # Quality Metrics
        self.db.quality_metrics.create_index("doctor_id")
        self.db.quality_metrics.create_index("period")

        # Improvements
        self.db.improvements.create_index("audit_id")
        self.db.improvements.create_index("violation_id")
        self.db.improvements.create_index("doctor_id")

        # Users
        self.db.users.create_index("email", unique=True)

    def get_db(self):
        return self.db


# Singleton instance
mongo = Mongo()
