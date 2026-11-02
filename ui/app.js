// 말끔이 화면 로직 — 기능 우선 단계. pywebview JS 브리지(window.pywebview.api.*) 호출.
const $ = id => document.getElementById(id);
const api = () => window.pywebview.api;
const MB = n => n >= 1024 ? (n / 1024).toFixed(1) + ' GB' : n + ' MB';
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// ── 탭 ──
document.querySelectorAll('nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('nav button').forEach(x => x.classList.remove('on'));
  document.querySelectorAll('main section').forEach(x => x.classList.remove('on'));
  b.classList.add('on'); $(b.dataset.tab).classList.add('on');
});

// ── 상태 탭: 작업관리자 대체 (3초마다 갱신) ──
async function refreshStatus() {
  try {
    const s = await api().status();
    $('summary').innerHTML = esc(s.summary) + (s.saved_total_mb > 0
      ? `<br><span class="dim">지금까지 말끔이가 비운 공간: <b>${MB(s.saved_total_mb)}</b> · 디스크 남은 공간 ${s.disk_free_gb}GB</span>`
      : `<br><span class="dim">디스크 남은 공간 ${s.disk_free_gb}GB / ${s.disk_total_gb}GB</span>`);
    const set = (g, t, pct, label) => {
      $(g).style.width = Math.min(100, pct) + '%'; $(g).className = pct >= 85 ? 'hot' : '';
      $(t).innerHTML = label;
    };
    set('g-cpu', 't-cpu', s.cpu_percent, `${s.cpu_percent}<small>%</small>`);
    set('g-mem', 't-mem', s.mem_percent, `${s.mem_used_gb}<small> / ${s.mem_total_gb} GB</small>`);
    if (s.gpu) {
      set('g-gpu', 't-gpu', s.gpu.util, `${s.gpu.util}<small>% · VRAM ${s.gpu.vram_used_gb}/${s.gpu.vram_total_gb}GB</small>`);
    } else { $('t-gpu').innerHTML = '<small>감지 안 됨</small>'; }
    const temps = [];
    if (s.cpu_temp !== null) temps.push(`CPU ${s.cpu_temp}°`);
    if (s.gpu) temps.push(`GPU ${s.gpu.temp}°`);
    $('t-temp').innerHTML = temps.length ? temps.join(' <small>·</small> ') : '<small>센서 없음</small>';
    $('t-temp-sub').textContent = s.cpu_temp === null ? 'CPU 온도는 이 보드가 제공하지 않아요' : '';
    window._top = s.top;
    $('toplist').innerHTML = s.top.map((t, i) => `
      <div class="row">
        <span style="width:24px;text-align:right" class="dim">${i + 1}</span>
        <span class="grow">${esc(t.name)}${t.count > 1 ? ` <span class="dim">×${t.count}</span>` : ''}</span>
        <span style="width:90px;text-align:right">CPU ${t.cpu}%</span>
        <span style="width:90px;text-align:right">${MB(t.mem_mb)}</span>
        ${t.protected ? '<span class="dim" style="width:64px;text-align:center">시스템</span>'
                      : `<button class="act danger" style="width:64px" onclick="killProc(${i})">종료</button>`}
      </div>`).join('');
  } catch (e) { /* 브리지 준비 전 */ }
}
async function killProc(i) {
  const t = window._top[i];
  const extra = t.warn ? '\n(이걸 끄면 바탕화면·작업표시줄이 잠깐 깜빡여요 — 윈도우가 다시 살려요)' : '';
  if (!confirm(`[${t.name}] ${t.count}개 프로세스를 종료해요.\n저장 안 한 작업이 있으면 날아가요!${extra}\n종료할까요?`)) return;
  const r = await api().proc_kill(t.name, t.pids);
  if (!r.ok) alert(r.error); else if (r.failed) alert(`${r.done}개 종료, ${r.failed}개는 권한 부족으로 실패`);
  refreshStatus();
}

// ── 테마 (화이트/다크/저자극 — 선택 기억) ──
function applyTheme(v) {
  document.documentElement.dataset.theme = v;
  localStorage.setItem('theme', v);
  $('theme-sel').value = v;
}

