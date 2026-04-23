from datetime import datetime

from app import db
from app.services.ledger import commit_transactions


class CopyrightContract(db.Model):
    __tablename__ = 'copyright_contract'

    id = db.Column(db.Integer, primary_key=True)
    copyright_id = db.Column(db.Integer, db.ForeignKey('copyright.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transferee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    copyright = db.relationship('Copyright', backref='transfer_contracts')
    owner = db.relationship('User', foreign_keys=[owner_id], backref='transfer_out_contracts')
    transferee = db.relationship('User', foreign_keys=[transferee_id], backref='transfer_in_contracts')

    def confirm_transfer(self):
        if self.status != 'pending':
            return False, '合约状态无效'

        self.copyright.user_id = self.transferee_id
        self.status = 'confirmed'

        transfer_data = {
            'type': 'copyright_transfer',
            'copyright_id': self.copyright_id,
            'from_user': self.owner.username,
            'to_user': self.transferee.username,
            'timestamp': datetime.utcnow().timestamp(),
            'contract_id': self.id,
        }

        block = commit_transactions([transfer_data], self.transferee.username)
        self.block_hash = block['hash']
        return True, '版权转让成功'

    def reject_transfer(self):
        if self.status != 'pending':
            return False, '合约状态无效'

        self.status = 'rejected'
        return True, '已拒绝转让'


class ContractTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('copyright_contract.id'))
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Float)
    type = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
