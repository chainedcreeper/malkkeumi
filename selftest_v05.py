# v0.5 신기능 헤드리스 점검 (개발용) — python selftest_v05.py
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import diskmap, dupes, adscan

t0 = time.time()
r = diskmap.children(os.path.expanduser('~'))
print(f"디스크 지도(내 폴더): {time.time()-t0:.1f}초, 합계 {r['total_mb']}MB")
for i in r['items'][:6]:
    print(f"  {i['pct']:>5}%  {i['size_mb']:>9} MB  {'📁' if i['is_dir'] else '  '} {i['name']}")

t0 = time.time()
d = dupes.find(min_mb=10)
print(f"중복(10MB+): {time.time()-t0:.1f}초, 그룹 {len(d['groups'])} / 낭비 {d['wasted_total_mb']}MB")
for g in d['groups'][:3]:
    print(f"  {g['size_mb']}MB x{len(g['files'])}:")
    for f in g['files']: print('    ', f)

items = adscan.startup_items()
print('자동실행(상태 포함):')
for i in items[:8]:
    print(f"  [{'ON ' if i['enabled'] else 'OFF'}] {i['kind']} | {i['name']}")