// ── 캐시 탭 ──
async function cacheCheck() {
  $('cachelist').textContent = '용량 재는 중...';
  const rows = await api().cache_check();
  $('cachelist').innerHTML = rows.map(r => `
    <div class="row">
      <span class="grow"><b>${esc(r.name)}</b><br><span class="dim">${esc(r.path)}</span></span>
      <span class="${r.over ? 'warn' : ''}">${r.exists ? MB(r.size_mb) : '없음'} / 기준 ${MB(r.limit_mb)}</span>
      <span class="dim">${r.last_clean ? '청소: ' + r.last_clean : ''}</span>
      ${r.exists ? `<button class="act" onclick="cleanOne('${esc(r.path).replace(/\\/g, '\\\\')}', '${esc(r.name)}')">비우기</button>` : ''}
    </div>`).join('') || '<span class="muted">등록된 대상이 없어요 — 자동 서치를 눌러 보세요.</span>';
}
async function cleanWithProgress(path, name) {
  // 비우기 실행 + 목록 상단에 % 진행 표시 — alert 대신 인라인 결과 배너
  const st = await api().cache_clean_start(path, name);
  if (!st.ok) { alert(st.error); return null; }
  return await new Promise(resolve => {
    const iv = setInterval(async () => {
      const p = await api().cache_clean_progress(path);
      $('cachelist').innerHTML = progressBar(p.pct, p.stage);
      if (!p.running && p.result) { clearInterval(iv); resolve(p.result); }
    }, 300);
  });
}
async function cleanOne(path, name) {
  const pv = await api().cache_preview(path);
  if (!confirm(`[${name}]\n${pv.count}개 항목, 총 ${MB(pv.total_mb)} 를 휴지통으로 비울까요?\n(사용 중인 파일은 자동으로 건너뜀)`)) return;
  const res = await cleanWithProgress(path, name);
  await cacheCheck();
  if (res) $('cachelist').insertAdjacentHTML('afterbegin', res.error
    ? `<div class="notice">실패: ${esc(res.error)}</div>`
    : `<div class="notice">✅ [${esc(name)}] <b>${MB(res.freed_mb)}</b> 비웠어요 — ${res.removed}개 휴지통행${res.skipped ? `, ${res.skipped}개는 사용 중이라 건너뜀` : ''}</div>`);
}
async function discover() {
  $('discover-card').style.display = 'block';
  $('discoverlist').textContent = 'AppData 전체를 뒤지는 중... (몇 초면 끝나요)';
  const found = await api().cache_discover();
  $('discoverlist').innerHTML = found.map((f, i) => `
    <div class="row">
      <span class="grow"><b>${esc(f.app)}</b><br><span class="dim">${esc(f.path)}</span></span>
      <span>${MB(f.size_mb)}</span>
      <button class="act" onclick="registerOne(${i})">등록</button>
    </div>`).join('') || '<span class="muted">새로 찾은 캐시가 없어요.</span>';
  window._found = found;
}
async function registerOne(i) {
  const f = window._found[i];
  const lim = prompt(`[${f.app}] 임계치(MB)를 정해 주세요 — 이 용량을 넘으면 청소 대상으로 표시돼요`, '512');
  if (!lim) return;
  await api().cache_register(`${f.app} 캐시`, f.path, parseInt(lim) || 512);
  cacheCheck(); discover();
}

async function cleanAllOver() {
  const rows = (await api().cache_check()).filter(r => r.over && r.exists);
  if (!rows.length) return alert('기준(임계치)을 넘은 캐시가 없어요 — 깨끗!');
  const total = rows.reduce((a, r) => a + r.size_mb, 0);
  if (!confirm(`기준 넘은 ${rows.length}곳(${rows.map(r => r.name).join(', ')}) 총 ${MB(total)} 를\n휴지통으로 한 번에 비울까요?`)) return;
  let freed = 0;
  for (let i = 0; i < rows.length; i++) {
    const res = await cleanWithProgress(rows[i].path, `(${i + 1}/${rows.length}) ${rows[i].name}`);
    if (res) freed += res.freed_mb || 0;
  }
  await cacheCheck(); recycleState();
  $('cachelist').insertAdjacentHTML('afterbegin',
    `<div class="notice">✅ ${rows.length}곳에서 총 <b>${MB(freed)}</b> 비웠어요</div>`);
}

