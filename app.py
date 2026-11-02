"""말끔이 — 캐시·광고·안 쓰는 것 관리자 (출품작)

실행: python app.py                (창 모드)
      python app.py --auto-clean   (작업 스케줄러가 부르는 자동 청소 — 창 없음)

구조: core/ 의 기능 모듈을 Api 클래스로 묶어 pywebview 의 JS 브리지로 노출.
화면(ui/)은 window.pywebview.api.* 로 호출한다.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.base import APP_DIR as HERE, RES_DIR

from core import (sysinfo, cache_registry, cleaner, adscan, adblock, scheduler, unused,
                  updater, recycle, toast, startup_ctl, diskmap, dupes, malscan)


class Api:
    def __init__(self):
        self._widget = None

    # ── 상태 탭 ──
    def status(self):
        return sysinfo.status()

    def quick_status(self):
        return sysinfo.quick()

    # ── 모서리 위젯 (우측 상단 상주, 드래그 이동, ✕/버튼으로 토글) ──
    def widget_toggle(self):
        import ctypes
        import webview
        if self._widget is not None:
            try: self._widget.destroy()
            except Exception: pass
            self._widget = None
            return {'on': False}
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        self._widget = webview.create_window(
            '말끔이 위젯', os.path.join(RES_DIR, 'ui', 'widget.html'), js_api=self,
            width=252, height=102, x=sw - 264, y=10,
            frameless=True, on_top=True, easy_drag=True, resizable=False)
        return {'on': True}

    def widget_state(self):
        return {'on': self._widget is not None}

    # ── 광고 차단 자가진단 ──
    def adblock_test(self):
        """대표 광고 도메인 3개를 실제로 이름 변환해 차단 동작을 실측 — 0.0.0.0 이면 차단 성공"""
        import socket
        out = []
        for d in ('doubleclick.net', 'googlesyndication.com', 'adnxs.com'):
            try:
                ip = socket.gethostbyname(d)
                out.append({'domain': d, 'ip': ip, 'blocked': ip == '0.0.0.0'})
            except socket.gaierror:
                out.append({'domain': d, 'ip': '해석 실패', 'blocked': True})
        return {'items': out, 'all_blocked': all(o['blocked'] for o in out)}

    def proc_kill(self, name, pids):
        return sysinfo.kill(name, pids)

    # ── 악성 점검 탭 (백그라운드 + 진행률 폴링) ──
    def mal_scan_start(self):
        return malscan.start(online=True)

    def mal_scan_progress(self):
        return malscan.progress()

    def defender_status(self):
        return malscan.defender_status()

    def defender_quick_scan(self):
        return malscan.defender_quick_scan()

    # ── 캐시 탭 ──
    def cache_check(self):
        return cache_registry.check(cache_registry.load())

    def cache_discover(self):
        return cache_registry.discover(cache_registry.load())

    def cache_register(self, name, path, limit_mb):
        return cache_registry.check(cache_registry.register(cache_registry.load(), name, path, limit_mb))

    def cache_set_limit(self, path, limit_mb):
        reg = cache_registry.load()
        for r in reg:
            if os.path.normcase(r['path']) == os.path.normcase(path):
                r['limit_mb'] = max(1, int(limit_mb))
        cache_registry.save(reg)
        return {'ok': True}

    def cache_preview(self, path):
        return cleaner.preview(path)

    def cache_clean(self, path, permanent=False):
        res = cleaner.clean(path, permanent)
        if not res.get('error'):
            cache_registry.mark_cleaned(cache_registry.load(), path)
        return res

    def cache_clean_start(self, path, label='', permanent=False):
        return cleaner.start(path, permanent, label)

    def cache_clean_progress(self, path=None):
        p = cleaner.progress()
        if path and not p['running'] and p['result'] and not p['result'].get('error'):
            cache_registry.mark_cleaned(cache_registry.load(), path)
        return p

    # ── 광고 탭 ──
    def ad_scan(self):
        return adscan.scan()

    def adblock_status(self):
        return adblock.status()

    def adblock_apply(self):
        return adblock.apply()

    def adblock_restore(self):
        return adblock.restore()

    # ── 안 쓰는 것 탭 ──
    def unused_scan(self, days=180):
        items = unused.scan(days=int(days))
        return {'items': items, 'notice': unused.notice(items)}

    def unused_programs(self, days=60, since=None):
        return unused.scan_programs(days=int(days), since=since or None)

    # ── 파일 정리(해석 후 삭제) 탭 ──
    def files_browse(self, where='downloads'):
        return unused.browse(where)

    def trash_paths(self, paths):
        return dupes.trash(paths)

    def unused_separate(self, paths):
        return unused.separate(paths)

    def unused_undo(self, to_path):
        return unused.undo(to_path)

    # ── 시작프로그램 끄기/켜기 (작업관리자 방식의 가역 비활성화) ──
    def startup_toggle(self, ctl, enable):
        return startup_ctl.toggle(ctl, bool(enable))

    # ── 디스크 지도 ──
    def disk_roots(self):
        return diskmap.roots()

    def open_in_explorer(self, path):
        """탐색기에서 해당 항목을 선택한 채로 열기"""
        import subprocess
        if os.path.exists(path):
            subprocess.Popen(['explorer', '/select,', path])
            return {'ok': True}
        return {'ok': False, 'error': '경로가 없음'}

    def copy_path(self, path):
        """경로를 클립보드로 — 한글 경로 안전하게 PowerShell Set-Clipboard 사용"""
        import subprocess
        try:
            subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command',
                            'Set-Clipboard -Value $env:MK_COPY'],
                           env={**os.environ, 'MK_COPY': path}, timeout=10,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return {'ok': True}
        except (OSError, subprocess.SubprocessError) as e:
            return {'ok': False, 'error': str(e)}

    def disk_children(self, path):
        return diskmap.children(path)

    def disk_start(self, path):
        return diskmap.start(path)

    def disk_progress(self):
        return diskmap.progress()

    # ── 중복 파일 ──
    def dupes_find(self, min_mb=10):
        return dupes.find(min_mb)

    def dupes_move_desktop(self, paths):
        return dupes.move_to_desktop(paths)

    def dupes_trash(self, paths):
        return dupes.trash(paths)

    # ── 휴지통 ──
    def recycle_status(self):
        return recycle.status()

    def recycle_empty(self):
        return recycle.empty()

    # ── 업데이트 (깃허브 연결) ──
    def update_check(self):
        return updater.check()

    def update_run(self):
        return updater.update()

    # ── 스케줄 ──
    def sched_status(self):
        return scheduler.status()

    def sched_register(self, hour):
        return scheduler.register(hour)

    def sched_unregister(self):
        return scheduler.unregister()


def auto_clean():
    """작업 스케줄러 모드 — 임계치 넘은 캐시만 휴지통 경유 청소, 로그 한 줄"""
    lines = []
    for r in cache_registry.check(cache_registry.load()):
        if r['over'] and r['exists']:
            res = cleaner.clean(r['path'])
            lines.append(f"{r['name']}: {res['freed_mb']}MB 비움 (건너뜀 {res['skipped']})")
            cache_registry.mark_cleaned(cache_registry.load(), r['path'])
    log = os.path.join(HERE, 'data', 'auto_clean.log')
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M')}] " + ('; '.join(lines) or '임계치 초과 없음') + '\n')
    if lines:   # 비운 게 있을 때만 토스트 — 매일 "할 일 없었음" 알림은 소음이다
        toast.notify('말끔이 자동 청소', ' · '.join(lines))


def main():
    if '--auto-clean' in sys.argv:
        auto_clean(); return
    if '--selftest' in sys.argv:   # 창 없이 코어만 점검 (개발용)
        api = Api()
        print(json.dumps({'status': api.status(), 'cache': api.cache_check()[:3],
                          'adblock': api.adblock_status(), 'sched': api.sched_status()},
                         ensure_ascii=False, indent=1)[:2000])
        return
    import threading
    import webview
    api = Api()
    # 스플래시: 아이콘이 천천히 떠오른 뒤 본창과 교대 — 깜빡 하고 들어가는 느낌 제거 (사용자 지시 2026-11-03)
    ui_dir = os.path.join(RES_DIR, 'ui')
    main_win = webview.create_window('말끔이 — 내 컴퓨터 청소 매니저',
                                     os.path.join(ui_dir, 'index.html'), js_api=api,
                                     width=1100, height=760, min_size=(900, 600), hidden=True)
    splash = None
    if os.path.exists(os.path.join(ui_dir, 'splash.html')):
        splash = webview.create_window('말끔이', os.path.join(ui_dir, 'splash.html'),
                                       width=380, height=420, frameless=True, on_top=True,
                                       resizable=False)

    def boot():
        import time as _t
        _t.sleep(1.8)   # 페이드인(1.1s) + 잠깐 머무름
        main_win.show()
        if splash is not None:
            _t.sleep(0.25)
            try: splash.destroy()
            except Exception: pass
    threading.Thread(target=boot, daemon=True).start()
    webview.start()


if __name__ == '__main__':
    main()
