"""말끔이 런처 — 폴더엔 이 exe 하나만 보이게 하는 깔끔한 입구.

켤 때마다:
1) 깃허브의 VERSION 과 로컬 app/VERSION 비교 (5초 안에 응답 없으면 그냥 통과 — 오프라인 OK)
2) 다르면 리포 main 을 통째로 받아 app/ 를 교체 (코드 정본은 깃허브)
3) app/app.py 를 실행 — 런타임(파이썬·웹뷰)은 이 exe 안에 있고, 코드만 갈아끼우는 구조라
   업데이트에 재설치가 필요 없다.

--update-only: 확인·다운로드만 하고 조용히 종료 (부팅 시 작업 스케줄러용)
"""
import ctypes
import io
import os
import shutil
import sys
import urllib.request
import zipfile

BASE = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) \
    else os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(BASE, 'app')
REPO = 'chainedcreeper/malkkeumi'
RAW_VERSION = f'https://raw.githubusercontent.com/{REPO}/main/VERSION'
ZIP_URL = f'https://codeload.github.com/{REPO}/zip/refs/heads/main'
KEEP = ('core/', 'ui/', 'app.py', 'VERSION')   # app/ 에 들어가는 것 — 코드와 화면만


def local_version():
    try:
        return open(os.path.join(APP, 'VERSION'), encoding='utf-8').read().strip()
    except OSError:
        return None


def remote_version():
    try:
        req = urllib.request.Request(RAW_VERSION, headers={'User-Agent': 'malkkeumi-launcher'})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.read().decode('utf-8').strip()
    except OSError:
        return None   # 오프라인/깃허브 장애 — 업데이트 없이 그대로 진행


def update():
    """리포 zip 을 받아 app/ 교체 — 임시 폴더에 다 풀리면 그때 바꿔치기(중간 실패에도 기존 유지)"""
    req = urllib.request.Request(ZIP_URL, headers={'User-Agent': 'malkkeumi-launcher'})
    with urllib.request.urlopen(req, timeout=60) as r:
        buf = io.BytesIO(r.read())
    tmp = APP + '_new'
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(buf) as z:
        for m in z.namelist():
            rel = m.split('/', 1)[1] if '/' in m else ''   # malkkeumi-main/ 프리픽스 제거
            if not rel or not rel.startswith(KEEP): continue
            dest = os.path.join(tmp, rel.replace('/', os.sep))
            if m.endswith('/'):
                os.makedirs(dest, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with z.open(m) as src, open(dest, 'wb') as out:
                    shutil.copyfileobj(src, out)
    old = APP + '_old'
    shutil.rmtree(old, ignore_errors=True)
    if os.path.isdir(APP): os.rename(APP, old)
    os.rename(tmp, APP)
    shutil.rmtree(old, ignore_errors=True)


def main():
    rv = remote_version()
    if rv and rv != local_version():
        try:
            update()
        except OSError:
            pass   # 받다 실패해도 기존 코드로 계속
    if '--update-only' in sys.argv:
        return
    if not os.path.isfile(os.path.join(APP, 'app.py')):
        ctypes.windll.user32.MessageBoxW(
            None, '첫 실행에는 인터넷이 필요해요 — 깃허브에서 프로그램 코드를 받아와요.\n'
                  '인터넷 연결 후 다시 실행해 주세요.', '말끔이', 0x10)
        return
    os.environ['MALKKEUMI_APP'] = APP   # core.base 가 화면(ui) 위치로 사용
    sys.path.insert(0, APP)
    import importlib
    app_mod = importlib.import_module('app')
    app_mod.main()


if __name__ == '__main__':
    main()