// ── 악성 점검 탭 ──
async function defenderBox() {
  const d = await api().defender_status();
  $('defender-box').innerHTML = d.ok
    ? `<div class="row"><span class="grow">실시간 보호 ${d.realtime ? '<span class="ok">켜짐 ✓</span>' : '<span class="warn">꺼짐!</span>'}
         <span class="dim"> · 백신 정의 ${esc(d.sig_date)} · 마지막 빠른 검사 ${esc(d.last_quick)}</span></span>
       <button class="act" onclick="defenderScan()">빠른 검사 실행</button></div>`
    : '<span class="muted">Defender 상태를 읽을 수 없어요 (다른 백신을 쓰는 중일 수 있어요)</span>';
}
async function defenderScan() {
  const r = await api().defender_quick_scan();
  alert(r.msg);
}
function progressBar(pct, stage) {
  return `<div class="row"><div class="gauge" style="max-width:420px"><div style="width:${pct}%"></div></div>
    <span style="width:52px;text-align:right"><b>${pct}%</b></span><span class="dim">${esc(stage)}</span></div>`;
}
async function malScan() {
  const st = await api().mal_scan_start();
  if (!st.ok) return alert(st.error);
  const r = await new Promise(resolve => {
    const iv = setInterval(async () => {
      const p = await api().mal_scan_progress();
      $('mallist').innerHTML = progressBar(p.pct, p.stage);
      if (!p.running && p.result) { clearInterval(iv); resolve(p.result); }
    }, 400);
  });
  if (r.error) { $('mallist').innerHTML = `<span class="muted">점검 실패: ${esc(r.error)}</span>`; return; }
  const c = r.counts;
  const head = c.bad ? `<div class="notice">🚨 <b>악성 해시 DB와 일치하는 파일 ${c.bad}개!</b> — 직접 지우지 말고 Defender 전체 검사를 돌리세요.</div>`
    : `<div class="row"><b>${c.warn ? `⚠️ 점검 권장 ${c.warn}개` : '✅ 의심 신호 없음'}</b> <span class="dim">(실행파일 ${r.items.length}개 점검 · 악성 확정 0)</span></div>`;
  $('mallist').innerHTML = head + r.items.filter(i => i.level !== 'ok').map(i => `
    <div class="row">
      <span class="lv-${i.level}" style="width:52px">${i.level === 'bad' ? '위험' : '주의'}</span>
      <span class="grow"><b>${esc(i.name)}</b> <span class="dim">· ${esc(i.origin)}</span><br>
        <span class="dim">${esc(i.flags.join(' · '))}${i.db_checked ? ' · 해시 DB 조회함' : ''}</span><br>
        <span class="dim">${i.created ? `생성/다운로드 ${i.created}` : ''}${i.source ? ` · 출처 ${esc(i.source)} (인터넷에서 받음)` : ''}</span>
        <span class="dim">${esc(i.path)}</span></span>
    </div>`).join('') + (c.warn || c.bad ? '' : '<div class="dim" style="padding-top:8px">전체 목록은 신호가 있을 때만 표시해요.</div>');
}

// ── 휴지통 ──
async function recycleState() {
  const r = await api().recycle_status();
  $('recycle-state').textContent = r.ok ? `${r.items}개 항목 · ${MB(r.size_mb)}` : '상태를 읽을 수 없음';
}
async function recycleEmpty() {
  const r = await api().recycle_status();
  if (!r.items) return alert('휴지통이 이미 비어 있어요');
  if (!confirm(`휴지통의 ${r.items}개 항목(${MB(r.size_mb)})을 완전히 삭제해요.\n이건 되돌릴 수 없어요 — 비울까요?`)) return;
  const e = await api().recycle_empty();
  alert(e.ok ? `${MB(e.freed_mb)} 확보!` : '비우기 실패');
  recycleState();
}

