import os
import sys
import subprocess
import threading
import requests as _requests
from flask import jsonify
from api import blueprint
from auth import login_required

_REPO_ROOT  = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_VERSION_FILE = os.path.join(_REPO_ROOT, 'VERSION')
_REMOTE_VERSION_URL = 'https://raw.githubusercontent.com/Armoji-code/armu-edu/main/VERSION'


def _local_version():
    try:
        return open(_VERSION_FILE).read().strip()
    except OSError:
        return 'unknown'


@blueprint.route('/admin/update/check', methods=['GET'])
@login_required(roles=['admin'])
def update_check(user):
    local = _local_version()
    try:
        r = _requests.get(_REMOTE_VERSION_URL, timeout=5)
        r.raise_for_status()
        remote = r.text.strip()
    except Exception as e:
        return jsonify({'error': f'Could not reach GitHub: {e}', 'local': local}), 502

    def _ver(v):
        try:
            return tuple(int(x) for x in v.lstrip('v').split('.'))
        except ValueError:
            return (0,)

    update_available = _ver(remote) > _ver(local)
    return jsonify({'local': local, 'remote': remote, 'update_available': update_available})


@blueprint.route('/admin/update/apply', methods=['POST'])
@login_required(roles=['admin'])
def update_apply(user):
    req_file = os.path.join(_REPO_ROOT, 'requirements.txt')
    venv_pip = os.path.join(_REPO_ROOT, '.venv', 'bin', 'pip')
    pip_cmd  = venv_pip if os.path.exists(venv_pip) else sys.executable.replace('python', 'pip')

    steps = [
        (['git', '-C', _REPO_ROOT, 'pull', '--ff-only'], 'git pull'),
        ([pip_cmd, 'install', '-q', '-r', req_file],       'pip install'),
        ([sys.executable, '-m', 'flask', '--app', 'app', 'db', 'upgrade'], 'db migrate'),
    ]

    log = []
    for cmd, label in steps:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True,
                cwd=os.path.join(_REPO_ROOT, 'backend'),
                timeout=120,
            )
            out = (result.stdout + result.stderr).strip()
            if result.returncode != 0:
                log.append(f'[{label}] FAILED\n{out}')
                return jsonify({'ok': False, 'log': '\n'.join(log)}), 500
            log.append(f'[{label}] ok\n{out}' if out else f'[{label}] ok')
        except subprocess.TimeoutExpired:
            log.append(f'[{label}] TIMEOUT')
            return jsonify({'ok': False, 'log': '\n'.join(log)}), 500

    def _restart():
        import time
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=_restart, daemon=True).start()
    log.append('[restart] restarting server…')
    return jsonify({'ok': True, 'log': '\n'.join(log)})
