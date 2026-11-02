"""깃허브 연결 업데이트 — 주기적으로 새 버전을 확인하고 받아온다.

방식 두 가지를 자동 선택:
- 소스 설치(.git 폴더 있음): git pull --ff-only 로 그 자리에서 갱신
- exe 배포(.git 없음): GitHub Releases 최신 태그를 확인하고 다운로드 페이지를 열어 줌

버전 비교는 리포의 VERSION 파일(raw.githubusercontent)과 로컬 VERSION 파일.
네트워크가 없으면 조용히 '확인 불가'만 돌려준다 — 업데이트 확인이 앱을 막으면 안 된다.
"""
import os
import subprocess
import urllib.request

REPO = 'chainedcreeper/malkkeumi'   # GitHub 리포 (owner/name)
from .base import APP_DIR as HERE, LAUNCHER_APP
# 런처 구조에선 코드·VERSION 이 app/ 폴더에 있다
VERSION_FILE = os.path.join(LAUNCHER_APP or HERE, 'VERSION')
RAW_VERSION = f'https://raw.githubusercontent.com/{REPO}/main/VERSION'
RELEASES = f'https://github.com/{REPO}/releases/latest'


def local_version():
    try:
        return open(VERSION_FILE, encoding='utf-8').read().strip()
    except OSError:
        return '0.0.0'


def remote_version():
    req = urllib.request.Request(RAW_VERSION, headers={'User-Agent': 'malkkeumi'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode('utf-8').strip()


def _tuple(v):
    try: return tuple(int(x) for x in v.split('.'))
    except ValueError: return (0,)


def check():
    """{local, remote, newer(bool|None), mode} — remote=None 이면 확인 실패(오프라인 등)"""
    lv = local_version()
    mode = 'launcher' if LAUNCHER_APP else ('git' if os.path.isdir(os.path.join(HERE, '.git')) else 'exe')
    try:
        rv = remote_version()
    except OSError:
        return {'local': lv, 'remote': None, 'newer': None, 'mode': mode}
    return {'local': lv, 'remote': rv, 'newer': _tuple(rv) > _tuple(lv), 'mode': mode,
            'releases': RELEASES}


def update():
    """런처 구조: 다시 켜면 런처가 자동으로 받음. 소스 설치: git pull. exe 단독: 다운로드 페이지."""
    if LAUNCHER_APP:
        return {'ok': True, 'msg': '프로그램을 껐다 다시 켜면 자동으로 최신 버전을 받아요 — 런처가 처리해요.'}
    if not os.path.isdir(os.path.join(HERE, '.git')):
        return {'ok': False, 'open': RELEASES,
                'msg': '설치판은 최신 버전을 내려받아 바꿔 주세요 (페이지를 열어 드릴게요).'}
    try:
        r = subprocess.run(['git', '-C', HERE, 'pull', '--ff-only'],
                           capture_output=True, timeout=60)
        out = (r.stdout + r.stderr).decode('utf-8', errors='replace').strip()
        if r.returncode == 0:
            return {'ok': True, 'msg': '업데이트 완료 — 프로그램을 다시 켜면 적용돼요.', 'detail': out}
        return {'ok': False, 'msg': '업데이트 실패', 'detail': out}
    except (OSError, subprocess.SubprocessError) as e:
        return {'ok': False, 'msg': f'업데이트 실패: {e}'}