// ── 광고 탭 ──
async function adblockBox() {
  const s = await api().adblock_status();
  $('adblock-box').innerHTML = s.applied
    ? `<span class="ok">✅ 차단 적용 중 — 광고 도메인 ${s.lines.toLocaleString()}개</span>
       <button class="act" onclick="adblockOff()">해제(원복)</button>`
    : `<span>⛔ 차단 꺼짐</span> <button class="act" onclick="adblockOn()">차단 적용</button>
       <span class="dim">${s.admin ? '' : '· 적용하려면 관리자 권한으로 실행 필요'}</span>`;
}
async function adblockOn() {
  if (!confirm('hosts 파일에 광고 도메인 차단 목록(StevenBlack)을 추가해요.\n원본은 자동 백업되고 언제든 원클릭으로 해제돼요.\n진행할까요?')) return;
  $('adblock-box').textContent = '목록 받는 중...';
  const r = await api().adblock_apply();
  alert(r.ok ? `적용 완료 — ${r.lines.toLocaleString()}개 도메인 차단` : r.error);
  adblockBox();
}
async function adblockOff() {
  const r = await api().adblock_restore();
  alert(r.ok ? '해제 완료 — 기존 hosts 내용은 그대로예요' : r.error);
  adblockBox();
}
async function adScan() {
  $('adlist').textContent = '스캔 중... (작업 스케줄러 조회로 수십 초 걸릴 수 있어요)';
  const items = await api().ad_scan();
  const n = items.filter(i => i.suspect).length;
  $('adlist').innerHTML =
    `<div class="row"><b>${n ? '⚠️ 주의 항목 ' + n + '개' : '✅ 광고성으로 보이는 항목 없음'}</b> <span class="dim">(전체 ${items.length}개 점검)</span></div>` +
    items.map((i, idx) => `
    <div class="row">
      <span style="width:110px" class="dim">${esc(i.kind)}</span>
      <span class="grow">${i.suspect ? '⚠️ ' : ''}${i.enabled === false ? '<s>' : ''}<b>${esc(i.name)}</b>${i.enabled === false ? '</s> <span class="dim">(꺼짐)</span>' : ''}<br><span class="dim">${esc(i.detail)}</span></span>
      ${i.ctl ? `<button class="act" onclick="startupToggle(${idx}, ${i.enabled === false})">${i.enabled === false ? '켜기' : '끄기'}</button>` : ''}
    </div>`).join('');
  window._aditems = items;
}

async function startupToggle(idx, enable) {
  const i = window._aditems[idx];
  const what = enable ? '다시 켜요' : '꺼요 (삭제 아님 — 작업관리자 방식, 언제든 되돌림)';
  if (!confirm(`[${i.name}] 자동 실행을 ${what}.
진행할까요?`)) return;
  const r = await api().startup_toggle(i.ctl, enable);
  alert(r.ok ? '완료 — 다음 부팅/로그인부터 적용돼요' : '실패: ' + r.error);
  adScan();
}

// ── 중복 파일 탭 ──
async function dupesFind() {
  $('dupeslist').textContent = '스캔 중... (파일 수에 따라 수십 초)';
  const r = await api().dupes_find($('dupes-min').value);
  if (!r.groups.length) { $('dupeslist').innerHTML = '<span class="muted">중복 파일이 없어요. 깨끗!</span>'; return; }
  $('dupeslist').innerHTML =
    `<div class="notice">같은 파일이 겹쳐서 낭비되는 공간: <b>${MB(r.wasted_total_mb)}</b></div>` +
    r.groups.map((g, gi) => `
    <div class="row"><span class="grow">
      ${g.files.map((f, i) => `<div>${i === 0 ? '📌 ' : '🔁 '}<span class="dim">${esc(f)}</span></div>`).join('')}
    </span><span>${MB(g.size_mb)} ×${g.files.length}</span>
    <span style="display:flex;gap:4px;flex-direction:column">
      <button class="act" onclick="dupesAct(${gi}, 'keep')">보관함 분리</button>
      <button class="act" onclick="dupesAct(${gi}, 'desktop')">바탕화면 모음</button>
      <button class="act danger" onclick="dupesAct(${gi}, 'trash')">휴지통 삭제</button>
    </span></div>`).join('');
  window._dupes = r.groups;
}
async function dupesAct(gi, mode) {
  const paths = window._dupes[gi].files.slice(1);   // 첫 파일은 원본으로 남김
  const what = {keep: '「말끔이 보관함」으로 옮겨요 (되돌리기 지원)',
                desktop: '바탕화면 「중복 파일 모음」 폴더로 옮겨요',
                trash: '휴지통으로 삭제해요'}[mode];
  if (!confirm(`사본 ${paths.length}개를 ${what}.
(첫 번째 파일은 원본으로 남겨요)`)) return;
  let msg;
  if (mode === 'keep') { const r = await api().unused_separate(paths); msg = `옮김 ${r.moved}개 — ${r.archive}`; }
  else if (mode === 'desktop') { const r = await api().dupes_move_desktop(paths); msg = `옮김 ${r.moved}개 — ${r.dest}`; }
  else { const r = await api().dupes_trash(paths); msg = `휴지통으로 ${r.done}개`; }
  alert(msg);
  dupesFind();
}

