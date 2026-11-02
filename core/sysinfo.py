"""상태 대시보드 데이터 — psutil 로 CPU/메모리/디스크/상위 프로세스를 읽어
'일반 사람이 읽는 문장' 과 함께 돌려준다. 읽기 전용(시스템을 바꾸지 않음)."""
import psutil


def _top_processes(n=7):
    """메모리 많이 쓰는 순 상위 n개 — 작업관리자의 핵심만. 이름이 같은 프로세스(크롬 탭 등)는 합친다."""
    merged = {}
    for p in psutil.process_iter(['name', 'memory_info', 'cpu_percent']):
        try:
            name = p.info['name'] or '?'
            m = merged.setdefault(name, {'name': name, 'mem': 0, 'cpu': 0.0, 'count': 0})
            m['mem'] += p.info['memory_info'].rss if p.info['memory_info'] else 0
            m['cpu'] += p.info['cpu_percent'] or 0.0
            m['count'] += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    top = sorted(merged.values(), key=lambda x: -x['mem'])[:n]
    return [{'name': t['name'], 'mem_mb': round(t['mem'] / 2**20), 'count': t['count']} for t in top]


def _plain_summary(cpu, mem, disk):
    """숫자를 모르는 사람을 위한 한 줄 진단"""
    if cpu >= 85: return '지금 컴퓨터가 매우 바빠요 — 무거운 프로그램이 돌고 있어요.'
    if mem.percent >= 90: return '메모리가 거의 꽉 찼어요 — 안 쓰는 프로그램을 닫으면 빨라져요.'
    if disk.percent >= 90: return '디스크가 거의 꽉 찼어요 — 캐시 청소 탭에서 공간을 비워 보세요.'
    if cpu >= 50 or mem.percent >= 75: return '컴퓨터가 조금 바쁘지만 정상 범위예요.'
    return '컴퓨터 상태가 쾌적해요.'


def status():
    cpu = psutil.cpu_percent(interval=0.4)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('C:\\')
    return {
        'cpu_percent': cpu,
        'mem_percent': mem.percent,
        'mem_used_gb': round(mem.used / 2**30, 1),
        'mem_total_gb': round(mem.total / 2**30, 1),
        'disk_percent': disk.percent,
        'disk_free_gb': round(disk.free / 2**30, 1),
        'disk_total_gb': round(disk.total / 2**30, 1),
        'top': _top_processes(),
        'summary': _plain_summary(cpu, mem, disk),
    }
