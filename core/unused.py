"""안 쓰는 것 탐지 — "이런 것들이 사용되지 않고 있어요!"

단위는 '사람이 아는 덩어리'다 (사용자 지시 2026-11-02):
- 파일 쪽: 다운로드·바탕화면·문서·동영상·사진 폴더의 **최상위 항목**만 본다.
  폴더면 폴더 통째로 1건(안의 세부 파일로 알림하지 않음 — 라이브러리 파일 하나하나 얘기하면 이상하니까),
  마지막 사용 시각은 '안의 내용물 중 가장 최근' 으로 판정한다(하나라도 최근에 썼으면 쓰는 덩어리).
- 프로그램 쪽: Prefetch 실행 기록(.pf 수정시각 = 마지막 실행)으로 '몇 달째 안 켠 앱'. 앱(exe) 단위.

처리는 삭제가 아니라 '분리': 바탕화면 「말끔이 보관함」으로 옮기고 원위치를 기록해 되돌리기 지원.
"""
import json
import os
import shutil
import time

from .winpaths import user_content_roots, known_folder
SCAN_ROOTS = user_content_roots()   # 이 컴퓨터의 실제 다운로드·바탕화면·문서… (OneDrive 이동·영어 윈도우 대응)
ARCHIVE = os.path.join(known_folder('desktop'), '말끔이 보관함')
from .base import DATA
MOVES_LOG = os.path.join(DATA, 'moves.json')   # 되돌리기용 원위치 기록
SKIP_NAMES = {'desktop.ini', 'thumbs.db'}
SKIP_TOP = {'말끔이 보관함', '말끔이'}   # 우리 것은 스캔 제외


def _folder_last_used(path, cap=20000):
    """폴더 '덩어리'의 마지막 사용 — 내용물의 접근/수정 시각 중 최신. cap개까지만 보고 그 시점 결론."""
    latest, seen, total = 0.0, 0, 0
    stack = [path]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    seen += 1
                    if seen > cap: return latest, total
                    try:
                        st = e.stat(follow_symlinks=False)
                        if st.st_file_attributes & 0x400: continue   # 정션/심링크 — 무한 재귀 방지
                        if e.is_dir(follow_symlinks=False): stack.append(e.path)
                        else: total += st.st_size
                        latest = max(latest, st.st_atime, st.st_mtime)
                    except OSError: continue
        except OSError: continue
    return latest, total


