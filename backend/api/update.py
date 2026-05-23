import os
import sys
import subprocess
import threading
from flask import jsonify
from api import blueprint, err, ok
from auth import login_required

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _git(*args, **kwargs):
    return subprocess.run(
        ['git', '-C', _REPO_ROOT] + list(args),
        capture_output=True, text=True, timeout=30, **kwargs
    )


@blueprint.route('/admin/update/check', methods=['GET'])
@login_required(roles=['admin'])
def update_check(user):
    try:
        _git('fetch', 'origin')
    except Exception as e:
        return jsonify({'error': f'git fetch failed: {e}'}), 502

    local  = _git('rev-parse', '--short', 'HEAD').stdout.strip()
    remote = _git('rev-parse', '--short', 'origin/main').stdout.strip()

    log_result = _git('log', 'HEAD..origin/main', '--oneline', '--no-decorate')
    lines = [l.strip() for l in log_result.stdout.strip().splitlines() if l.strip()]

    commits = []
    for line in lines:
        parts = line.split(' ', 1)
        commits.append({'hash': parts[0], 'message': parts[1] if len(parts) > 1 else ''})

    return jsonify({
        'local': local,
        'remote': remote,
        'up_to_date': local == remote or len(commits) == 0,
        'commits_behind': len(commits),
        'commits': commits,
    })


@blueprint.route('/admin/update/apply', methods=['POST'])
@login_required(roles=['admin'])
def update_apply(user):
    req_file = os.path.join(_REPO_ROOT, 'requirements.txt')
    venv_pip = os.path.join(_REPO_ROOT, '.venv', 'bin', 'pip')
    pip_cmd  = venv_pip if os.path.exists(venv_pip) else sys.executable.replace('python', 'pip')

    steps = [
        (['git', '-C', _REPO_ROOT, 'pull', '--ff-only'],              'git pull'),
        ([pip_cmd, 'install', '-q', '-r', req_file],                   'pip install'),
        ([sys.executable, '-m', 'flask', '--app', 'app', 'db', 'upgrade'], 'db migrate'),
    ]

    log = []
    for cmd, label in steps:
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                cwd=os.path.join(_REPO_ROOT, 'backend'), timeout=120,
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
