from datetime import datetime
import hashlib
import os

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import db
from app.models.copyright import Copyright
from app.models.reference import CopyrightReference
from app.services.ledger import commit_transactions

bp = Blueprint('copyright', __name__)


def allowed_file(filename):
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def ensure_upload_folder():
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    return upload_folder


def parse_reference_ids(raw_reference_ids):
    if not raw_reference_ids:
        return []

    parts = [item.strip() for item in raw_reference_ids.split(',')]
    ids = []
    for item in parts:
        if not item:
            continue
        if not item.isdigit():
            raise ValueError(f'引用ID格式错误: {item}')
        ids.append(int(item))
    return list(dict.fromkeys(ids))


def build_trace(copyright_id, max_depth=8):
    nodes = {}
    edges = []
    upstream = []
    downstream = []

    root = Copyright.query.get(copyright_id)
    if not root:
        return None

    nodes[root.id] = {'id': root.id, 'title': root.title}

    queue = [(copyright_id, 0)]
    visited = {copyright_id}
    while queue:
        current_id, depth = queue.pop(0)
        if depth >= max_depth:
            continue

        refs = CopyrightReference.query.filter_by(source_id=current_id).all()
        for ref in refs:
            target = Copyright.query.get(ref.target_id)
            if not target:
                continue

            nodes[target.id] = {'id': target.id, 'title': target.title}
            upstream.append(
                {
                    'source_id': ref.source_id,
                    'target_id': ref.target_id,
                    'target_title': target.title,
                    'block_hash': ref.block_hash,
                    'created_at': ref.created_at.timestamp(),
                }
            )
            edges.append({'source': ref.source_id, 'target': ref.target_id, 'direction': 'upstream'})
            if target.id not in visited:
                visited.add(target.id)
                queue.append((target.id, depth + 1))

    queue = [(copyright_id, 0)]
    visited = {copyright_id}
    while queue:
        current_id, depth = queue.pop(0)
        if depth >= max_depth:
            continue

        refs = CopyrightReference.query.filter_by(target_id=current_id).all()
        for ref in refs:
            source = Copyright.query.get(ref.source_id)
            if not source:
                continue

            nodes[source.id] = {'id': source.id, 'title': source.title}
            downstream.append(
                {
                    'source_id': ref.source_id,
                    'source_title': source.title,
                    'target_id': ref.target_id,
                    'block_hash': ref.block_hash,
                    'created_at': ref.created_at.timestamp(),
                }
            )
            edges.append({'source': ref.source_id, 'target': ref.target_id, 'direction': 'downstream'})
            if source.id not in visited:
                visited.add(source.id)
                queue.append((source.id, depth + 1))

    return {
        'root': {'id': root.id, 'title': root.title},
        'nodes': list(nodes.values()),
        'edges': edges,
        'upstream': upstream,
        'downstream': downstream,
        'max_depth': max_depth,
    }


@bp.route('/')
def index():
    copyrights = Copyright.query.order_by(Copyright.timestamp.desc()).all()
    return render_template('copyright/index.html', copyrights=copyrights)


