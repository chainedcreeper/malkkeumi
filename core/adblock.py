"""hosts 광고 차단 — 시스템 전체 광고 서버 차단의 적용/해제.

원리: C:\\Windows\\System32\\drivers\\etc\\hosts 는 DNS보다 먼저 조회되는 로컬 매핑이라,
광고 도메인을 0.0.0.0 으로 적으면 모든 프로그램에서 그 서버 접속이 연결 단계에서 실패한다.

안전 규칙:
- 적용 전 원본을 data/hosts.backup.<시각> 으로 백업 (최초 1회는 영구 보관본도)
- 우리 블록은 마커 주석(BEGIN/END 말끔이) 사이에만 쓴다 — 해제는 그 구간만 제거, 사용자의 기존 내용은 절대 건드리지 않음
- 관리자 권한이 없으면 아무것도 쓰지 않고 그 사실을 알린다
"""
import ctypes
import os
import shutil
import time
import urllib.request

HOSTS = r'C:\Windows\System32\drivers\etc\hosts'
MARK_BEGIN = '# ===== BEGIN 말끔이 광고 차단 ====='
MARK_END = '# ===== END 말끔이 광고 차단 ====='
LIST_URL = 'https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts'   # 광고+악성 통합(중복 제거) 목록
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def status():
    try:
        txt = open(HOSTS, encoding='utf-8', errors='replace').read()
    except OSError:
        return {'applied': False, 'lines': 0, 'admin': is_admin(), 'error': 'hosts 파일을 읽을 수 없음'}
    applied = MARK_BEGIN in txt
    lines = 0
    if applied:
        block = txt.split(MARK_BEGIN, 1)[1].split(MARK_END, 1)[0]
        lines = sum(1 for ln in block.splitlines() if ln.strip().startswith('0.0.0.0'))
    return {'applied': applied, 'lines': lines, 'admin': is_admin()}


def _download_list():
    """StevenBlack 목록에서 0.0.0.0 차단 줄만 추린다 (localhost 류 기본 줄은 제외)"""
    os.makedirs(DATA, exist_ok=True)
    cache = os.path.join(DATA, 'blocklist.txt')
    req = urllib.request.Request(LIST_URL, headers={'User-Agent': 'malkkeumi/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode('utf-8', errors='replace')
    lines = [ln for ln in raw.splitlines()
             if ln.startswith('0.0.0.0 ') and not ln.startswith('0.0.0.0 0.0.0.0')]
    with open(cache, 'w', encoding='utf-8') as f: f.write('\n'.join(lines))
    return lines


def _backup(txt):
    os.makedirs(DATA, exist_ok=True)
    first = os.path.join(DATA, 'hosts.backup.original')
    if not os.path.exists(first):
        with open(first, 'w', encoding='utf-8') as f: f.write(txt)
    stamp = os.path.join(DATA, f'hosts.backup.{time.strftime("%Y%m%d-%H%M%S")}')
    with open(stamp, 'w', encoding='utf-8') as f: f.write(txt)
    return stamp


def apply():
    """차단 적용 — 기존 말끔이 구간이 있으면 갈아끼운다"""
    if not is_admin():
        return {'ok': False, 'error': '관리자 권한이 필요해요 — 프로그램을 「관리자 권한으로 실행」해 주세요.'}
    try:
        blocked = _download_list()
    except OSError as e:
        return {'ok': False, 'error': f'차단 목록 다운로드 실패: {e}'}
    txt = open(HOSTS, encoding='utf-8', errors='replace').read()
    _backup(txt)
    base = _strip_block(txt)
    block = '\n'.join([MARK_BEGIN,
                       f'# StevenBlack 통합 목록, 적용 {time.strftime("%Y-%m-%d %H:%M")} · 해제는 말끔이에서 원클릭',
                       *blocked, MARK_END])
    new = base.rstrip('\n') + '\n\n' + block + '\n'
    try:
        with open(HOSTS, 'w', encoding='utf-8') as f: f.write(new)
    except OSError as e:
        return {'ok': False, 'error': f'hosts 쓰기 실패: {e}'}
    _flush_dns()
    return {'ok': True, 'lines': len(blocked)}


def restore():
    """말끔이 구간만 제거 — 사용자의 기존 hosts 내용은 그대로"""
    if not is_admin():
        return {'ok': False, 'error': '관리자 권한이 필요해요 — 프로그램을 「관리자 권한으로 실행」해 주세요.'}
    txt = open(HOSTS, encoding='utf-8', errors='replace').read()
    if MARK_BEGIN not in txt:
        return {'ok': True, 'lines': 0, 'note': '적용된 차단이 없음'}
    _backup(txt)
    try:
        with open(HOSTS, 'w', encoding='utf-8') as f: f.write(_strip_block(txt))
    except OSError as e:
        return {'ok': False, 'error': f'hosts 쓰기 실패: {e}'}
    _flush_dns()
    return {'ok': True}


def _strip_block(txt):
    if MARK_BEGIN not in txt: return txt
    head, rest = txt.split(MARK_BEGIN, 1)
    tail = rest.split(MARK_END, 1)[1] if MARK_END in rest else ''
    return head.rstrip('\n') + '\n' + tail.lstrip('\n')


def _flush_dns():
    import subprocess
    try: subprocess.run(['ipconfig', '/flushdns'], capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError): pass
