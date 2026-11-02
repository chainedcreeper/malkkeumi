"""광고(ad) 벡터 스캐너 — 광고가 들어오는 네 가지 길을 읽기 전용으로 점검한다.

① 자동 실행(레지스트리 Run 키 + 시작프로그램 폴더)
② 작업 스케줄러에 숨은 광고성 작업
③ 브라우저 확장 (Chrome/Edge/웨일)
④ 브라우저 알림 허용 사이트 (광고 알림 스팸의 본거지)

여기서는 '찾고 보여주기'만 한다 — 제거는 사용자가 항목을 보고 결정(각 항목에 위치를 명시).
"""
import csv
import glob
import io
import json
import os
import subprocess
import winreg

E = os.path.expandvars

# 광고성/번들성으로 악명 있는 이름 조각들 (소문자 비교) — 확정 판정이 아니라 '주의' 표시용
SUSPECT_WORDS = ['ad', 'ads', 'adware', 'toolbar', 'coupon', 'deal', 'savings', 'sweet',
                 'updater', 'bundle', 'offer', 'shopper', 'price', 'popup', 'banner']
# 'ad' 는 오탐이 많아서(adobe, upload…) 단어 경계로만 본다
SAFE_WORDS = ['adobe', 'amd', 'adapter', 'radeon', 'thread', 'read', 'load', 'adal', 'gradle', 'adb']

BROWSERS = {
    'Chrome': E(r'%LOCALAPPDATA%\Google\Chrome\User Data'),
    'Edge': E(r'%LOCALAPPDATA%\Microsoft\Edge\User Data'),
    '웨일': E(r'%LOCALAPPDATA%\Naver\Naver Whale\User Data'),
}


def _suspicious(name):
    low = name.lower()
    if any(w in low for w in SAFE_WORDS): return False
    return any((f' {w}' in f' {low}' or low.startswith(w) or w in low.replace('-', '').replace('_', ''))
               for w in SUSPECT_WORDS if len(w) > 2) or low.split('.')[0] in ('ad', 'ads')


