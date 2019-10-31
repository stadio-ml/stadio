from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(32), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    filename = db.Column(db.String(128), nullable=False)

    def __repr__(self):
        return f"<Submission ({self.user_id}, {self.timestamp})>"

class Evaluation(db.Model):
    submission_id = db.Column(db.Integer, db.ForeignKey("submission.id"), primary_key=True)
    submission = db.relationship("Submission", backref="evaluation")
    evaluation_public = db.Column(db.Numeric, nullable=False)
    evaluation_private = db.Column(db.Numeric, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Evaluation ({self.submission_id}, pub: {self.evaluation_public}, pri: {self.evaluation_private})>"