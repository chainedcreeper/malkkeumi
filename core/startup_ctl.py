"""시작프로그램 끄기/켜기 — 삭제가 아니라 '작업관리자와 같은 방식'의 가역 비활성화.

윈도우 작업관리자의 시작프로그램 사용/사용 안 함은 레지스트리 StartupApproved 키에
12바이트 값(02=사용, 03+끈시각=사용 안 함)을 적는 것뿐이다 — 우리도 똑같이 한다.
원본 Run 항목·시작폴더 파일은 전혀 건드리지 않으므로 언제든 되돌릴 수 있고,
작업관리자에도 그대로 "사용 안 함"으로 표시된다. 작업 스케줄러 항목은 schtasks /change 로.
"""
import subprocess
import time
import winreg

APPROVED = r'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved'
ENABLED = bytes([2] + [0] * 11)


def _disabled_blob():
    ft = int((time.time() + 11644473600) * 10**7)   # 현재 시각의 FILETIME — 작업관리자가 적는 것과 동일
    return bytes([3, 0, 0, 0]) + ft.to_bytes(8, 'little')


def _hive(name):
    return winreg.HKEY_LOCAL_MACHINE if name == 'HKLM' else winreg.HKEY_CURRENT_USER


def _approved_state(hive, sub, value_name):
    """None=기록 없음(=사용), True=사용, False=사용 안 함"""
    try:
        with winreg.OpenKey(_hive(hive), f'{APPROVED}\\{sub}') as k:
            data, _ = winreg.QueryValueEx(k, value_name)
        return data[0] != 3
    except OSError:
        return None


def run_state(hive, name):
    return _approved_state(hive, 'Run', name)


def folder_state(filename):
    return _approved_state('HKCU', 'StartupFolder', filename)


def _set_approved(hive, sub, value_name, enable):
    try:
        k = winreg.CreateKeyEx(_hive(hive), f'{APPROVED}\\{sub}', 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(k, value_name, 0, winreg.REG_BINARY, ENABLED if enable else _disabled_blob())
        winreg.CloseKey(k)
        return {'ok': True}
    except OSError as e:
        return {'ok': False, 'error': f'레지스트리 쓰기 실패(관리자 권한 필요할 수 있음): {e}'}


def toggle(ctl, enable):
    """ctl 문자열로 항목을 끄거나 켠다 — adscan 이 각 항목에 붙여 주는 제어 주소.
    'run:HKCU:이름' / 'folder:파일명' / 'task:\\작업이름'"""
    kind, _, rest = ctl.partition(':')
    if kind == 'run':
        hive, _, name = rest.partition(':')
        return _set_approved(hive, 'Run', name, enable)
    if kind == 'folder':
        return _set_approved('HKCU', 'StartupFolder', rest, enable)
    if kind == 'task':
        try:
            r = subprocess.run(['schtasks', '/change', '/tn', rest,
                                '/enable' if enable else '/disable'],
                               capture_output=True, timeout=30)
            if r.returncode == 0: return {'ok': True}
            from .winpaths import console_decode
            return {'ok': False, 'error': console_decode(r.stdout + r.stderr).strip()}
        except (OSError, subprocess.SubprocessError) as e:
            return {'ok': False, 'error': str(e)}
    return {'ok': False, 'error': '알 수 없는 항목'}
