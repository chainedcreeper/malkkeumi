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

// ── 상태 탭 (3초마다 갱신) ──
async function refreshStatus() {
  try {
    const s = await api().status();
    $('summary').textContent = s.summary;
    const set = (g, t, pct, label) => {
      $(g).style.width = pct + '%'; $(g).className = pct >= 85 ? 'hot' : '';
      $(t).textContent = label;
    };
    set('g-cpu', 't-cpu', s.cpu_percent, s.cpu_percent + '%');
    set('g-mem', 't-mem', s.mem_percent, `${s.mem_used_gb} / ${s.mem_total_gb} GB`);
    set('g-disk', 't-disk', s.disk_percent, `남은 공간 ${s.disk_free_gb} GB`);
    $('toplist').innerHTML = s.top.map(t =>
      `<div class="row"><span class="grow">${esc(t.name)}${t.count > 1 ? ` <span class="dim">×${t.count}</span>` : ''}</span><span>${MB(t.mem_mb)}</span></div>`).join('');
  } catch (e) { /* 브리지 준비 전 */ }
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
async function cleanOne(path, name) {
  const pv = await api().cache_preview(path);
  if (!confirm(`[${name}]\n${pv.count}개 항목, 총 ${MB(pv.total_mb)} 를 휴지통으로 비울까요?\n(사용 중인 파일은 자동으로 건너뜀)`)) return;
  const res = await api().cache_clean(path, false);
  alert(res.error ? '실패: ' + res.error : `${MB(res.freed_mb)} 비웠어요 (건너뜀 ${res.skipped}개 — 사용 중)`);
  cacheCheck();
}
async function discover() {
  $('discover-card').style.display = 'block';
  $('discoverlist').textContent = 'AppData 전체를 뒤지는 중... (수십 초 걸릴 수 있어요)';
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
    items.map(i => `
    <div class="row">
      <span style="width:110px" class="dim">${esc(i.kind)}</span>
      <span class="grow">${i.suspect ? '⚠️ ' : ''}<b>${esc(i.name)}</b><br><span class="dim">${esc(i.detail)}</span></span>
    </div>`).join('');
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
  const r = await api().unused_programs();
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

// ── 시작 ──
for (let h = 0; h < 24; h++) $('sched-hour').insertAdjacentHTML('beforeend', `<option ${h === 21 ? 'selected' : ''}>${h}</option>`);
window.addEventListener('pywebviewready', () => {
  refreshStatus(); setInterval(refreshStatus, 3000);
  cacheCheck(); adblockBox(); schedState();
});
