"""주기 청소 — 상주 프로그램 없이 윈도우 작업 스케줄러에 등록한다.

등록되는 작업: 매일 지정 시각에 `app.py --auto-clean` 실행 —
등록부에서 임계치를 넘은 캐시만 휴지통 경유로 청소하고 data/auto_clean.log 에 한 줄 남긴다.
"""
import os
import subprocess
import sys

TASK = 'Malkkeumi_AutoClean'
APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.py')


def _run(args):
    try:
        r = subprocess.run(args, capture_output=True, timeout=30)
        from .winpaths import console_decode
        return r.returncode == 0, console_decode(r.stdout + r.stderr).strip()
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


def status():
    ok, _ = _run(['schtasks', '/query', '/tn', TASK])
    return {'registered': ok}


def register(hour=21):
    """매일 hour시에 자동 청소 — pythonw(창 없음)로"""
    py = sys.executable.replace('python.exe', 'pythonw.exe')
    if not os.path.exists(py): py = sys.executable
    cmd = f'"{py}" "{APP}" --auto-clean'
    ok, msg = _run(['schtasks', '/create', '/f', '/tn', TASK, '/sc', 'daily',
                    '/st', f'{int(hour):02d}:00', '/tr', cmd])
    return {'ok': ok, 'msg': msg}


def unregister():
    ok, msg = _run(['schtasks', '/delete', '/f', '/tn', TASK])
    return {'ok': ok, 'msg': msg}
