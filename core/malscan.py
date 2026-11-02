"""악성 코드 점검 — 백신 엔진 흉내가 아니라 '백신이 좋아하는 지점'을 정밀 점검한다.

솔직한 설계(과장 금지): 시그니처 DB 전수 검사는 백신의 영역이다. 우리가 잘할 수 있는 것은
① 악성코드가 숨는 자리(자동실행·임시폴더·다운로드)의 실행파일을 모아
② 정적 신호 4가지로 점수를 매기고   — 서명 없음/위조 · 수상한 위치 · 이중 확장자 · 숨김 속성
③ SHA-256 을 MalwareBazaar(abuse.ch 공개 악성 해시 DB)에 조회하고
④ 진짜 검사는 Windows Defender 빠른 검사로 연결하는 것(상태 확인 + 실행 버튼).

판정 언어도 솔직하게: '악성 확정'은 ③에서 해시가 일치할 때만. 나머지는 '점검 권장' 신호다.
"""
import hashlib
import json
import os
import re
import subprocess
import threading
import urllib.parse
import urllib.request

from .winpaths import console_decode

# 진행 상황 — UI 가 0.5초마다 폴링해서 1~100% 게이지로 보여준다
_progress = {'running': False, 'pct': 0, 'stage': '', 'result': None}
_lock = threading.Lock()


def _set(pct, stage):
    with _lock:
        _progress['pct'] = int(pct); _progress['stage'] = stage


def progress():
    with _lock:
        return dict(_progress)


def start(online=True):
    """점검을 백그라운드 스레드로 시작 — UI 는 progress() 를 폴링"""
    with _lock:
        if _progress['running']: return {'ok': False, 'error': '이미 점검 중'}
        _progress.update(running=True, pct=1, stage='준비', result=None)
    def run():
        try:
            res = scan(online=online)
        except Exception as e:   # 어떤 오류도 UI 를 영원히 기다리게 하면 안 된다
            res = {'items': [], 'counts': {'bad': 0, 'warn': 0, 'ok': 0}, 'error': str(e)}
        with _lock:
            _progress.update(running=False, pct=100, stage='완료', result=res)
    threading.Thread(target=run, daemon=True).start()
    return {'ok': True}

E = os.path.expandvars
NOWIN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
EXE_EXT = ('.exe', '.scr', '.com', '.bat', '.cmd', '.vbs', '.js')
DOUBLE_EXT = re.compile(r'\.(pdf|doc|docx|xls|xlsx|hwp|jpg|jpeg|png|txt|zip)\.(exe|scr|com|bat|cmd|vbs|js)$', re.I)


def _exe_from_command(cmd):
    """레지스트리 Run 값·스케줄러 액션 문자열에서 실행파일 경로만 추출"""
    if not cmd: return None
    cmd = cmd.strip()
    m = re.match(r'"([^"]+)"', cmd)
    path = m.group(1) if m else re.split(r'\s+[-/]', cmd)[0].strip()
    path = E(path.strip('"'))
    if not path.lower().endswith(EXE_EXT):
        m2 = re.search(r'([A-Za-z]:\\[^"]+?\.(?:exe|scr|com|bat|cmd|vbs|js))', cmd, re.I)
        path = E(m2.group(1)) if m2 else None
    return path if path and os.path.isfile(path) else None


def _targets():
    """점검 대상 수집 — (경로, 어디서 나왔나)"""
    out = {}
    from . import adscan
    for item in adscan.startup_items() + adscan.scheduled_tasks():
        p = _exe_from_command(item.get('detail', ''))
        if p: out.setdefault(os.path.normcase(p), (p, item['kind'] + ': ' + item['name']))
    # 임시폴더·AppData 루트의 실행파일 (악성코드 단골 자리 — 정상 프로그램은 여기에 exe 를 잘 안 둔다)
    for root, why in ((E(r'%TEMP%'), '임시 폴더'), (E(r'%APPDATA%'), 'AppData 루트'),
                      (E(r'%LOCALAPPDATA%'), 'AppData 루트'), (os.path.join(os.path.expanduser('~'), 'Downloads'), '다운로드 폴더')):
        try:
            with os.scandir(root) as it:
                for e in it:
                    if e.is_file(follow_symlinks=False) and e.name.lower().endswith(EXE_EXT):
                        out.setdefault(os.path.normcase(e.path), (e.path, why))
        except OSError: continue
    return list(out.values())


def _signatures(paths):
    """Authenticode 일괄 검사 — Valid / NotSigned / HashMismatch(변조!) 등"""
    if not paths: return {}
    lst = ','.join(f"'{p}'" for p in paths if "'" not in p)
    ps = (f"Get-AuthenticodeSignature -FilePath @({lst}) | "
          "ForEach-Object { $_.Path + '|' + $_.Status }")
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
                           capture_output=True, timeout=120, creationflags=NOWIN)
        out = {}
        for ln in console_decode(r.stdout).splitlines():
            if '|' in ln:
                p, st = ln.rsplit('|', 1)
                out[os.path.normcase(p.strip())] = st.strip()
        return out
    except (OSError, subprocess.SubprocessError):
        return {}