// ── 파일 정리(해석 후 삭제) 탭 ──
async function filesBrowse() {
  $('fileslist').textContent = '읽는 중...';
  const r = await api().files_browse($('files-where').value);
  if (r.error) { $('fileslist').innerHTML = `<span class="muted">${esc(r.error)}</span>`; return; }
  window._files = r.items;
  $('fileslist').innerHTML = r.items.map((f, i) => `
    <div class="row">
      <input type="checkbox" class="ftrash" value="${i}">
      <span class="grow"><b>${esc(f.name)}</b><br>
        <span class="dim">${esc(f.kind)} · ${MB(f.size_mb)} · ${f.created}${f.hint ? ` · <span class="ok">${esc(f.hint)}</span>` : ''}</span></span>
      <button class="act danger" onclick="filesTrashOne(${i})">휴지통</button>
    </div>`).join('') || '<span class="muted">파일이 없어요.</span>';
}
async function filesTrashOne(i) {
  const f = window._files[i];
  if (!confirm(`[${f.name}] 휴지통으로 보낼까요?`)) return;
  await api().trash_paths([f.path]);
  filesBrowse();
}
async function filesTrashChecked() {
  const idx = [...document.querySelectorAll('.ftrash:checked')].map(c => +c.value);
  if (!idx.length) return alert('삭제할 파일을 체크하세요');
  const total = idx.reduce((a, i) => a + window._files[i].size_mb, 0);
  if (!confirm(`${idx.length}개 파일(${MB(Math.round(total))})을 휴지통으로 보낼까요?`)) return;
  const r = await api().trash_paths(idx.map(i => window._files[i].path));
  alert(`휴지통으로 ${r.done}개${r.skipped ? `, 실패 ${r.skipped}개` : ''}`);
  filesBrowse();
}

// ── 디스크 지도 탭: 측정한 폴더를 캐시에 쌓아 '펼침/접힘 트리'로 누적 재구성 ──
// 경로는 HTML 속성에 넣지 않는다(이스케이프 지옥) — 노드 배열 인덱스로만 참조
window._diskCache = {};   // 경로 -> 측정 결과
window._diskOpen = {};    // 경로 -> 펼침 여부
window._diskRoot = null;
window._diskNodes = [];   // 이번 렌더의 행 인덱스 -> 항목
window._diskRoots = [];
const dnorm = p => p.toLowerCase().replace(/\\+$/, '');

