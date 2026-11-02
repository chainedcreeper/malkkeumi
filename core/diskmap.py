"""디스크 지도 — "어디가 공간을 먹고 있나"를 폴더 클릭으로 파고드는 탐색.

한 번에 한 계층만 잰다(클릭한 폴더의 바로 아래 항목들) — 전체 디스크를 미리 다 재는
프로그램들과 달리 기다림이 없다. 측정은 스레드 병렬, 정션은 제외(C 드라이브 중복 방지).
아주 큰 시스템 폴더는 측정 상한에서 끊으므로 '약 ~ 이상' 근사치로 표시한다.
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from .cache_registry import dir_size
from .winpaths import is_reparse

CAP_ENTRIES = 300000   # 폴더 하나당 측정 상한 — Windows 폴더 같은 괴물에서 멈추지 않기 위함

# 진행 상황 — UI 폴링용 (malscan 과 같은 패턴)
_progress = {'running': False, 'pct': 0, 'stage': '', 'result': None}
_lock = threading.Lock()


def progress():
    with _lock:
        return dict(_progress)


def start(path):
    with _lock:
        if _progress['running']: return {'ok': False, 'error': '이미 재는 중'}
        _progress.update(running=True, pct=1, stage='폴더 목록 읽는 중', result=None)
    def run():
        try:
            res = children(path)
        except Exception as e:
            res = {'error': str(e), 'items': [], 'path': path}
        with _lock:
            _progress.update(running=False, pct=100, stage='완료', result=res)
    threading.Thread(target=run, daemon=True).start()
    return {'ok': True}


def children(path):
    """path 바로 아래 폴더/파일들의 크기 — 큰 순. capped=True 면 '약 ~ 이상'."""
    dirs, files = [], []
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        if not is_reparse(e): dirs.append(e.path)
                    else:
                        files.append({'name': e.name, 'path': e.path, 'is_dir': False, 'capped': False,
                                      'size_mb': round(e.stat().st_size / 2**20, 1)})
                except OSError: continue
    except OSError as e:
        return {'error': f'폴더를 열 수 없음: {e}', 'items': [], 'path': path}

    def measure(d):
        size = dir_size(d, limit_entries=CAP_ENTRIES)
        # 상한에서 끊겼는지는 한 번 더 세어보지 않고, 상한 근처면 근사로 표시
        return {'name': os.path.basename(d) or d, 'path': d, 'is_dir': True,
                'size_mb': round(size / 2**20, 1), 'capped': size >= CAP_ENTRIES * 4096}
    items = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(measure, d): d for d in dirs}
        for n, f in enumerate(as_completed(futs), 1):
            items.append(f.result())
            with _lock:
                if _progress['running']:
                    _progress['pct'] = int(5 + 93 * n / max(1, len(futs)))
                    _progress['stage'] = f'폴더 크기 재는 중 ({n}/{len(futs)})'
    items += files
    items.sort(key=lambda x: -x['size_mb'])
    total = sum(i['size_mb'] for i in items)
    for i in items:
        i['pct'] = round(i['size_mb'] / total * 100, 1) if total else 0
    parent = os.path.dirname(path.rstrip('\\'))
    return {'path': path, 'parent': parent if parent != path else None,
            'total_mb': round(total), 'items': items[:60]}


def roots():
    """출발점 후보 — 내 폴더와 각 드라이브"""
    out = [{'name': '내 폴더', 'path': os.path.expanduser('~')}]
    for d in 'CDEFG':
        if os.path.isdir(f'{d}:\\'): out.append({'name': f'{d}: 드라이브', 'path': f'{d}:\\'})
    return out
