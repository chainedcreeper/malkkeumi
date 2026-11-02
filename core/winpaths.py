"""어떤 컴퓨터에서든 맞는 실제 폴더 경로 — '바탕화면=~\\Desktop' 가정은 깨진다.

OneDrive 백업이 켜진 컴퓨터는 바탕화면이 %USERPROFILE%\\OneDrive\\바탕 화면 에 있고,
영어/한국어 윈도우에서 폴더 이름도 다르다. 정답은 레지스트리 User Shell Folders —
윈도우가 실제로 쓰는 위치를 그대로 읽는다.
"""
import os
import winreg

_KEY = r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
_IDS = {
    'desktop': 'Desktop',
    'downloads': '{374DE290-123F-4565-9164-39C4925E467B}',   # Downloads 는 GUID 로만 있음
    'documents': 'Personal',
    'pictures': 'My Pictures',
    'videos': 'My Video',
}


def known_folder(name):
    """'desktop' 등 → 이 컴퓨터의 실제 경로. 못 읽으면 고전적 기본값."""
    fallback = os.path.join(os.path.expanduser('~'), {'desktop': 'Desktop', 'downloads': 'Downloads',
                            'documents': 'Documents', 'pictures': 'Pictures', 'videos': 'Videos'}[name])
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY) as k:
            raw, _ = winreg.QueryValueEx(k, _IDS[name])
        return os.path.expandvars(raw)
    except OSError:
        return fallback


def user_content_roots():
    """안 쓰는 것 스캔 대상 — 이 컴퓨터의 실제 다운로드·바탕화면·문서·동영상·사진"""
    seen, out = set(), []
    for n in ('downloads', 'desktop', 'documents', 'videos', 'pictures'):
        p = known_folder(n)
        if os.path.isdir(p) and os.path.normcase(p) not in seen:
            seen.add(os.path.normcase(p)); out.append(p)
    return out


def console_decode(raw):
    """schtasks 등 콘솔 출력 디코딩 — 한국어(cp949)·영어(cp437)·기타 로케일 전부 대응"""
    for enc in ('utf-8', 'cp949', 'cp437', 'latin-1'):
        try: return raw.decode(enc)
        except (UnicodeDecodeError, LookupError): continue
    return raw.decode('utf-8', errors='replace')