async function diskMeasure(path) {
  const st = await api().disk_start(path);
  if (!st.ok) return null;
  const r = await new Promise(resolve => {
    const iv = setInterval(async () => {
      const p = await api().disk_progress();
      $('disk-busy').innerHTML = progressBar(p.pct, p.stage);
      if (!p.running && p.result) { clearInterval(iv); resolve(p.result); }
    }, 300);
  });
  $('disk-busy').innerHTML = '';
  if (r.error) { $('disk-busy').innerHTML = `<span class="muted">${esc(r.error)}</span>`; return null; }
  window._diskCache[dnorm(r.path)] = r;
  return r;
}
function diskTreeHTML(path, depth) {
  const r = window._diskCache[dnorm(path)];
  if (!r) return '';
  return r.items.map(i => {
    const key = dnorm(i.path);
    const cached = !!window._diskCache[key];
    const open = cached && window._diskOpen[key];
    const idx = window._diskNodes.push(i) - 1;
    const pad = 14 + depth * 22;
    const toggle = i.is_dir
      ? `<a href="#" onclick="diskToggle(${idx}); return false" style="font-weight:600">${open ? '▾' : '▸'} 📁 ${esc(i.name)}</a>`
      : `<a href="#" onclick="diskOpen(${idx}); return false"><span class="dim">▪</span> ${esc(i.name)}</a>`;
    return `
    <div class="row" style="padding-left:${pad}px" oncontextmenu="diskCopy(${idx}); return false" title="우클릭: 경로 복사">
      <span class="grow">${toggle}</span>
      <button class="act" style="padding:2px 7px;font-size:11px" onclick="diskOpen(${idx})" title="탐색기에서 열기">📂</button>
      <div class="gauge" style="max-width:150px"><div style="width:${Math.min(100, i.pct)}%"></div></div>
      <span style="width:48px;text-align:right" class="dim">${i.pct}%</span>
      <span style="width:92px;text-align:right">${i.capped ? '약 ' : ''}${MB(i.size_mb)}${i.capped ? '+' : ''}</span>
    </div>` + (open ? diskTreeHTML(i.path, depth + 1) : '');
  }).join('');
}
function diskRender() {
  const root = window._diskCache[dnorm(window._diskRoot)];
  if (!root) return;
  window._diskNodes = [];
  $('disk-path').innerHTML = `${esc(root.path)} — 합계 약 ${MB(root.total_mb)} <span class="dim">(폴더를 누르면 안을 재서 트리에 쌓아요)</span>`;
  $('disklist').innerHTML = diskTreeHTML(window._diskRoot, 0) || '<span class="muted">비어 있음</span>';
}
async function diskOpen(idx) {
  await api().open_in_explorer(window._diskNodes[idx].path);
}
async function diskCopy(idx) {
  const p = window._diskNodes[idx].path;
  const r = await api().copy_path(p);
  $('disk-busy').innerHTML = r.ok ? `<span class="ok">📋 경로 복사됨:</span> <span class="dim">${esc(p)}</span>` : '복사 실패';
  setTimeout(() => { if ($('disk-busy').innerHTML.includes('복사')) $('disk-busy').innerHTML = ''; }, 2500);
}
async function diskToggle(idx) {
  const i = window._diskNodes[idx];
  const key = dnorm(i.path);
  if (window._diskOpen[key]) { window._diskOpen[key] = false; diskRender(); return; }
  if (!window._diskCache[key]) { if (!await diskMeasure(i.path)) return; }
  window._diskOpen[key] = true; diskRender();
}
async function diskGo(path) {
  if (!await diskMeasure(path)) return;
  window._diskRoot = path; diskRender();
}
function diskGoRoot(i) { diskGo(window._diskRoots[i].path); }
async function diskRoots() {
  const roots = await api().disk_roots();
  window._diskRoots = roots;
  $('disk-roots').innerHTML = roots.map((r, i) =>
    `<button class="act" onclick="diskGoRoot(${i})">${esc(r.name)}</button>`).join(' ');
}

// ── 모서리 위젯 ──
async function widgetToggle() {
  const r = await api().widget_toggle();
  $('widget-btn').textContent = r.on ? '📌 위젯 닫기' : '📌 모서리에 띄우기';
}

// ── 광고 차단 자가진단 ──
async function adblockTest() {
  $('adblock-test').innerHTML = '<span class="dim">대표 광고 도메인 3곳에 실제 연결을 시도하는 중...</span>';
  const r = await api().adblock_test();
  $('adblock-test').innerHTML =
    `<div class="row"><b>${r.all_blocked ? '✅ 차단 작동 중' : '⚠️ 일부가 안 막혀요 (차단 꺼짐이거나 브라우저 DoH)'}</b></div>` +
    r.items.map(i => `<div class="row"><span class="grow dim">${esc(i.domain)}</span>
      <span class="${i.blocked ? 'ok' : 'warn'}">${i.blocked ? '차단됨 (' + esc(i.ip) + ')' : '뚫림 → ' + esc(i.ip)}</span></div>`).join('');
}

