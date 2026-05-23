import json
import threading
from flask import request, jsonify
from api import blueprint
from auth import login_required
from models import db
from models.push import PushSubscription
from models.school import School
from sqlalchemy.orm.attributes import flag_modified


def _ensure_vapid_keys():
    school = School.query.first()
    if not school:
        return None, None
    settings = dict(school.settings or {})
    if not settings.get('vapid_private_key') or not settings.get('vapid_public_key'):
        from py_vapid import Vapid
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PrivateFormat, NoEncryption,
        )
        v = Vapid()
        v.generate_keys()
        settings['vapid_private_key'] = v.private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        ).decode()
        settings['vapid_public_key'] = v.public_key_urlsafe_base64
        school.settings = settings
        flag_modified(school, 'settings')
        db.session.commit()
    return settings['vapid_private_key'], settings['vapid_public_key']


def send_web_push(app, user_id, title, body, url='/'):
    """Fire-and-forget web push to all subscriptions for a user."""
    def _send():
        with app.app_context():
            try:
                from pywebpush import webpush, WebPushException
                private_key, _ = _ensure_vapid_keys()
                if not private_key:
                    return
                subs = PushSubscription.query.filter_by(user_id=user_id).all()
                stale = []
                for sub in subs:
                    try:
                        webpush(
                            subscription_info={
                                'endpoint': sub.endpoint,
                                'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                            },
                            data=json.dumps({'title': title, 'body': body, 'url': url}),
                            vapid_private_key=private_key,
                            vapid_claims={'sub': 'mailto:armu@armu.school'},
                            ttl=86400,
                        )
                    except WebPushException as ex:
                        if ex.response and ex.response.status_code in (404, 410):
                            stale.append(sub.id)
                    except Exception:
                        pass
                if stale:
                    PushSubscription.query.filter(
                        PushSubscription.id.in_(stale)
                    ).delete(synchronize_session=False)
                    db.session.commit()
            except Exception:
                pass
    threading.Thread(target=_send, daemon=True).start()


@blueprint.route('/push/vapid-public-key', methods=['GET'])
@login_required()
def get_vapid_public_key(user):
    _, public_key = _ensure_vapid_keys()
    if not public_key:
        return jsonify({'error': 'no school configured'}), 500
    return jsonify({'public_key': public_key})


@blueprint.route('/push/subscribe', methods=['POST'])
@login_required()
def push_subscribe(user):
    data     = request.get_json(silent=True) or {}
    endpoint = data.get('endpoint', '').strip()
    keys     = data.get('keys') or {}
    p256dh   = keys.get('p256dh', '').strip()
    auth     = keys.get('auth', '').strip()
    if not endpoint or not p256dh or not auth:
        return jsonify({'error': 'invalid subscription'}), 400
    sub = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if sub:
        sub.user_id = user.id
        sub.p256dh  = p256dh
        sub.auth    = auth
    else:
        sub = PushSubscription(
            user_id=user.id, endpoint=endpoint, p256dh=p256dh, auth=auth,
        )
        db.session.add(sub)
    db.session.commit()
    return jsonify({'ok': True}), 201


@blueprint.route('/push/unsubscribe', methods=['POST'])
@login_required()
def push_unsubscribe(user):
    data     = request.get_json(silent=True) or {}
    endpoint = data.get('endpoint', '').strip()
    if endpoint:
        PushSubscription.query.filter_by(user_id=user.id, endpoint=endpoint).delete()
    else:
        PushSubscription.query.filter_by(user_id=user.id).delete()
    db.session.commit()
    return jsonify({'ok': True})
