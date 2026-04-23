from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models.copyright import Copyright
from app.models.smart_contract import CopyrightContract
from app.services.ledger import find_transactions

bp = Blueprint('contract', __name__, url_prefix='/contract')


@bp.route('/transfer/<int:copyright_id>', methods=['GET', 'POST'])
@login_required
def initiate_transfer(copyright_id):
    copyright_record = Copyright.query.get_or_404(copyright_id)

    if copyright_record.user_id != current_user.id:
        flash('你不是该版权的所有者')
        return redirect(url_for('copyright.detail', id=copyright_id))

    if request.method == 'POST':
        transferee_username = request.form['transferee']
        from app.models.user import User

        transferee = User.query.filter_by(username=transferee_username).first()
        if not transferee:
            flash('接收方用户不存在')
            return redirect(url_for('contract.initiate_transfer', copyright_id=copyright_id))

        contract = CopyrightContract(
            copyright_id=copyright_id,
            owner_id=current_user.id,
            transferee_id=transferee.id,
            status='pending',
        )

        try:
            db.session.add(contract)
            db.session.commit()
            flash('转让请求已发送')
            return redirect(url_for('copyright.detail', id=copyright_id))
        except Exception as ex:
            db.session.rollback()
            flash(f'发生错误：{str(ex)}')
            return redirect(url_for('contract.initiate_transfer', copyright_id=copyright_id))

    return render_template('contract/transfer.html', copyright=copyright_record)


@bp.route('/verify/<int:copyright_id>')
def verify_owner(copyright_id):
    copyright_record = Copyright.query.get_or_404(copyright_id)

    transfer_history = (
        db.session.query(
            CopyrightContract.id,
            CopyrightContract.created_at,
            CopyrightContract.owner_id,
            CopyrightContract.transferee_id,
        )
        .filter_by(copyright_id=copyright_id, status='confirmed')
        .order_by(CopyrightContract.created_at.desc())
        .all()
    )

    records = find_transactions(
        lambda tx: isinstance(tx, dict)
        and tx.get('type') == 'copyright_transfer'
        and tx.get('copyright_id') == copyright_id
    )
    blockchain_records = []
    for item in records:
        tx = dict(item['transaction'])
        tx['block_hash'] = item['block_hash']
        blockchain_records.append(tx)

    return render_template(
        'contract/verify.html',
        copyright=copyright_record,
        transfer_history=transfer_history,
        blockchain_records=blockchain_records,
    )


@bp.route('/confirm/<int:contract_id>', methods=['POST'])
@login_required
def confirm_transfer(contract_id):
    contract = CopyrightContract.query.get_or_404(contract_id)
    if contract.transferee_id != current_user.id:
        return jsonify({'error': '你不是该转让的接收方'}), 403

    success, message = contract.confirm_transfer()
    if success:
        db.session.commit()
        flash('版权转让已确认')
    else:
        flash(message)

    return redirect(url_for('copyright.detail', id=contract.copyright_id))


@bp.route('/pending_transfers')
@login_required
def pending_transfers():
    pending_contracts = CopyrightContract.query.filter_by(transferee_id=current_user.id, status='pending').all()
    return render_template('contract/pending_transfers.html', contracts=pending_contracts)


@bp.route('/reject/<int:contract_id>', methods=['POST'])
@login_required
def reject_transfer(contract_id):
    contract = CopyrightContract.query.get_or_404(contract_id)
    if contract.transferee_id != current_user.id:
        flash('你不是该转让的接收方')
        return redirect(url_for('contract.pending_transfers'))

    success, message = contract.reject_transfer()
    if success:
        db.session.commit()
        flash('已拒绝版权转让')
    else:
        flash(message)
    return redirect(url_for('contract.pending_transfers'))