// ── 안 쓰는 것 탭 ──
async function unusedScan() {
  $('unusedlist').textContent = '스캔 중...';
  const r = await api().unused_scan($('unused-days').value);
  $('unused-notice').innerHTML = r.notice ? `<div class="notice">🔔 ${esc(r.notice)}</div>` : '';
  $('unusedlist').innerHTML = r.items.map((f, i) => `
    <div class="row">
      <input type="checkbox" class="sep" value="${i}">
      <span class="grow"><b>${esc(f.name)}</b> <span class="dim">(${f.kind} · ${esc(f.where)})</span><br>
        <span class="dim">마지막 사용 ${f.last_used} — ${f.days}일 전</span></span>
      <span>${MB(f.size_mb)}</span>
    </div>`).join('') || '<span class="muted">기준 기간 안에서 안 쓰는 큰 덩어리가 없어요. 깨끗!</span>';
  window._unused = r.items;
}
async function separateChecked() {
  const idx = [...document.querySelectorAll('.sep:checked')].map(c => +c.value);
  if (!idx.length) return alert('분리할 항목을 체크하세요');
  const paths = idx.map(i => window._unused[i].path);
  if (!confirm(`${paths.length}개를 바탕화면 「말끔이 보관함」으로 옮겨요. (삭제 아님 — 언제든 되돌리기 가능)`)) return;
  const r = await api().unused_separate(paths);
  alert(`옮김 ${r.moved}개, 건너뜀 ${r.skipped}개\n위치: ${r.archive}`);
  unusedScan();
}
async function unusedPrograms() {
  $('programlist').textContent = '확인 중...';
  const r = await api().unused_programs($('prog-days').value);
  if (r.error) { $('programlist').innerHTML = `<span class="muted">${esc(r.error)}</span>`; return; }
  $('programlist').innerHTML = r.items.map(p => `
    <div class="row"><span class="grow">${esc(p.name)}</span>
      <span class="dim">마지막 실행 ${p.last_run} (${p.days}일 전)</span></div>`).join('')
    || '<span class="muted">두 달 넘게 안 켠 프로그램이 없어요.</span>';
}

// ── 자동 청소 탭 ──
async function schedState() {
  const s = await api().sched_status();
  $('sched-state').textContent = s.registered ? '✅ 등록돼 있음 (매일 실행)' : '등록 안 됨';
}
async function schedOn() {
  const r = await api().sched_register($('sched-hour').value);
  alert(r.ok ? '등록 완료 — 매일 자동으로 점검·청소해요' : '실패: ' + r.msg);
  schedState();
}
async function schedOff() {
  const r = await api().sched_unregister();
  alert(r.ok ? '해제 완료' : '실패: ' + r.msg);
  schedState();
}

// ── 업데이트 ──
async function updateCheck() {
  const u = await api().update_check();
  if (u.remote === null) { $('update-state').textContent = `버전 ${u.local} · 업데이트 확인 불가(오프라인?)`; return; }
  $('update-state').textContent = u.newer
    ? `새 버전 있어요! ${u.local} → ${u.remote}` : `최신 버전이에요 (${u.local})`;
  $('update-btn').style.display = u.newer ? '' : 'none';
}
async function updateRun() {
  const r = await api().update_run();
  alert(r.msg + (r.detail ? '\n' + r.detail : ''));
  if (r.open) window.open(r.open);
  updateCheck();
}

// ── 시작 ──
for (let h = 0; h < 24; h++) $('sched-hour').insertAdjacentHTML('beforeend', `<option ${h === 21 ? 'selected' : ''}>${h}</option>`);
applyTheme(localStorage.getItem('theme') || 'light');
$('theme-sel').onchange = e => applyTheme(e.target.value);
window.addEventListener('pywebviewready', () => {
  refreshStatus(); setInterval(refreshStatus, 3000);
  cacheCheck(); adblockBox(); schedState(); updateCheck(); recycleState(); diskRoots(); defenderBox();
});
