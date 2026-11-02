# 진행률 기능 점검 (개발용)
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import malscan, diskmap

malscan.start(online=False)
seen = []
while True:
    p = malscan.progress()
    if not seen or p['pct'] != seen[-1][0]: seen.append((p['pct'], p['stage']))
    if not p['running'] and p['result'] is not None: break
    time.sleep(0.25)
print('malscan 진행:', seen[:3], '...', seen[-2:])
print('결과:', p['result']['counts'])
for i in [i for i in p['result']['items'] if i.get('created')][:3]:
    print('  예:', i['name'], '| 생성', i['created'], '| 출처', i.get('source'))

diskmap.start(os.path.expanduser('~'))
seen = []
while True:
    p = diskmap.progress()
    if not seen or p['pct'] != seen[-1]: seen.append(p['pct'])
    if not p['running'] and p['result'] is not None: break
    time.sleep(0.2)
print('diskmap 진행:', seen[:8], '→ 100 | 항목', len(p['result']['items']))