def startup_items():
    """레지스트리 Run 키 + 시작프로그램 폴더"""
    out = []
    for hive, hname in ((winreg.HKEY_CURRENT_USER, 'HKCU'), (winreg.HKEY_LOCAL_MACHINE, 'HKLM')):
        for keypath in (r'Software\Microsoft\Windows\CurrentVersion\Run',
                        r'Software\Microsoft\Windows\CurrentVersion\RunOnce'):
            try:
                with winreg.OpenKey(hive, keypath) as k:
                    for i in range(winreg.QueryInfoKey(k)[1]):
                        name, val, _ = winreg.EnumValue(k, i)
                        from .startup_ctl import run_state
                        en = run_state(hname, name)
                        out.append({'kind': '레지스트리 자동실행', 'name': name, 'detail': str(val),
                                    'where': f'{hname}\\{keypath}', 'suspect': _suspicious(name + ' ' + str(val)),
                                    'ctl': f'run:{hname}:{name}', 'enabled': en is not False})
            except OSError: continue
    for folder in (E(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup'),
                   E(r'%ProgramData%\Microsoft\Windows\Start Menu\Programs\StartUp')):
        for f in glob.glob(os.path.join(folder, '*')):
            n = os.path.basename(f)
            if n.lower() == 'desktop.ini': continue
            from .startup_ctl import folder_state
            en = folder_state(n)
            out.append({'kind': '시작프로그램 폴더', 'name': n, 'detail': f, 'where': folder,
                        'suspect': _suspicious(n), 'ctl': f'folder:{n}', 'enabled': en is not False})
    return out


def scheduled_tasks():
    """작업 스케줄러 — MS 기본 작업은 숨기고 서드파티만"""
    out = []
    try:
        r = subprocess.run(['schtasks', '/query', '/fo', 'csv', '/v'],
                           capture_output=True, timeout=60)
        from .winpaths import console_decode
        text = console_decode(r.stdout)
    except (OSError, subprocess.SubprocessError):
        return out
    rows = csv.DictReader(io.StringIO(text))
    seen = set()
    for row in rows:
        tn = row.get('작업 이름') or row.get('TaskName') or ''
        action = row.get('실행할 작업') or row.get('Task To Run') or ''
        state = row.get('예약된 작업 상태') or row.get('Scheduled Task State') or ''
        if not tn or tn in seen or tn.startswith('\\Microsoft\\'): continue
        seen.add(tn)
        if tn == '작업 이름': continue   # /v 모드의 반복 헤더 행
        out.append({'kind': '작업 스케줄러', 'name': tn, 'detail': action,
                    'where': 'C:\\Windows\\System32\\Tasks' + tn,
                    'suspect': _suspicious(tn + ' ' + action),
                    'ctl': f'task:{tn}', 'enabled': state not in ('사용 안 함', 'Disabled')})
    return out


def _profiles(root):
    for prof in ('Default', 'Profile 1', 'Profile 2', 'Profile 3'):
        p = os.path.join(root, prof)
        if os.path.isdir(p): yield p


def browser_extensions():
    """설치된 확장 나열 — 이름은 manifest.json(또는 메시지 파일)에서"""
    out = []
    for bname, root in BROWSERS.items():
        for prof in _profiles(root):
            ext_root = os.path.join(prof, 'Extensions')
            if not os.path.isdir(ext_root): continue
            for ext_id in os.listdir(ext_root):
                vers = sorted(glob.glob(os.path.join(ext_root, ext_id, '*', 'manifest.json')))
                if not vers: continue
                try:
                    mf = json.load(open(vers[-1], encoding='utf-8'))
                except (OSError, json.JSONDecodeError): continue
                name = mf.get('name', ext_id)
                if name.startswith('__MSG_'):
                    name = _msg_name(os.path.dirname(vers[-1]), name) or ext_id
                out.append({'kind': f'{bname} 확장', 'name': name, 'detail': ext_id,
                            'where': os.path.dirname(vers[-1]), 'suspect': _suspicious(name)})
    return out


def _msg_name(ext_dir, key):
    key = key[6:-2]  # __MSG_xxx__
    for loc in ('ko', 'en', 'en_US'):
        p = os.path.join(ext_dir, '_locales', loc, 'messages.json')
        try:
            msgs = json.load(open(p, encoding='utf-8'))
            for k, v in msgs.items():
                if k.lower() == key.lower(): return v.get('message')
        except (OSError, json.JSONDecodeError): continue
    return None


def notification_sites():
    """브라우저 '알림 허용' 사이트 — Preferences(JSON)의 content_settings 에서 읽는다.
    광고 알림 스팸은 대부분 여기서 나온다. 해제는 브라우저 설정 경로를 안내."""
    out = []
    for bname, root in BROWSERS.items():
        for prof in _profiles(root):
            p = os.path.join(prof, 'Preferences')
            try:
                prefs = json.load(open(p, encoding='utf-8'))
            except (OSError, json.JSONDecodeError): continue
            exc = (prefs.get('profile', {}).get('content_settings', {})
                   .get('exceptions', {}).get('notifications', {}))
            for origin, cfg in exc.items():
                if cfg.get('setting') == 1:   # 1 = 허용
                    site = origin.split(',')[0]
                    out.append({'kind': f'{bname} 알림 허용', 'name': site,
                                'detail': f'{bname} 설정 → 개인정보 보호 → 사이트 설정 → 알림에서 해제',
                                'where': p, 'suspect': _suspicious(site)})
    return out


def scan():
    """전체 스캔 — suspect(주의) 항목이 위로 오게"""
    items = startup_items() + scheduled_tasks() + browser_extensions() + notification_sites()
    return sorted(items, key=lambda x: not x['suspect'])
