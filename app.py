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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from core import sysinfo, cache_registry, cleaner, adscan, adblock, scheduler, unused


class Api:
    # ── 상태 탭 ──
    def status(self):
        return sysinfo.status()

    # ── 캐시 탭 ──
    def cache_check(self):
        return cache_registry.check(cache_registry.load())

    def cache_discover(self):
        return cache_registry.discover(cache_registry.load())

    def cache_register(self, name, path, limit_mb):
        return cache_registry.check(cache_registry.register(cache_registry.load(), name, path, limit_mb))

    def cache_preview(self, path):
        return cleaner.preview(path)

    def cache_clean(self, path, permanent=False):
        res = cleaner.clean(path, permanent)
        if not res.get('error'):
            cache_registry.mark_cleaned(cache_registry.load(), path)
        return res

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

    def unused_programs(self):
        return unused.scan_programs()

    def unused_separate(self, paths):
        return unused.separate(paths)

    def unused_undo(self, to_path):
        return unused.undo(to_path)

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


def main():
    if '--auto-clean' in sys.argv:
        auto_clean(); return
    if '--selftest' in sys.argv:   # 창 없이 코어만 점검 (개발용)
        api = Api()
        print(json.dumps({'status': api.status(), 'cache': api.cache_check()[:3],
                          'adblock': api.adblock_status(), 'sched': api.sched_status()},
                         ensure_ascii=False, indent=1)[:2000])
        return
    import webview
    api = Api()
    webview.create_window('말끔이 — 내 컴퓨터 청소 매니저',
                          os.path.join(HERE, 'ui', 'index.html'),
                          js_api=api, width=1100, height=760, min_size=(900, 600))
    webview.start()


if __name__ == '__main__':
    main()