def scan(days=180, min_mb=30, max_items=100):
    """N일 넘게 안 쓴 최상위 덩어리(폴더/파일) — 큰 것부터"""
    cutoff = time.time() - days * 86400
    out = []
    for root in SCAN_ROOTS:
        if not os.path.isdir(root): continue
        try:
            entries = list(os.scandir(root))
        except OSError: continue
        for e in entries:
            if e.name in SKIP_TOP or e.name.lower() in SKIP_NAMES or e.name.startswith('.'): continue
            try:
                if e.is_dir(follow_symlinks=False):
                    lu, size = _folder_last_used(e.path)
                    kind = '폴더'
                else:
                    st = e.stat()
                    lu, size = max(st.st_atime, st.st_mtime), st.st_size
                    kind = '파일'
            except OSError: continue
            if lu and lu < cutoff and size >= min_mb * 2**20:
                out.append({'path': e.path, 'name': e.name, 'kind': kind,
                            'where': os.path.basename(root),
                            'size_mb': round(size / 2**20),
                            'last_used': time.strftime('%Y-%m-%d', time.localtime(lu)),
                            'days': int((time.time() - lu) // 86400)})
    out.sort(key=lambda x: -x['size_mb'])
    return out[:max_items]


def scan_programs(days=60):
    """Prefetch 실행 기록으로 '오래 안 켠 프로그램' (앱 단위). 관리자 권한 없으면 그 사실을 알림."""
    pf_dir = r'C:\Windows\Prefetch'
    progs = {}
    try:
        with os.scandir(pf_dir) as it:
            for e in it:
                if not e.name.endswith('.pf'): continue
                exe = e.name.rsplit('-', 1)[0]
                try: mt = e.stat().st_mtime
                except OSError: continue
                progs[exe] = max(progs.get(exe, 0), mt)
    except PermissionError:
        return {'error': '프로그램 실행 기록(Prefetch)은 관리자 권한으로 실행해야 보여요.', 'items': []}
    except OSError:
        return {'error': '실행 기록을 읽을 수 없음', 'items': []}
    cutoff = time.time() - days * 86400
    items = [{'name': exe, 'last_run': time.strftime('%Y-%m-%d', time.localtime(mt)),
              'days': int((time.time() - mt) // 86400)}
             for exe, mt in progs.items() if mt < cutoff]
    items.sort(key=lambda x: -x['days'])
    return {'error': None, 'items': items[:100]}


# 파일 해석 사전 — "이 파일이 뭔지"를 사람 말로
EXT_KIND = {
    '.exe': ('실행 파일', None), '.msi': ('설치 패키지', '설치가 끝났으면 지워도 돼요'),
    '.zip': ('압축 파일', '풀어서 썼다면 원본은 지워도 돼요'), '.7z': ('압축 파일', '풀어서 썼다면 원본은 지워도 돼요'),
    '.rar': ('압축 파일', '풀어서 썼다면 원본은 지워도 돼요'), '.iso': ('디스크 이미지', '설치 후엔 보통 필요 없어요'),
    '.mp4': ('동영상', None), '.mkv': ('동영상', None), '.avi': ('동영상', None), '.gif': ('움짤', None),
    '.mp3': ('음악', None), '.wav': ('소리 파일', None), '.flac': ('음악', None),
    '.jpg': ('사진', None), '.jpeg': ('사진', None), '.png': ('이미지', None), '.webp': ('이미지', None),
    '.pdf': ('PDF 문서', None), '.hwp': ('한글 문서', None), '.docx': ('워드 문서', None),
    '.xlsx': ('엑셀 문서', None), '.pptx': ('파워포인트', None), '.txt': ('텍스트', None),
    '.torrent': ('토렌트 시드', '다운로드 끝났으면 지워도 돼요'), '.apk': ('안드로이드 앱', None),
    '.json': ('데이터 파일', None), '.csv': ('표 데이터', None), '.log': ('로그 기록', '지워도 돼요'),
    '.tmp': ('임시 파일', '지워도 돼요'), '.bak': ('백업 사본', None), '.lnk': ('바로가기', '원본이 아니라 지워도 돼요'),
}
import re as _re
_INSTALLER = _re.compile(r'setup|install|installer|_x64|_x86|win64|다운로더', _re.I)


def browse(where='downloads', max_items=300):
    """파일 해석 화면 — 폴더 최상위 파일을 '뭔지 + 지워도 되는지 힌트'와 함께 나열 (큰 것부터)"""
    root = known_folder(where)
    out = []
    try:
        entries = [e for e in os.scandir(root) if e.is_file(follow_symlinks=False)]
    except OSError:
        return {'root': root, 'items': [], 'error': '폴더를 열 수 없음'}
    for e in entries:
        if e.name.lower() in SKIP_NAMES: continue
        try: st = e.stat()
        except OSError: continue
        ext = os.path.splitext(e.name)[1].lower()
        kind, hint = EXT_KIND.get(ext, (f'{ext[1:].upper()} 파일' if ext else '파일', None))
        if ext in ('.exe', '.msi') and _INSTALLER.search(e.name):
            kind, hint = '설치 프로그램', '프로그램을 이미 설치했다면 지워도 돼요'
        out.append({'path': e.path, 'name': e.name, 'size_mb': round(st.st_size / 2**20, 1),
                    'created': time.strftime('%Y-%m-%d', time.localtime(st.st_ctime)),
                    'kind': kind, 'hint': hint})
    out.sort(key=lambda x: -x['size_mb'])
    return {'root': root, 'items': out[:max_items]}


def notice(items):
    """알림 문장 — 사람이 읽는 한 줄"""
    if not items: return None
    total = sum(f['size_mb'] for f in items)
    oldest = max(f['days'] for f in items)
    return (f'이런 것들이 사용되지 않고 있어요! — {len(items)}개 (총 {total:,}MB, '
            f'가장 오래된 건 {oldest}일 전이 마지막). 보관함으로 분리해 두면 디스크가 가벼워져요.')


def _load_moves():
    try:
        with open(MOVES_LOG, encoding='utf-8') as f: return json.load(f)
    except (OSError, json.JSONDecodeError): return []


def separate(paths):
    """선택한 덩어리를 보관함으로 이동(삭제 아님) + 원위치 기록"""
    os.makedirs(DATA, exist_ok=True)
    dest_dir = os.path.join(ARCHIVE, time.strftime('%Y-%m-%d'))
    os.makedirs(dest_dir, exist_ok=True)
    moves = _load_moves()
    moved = skipped = 0
    for p in paths:
        try:
            dest = os.path.join(dest_dir, os.path.basename(p))
            i = 1
            while os.path.exists(dest):
                stem, ext = os.path.splitext(os.path.basename(p))
                dest = os.path.join(dest_dir, f'{stem} ({i}){ext}'); i += 1
            shutil.move(p, dest)
            moves.append({'from': p, 'to': dest, 'when': time.strftime('%Y-%m-%d %H:%M')})
            moved += 1
        except OSError:
            skipped += 1
    with open(MOVES_LOG, 'w', encoding='utf-8') as f: json.dump(moves, f, ensure_ascii=False, indent=1)
    return {'moved': moved, 'skipped': skipped, 'archive': dest_dir}


def undo(to_path):
    """보관함의 항목 하나를 원위치로"""
    moves = _load_moves()
    for m in reversed(moves):
        if os.path.normcase(m['to']) == os.path.normcase(to_path) and os.path.exists(m['to']):
            try:
                os.makedirs(os.path.dirname(m['from']), exist_ok=True)
                shutil.move(m['to'], m['from'])
                return {'ok': True, 'restored': m['from']}
            except OSError as e:
                return {'ok': False, 'error': str(e)}
    return {'ok': False, 'error': '기록에 없는 항목'}
