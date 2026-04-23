import json
from datetime import datetime
from urllib import request, error

from flask import current_app

from app.models.blockchain import blockchain


class LocalLedgerBackend:
    name = 'local'

    def commit_transactions(self, transactions, miner):
        for tx in transactions:
            blockchain.add_transaction(tx)
        block = blockchain.mine_pending_transactions(miner)
        return {'hash': block.hash, 'index': block.index}

    def get_blocks(self):
        return [
            {
                'index': block.index,
                'hash': block.hash,
                'previous_hash': block.previous_hash,
                'timestamp': block.timestamp,
                'transactions': block.transactions,
            }
            for block in blockchain.chain
        ]


class FabricLedgerBackend:
    name = 'fabric'

    def __init__(self, gateway_url, channel, chaincode):
        self.gateway_url = gateway_url.rstrip('/')
        self.channel = channel
        self.chaincode = chaincode

    def _post_json(self, path, payload):
        req = request.Request(
            url=f'{self.gateway_url}{path}',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            return json.loads(body) if body else {}

    def _get_json(self, path):
        req = request.Request(url=f'{self.gateway_url}{path}', method='GET')
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            return json.loads(body) if body else {}

    def commit_transactions(self, transactions, miner):
        payload = {
            'channel': self.channel,
            'chaincode': self.chaincode,
            'fcn': 'BatchCommit',
            'args': [json.dumps({'miner': miner, 'transactions': transactions})],
        }
        try:
            result = self._post_json('/invoke', payload)
            return {
                'hash': result.get('block_hash') or result.get('tx_id') or f'fabric-{datetime.utcnow().timestamp()}',
                'index': result.get('block_number', 0),
            }
        except error.URLError as ex:
            raise RuntimeError(f'fabric gateway unavailable: {str(ex)}')

    def get_blocks(self):
        try:
            data = self._get_json('/blocks')
            blocks = data.get('blocks', data if isinstance(data, list) else [])
            normalized = []
            for idx, block in enumerate(blocks):
                normalized.append(
                    {
                        'index': block.get('index', idx),
                        'hash': block.get('hash', ''),
                        'previous_hash': block.get('previous_hash', ''),
                        'timestamp': block.get('timestamp', 0),
                        'transactions': block.get('transactions', []),
                    }
                )
            return normalized
        except Exception:
            return []


def get_ledger_backend():
    backend = (current_app.config.get('LEDGER_BACKEND') or 'local').lower()
    if backend == 'fabric':
        return FabricLedgerBackend(
            gateway_url=current_app.config.get('FABRIC_GATEWAY_URL', 'http://127.0.0.1:4000'),
            channel=current_app.config.get('FABRIC_CHANNEL', 'mychannel'),
            chaincode=current_app.config.get('FABRIC_CHAINCODE', 'copyright_cc'),
        )
    return LocalLedgerBackend()


def commit_transactions(transactions, miner):
    return get_ledger_backend().commit_transactions(transactions, miner)


def get_blocks():
    return get_ledger_backend().get_blocks()


def find_transactions(predicate):
    matched = []
    for block in get_blocks():
        for tx in block.get('transactions', []):
            if predicate(tx):
                matched.append({'transaction': tx, 'block_hash': block.get('hash')})
    return matched

