"""휴지통 — 용량 조회와 비우기. 외부 패키지 없이 윈도우 셸 API(ctypes) 직접 호출.

우리 청소는 휴지통 '경유'라서, 마지막 단계(휴지통 비우기)까지 앱 안에서 끝낼 수 있어야 한다.
비우기는 UI에서 반드시 확인을 받고 부른다 — 여기서는 확인창 없이 조용히 실행(NOCONFIRMATION).
"""
import ctypes
from ctypes import wintypes


class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('i64Size', ctypes.c_longlong),
                ('i64NumItems', ctypes.c_longlong)]


def status():
    """휴지통에 든 항목 수와 용량(MB)"""
    info = _SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(info)
    r = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
    if r != 0:
        return {'ok': False, 'items': 0, 'size_mb': 0}
    return {'ok': True, 'items': int(info.i64NumItems), 'size_mb': round(info.i64Size / 2**20)}


def empty():
    """휴지통 비우기 — 확인창·진행창·소리 없이 (확인은 UI 몫)"""
    SHERB = 0x1 | 0x2 | 0x4   # NOCONFIRMATION | NOPROGRESSUI | NOSOUND
    before = status()
    r = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, SHERB)
    # 이미 비어 있으면 E_UNEXPECTED(0x8000FFFF) 류가 돌아온다 — 실패가 아님
    ok = r == 0 or before['items'] == 0
    return {'ok': ok, 'freed_mb': before['size_mb'] if ok else 0}
