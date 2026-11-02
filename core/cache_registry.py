"""앱별 캐시 등록부 — 이 프로그램의 심장.

구조: data/registry.json 에 {이름, 경로, 임계치MB, 마지막 청소} 레코드 목록.
- 기본 등록부(DEFAULTS): 누구나 있는 캐시(브라우저·윈도우 임시 등) — 경로가 실제로 존재하는 것만 올라간다.
- 자동 서치(discover): AppData 전체를 돌며 '캐시 폴더로 보이는' 폴더를 찾아 후보로 제안 —
  사용자가 승인한 것만 등록부에 들어간다(멋대로 등록하지 않음).
- 용량 측정은 등록/점검 때마다 다시 잰다.
"""
import glob as _glob
import json
import os
import time
import winreg

from .winpaths import is_reparse

from .base import DATA
REG_FILE = os.path.join(DATA, 'registry.json')

E = os.path.expandvars


def _steam_root():
    """Steam 설치 경로 — 레지스트리에서 읽는다 (Program Files 하드코딩은 이식성이 깨짐)"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as k:
            return winreg.QueryValueEx(k, 'SteamPath')[0].replace('/', '\\')
    except OSError:
        return r'C:\Program Files (x86)\Steam'


def _browser_profiles(user_data, label):
    """브라우저의 모든 프로필 캐시 — Default 만 쓰는 컴퓨터는 하나, 프로필 여럿이면 전부"""
    out = []
    for cd in _glob.glob(os.path.join(user_data, '*', 'Cache', 'Cache_Data')):
        prof = os.path.basename(os.path.dirname(os.path.dirname(cd)))
        tag = '' if prof == 'Default' else f' ({prof})'
        out.append((f'{label} 캐시{tag}', cd, 1024))
    return out


def defaults():
    """기본 등록부 후보 — 이 컴퓨터에 실존하는 것만 쓰인다. 캐시 '내용물'만 지워도 앱이 다시 만드는 안전한 위치만."""
    items = []
    for label, ud in (('Chrome', E(r'%LOCALAPPDATA%\Google\Chrome\User Data')),
                      ('Edge', E(r'%LOCALAPPDATA%\Microsoft\Edge\User Data')),
                      ('웨일', E(r'%LOCALAPPDATA%\Naver\Naver Whale\User Data'))):
        items += _browser_profiles(ud, label)
    items += [
        ('Discord 캐시', E(r'%APPDATA%\discord\Cache\Cache_Data'), 512),
        ('윈도우 임시 파일', E(r'%TEMP%'), 2048),
        ('NVIDIA 셰이더 캐시(DX)', E(r'%LOCALAPPDATA%\NVIDIA\DXCache'), 1024),
        ('NVIDIA 셰이더 캐시(GL)', E(r'%LOCALAPPDATA%\NVIDIA\GLCache'), 1024),
        ('AMD 셰이더 캐시', E(r'%LOCALAPPDATA%\AMD\DxCache'), 1024),
        ('Steam 셰이더 캐시', os.path.join(_steam_root(), 'steamapps', 'shadercache'), 4096),
        ('Steam 웹 캐시', os.path.join(_steam_root(), 'appcache', 'httpcache'), 512),
        ('Epic 런처 웹 캐시', E(r'%LOCALAPPDATA%\EpicGamesLauncher\Saved\webcache'), 512),
        ('윈도우 썸네일 캐시', E(r'%LOCALAPPDATA%\Microsoft\Windows\Explorer'), 1024),
    ]
    return items

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
                        elif e.is_dir(follow_symlinks=False) and not is_reparse(e): stack.append(e.path)
                    except OSError: continue
        except OSError: continue
    return total


def load():
    """등록부 읽기 + 기본 등록부 동기화 — 업데이트로 새 기본 캐시가 추가되거나(깃허브 pull)
    새 브라우저 프로필이 생기면, 기존 등록부를 유지한 채 빠진 것만 합쳐 넣는다."""
    reg = []
    if os.path.exists(REG_FILE):
        try:
            with open(REG_FILE, encoding='utf-8') as f: reg = json.load(f)
        except (OSError, json.JSONDecodeError): reg = []
    known = {os.path.normcase(r['path']) for r in reg}
    added = False
    for n, p, lim in defaults():
        if os.path.isdir(p) and os.path.normcase(p) not in known:
            reg.append({'name': n, 'path': p, 'limit_mb': lim, 'last_clean': None})
            known.add(os.path.normcase(p)); added = True
    if added or not os.path.exists(REG_FILE): save(reg)
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


def _overlaps(path, known_paths):
    """후보가 이미 등록된 경로의 조상/자손이면 중복 — Chrome 의 Cache(부모)와 Cache\\Cache_Data(등록됨) 같은 경우"""
    p = os.path.normcase(path) + os.sep
    for k in known_paths:
        k2 = k + os.sep
        if p.startswith(k2) or k2.startswith(p): return True
    return False


def discover(reg, max_depth=4, min_mb=30):
    """자동 서치 — AppData 를 돌며 캐시형 폴더 이름을 찾아 후보로 제안한다. 등록은 사용자 승인제.
    거르는 것: 정션(무한 재귀 방지) · 이미 등록된 경로와 겹치는 것(조상/자손 포함) · min_mb 미만.
    용량 측정은 스레드 병렬."""
    from concurrent.futures import ThreadPoolExecutor
    known = {os.path.normcase(r['path']) for r in reg}
    cand = []
    for root in SEARCH_ROOTS:
        if not os.path.isdir(root): continue
        stack = [(root, 0)]
        while stack:
            d, depth = stack.pop()
            try:
                with os.scandir(d) as it:
                    for e in it:
                        if not e.is_dir(follow_symlinks=False) or is_reparse(e): continue
                        low = e.name.lower()
                        if depth == 0 and low in SKIP_DIRS: continue
                        if low in CACHE_NAMES:
                            if _overlaps(e.path, known): continue
                            # 앱 이름: 루트 바로 아래 한두 단계 (Google\Chrome, STOVE 처럼 사람이 아는 이름)
                            rel = os.path.relpath(e.path, root).split(os.sep)
                            app = '\\'.join(rel[:2]) if len(rel) > 2 else rel[0]
                            cand.append({'app': app, 'path': e.path})
                        elif depth < max_depth:
                            stack.append((e.path, depth + 1))
            except OSError: continue
    with ThreadPoolExecutor(max_workers=8) as ex:
        sizes = list(ex.map(lambda c: round(dir_size(c['path']) / 2**20), cand))
    found = [{**c, 'size_mb': mb} for c, mb in zip(cand, sizes) if mb >= min_mb]
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
