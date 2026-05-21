import os
import pty
import fcntl
import struct
import termios
import threading
import subprocess
from flask import session, request
from app import socketio

_sessions = {}  # sid -> {'proc': Popen, 'fd': int}


def _read_loop(sid, fd):
    while True:
        try:
            data = os.read(fd, 4096)
            if not data:
                break
            socketio.emit('term_output',
                          {'data': data.decode('utf-8', errors='replace')},
                          namespace='/terminal', to=sid)
        except OSError:
            break


@socketio.on('connect', namespace='/terminal')
def term_connect():
    user_id = session.get('user_id')
    if not user_id:
        return False
    from models.user import User
    user = User.query.get(user_id)
    if not user or user.role != 'admin':
        return False

    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        ['/bin/bash', '--login'],
        stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
        close_fds=True,
        cwd=os.path.expanduser('~'),
    )
    os.close(slave_fd)

    sid = request.sid
    _sessions[sid] = {'proc': proc, 'fd': master_fd}

    t = threading.Thread(target=_read_loop, args=(sid, master_fd), daemon=True)
    t.start()


@socketio.on('term_input', namespace='/terminal')
def term_input(data):
    sid = request.sid
    if sid in _sessions:
        try:
            os.write(_sessions[sid]['fd'], data['data'].encode('utf-8', errors='replace'))
        except OSError:
            pass


@socketio.on('term_resize', namespace='/terminal')
def term_resize(data):
    sid = request.sid
    if sid in _sessions:
        try:
            cols = max(1, int(data.get('cols', 80)))
            rows = max(1, int(data.get('rows', 24)))
            fcntl.ioctl(_sessions[sid]['fd'], termios.TIOCSWINSZ,
                        struct.pack('HHHH', rows, cols, 0, 0))
        except OSError:
            pass


@socketio.on('disconnect', namespace='/terminal')
def term_disconnect():
    sid = request.sid
    if sid in _sessions:
        try:
            _sessions[sid]['proc'].kill()
        except Exception:
            pass
        try:
            os.close(_sessions[sid]['fd'])
        except Exception:
            pass
        del _sessions[sid]
