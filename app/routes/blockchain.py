from flask import Blueprint, jsonify, render_template

from app import db
from app.models.block import Block
from app.models.blockchain import blockchain
from app.models.copyright import Copyright
from app.services.ledger import get_blocks

bp = Blueprint('blockchain', __name__, url_prefix='/blockchain')


def sync_blockchain_with_db():
    # Fabric 模式下由网关提供链数据，不执行本地同步。
    if len(blockchain.chain) > 1:
        return

    copyrights = Copyright.query.filter_by(status='confirmed').order_by(Copyright.timestamp).all()
    for item in copyrights:
        transaction = item.to_dict()
        blockchain.add_transaction(transaction)

        block = Block(
            index=len(blockchain.chain),
            transactions=blockchain.pending_transactions,
            timestamp=item.timestamp.timestamp(),
            previous_hash=blockchain.get_latest_block().hash,
        )
        block.mine_block(blockchain.difficulty)
        blockchain.chain.append(block)
        blockchain.pending_transactions = []

        item.block_hash = block.hash
        db.session.commit()


@bp.route('/explorer')
def explorer():
    sync_blockchain_with_db()
    blocks = get_blocks()
    block_cards = [
        {
            'index': block.get('index', 0),
            'hash': block.get('hash', ''),
            'previous_hash': block.get('previous_hash', ''),
            'timestamp': block.get('timestamp', 0),
            'transactions': len(block.get('transactions', [])),
        }
        for block in blocks
    ]
    return render_template('blockchain/explorer.html', blocks=block_cards)


@bp.route('/api/blocks')
def api_blocks():
    return jsonify(get_blocks())


@bp.route('/api/block/<int:index>')
def api_block(index):
    blocks = get_blocks()
    if index < 0 or index >= len(blocks):
        return jsonify({'error': '区块不存在'}), 404
    return jsonify(blocks[index])


@bp.route('/block/<int:index>')
def block_detail(index):
    blocks = get_blocks()
    if index < 0 or index >= len(blocks):
        return jsonify({'error': '区块不存在'}), 404

    block = blocks[index]
    block_data = {
        'index': block.get('index', 0),
        'hash': block.get('hash', ''),
        'previous_hash': block.get('previous_hash', ''),
        'timestamp': block.get('timestamp', 0),
        'transactions': block.get('transactions', []),
    }
    return render_template('blockchain/block_detail.html', block=block_data)
