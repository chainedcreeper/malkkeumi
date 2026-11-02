"""중복 파일 찾기 — 같은 내용의 파일이 여러 곳에 흩어진 낭비를 잡는다.

정확하면서 빠른 3단 필터:
① 크기가 같은 파일끼리만 후보 (크기가 다르면 내용이 같을 수 없다)
② 후보끼리 앞 64KB 해시 비교 (대부분 여기서 갈라진다 — 큰 파일을 통째로 읽지 않음)
③ 남은 것만 전체 SHA-256 — 여기서 같으면 진짜 중복(해시 충돌은 사실상 불가능)

대상은 사용자 콘텐츠 폴더(다운로드·바탕화면·문서·동영상·사진). 처리는 삭제가 아니라
'원본 1개만 남기고 보관함으로 분리'를 안내 — unused.separate 를 그대로 재사용한다.
"""
import hashlib
import os

from .unused import SCAN_ROOTS
from .winpaths import is_reparse


def _walk_files(min_bytes):
    for root in SCAN_ROOTS:
        if not os.path.isdir(root): continue
        stack = [root]
        while stack:
            d = stack.pop()
            try:
                with os.scandir(d) as it:
                    for e in it:
                        try:
                            if e.is_dir(follow_symlinks=False):
                                if not is_reparse(e) and not e.name.startswith('말끔이'): stack.append(e.path)
                            else:
                                st = e.stat()
                                if st.st_size >= min_bytes:
                                    yield e.path, st.st_size
                        except OSError: continue
            except OSError: continue


def _hash(path, limit=None):
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            if limit:
                h.update(f.read(limit))
            else:
                for chunk in iter(lambda: f.read(1 << 20), b''):
                    h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def find(min_mb=10, max_groups=50):
    """중복 그룹 [{size_mb, files:[경로…], wasted_mb}] — 낭비 큰 순"""
    by_size = {}
    for path, size in _walk_files(int(min_mb) * 2**20):
        by_size.setdefault(size, []).append(path)

    groups = []
    for size, paths in by_size.items():
        if len(paths) < 2: continue
        by_quick = {}   # ② 앞 64KB
        for p in paths:
            q = _hash(p, limit=65536)
            if q: by_quick.setdefault(q, []).append(p)
        for qpaths in by_quick.values():
            if len(qpaths) < 2: continue
            by_full = {}   # ③ 전체 해시
            for p in qpaths:
                f = _hash(p)
                if f: by_full.setdefault(f, []).append(p)
            for fpaths in by_full.values():
                if len(fpaths) >= 2:
                    mb = round(size / 2**20)
                    groups.append({'size_mb': mb, 'files': sorted(fpaths),
                                   'wasted_mb': mb * (len(fpaths) - 1)})
    groups.sort(key=lambda g: -g['wasted_mb'])
    return {'groups': groups[:max_groups],
            'wasted_total_mb': sum(g['wasted_mb'] for g in groups)}
