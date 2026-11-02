"""청소 실행 — 절대 바로 지우지 않는다.

절차: preview(미리보기: 뭘 얼마나 지울지) → 사용자 승인 → clean(휴지통 경유 삭제).
- 폴더 자체가 아니라 '폴더 안 내용물'만 지운다 (앱이 폴더를 다시 만들 필요 없게).
- 사용 중(잠긴) 파일은 건너뛰고 결과에 집계한다 — 실행 중인 브라우저가 있어도 안전.
- 휴지통(send2trash)이 기본. '완전 삭제' 는 옵션(두 번째 확인 필요).
"""
import json
import os
import time

from .base import DATA

try:
    from send2trash import send2trash
    HAS_TRASH = True
except ImportError:
    HAS_TRASH = False


def preview(path, max_items=5000):
    """지울 대상(1단계 항목들)과 총 용량 — 이 목록을 사용자에게 보여주고 승인받는다"""
    items = []
    total = 0
    try:
        with os.scandir(path) as it:
            for e in it:
                if len(items) >= max_items: break
                try:
                    from .cache_registry import dir_size
                    size = e.stat().st_size if e.is_file(follow_symlinks=False) else dir_size(e.path)
                    items.append({'path': e.path, 'name': e.name, 'size_mb': round(size / 2**20, 1),
                                  'is_dir': e.is_dir(follow_symlinks=False)})
                    total += size
                except OSError: continue
    except OSError:
        return {'items': [], 'total_mb': 0, 'error': '폴더를 열 수 없음'}
    return {'items': sorted(items, key=lambda x: -x['size_mb'])[:200], 'count': len(items),
            'total_mb': round(total / 2**20)}


def clean(path, permanent=False):
    """path 폴더의 내용물을 휴지통으로(기본) 또는 완전 삭제(permanent). 잠긴 파일은 건너뜀.
    반환: {removed, skipped, freed_mb}"""
    removed = skipped = freed = 0
    try:
        entries = list(os.scandir(path))
    except OSError:
        return {'removed': 0, 'skipped': 0, 'freed_mb': 0, 'error': '폴더를 열 수 없음'}
    for e in entries:
        try:
            from .cache_registry import dir_size
            size = e.stat().st_size if e.is_file(follow_symlinks=False) else dir_size(e.path)
            if permanent or not HAS_TRASH:
                _rm(e.path)
            else:
                send2trash(e.path)
            removed += 1; freed += size
        except OSError:
            skipped += 1
    freed_mb = round(freed / 2**20)
    if freed_mb > 0: _log_history(path, freed_mb)
    return {'removed': removed, 'skipped': skipped, 'freed_mb': freed_mb}


def _log_history(path, freed_mb):
    """'지금까지 비운 공간' 누적 — 상태 탭의 자랑거리"""
    os.makedirs(DATA, exist_ok=True)
    hist_file = os.path.join(DATA, 'history.json')
    try:
        with open(hist_file, encoding='utf-8') as f: hist = json.load(f)
    except (OSError, json.JSONDecodeError): hist = []
    hist.append({'when': time.strftime('%Y-%m-%d %H:%M'), 'path': path, 'freed_mb': freed_mb})
    with open(hist_file, 'w', encoding='utf-8') as f: json.dump(hist, f, ensure_ascii=False, indent=1)


def _rm(p):
    if os.path.isdir(p) and not os.path.islink(p):
        for root, dirs, files in os.walk(p, topdown=False):
            for f in files:
                try: os.remove(os.path.join(root, f))
                except OSError: pass
            for d in dirs:
                try: os.rmdir(os.path.join(root, d))
                except OSError: pass
        os.rmdir(p)
    else:
        os.remove(p)
