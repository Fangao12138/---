from datetime import datetime
from app import db


class CopyrightReference(db.Model):
    __tablename__ = 'copyright_reference'

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('copyright.id'), nullable=False, index=True)
    target_id = db.Column(db.Integer, db.ForeignKey('copyright.id'), nullable=False, index=True)
    relation_type = db.Column(db.String(32), default='quote', nullable=False)
    evidence_hash = db.Column(db.String(64))
    block_hash = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