@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': '没有上传文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '未选择文件'}), 400

        if not file or not allowed_file(file.filename):
            return jsonify({'error': '不支持的文件类型'}), 400

        try:
            upload_folder = ensure_upload_folder()
            filename = secure_filename(file.filename)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)

            with open(file_path, 'rb') as f:
                content = f.read()
                content_hash = hashlib.sha256(content).hexdigest()

            reference_ids = parse_reference_ids(request.form.get('reference_ids', ''))

            copyright_record = Copyright(
                title=request.form['title'],
                description=request.form['description'],
                content_hash=content_hash,
                user_id=current_user.id,
                timestamp=datetime.utcnow(),
            )

            db.session.add(copyright_record)
            db.session.flush()

            if copyright_record.id in reference_ids:
                return jsonify({'error': '不允许引用自己'}), 400

            if reference_ids:
                existing_targets = Copyright.query.filter(Copyright.id.in_(reference_ids)).all()
                existing_target_ids = {item.id for item in existing_targets}
                missing_ids = [str(ref_id) for ref_id in reference_ids if ref_id not in existing_target_ids]
                if missing_ids:
                    return jsonify({'error': f'无效的引用ID: {",".join(missing_ids)}'}), 400

            transactions = [copyright_record.to_dict()]

            pending_reference_records = []
            for target_id in reference_ids:
                evidence_seed = f'{content_hash}:{copyright_record.id}:{target_id}'
                evidence_hash = hashlib.sha256(evidence_seed.encode('utf-8')).hexdigest()
                relation = CopyrightReference(
                    source_id=copyright_record.id,
                    target_id=target_id,
                    relation_type='quote',
                    evidence_hash=evidence_hash,
                )
                db.session.add(relation)
                pending_reference_records.append(relation)

                transactions.append(
                    {
                        'type': 'copyright_reference',
                        'source_id': copyright_record.id,
                        'target_id': target_id,
                        'evidence_hash': evidence_hash,
                        'timestamp': datetime.utcnow().timestamp(),
                    }
                )

            block = commit_transactions(transactions, current_user.username)
            copyright_record.block_hash = block['hash']
            copyright_record.status = 'confirmed'
            for relation in pending_reference_records:
                relation.block_hash = block['hash']

            db.session.commit()
            return jsonify(
                {
                    'success': True,
                    'copyright_id': copyright_record.id,
                    'references_created': len(pending_reference_records),
                    'message': '上传成功',
                }
            )
        except ValueError as ex:
            db.session.rollback()
            return jsonify({'error': str(ex)}), 400
        except Exception as ex:
            db.session.rollback()
            current_app.logger.error(f'Upload error: {str(ex)}')
            return jsonify({'error': f'上传失败: {str(ex)}'}), 500

    latest_copyrights = Copyright.query.order_by(Copyright.timestamp.desc()).limit(20).all()
    return render_template('copyright/upload.html', latest_copyrights=latest_copyrights)


@bp.route('/search')
def search():
    query = request.args.get('q', '')
    copyrights = Copyright.query.filter(Copyright.title.contains(query) | Copyright.description.contains(query)).all()
    return render_template('copyright/search.html', copyrights=copyrights)


@bp.route('/copyright/<int:id>')
def detail(id):
    copyright_record = Copyright.query.get_or_404(id)
    outgoing_refs = CopyrightReference.query.filter_by(source_id=id).order_by(CopyrightReference.created_at.desc()).all()
    incoming_refs = CopyrightReference.query.filter_by(target_id=id).order_by(CopyrightReference.created_at.desc()).all()

    target_map = {}
    if outgoing_refs:
        target_ids = [ref.target_id for ref in outgoing_refs]
        target_map = {row.id: row for row in Copyright.query.filter(Copyright.id.in_(target_ids)).all()}

    source_map = {}
    if incoming_refs:
        source_ids = [ref.source_id for ref in incoming_refs]
        source_map = {row.id: row for row in Copyright.query.filter(Copyright.id.in_(source_ids)).all()}

    return render_template(
        'copyright/detail.html',
        copyright=copyright_record,
        outgoing_refs=outgoing_refs,
        incoming_refs=incoming_refs,
        target_map=target_map,
        source_map=source_map,
    )


@bp.route('/api/verify/<content_hash>')
def verify(content_hash):
    copyright_record = Copyright.query.filter_by(content_hash=content_hash).first()
    if copyright_record:
        return jsonify(copyright_record.to_dict())
    return jsonify({'error': '未找到匹配的版权信息'}), 404


@bp.route('/api/trace/<int:copyright_id>')
def trace(copyright_id):
    trace_data = build_trace(copyright_id)
    if not trace_data:
        return jsonify({'error': '版权记录不存在'}), 404
    return jsonify(trace_data)


@bp.route('/trace/<int:copyright_id>/graph')
def trace_graph(copyright_id):
    copyright_record = Copyright.query.get_or_404(copyright_id)
    return render_template('copyright/trace_graph.html', copyright=copyright_record)
