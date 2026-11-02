"""상태 대시보드 — "작업관리자를 대체할 만큼 쉽게".

CPU·RAM·GPU 사용량·온도 + '지금 컴퓨터 부하에 영향을 주는 프로그램' 순위 + 종료 기능.
- 프로세스 CPU% 는 구간 측정이라, Process 객체를 캐시에 들고 있어야 호출 간격 동안의
  사용률이 나온다(새로 만들면 항상 0) — _PROCS 캐시가 그 역할.
- GPU 는 nvidia-smi(NVIDIA), 없으면 표시 생략. CPU 온도는 윈도우가 표준으로 안 내놓아서
  WMI 열존을 시도하고, 안 되면 GPU 온도만 보여준다(없는 값을 지어내지 않는다).
- 종료는 시스템 필수 프로세스를 거부 목록으로 보호하고, 이름 단위(해당 이름의 모든 PID)로.
"""
import os
import json
import subprocess
import time

import psutil

from .base import DATA

psutil.cpu_percent(interval=None)   # 기준점
_PROCS = {}                         # pid -> Process (구간 CPU% 용 캐시)

# 종료 금지 — 끄면 윈도우가 죽거나 바로 살아나는 것들
PROTECTED = {'system', 'system idle process', 'registry', 'memcompression', 'smss.exe', 'csrss.exe',
             'wininit.exe', 'winlogon.exe', 'services.exe', 'lsass.exe', 'svchost.exe', 'dwm.exe',
             'fontdrvhost.exe', 'conhost.exe', 'sihost.exe', 'ctfmon.exe', 'audiodg.exe',
             'malkkeumi.exe', 'python.exe', 'pythonw.exe'}
WARN = {'explorer.exe'}   # 끌 수는 있지만 화면이 깜빡이는 것들 — UI가 한 번 더 경고


def saved_total_mb():
    try:
        with open(os.path.join(DATA, 'history.json'), encoding='utf-8') as f:
            return sum(h.get('freed_mb', 0) for h in json.load(f))
    except (OSError, json.JSONDecodeError):
        return 0


def _gpu():
    """NVIDIA: 사용률·온도·VRAM. 없으면 None (AMD/내장은 v1.1에선 표시 생략)"""
    try:
        r = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total',
                            '--format=csv,noheader,nounits'], capture_output=True, timeout=5,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if r.returncode != 0: return None
        u, t, mu, mt = [x.strip() for x in r.stdout.decode().splitlines()[0].split(',')]
        return {'util': int(u), 'temp': int(t), 'vram_used_gb': round(int(mu) / 1024, 1),
                'vram_total_gb': round(int(mt) / 1024, 1)}
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def _cpu_temp():
    """WMI 열존 — 보드가 안 내놓는 경우가 많아 실패하면 None (지어내지 않음)"""
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command',
                            '(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop | Select-Object -First 1).CurrentTemperature'],
                           capture_output=True, timeout=8,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        v = r.stdout.decode().strip()
        if v and v.isdigit():
            c = round(int(v) / 10 - 273.15)
            if 10 <= c <= 120: return c
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None


def _load_ranked(n=12):
    """부하 영향 순위 — CPU% 와 메모리를 함께 본 점수로 정렬(이름 단위 합산).
    점수: CPU 1% = RAM 0.15GB 와 같은 무게(체감 기준의 단순 가중치)."""
    merged = {}
    seen_pids = set()
    for p in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            pid = p.info['pid']; seen_pids.add(pid)
            if pid == 0: continue   # System Idle Process = '남는 CPU' — 부하 목록에 넣으면 항상 1위가 되는 함정
            proc = _PROCS.get(pid)
            if proc is None:
                proc = p; _PROCS[pid] = p; p.cpu_percent(None)   # 첫 등장 — 다음 호출부터 구간값
                cpu = 0.0
            else:
                cpu = proc.cpu_percent(None)
            name = p.info['name'] or '?'
            mem = p.info['memory_info'].rss if p.info['memory_info'] else 0
            m = merged.setdefault(name, {'name': name, 'cpu': 0.0, 'mem': 0, 'pids': []})
            m['cpu'] += cpu; m['mem'] += mem; m['pids'].append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    for pid in list(_PROCS):
        if pid not in seen_pids: del _PROCS[pid]
    ncpu = psutil.cpu_count() or 1
    out = []
    for m in merged.values():
        cpu = round(m['cpu'] / ncpu, 1)          # 전체 대비 %
        mem_gb = m['mem'] / 2**30
        score = cpu + mem_gb * 6.7   # 가중치: RAM 0.15GB ≒ CPU 1% 로 환산해 합산
        low = m['name'].lower()
        out.append({'name': m['name'], 'cpu': cpu, 'mem_mb': round(m['mem'] / 2**20),
                    'count': len(m['pids']), 'pids': m['pids'], 'score': round(score, 1),
                    'protected': low in PROTECTED, 'warn': low in WARN})
    out.sort(key=lambda x: -x['score'])
    return out[:n]


def status():
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('C:\\')
    up_days = int((time.time() - psutil.boot_time()) // 86400)
    gpu = _gpu()
    return {
        'uptime_days': up_days,
        'saved_total_mb': saved_total_mb(),
        'cpu_percent': cpu,
        'cpu_temp': _cpu_temp(),
        'gpu': gpu,
        'mem_percent': mem.percent,
        'mem_used_gb': round(mem.used / 2**30, 1),
        'mem_total_gb': round(mem.total / 2**30, 1),
        'disk_percent': disk.percent,
        'disk_free_gb': round(disk.free / 2**30, 1),
        'disk_total_gb': round(disk.total / 2**30, 1),
        'top': _load_ranked(),
        'summary': _plain_summary(cpu, mem, disk, up_days, gpu),
    }


def _plain_summary(cpu, mem, disk, up_days, gpu):
    if cpu >= 85: return '지금 컴퓨터가 매우 바빠요 — 아래 목록 맨 위 프로그램이 주범이에요.'
    if mem.percent >= 90: return '메모리가 거의 꽉 찼어요 — 아래에서 안 쓰는 프로그램을 종료하면 빨라져요.'
    if gpu and gpu['util'] >= 90: return 'GPU가 풀가동 중이에요 — 게임이나 그래픽 작업이 돌고 있어요.'
    if disk.percent >= 90: return '디스크가 거의 꽉 찼어요 — 캐시 청소 탭에서 공간을 비워 보세요.'
    if up_days >= 7: return f'컴퓨터를 끄지 않은 지 {up_days}일째예요 — 한 번 재부팅하면 가벼워져요.'
    if cpu >= 50 or mem.percent >= 75: return '컴퓨터가 조금 바쁘지만 정상 범위예요.'
    return '컴퓨터 상태가 쾌적해요.'


def kill(name, pids):
    """이름 단위 종료 — 보호 목록 거부, terminate(정상 종료 요청) 후 3초 내 안 죽으면 kill"""
    if name.lower() in PROTECTED:
        return {'ok': False, 'error': '윈도우 필수 프로세스라 종료할 수 없어요.'}
    done = failed = 0
    procs = []
    for pid in pids:
        try:
            p = psutil.Process(int(pid))
            if p.name().lower() != name.lower(): continue   # pid 재사용 안전장치
            p.terminate(); procs.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            failed += 1
    _, alive = psutil.wait_procs(procs, timeout=3)
    for p in alive:
        try: p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied): failed += 1
    done = len(procs) - sum(1 for p in alive if p.is_running())
    return {'ok': True, 'done': done, 'failed': failed}