def _sha256(path, max_mb=200):
    try:
        if os.path.getsize(path) > max_mb * 2**20: return None
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _bazaar_lookup(sha):
    """MalwareBazaar 공개 DB 조회 — 일치하면 악성 '확정'. 네트워크/정책 실패는 None(모름)으로."""
    try:
        data = urllib.parse.urlencode({'query': 'get_info', 'hash': sha}).encode()
        req = urllib.request.Request('https://mb-api.abuse.ch/api/v1/', data=data,
                                     headers={'User-Agent': 'malkkeumi/1.1'})
        with urllib.request.urlopen(req, timeout=10) as r:
            j = json.load(r)
        if j.get('query_status') == 'ok':
            info = j['data'][0]
            return {'hit': True, 'family': info.get('signature') or '알 수 없는 계열'}
        if j.get('query_status') in ('hash_not_found', 'no_results'):
            return {'hit': False}
        return None
    except (OSError, json.JSONDecodeError, KeyError, IndexError):
        return None


def scan(online=True):
    """전체 점검 — 항목마다 신호와 위험도(bad: 해시 일치, warn: 신호 1개 이상, ok).
    진행률: 수집 1~10 → 서명 검사 10~45(8개 묶음마다 갱신) → 신호·해시 45~99(파일마다 갱신)"""
    _set(3, '점검 대상 모으는 중')
    targets = _targets()
    _set(10, f'디지털 서명 검사 (0/{len(targets)})')
    paths = [p for p, _ in targets]
    sigs = {}
    for b in range(0, len(paths), 8):
        sigs.update(_signatures(paths[b:b + 8]))
        _set(10 + 35 * min(b + 8, len(paths)) / max(1, len(paths)), f'디지털 서명 검사 ({min(b + 8, len(paths))}/{len(paths)})')
    items = []
    for ti, (path, origin) in enumerate(targets):
        _set(45 + 54 * ti / max(1, len(targets)), f'신호 분석·해시 조회 ({ti + 1}/{len(targets)})')
        flags = []
        sig = sigs.get(os.path.normcase(path), '?')
        if sig == 'HashMismatch': flags.append('서명 불일치(파일 변조 신호!)')
        elif sig == 'NotSigned': flags.append('디지털 서명 없음')
        low = path.lower()
        if '\\temp\\' in low or low.startswith(E(r'%TEMP%').lower()): flags.append('임시 폴더에서 실행')
        if DOUBLE_EXT.search(os.path.basename(low)): flags.append('이중 확장자(위장 의심!)')
        try:
            if os.stat(path).st_file_attributes & 0x2: flags.append('숨김 속성')
        except OSError: pass
        level = 'warn' if flags else 'ok'
        baz = None
        if online and flags:   # 신호 있는 것만 해시 조회 (전수 조회는 느리고 과함)
            sha = _sha256(path)
            if sha:
                baz = _bazaar_lookup(sha)
                if baz and baz.get('hit'):
                    level = 'bad'; flags.insert(0, f"악성 해시 DB 일치 — {baz['family']}")
        items.append({'path': path, 'name': os.path.basename(path), 'origin': origin,
                      'signature': sig, 'flags': flags, 'level': level,
                      'db_checked': baz is not None, **_file_birth(path)})
    order = {'bad': 0, 'warn': 1, 'ok': 2}
    items.sort(key=lambda x: (order[x['level']], -len(x['flags'])))
    return {'items': items,
            'counts': {k: sum(1 for i in items if i['level'] == k) for k in ('bad', 'warn', 'ok')}}


def _file_birth(path):
    """파일이 언제 생겼나 + 어디서 받았나.
    - created: 윈도우의 파일 생성 시각(다운로드 파일이면 받은 시점)
    - source: 인터넷에서 받은 파일에 윈도우가 적어 두는 Zone.Identifier(Mark of the Web)의 출처 URL —
      있으면 '인터넷에서 받은 파일'이라는 확실한 표식이고, 없으면 로컬 생성/복사본이다."""
    import time as _t
    out = {'created': None, 'source': None}
    try:
        out['created'] = _t.strftime('%Y-%m-%d', _t.localtime(os.stat(path).st_ctime))
    except OSError:
        pass
    try:
        with open(path + ':Zone.Identifier', encoding='utf-8', errors='ignore') as f:
            for ln in f:
                if ln.lower().startswith(('hosturl=', 'referrerurl=')):
                    url = ln.split('=', 1)[1].strip()
                    if url and not url.startswith('about:'):
                        host = re.sub(r'^https?://([^/]+).*$', r'\1', url)
                        out['source'] = host[:80]
                        if ln.lower().startswith('hosturl='): break
    except OSError:
        pass
    return out


def defender_status():
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command',
                            "$s=Get-MpComputerStatus; $s.RealTimeProtectionEnabled.ToString()+'|'+$s.AntivirusSignatureLastUpdated.ToString('yyyy-MM-dd')+'|'+$s.QuickScanEndTime.ToString('yyyy-MM-dd HH:mm')"],
                           capture_output=True, timeout=20, creationflags=NOWIN)
        parts = console_decode(r.stdout).strip().split('|')
        if len(parts) == 3:
            return {'ok': True, 'realtime': parts[0] == 'True', 'sig_date': parts[1], 'last_quick': parts[2]}
    except (OSError, subprocess.SubprocessError):
        pass
    return {'ok': False}


def defender_quick_scan():
    """Defender 빠른 검사 — 백그라운드로 던지고, 결과는 윈도우 보안 알림이 알려준다"""
    try:
        subprocess.Popen(['powershell', '-NoProfile', '-NonInteractive', '-Command', 'Start-MpScan -ScanType QuickScan'],
                         creationflags=NOWIN)
        return {'ok': True, 'msg': 'Defender 빠른 검사를 시작했어요 — 몇 분 걸리고, 결과는 윈도우 보안 알림으로 와요.'}
    except OSError as e:
        return {'ok': False, 'msg': str(e)}
