"""앱별 캐시 등록부 — 이 프로그램의 심장.

구조: data/registry.json 에 {이름, 경로, 임계치MB, 마지막 청소} 레코드 목록.
- 기본 등록부(DEFAULTS): 누구나 있는 캐시(브라우저·윈도우 임시 등) — 경로가 실제로 존재하는 것만 올라간다.
- 자동 서치(discover): AppData 전체를 돌며 '캐시 폴더로 보이는' 폴더를 찾아 후보로 제안 —
  사용자가 승인한 것만 등록부에 들어간다(멋대로 등록하지 않음).
- 용량 측정은 등록/점검 때마다 다시 잰다.
"""
import json
import os
import time

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
REG_FILE = os.path.join(DATA, 'registry.json')

E = os.path.expandvars
DEFAULTS = [
    # (이름, 경로, 임계치 MB) — 캐시 '내용물'만 지워도 앱이 스스로 다시 만드는 안전한 위치만
    ('Chrome 캐시', E(r'%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cache\Cache_Data'), 1024),
    ('Chrome GPU 캐시', E(r'%LOCALAPPDATA%\Google\Chrome\User Data\Default\GPUCache'), 256),
    ('Edge 캐시', E(r'%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cache\Cache_Data'), 1024),
    ('웨일 캐시', E(r'%LOCALAPPDATA%\Naver\Naver Whale\User Data\Default\Cache\Cache_Data'), 1024),
    ('Discord 캐시', E(r'%APPDATA%\discord\Cache\Cache_Data'), 512),
    ('윈도우 임시 파일', E(r'%TEMP%'), 2048),
    ('NVIDIA 셰이더 캐시', E(r'%LOCALAPPDATA%\NVIDIA\DXCache'), 1024),
    ('Steam 셰이더 캐시', r'C:\Program Files (x86)\Steam\steamapps\shadercache', 4096),
    ('윈도우 썸네일 캐시', E(r'%LOCALAPPDATA%\Microsoft\Windows\Explorer'), 1024),
]

# 자동 서치가 '캐시 폴더'로 인정하는 폴더 이름 (소문자 비교)
CACHE_NAMES = {'cache', 'caches', 'cache_data', 'gpucache', 'code cache', 'cachestorage',
               'cacheddata', 'cachedfiles', 'shadercache', 'dxcache', 'glcache',
               'temp', 'tmp', 'webcache', 'mediacache'}
# 파고들 루트 — 사용자 영역만(프로그램 설치 폴더·시스템 폴더는 건드리지 않음)
SEARCH_ROOTS = [E(r'%LOCALAPPDATA%'), E(r'%APPDATA%'),
                E(r'%USERPROFILE%\AppData\LocalLow')]
SKIP_DIRS = {'microsoft', 'packages', 'windowsapps'}   # 시스템성 영역 — 1단계에선 안 파고듦(기본 등록부가 커버)


def dir_size(path, limit_entries=400000):
    """폴더 용량(byte). scandir 재귀 — 너무 큰 폴더는 limit에서 끊고 그때까지의 합을 돌려준다."""
    total, stack, seen = 0, [path], 0
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    seen += 1
                    if seen > limit_entries: return total
                    try:
                        if e.is_file(follow_symlinks=False): total += e.stat().st_size
                        elif e.is_dir(follow_symlinks=False): stack.append(e.path)
                    except OSError: continue
        except OSError: continue
    return total


def load():
    """등록부 읽기 — 없으면 기본 등록부 중 실존 경로로 초기화"""
    if os.path.exists(REG_FILE):
        with open(REG_FILE, encoding='utf-8') as f: return json.load(f)
    reg = [{'name': n, 'path': p, 'limit_mb': lim, 'last_clean': None}
           for n, p, lim in DEFAULTS if os.path.isdir(p)]
    save(reg)
    return reg


def save(reg):
    os.makedirs(DATA, exist_ok=True)
    with open(REG_FILE, 'w', encoding='utf-8') as f: json.dump(reg, f, ensure_ascii=False, indent=1)


def check(reg):
    """등록된 앱마다 현재 캐시 용량을 재서 상태를 돌려준다 (over = 임계치 초과).
    용량 측정은 디스크 대기가 대부분이라 스레드로 병렬 — 10GB짜리 폴더가 있어도 전체가 그만큼만 걸린다."""
    from concurrent.futures import ThreadPoolExecutor
    def one(r):
        exists = os.path.isdir(r['path'])
        mb = round(dir_size(r['path']) / 2**20) if exists else 0
        return {**r, 'size_mb': mb, 'over': mb >= r['limit_mb'], 'exists': exists}
    with ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(one, reg))


def discover(reg, max_depth=4, min_mb=30):
    """자동 서치 — AppData 를 돌며 캐시형 폴더 이름을 찾고, 이미 등록된 경로·min_mb 미만은 걸러서
    [{앱 이름(부모 폴더로 추정), 경로, 용량}] 후보를 돌려준다. 등록은 사용자가 승인해야 한다."""
    known = {os.path.normcase(r['path']) for r in reg}
    found = []
    for root in SEARCH_ROOTS:
        if not os.path.isdir(root): continue
        stack = [(root, 0)]
        while stack:
            d, depth = stack.pop()
            try:
                with os.scandir(d) as it:
                    for e in it:
                        if not e.is_dir(follow_symlinks=False): continue
                        low = e.name.lower()
                        if depth == 0 and low in SKIP_DIRS: continue
                        if low in CACHE_NAMES:
                            if os.path.normcase(e.path) in known: continue
                            mb = round(dir_size(e.path) / 2**20)
                            if mb >= min_mb:
                                # 앱 이름 추정: AppData 루트 바로 아래 폴더명 (예: ...\Local\SomeGame\cache → SomeGame)
                                rel = os.path.relpath(e.path, root).split(os.sep)
                                app = rel[0] if rel else e.name
                                found.append({'app': app, 'path': e.path, 'size_mb': mb})
                        elif depth < max_depth:
                            stack.append((e.path, depth + 1))
            except OSError: continue
    return sorted(found, key=lambda x: -x['size_mb'])


def register(reg, name, path, limit_mb=512):
    reg.append({'name': name, 'path': path, 'limit_mb': int(limit_mb), 'last_clean': None})
    save(reg)
    return reg


def mark_cleaned(reg, path):
    for r in reg:
        if os.path.normcase(r['path']) == os.path.normcase(path):
            r['last_clean'] = time.strftime('%Y-%m-%d %H:%M')
    save(reg)
