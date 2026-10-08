/* AX 룰랩 화면 (프레임워크 없이 순수 JavaScript). 주소의 #/ 뒤 경로로 화면을 바꿔요.
   #/  홈   #/c/005930  종목   #/rules  내 규칙   #/rules/3  규칙 상세(백테스트)   #/account  모의투자 */
'use strict'

// ───────── 공통 도구 ─────────
const $ = (s, r = document) => r.querySelector(s)
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
const num = (n) => Math.round(n).toLocaleString('ko-KR')
const won = (n) => `${num(n)}원`
const pct = (r, d = 2) => (r == null ? '-' : `${r > 0 ? '+' : r < 0 ? '-' : ''}${Math.abs(r).toFixed(d)}%`)
const tone = (r) => (r > 0 ? 'up' : r < 0 ? 'down' : 'flat') // 한국 관례: 상승·이익 빨강, 하락·손실 파랑
const d10 = (d) => String(d).slice(0, 10)
const REASON = { tp: '익절', sl: '손절', time: '기간 만료', end: '데이터 끝' }
const ENTRY = { ma_cross: '이동평균선 상향 돌파', dip_buy: '급락일 매수', breakout: '신고가 돌파' }
const PERIOD = { '6m': '최근 6개월', '1y': '최근 1년', all: '전체 기간' }
const PRESETS = [
  { name: '20일선 돌파', entry_type: 'ma_cross', entry_param: 20, take_profit_pct: 8, stop_loss_pct: 4, max_hold_days: 20 },
  { name: '급락 줍기', entry_type: 'dip_buy', entry_param: 4, take_profit_pct: 6, stop_loss_pct: 5, max_hold_days: 10 },
  { name: '20일 신고가 돌파', entry_type: 'breakout', entry_param: 20, take_profit_pct: 10, stop_loss_pct: 5, max_hold_days: 30 },
]

function ruleText(r) {
  const p = Number(r.entry_param)
  const e = { ma_cross: `종가가 ${Math.round(p)}일선을 위로 뚫으면 매수`, dip_buy: `하루 ${p}% 이상 떨어지면 매수`, breakout: `종가가 직전 ${Math.round(p)}일 최고가를 넘으면 매수` }[r.entry_type]
  return `${e} → +${Number(r.take_profit_pct)}% 익절 / -${Number(r.stop_loss_pct)}% 손절 / 최대 ${Number(r.max_hold_days)}일 보유`
}

function clientId() {
  try {
    let id = localStorage.getItem('axrule-client-id')
    if (!id) {
      id = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()) + Math.random().toString(16).slice(2)
      localStorage.setItem('axrule-client-id', id)
    }
    return id
  } catch (e) {
    return 'anonymous'
  }
}

async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: { 'X-Client-Id': clientId(), ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (res.status === 204) return null
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const d = data.detail
    throw new Error(typeof d === 'string' ? d : Array.isArray(d) ? '입력값을 확인해 주세요.' : `요청에 실패했어요 (${res.status})`)
  }
  return data
}
const get = (p) => api('GET', p)

const app = $('#app')
let token = 0 // 화면이 바뀐 뒤 늦게 도착한 응답은 버려요
const stale = (t) => t !== token
const loading = () => (app.innerHTML = '<div class="page"><p class="panel-loading">불러오는 중…</p></div>')
const fail = (e) => (app.innerHTML = `<div class="page"><p class="empty err">${esc(e.message)}</p></div>`)
const msg = (el, text, ok = false) => el && ((el.textContent = text), (el.className = `msg ${ok ? 'ok' : 'err'}`))

// ───────── 차트 ─────────
// ov = { segments: [{entry_date, exit_date, return_pct}], marks: [{d, side, text}], volume: true, label: '종가', fmt: (v) => 문자열 }
function drawChart(box, prices, ov = {}) {
  const n = prices.length
  if (n < 2) return (box.innerHTML = '<p class="empty">시세가 없어요.</p>')
  const VH = ov.volume ? 58 : 0, W = 760, H = 300 + VH, L = 62, R = 10, T = 10, B = 26 + VH, fmt = ov.fmt || num, label = ov.label || '종가'
  const cl = prices.map((p) => p.close), lo = Math.min(...cl), hi = Math.max(...cl), pad = (hi - lo) * 0.08 || 1
  const y0 = lo - pad, y1 = hi + pad
  const X = (i) => L + (i / (n - 1)) * (W - L - R)
  const Y = (v) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B)
  const idx = new Map(prices.map((p, i) => [d10(p.d), i]))
  const line = prices.map((p, i) => `${X(i).toFixed(1)},${Y(p.close).toFixed(1)}`).join(' ')
  const grid = [0, 1, 2, 3].map((k) => { const v = y0 + ((y1 - y0) * k) / 3; return `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" class="grid"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" class="tick">${fmt(v)}</text>` }).join('')
  let last = '', ticks = ''
  prices.forEach((p, i) => { const m = d10(p.d).slice(0, 7); if (m !== last) { last = m; if (i > 3 && i < n - 3) ticks += `<text x="${X(i)}" y="${H - 8}" text-anchor="middle" class="tick">${Number(m.slice(5))}월</text>` } })
  const segs = (ov.segments || []).map((s) => {
    const a = idx.get(d10(s.entry_date)), b = idx.get(d10(s.exit_date))
    if (a == null || b == null) return ''
    const pts = []
    for (let i = a; i <= b; i++) pts.push(`${X(i).toFixed(1)},${Y(cl[i]).toFixed(1)}`)
    if (pts.length < 2) pts.push(pts[0])
    return `<g class="bt ${tone(s.return_pct)}"><polyline points="${pts.join(' ')}"/><circle cx="${X(a)}" cy="${Y(cl[a])}" r="4.5" class="in"/><circle cx="${X(b)}" cy="${Y(cl[b])}" r="4.5" class="out"/></g>`
  }).join('')
  const marks = (ov.marks || []).map((m) => {
    const i = idx.get(d10(m.d)); if (i == null) return ''
    const x = X(i), y = Y(cl[i])
    return m.side === 'buy' ? `<path d="M${x} ${y - 4} l7 -12 h-14 z" class="mk buy"/>` : `<path d="M${x} ${y + 4} l7 12 h-14 z" class="mk sell"/>`
  }).join('')
  let vol = ''
  if (ov.volume) {
    const vmax = Math.max(...prices.map((p) => p.volume || 0), 1), base = H - 26, bw = Math.max(1, (W - L - R) / n - 1)
    vol = `<text x="${L - 6}" y="${base - VH + 30}" text-anchor="end" class="tick">거래량</text>` + prices.map((p, i) => { const h = ((p.volume || 0) / vmax) * (VH - 12); return `<rect x="${(X(i) - bw / 2).toFixed(1)}" y="${(base - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" class="vol ${i && p.close < prices[i - 1].close ? 'dn' : 'upv'}"/>` }).join('')
  }
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)} 차트">${grid}${ticks}${vol}<polyline points="${line}" class="price-line"/>${segs}${marks}
    <line class="cross" x1="0" x2="0" y1="${T}" y2="${H - B}" hidden/><circle class="hover-dot" r="4" hidden/><rect class="hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent"/></svg><div class="chart-tip" hidden></div>`
  const svg = $('svg', box), tip = $('.chart-tip', box), cross = $('.cross', box), dot = $('.hover-dot', box)
  const byDate = {}
  ;(ov.marks || []).forEach((m) => (byDate[d10(m.d)] = (byDate[d10(m.d)] || []).concat(m.text)))
  const move = (e) => {
    const r = svg.getBoundingClientRect(), vx = ((e.clientX - r.left) / r.width) * W
    const i = Math.max(0, Math.min(n - 1, Math.round(((vx - L) / (W - L - R)) * (n - 1))))
    const p = prices[i], x = X(i)
    cross.setAttribute('x1', x); cross.setAttribute('x2', x); dot.setAttribute('cx', x); dot.setAttribute('cy', Y(p.close))
    cross.hidden = dot.hidden = tip.hidden = false
    tip.style.left = `${Math.max(60, Math.min(r.width - 60, (x / W) * r.width))}px`
    tip.innerHTML = `<b>${d10(p.d)}</b><span>${esc(label)} ${ov.fmt ? fmt(p.close) : num(p.close) + '원'}</span>${p.volume != null && ov.volume ? `<span class="mute">거래량 ${num(p.volume)}</span>` : ''}${(byDate[d10(p.d)] || []).map((t) => `<span class="mute">${esc(t)}</span>`).join('')}`
  }
  svg.addEventListener('mousemove', move)
  svg.addEventListener('mouseleave', () => (cross.hidden = dot.hidden = tip.hidden = true))
}

// ───────── 이벤트 위임: data-act(클릭), data-change(변경), data-submit(전송) ─────────
const acts = {}
const go = (h) => (location.hash === h ? route() : (location.hash = h)) // 같은 주소면 hashchange 가 안 와서 직접 다시 그려요
app.addEventListener('click', (e) => { const t = e.target.closest('[data-act]'); if (t && acts[t.dataset.act]) acts[t.dataset.act](t, e) })
app.addEventListener('change', (e) => { const t = e.target.closest('[data-change]'); if (t && acts[t.dataset.change]) acts[t.dataset.change](t, e) })
app.addEventListener('submit', (e) => { const t = e.target.closest('[data-submit]'); if (t) { e.preventDefault(); acts[t.dataset.submit]?.(t, e) } })
const confirmTwice = (btn, label, fn) => { // 한 번 누르면 "정말?" 으로 바뀌고 두 번째 누를 때 실행
  if (btn.dataset.armed) return fn()
  btn.dataset.armed = '1'; btn.dataset.label = btn.textContent; btn.textContent = label
  setTimeout(() => { if (btn.isConnected) { delete btn.dataset.armed; btn.textContent = btn.dataset.label } }, 3000)
}

// ───────── 공용 조각 ─────────
const statBox = (label, value, sub = '', cls = '') => `<div class="stat card"><span class="mute small">${label}</span><b class="${cls}">${value}</b>${sub ? `<span class="mute small">${sub}</span>` : ''}</div>`

function runStats(r) {
  const better = r.total_return != null && r.total_return > r.benchmark_return
  return `<div class="stats">
    ${statBox('거래 횟수', `${r.trade_count}번`, r.trade_count ? `${r.win_count}번 이익 · 승률 ${r.win_rate}%` : '신호가 없었어요')}
    ${statBox('거래당 평균', pct(r.avg_return), '수수료 반영', tone(r.avg_return))}
    ${statBox('누적 수익률', pct(r.total_return), '거래를 복리로 이어 붙임', tone(r.total_return))}
    ${statBox('최대 낙폭', pct(r.mdd), '거래 기준 고점 대비 하락', r.mdd < 0 ? 'down' : '')}
    ${statBox('평균 보유일', r.avg_hold_days == null ? '-' : `${r.avg_hold_days}일`)}
    ${statBox('그냥 들고 있었다면', pct(r.benchmark_return), `${d10(r.start_date)} ~ ${d10(r.end_date)}`, tone(r.benchmark_return))}
  </div>
  ${r.trade_count ? `<p class="verdict ${better ? 'good' : 'bad'}">${better ? '이 기간엔 규칙대로 거래한 쪽이 그냥 들고 있는 것보다 나았어요.' : '이 기간엔 그냥 들고 있는 것이 규칙대로 거래한 것보다 나았어요.'} <span class="mute">(한 종목·한 기간 결과라 우연일 수 있어요)</span></p>` : ''}`
}

function runTrades(trades) {
  if (!trades.length) return '<p class="empty">이 기간에는 진입 신호가 없었어요.</p>'
  return `<div class="scroll card"><table><thead><tr><th>매수일</th><th>매수가</th><th>매도일</th><th>매도가</th><th>이유</th><th>보유</th><th>수익률</th></tr></thead><tbody>
  ${trades.map((t) => `<tr><td>${d10(t.entry_date)}</td><td class="num">${num(t.entry_price)}</td><td>${d10(t.exit_date)}</td><td class="num">${num(t.exit_price)}</td><td>${REASON[t.exit_reason]}</td><td class="num">${t.hold_days}일</td><td class="num ${tone(t.return_pct)}">${pct(t.return_pct)}</td></tr>`).join('')}</tbody></table></div>`
}

const seg = (name, opts, cur) => `<div class="seg" role="group">${opts.map(([v, l]) => `<button type="button" data-act="${name}" data-v="${v}" aria-pressed="${v === cur}">${l}</button>`).join('')}</div>`

// ───────── 홈: 종목 분석 대시보드 ─────────
const D = { data: null, sort: 'score', desc: true, sector: '' }
const COLS = [ // [키, 머리글, 형식, 설명]
  ['name', '종목', 's'], ['close', '현재가', 'won'], ['chg', '등락', 'pct'], ['r1m', '1개월', 'pct'], ['r3m', '3개월', 'pct'], ['r6m', '6개월', 'pct'],
  ['ma_gap', '120일선', 'pct', '120일 평균 대비'], ['vol_ratio', '거래량', 'x', '오늘 ÷ 20일 평균'], ['per', 'PER', 'n1'], ['pbr', 'PBR', 'n2'],
  ['op_margin', '영업이익률', 'p1'], ['rev_growth', '매출성장', 'pct1'], ['score', '점수', 'score'],
]
function cell(v, f) {
  if (v == null) return '<td class="num mute">-</td>'
  if (f === 'won') return `<td class="num">${num(v)}</td>`
  if (f === 'pct') return `<td class="num ${tone(v)}">${pct(v)}</td>`
  if (f === 'pct1') return `<td class="num ${tone(v)}">${pct(v, 1)}</td>`
  if (f === 'p1') return `<td class="num">${v.toFixed(1)}%</td>`
  if (f === 'x') return `<td class="num ${v >= 2 ? 'hot' : ''}">${v.toFixed(2)}배</td>`
  if (f === 'n1') return `<td class="num">${v.toFixed(1)}</td>`
  if (f === 'n2') return `<td class="num">${v.toFixed(2)}</td>`
  if (f === 'score') return `<td class="num"><span class="sbar"><i style="width:${v}%"></i></span> <b>${v}</b></td>`
  return `<td>${esc(v)}</td>`
}

async function pageHome() {
  const t = ++token
  loading()
  try {
    const [data, status, accounts, signals] = await Promise.all([get('/api/dashboard'), get('/api/status'), get('/api/accounts'), get('/api/signals')])
    if (stale(t)) return
    const acc = accounts.length ? await get(`/api/accounts/${accounts[0].account_id}`) : null
    if (stale(t)) return
    D.data = data
    const s = data.summary, top = [...data.rows].sort((a, b) => b.score - a.score)[0]
    app.innerHTML = `<div class="page">
      ${status.is_sample ? '<div class="banner warn">지금 보이는 시세·재무·PER/PBR 은 <b>개발용 가상 샘플</b>이에요. 실제 데이터는 README 의 수집 방법(<code>python -m app.ingest all</code>)을 보세요.</div>' : `<div class="banner ok">실제 데이터 기준일: ${d10(status.last_price_date)}</div>`}
      <div class="dash-head"><h1>종목 분석 대시보드</h1><span class="mute">기준일 ${s.last_date ?? '-'} · 주가·거래량·PER/PBR·재무를 SQL 로 분석</span></div>
      <div class="stats">
        ${statBox('분석 종목', `${s.count}개`, `업종 ${data.sectors.length}개`)}
        ${statBox('오늘 상승 / 하락', `<span class="up">${s.up}</span> / <span class="down">${s.down}</span>`, s.flat ? `보합 ${s.flat}` : '전일 종가 대비')}
        ${statBox('평균 3개월 수익률', pct(s.avg_r3m), '분석 종목 단순 평균', tone(s.avg_r3m))}
        ${top ? statBox('종합 점수 1위', `<a class="link" href="#/c/${top.code}">${esc(top.name)}</a>`, `${top.score}점 / 100`) : ''}
      </div>
      <div class="dash-grid">
        <section class="card pad"><h3>업종별 평균 수익률 <span class="mute small">(SQL GROUP BY)</span></h3>${seg('secPeriod', [['avg_r1m', '1개월'], ['avg_r3m', '3개월']], D.secKey || 'avg_r3m')}<div id="sector-chart"></div></section>
        <div class="dash-side">
          <section class="card pad"><h3>오늘의 신호</h3>${signals.length ? signals.map((g) => `<div class="sig"><a class="link" href="#/rules/${g.rule_id}">${esc(g.rule_name)}</a><div class="chips">${g.companies.map((c) => `<a class="chip" href="#/c/${c.code}">${esc(c.name)}</a>`).join('')}</div></div>`).join('') : '<p class="mute small">내 규칙의 진입 조건이 오늘 맞은 종목이 없어요. <a class="link" href="#/rules">규칙 만들기 →</a></p>'}</section>
          <section class="card pad"><h3>내 모의투자</h3>${acc ? `<p class="big num">${won(acc.equity)} <span class="${tone(acc.pnl)}">${pct(acc.pnl_pct)}</span></p><p class="mute small">현금 ${won(acc.cash)} · 보유 ${acc.holdings.length}종목 · <a class="link" href="#/account">자세히 →</a></p>` : '<p class="mute small">가상의 돈으로 연습해 보세요. <a class="link" href="#/account">계좌 만들기 →</a></p>'}</section>
        </div>
      </div>
      <h2 class="sec-head">종목 분석 표 <span class="mute small">머리글을 누르면 정렬돼요</span></h2>
      <div class="toolbar" style="padding:0 0 10px">${seg('secFilter', [['', '전체'], ...data.sectors.map((x) => [x.sector, x.sector])], D.sector)}</div>
      <div class="scroll card"><table class="dash-table" id="dash-table"></table></div>
      <p class="mute small" style="margin-top:8px"><b>점수</b>는 모멘텀(3개월 수익률)·추세(120일선 괴리)·가치(PER)·수익성(영업이익률)·성장(매출 성장률)을 종목 사이 순위로 0~20점씩 매겨 더한 <b>규칙 기반 점수</b>예요. 계산식은 종목 화면 <b>분석</b> 탭에서 볼 수 있어요. 투자 추천이 아니에요.</p>
      <div class="cta card pad"><b>점수가 높은 종목, 정말 오를까?</b> <span class="mute">사고팔 규칙을 만들어 과거 시세로 검증(백테스트)하고, 가상의 돈으로 실행해 보세요.</span> <a class="btn-sm" href="#/rules">규칙 만들기 →</a> <a class="btn-sm ghost" href="#/account">모의투자 →</a></div>
    </div>`
    drawSectorChart(); drawDashTable()
  } catch (e) { fail(e) }
}

function drawSectorChart() {
  const box = $('#sector-chart'); if (!box || !D.data) return
  const key = D.secKey || 'avg_r3m', rows = [...D.data.sectors].sort((a, b) => (b[key] ?? 0) - (a[key] ?? 0))
  const W = 520, rowH = 34, H = rows.length * rowH + 10, mid = 320, max = Math.max(...rows.map((r) => Math.abs(r[key] ?? 0)), 1), sc = Math.min(W - mid - 72, mid - 132) / max
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="업종별 평균 수익률"><line x1="${mid}" x2="${mid}" y1="0" y2="${H}" class="grid"/>
    ${rows.map((r, i) => { const v = r[key] ?? 0, w = Math.abs(v) * sc, y = 6 + i * rowH, x = v >= 0 ? mid : mid - w
      return `<g><title>${r.sector}: ${pct(v)} (${r.n}종목)</title><text x="4" y="${y + 18}" class="sec-label">${esc(r.sector)} <tspan class="tick">${r.n}종목</tspan></text>
      <rect x="${x}" y="${y + 4}" width="${Math.max(w, 1.5)}" height="20" rx="4" class="sbar-${tone(v)}"/><text x="${v >= 0 ? mid + w + 6 : mid + 6}" y="${y + 18}" class="bar-val ${tone(v)}">${pct(v)}</text></g>` }).join('')}</svg>`
}
acts.secPeriod = (b) => { D.secKey = b.dataset.v; b.parentElement.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', x === b)); drawSectorChart() }
acts.secFilter = (b) => { D.sector = b.dataset.v; b.parentElement.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', x === b)); drawDashTable() }
acts.sortBy = (th) => { const k = th.dataset.k; D.desc = D.sort === k ? !D.desc : k !== 'name' && k !== 'per' && k !== 'pbr'; D.sort = k; drawDashTable() }
function drawDashTable() {
  const tb = $('#dash-table'); if (!tb || !D.data) return
  const k = D.sort, dir = D.desc ? -1 : 1
  const rows = D.data.rows.filter((r) => !D.sector || r.sector === D.sector).sort((a, b) => {
    const x = a[k], y = b[k]
    if (x == null && y == null) return 0
    if (x == null) return 1
    if (y == null) return -1
    return (typeof x === 'string' ? x.localeCompare(y) : x - y) * dir
  })
  tb.innerHTML = `<thead><tr>${COLS.map(([key, l, , hint]) => `<th data-act="sortBy" data-k="${key}" class="sortable ${k === key ? 'on' : ''}" ${hint ? `title="${hint}"` : ''}>${l}${k === key ? (D.desc ? ' ▼' : ' ▲') : ''}</th>`).join('')}</tr></thead>
    <tbody>${rows.map((r) => `<tr class="clickable" data-act="openRow" data-code="${r.code}"><td><a class="link" href="#/c/${r.code}">${esc(r.name)}</a> <span class="mute small">${esc(r.sector)}</span></td>${COLS.slice(1).map(([key, , f]) => cell(r[key], f)).join('')}</tr>`).join('')}</tbody>`
}
acts.openRow = (tr, e) => { if (!e.target.closest('a')) location.hash = `#/c/${tr.dataset.code}` }

// ───────── 종목 ─────────
const C = { tab: 'chart', an: null, fund: null, fins: null, peers: null, monthly: null, code: '', info: null, prices: [], days: 365, rules: [], runs: [], runId: null, run: null, accounts: [], accId: null, acc: null, mine: [], showMine: true }

async function pageCompany(code) {
  const t = ++token
  loading()
  try {
    const [info, rules, accounts] = await Promise.all([get(`/api/companies/${code}`), get('/api/rules'), get('/api/accounts')])
    if (stale(t)) return
    Object.assign(C, { tab: C.code === code ? C.tab : 'chart', an: null, fund: null, fins: null, peers: null, monthly: null, code, info, rules, accounts, days: 365, runId: null, run: null, accId: accounts[0]?.account_id ?? null })
    const [prices, mine, runsByRule] = await Promise.all([get(`/api/companies/${code}/prices?days=365`), get(`/api/companies/${code}/my-trades`), Promise.all(rules.map((r) => get(`/api/rules/${r.rule_id}/backtests`)))])
    if (stale(t)) return
    C.prices = prices; C.mine = mine
    C.runs = runsByRule.flat().filter((r) => r.code === code).sort((a, b) => b.run_id - a.run_id)
    ;[C.acc, C.an] = await Promise.all([C.accId ? get(`/api/accounts/${C.accId}`) : null, get(`/api/companies/${code}/analysis`).catch(() => null)])
    if (stale(t)) return
    renderCompany()
  } catch (e) { fail(e) }
}

function renderCompany() {
  const c = C.info, an = C.an
  app.innerHTML = `<div class="page">
    <div class="company-head"><h1>${esc(c.name)}</h1><span class="mute">${c.code} · ${esc(c.sector)}</span>${an ? `<span class="score-pill" title="규칙 기반 종합 점수(0~100)">종합 점수 <b>${an.score}</b></span>` : ''}</div>
    <div class="company-head"><span class="price num">${won(c.price)}</span><span class="num ${tone(c.change_rate)}">${pct(c.change_rate)}</span><span class="mute small">${d10(c.trade_date)} 종가</span>
      ${an ? `<span class="mute small">PER ${an.per ?? '-'} · PBR ${an.pbr ?? '-'}</span>` : ''}</div>
    <div class="tabs" role="tablist">${[['chart', '시세·주문'], ['analysis', '분석'], ['fin', '재무·업종 비교']].map(([k, l]) => `<button role="tab" data-act="ctab" data-v="${k}" aria-selected="${C.tab === k}">${l}</button>`).join('')}</div>
    <div id="tab-body"></div></div>`
  drawCompanyTab()
}
acts.ctab = (b) => { C.tab = b.dataset.v; $$('.tabs [role=tab]').forEach((x) => x.setAttribute('aria-selected', x === b)); drawCompanyTab() }

async function drawCompanyTab() {
  const box = $('#tab-body'); if (!box) return
  if (C.tab === 'chart') {
    box.innerHTML = `<div class="event-layout">
      <div>
        <div class="card chart-card">
          <div class="toolbar">${seg('days', [[90, '3개월'], [183, '6개월'], [365, '1년'], [800, '전체']], C.days)}
            <label class="small"><input type="checkbox" data-change="toggleMine" ${C.showMine ? 'checked' : ''}> 내 거래 표시</label>
            <span class="grow"></span>
            <label class="small mute">백테스트 보기 <select data-change="pickRun" id="run-pick"><option value="">없음</option>${C.runs.map((r) => `<option value="${r.run_id}" ${r.run_id === C.runId ? 'selected' : ''}>${esc(ruleName(r.rule_id))} · ${d10(r.start_date)}~ · ${r.trade_count}번</option>`).join('')}</select></label></div>
          <div class="chart" id="chart"></div>
          <div class="chart-legend small mute"><span><i class="lg up"></i> 이익 구간</span><span><i class="lg down"></i> 손실 구간</span><span><i class="tri buy"></i> 내 매수</span><span><i class="tri sell"></i> 내 매도</span><span>아래 막대: 거래량</span></div>
        </div>
        <div id="run-box"></div>
      </div>
      <div class="side">
        <div class="card pad" id="order-box"></div>
        <div class="card pad" id="bt-box"></div>
      </div>
    </div>`
    drawCompanyChart(); drawRunBox(); drawOrderBox(); drawBtBox()
    return
  }
  const t = token
  box.innerHTML = '<p class="panel-loading">불러오는 중…</p>'
  try {
    if (C.tab === 'analysis') {
      if (!C.fund) [C.fund, C.monthly] = await Promise.all([get(`/api/companies/${C.code}/fundamentals?days=365`), get(`/api/companies/${C.code}/monthly`)])
      if (stale(t) || C.tab !== 'analysis') return
      box.innerHTML = analysisHTML(C.an, C.monthly)
      if (C.fund.length > 1) {
        drawChart($('#per-chart'), C.fund.filter((f) => f.per != null).map((f) => ({ d: f.d, close: f.per })), { label: 'PER', fmt: (v) => `${v.toFixed(1)}배` })
        drawChart($('#pbr-chart'), C.fund.filter((f) => f.pbr != null).map((f) => ({ d: f.d, close: f.pbr })), { label: 'PBR', fmt: (v) => `${v.toFixed(2)}배` })
      }
    } else {
      if (!C.fins) [C.fins, C.peers] = await Promise.all([get(`/api/companies/${C.code}/financials`), get(`/api/companies/${C.code}/peers`)])
      if (stale(t) || C.tab !== 'fin') return
      box.innerHTML = finHTML(C.fins, C.peers)
    }
  } catch (e) { box.innerHTML = `<p class="empty err">${esc(e.message)}</p>` }
}

function scoreHTML(an) {
  return `<div class="card pad score-card"><div class="score-top"><div><span class="mute small">규칙 기반 종합 점수</span><p class="score-big">${an.score}<span>/100</span></p></div>
    <p class="mute small">비교 대상 ${an.score_pool}종목 사이의 순위로 5가지 기준을 각각 0~20점 매겨 더했어요. AI 예측이 아니라 <b>계산식이 공개된 점수</b>이고, 투자 추천이 아니에요.</p></div>
    <ul class="score-parts">${Object.values(an.score_parts).map((p) => `<li><span class="sp-label">${p.label}</span><span class="sp-bar"><i style="width:${(p.points / 20) * 100}%"></i></span><b class="num">${p.points}</b><span class="mute small">${p.note || SCORE_HINT[p.label]}</span></li>`).join('')}</ul></div>`
}
const SCORE_HINT = { 모멘텀: '3개월 수익률이 높을수록', 추세: '120일선보다 위에 있을수록', 가치: 'PER 이 낮을수록', 수익성: '영업이익률이 높을수록', 성장: '매출 성장률이 높을수록' }

function analysisHTML(an, monthly) {
  if (!an) return '<p class="empty">분석할 시세가 없어요.</p>'
  const r = an.returns
  return `<div class="analysis-grid">${scoreHTML(an)}
    <div class="stats">
      ${statBox('1개월 수익률', pct(r['1개월']), '', tone(r['1개월']))}${statBox('3개월 수익률', pct(r['3개월']), '', tone(r['3개월']))}${statBox('6개월 수익률', pct(r['6개월']), '', tone(r['6개월']))}
      ${statBox('120일선 괴리', pct(an.ma120_gap), '120일 평균 대비 지금 가격', tone(an.ma120_gap))}${statBox('거래량 배수', an.vol_ratio == null ? '-' : `${an.vol_ratio.toFixed(2)}배`, '오늘 ÷ 직전 20일 평균')}
      ${statBox('최대 낙폭(1년)', pct(an.mdd), '고점 대비 가장 크게 내린 폭', an.mdd < 0 ? 'down' : '')}${statBox('변동성(연환산)', an.volatility_annual == null ? '-' : `${an.volatility_annual}%`, `하루 평균 ±${an.volatility_daily ?? '-'}%`)}
      ${statBox('PER', an.per == null ? '-' : `${an.per}배`, '주가 ÷ 주당순이익')}${statBox('PBR', an.pbr == null ? '-' : `${an.pbr}배`, '주가 ÷ 주당순자산')}
    </div></div>
    <div class="two-col"><div class="card chart-card"><h3 class="pad-h">PER 추이 (1년)</h3><div class="chart" id="per-chart"></div></div><div class="card chart-card"><h3 class="pad-h">PBR 추이 (1년)</h3><div class="chart" id="pbr-chart"></div></div></div>
    <details class="monthly card"><summary class="pad">월별 통계 보기 (SQL GROUP BY)</summary><div class="scroll"><table><thead><tr><th>월</th><th>평균 종가</th><th>최저</th><th>최고</th><th>거래량 합계</th></tr></thead><tbody>
      ${[...monthly].reverse().map((m) => `<tr><td>${m.ym}</td><td class="num">${num(m.avg_close)}</td><td class="num">${num(m.low)}</td><td class="num">${num(m.high)}</td><td class="num">${num(m.volume)}</td></tr>`).join('')}</tbody></table></div></details>
    <p class="mute small" style="margin-top:10px">기준일 ${an.trade_date} · 윈도 함수(<code>LAG</code>, <code>AVG OVER</code>, <code>MAX OVER</code>)로 계산했어요. <a class="link" href="#/rules">이 종목에 규칙을 적용해 과거에 검증해 보기 →</a></p>`
}

const eok = (n) => (Math.abs(n) >= 10000 ? `${(n / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}조` : `${num(n)}억`)
function barsHTML(title, rows, field, cls) {
  const max = Math.max(...rows.map((r) => Math.max(r[field], 0)), 1), W = 420, H = 170, bw = W / rows.length
  return `<figure class="bars card"><figcaption>${title}</figcaption><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${title}"><line x1="0" x2="${W}" y1="${H - 26}" y2="${H - 26}" class="grid"/>
  ${rows.map((r, i) => { const h = (Math.max(r[field], 0) / max) * (H - 62), last = i === rows.length - 1
    return `<g><title>${r.fiscal_year}년 ${eok(r[field])}원</title><rect x="${i * bw + 10}" y="${H - 26 - h}" width="${bw - 20}" height="${h}" rx="4" class="${cls}" opacity="${last ? 1 : 0.55}"/>
    <text x="${i * bw + bw / 2}" y="${H - 32 - h}" text-anchor="middle" class="bar-val">${eok(r[field])}</text><text x="${i * bw + bw / 2}" y="${H - 8}" text-anchor="middle" class="tick">${r.fiscal_year}</text></g>` }).join('')}</svg></figure>`
}
function finHTML(rows, peers) {
  if (!rows.length) return '<p class="empty">재무 데이터가 없어요. (실데이터는 <code>python -m app.ingest financials</code>, OpenDART 키 필요)</p>'
  const asc = [...rows].reverse(), me = C.code
  return `<div class="fin"><div class="fin-bars">${barsHTML('연간 매출', asc, 'revenue', 'b-rev')}${barsHTML('연간 영업이익', asc, 'operating_profit', 'b-op')}</div>
  <div class="scroll card"><table><thead><tr><th>연도</th><th>매출(억원)</th><th>영업이익(억원)</th><th>순이익(억원)</th><th>영업이익률</th><th>매출 성장률</th></tr></thead><tbody>
  ${rows.map((r) => `<tr><td>${r.fiscal_year}년</td><td class="num">${num(r.revenue)}</td><td class="num">${num(r.operating_profit)}</td><td class="num">${r.net_income == null ? '-' : num(r.net_income)}</td><td class="num">${r.op_margin}%</td><td class="num ${r.rev_growth == null ? '' : tone(r.rev_growth)}">${r.rev_growth == null ? '-' : pct(r.rev_growth, 1)}</td></tr>`).join('')}</tbody></table></div>
  <h3 class="sec-head">같은 업종 비교 <span class="mute small">${peers[0] ? `${peers[0].fiscal_year}년 · ${peers.length}개 회사 · SQL RANK() / AVG() OVER` : ''}</span></h3>
  ${peers.length > 1 ? `<div class="scroll card"><table><thead><tr><th>회사</th><th>매출(억원)</th><th>영업이익률</th><th>순위</th><th>매출 성장률</th><th>순위</th></tr></thead><tbody>
  ${peers.map((p) => `<tr class="${p.code === me ? 'me' : ''}"><td><a class="link" href="#/c/${p.code}">${esc(p.name)}</a></td><td class="num">${num(p.revenue)}</td><td class="num">${p.op_margin}%</td><td class="num">${p.margin_rank}위</td><td class="num ${p.rev_growth == null ? '' : tone(p.rev_growth)}">${p.rev_growth == null ? '-' : pct(p.rev_growth, 1)}</td><td class="num">${p.growth_rank}위</td></tr>`).join('')}
  <tr class="avg"><td>업종 평균</td><td></td><td class="num">${peers[0].avg_margin}%</td><td></td><td class="num">${peers[0].avg_growth == null ? '-' : pct(peers[0].avg_growth, 1)}</td><td></td></tr></tbody></table></div>` : '<p class="empty">같은 업종 회사가 하나뿐이라 비교할 수 없어요.</p>'}</div>`
}
const ruleName = (id) => C.rules.find((r) => r.rule_id === id)?.name ?? '(삭제된 규칙)'

async function drawCompanyChart() {
  const box = $('#chart'); if (!box) return
  const from = C.prices.length ? C.prices[C.prices.length - 1].d : null
  const since = from ? new Date(new Date(d10(from)).getTime() - C.days * 864e5).toISOString().slice(0, 10) : ''
  const shown = C.prices.filter((p) => d10(p.d) >= since)
  const ov = { segments: C.run ? C.run.trades : [], marks: C.showMine ? C.mine.map((m) => ({ d: m.trade_date, side: m.side, text: `${m.side === 'buy' ? '내 매수' : '내 매도'} ${m.qty}주 (${m.account_name})` })) : [] }
  drawChart(box, shown, { ...ov, volume: true })
}

acts.days = async (b) => {
  C.days = Number(b.dataset.v)
  if (C.days > 365 && C.prices.length < 600) C.prices = await get(`/api/companies/${C.code}/prices?days=800`)
  drawCompanyTab()
}
acts.toggleMine = (el) => { C.showMine = el.checked; drawCompanyChart() }
acts.pickRun = async (el) => {
  C.runId = el.value ? Number(el.value) : null
  C.run = C.runId ? await get(`/api/backtests/${C.runId}`) : null
  drawCompanyChart(); drawRunBox()
}
function drawRunBox() {
  const box = $('#run-box'); if (!box) return
  box.innerHTML = C.run ? `<h3 class="sec-head" style="margin-top:20px">백테스트 결과 <span class="mute small">${esc(C.run.rule_text)}</span></h3>${runStats(C.run)}<div style="margin-top:12px">${runTrades(C.run.trades)}</div>` : ''
}

function drawOrderBox() {
  const box = $('#order-box'); if (!box) return
  if (!C.accounts.length) { box.innerHTML = '<h3>모의 주문</h3><p class="mute">주문하려면 먼저 모의투자 계좌가 있어야 해요.</p><a class="btn-sm" href="#/account">계좌 만들기</a>'; return }
  const last = C.prices[C.prices.length - 1]
  const held = C.acc?.holdings.find((h) => h.code === C.code)
  box.innerHTML = `<h3>모의 주문</h3>
    <form data-submit="order" class="form">
      <label>계좌<select name="account" data-change="pickAccount">${C.accounts.map((a) => `<option value="${a.account_id}" ${a.account_id === C.accId ? 'selected' : ''}>${esc(a.name)}</option>`).join('')}</select></label>
      <p class="mute small">현금 ${won(C.acc?.cash ?? 0)} · 이 종목 ${held ? `${held.qty}주 (평균 ${won(held.avg_cost)})` : '보유 없음'}</p>
      <div class="seg" role="group" id="side-seg"><button type="button" data-act="side" data-v="buy" aria-pressed="true">매수</button><button type="button" data-act="side" data-v="sell" aria-pressed="false">매도</button></div>
      <label>날짜<input type="date" name="date" value="${last ? d10(last.d) : ''}" max="${last ? d10(last.d) : ''}" data-change="orderPreview"></label>
      <label>수량(주)<input type="number" name="qty" min="1" step="1" value="1" data-change="orderPreview"></label>
      <label>어떤 규칙에 따라?<select name="rule"><option value="">규칙 없음</option>${C.rules.map((r) => `<option value="${r.rule_id}">${esc(r.name)}</option>`).join('')}</select></label>
      <label>메모<input type="text" name="memo" maxlength="200" placeholder="(선택) 왜 샀는지"></label>
      <p class="mute small" id="preview"></p>
      <button class="btn">주문하기</button><p class="msg" id="order-msg"></p>
    </form>`
  acts.orderPreview()
}
acts.side = (b) => { $$('#side-seg button').forEach((x) => x.setAttribute('aria-pressed', x === b)); acts.orderPreview() }
const $$ = (s, r = document) => [...r.querySelectorAll(s)]
acts.orderPreview = () => {
  const f = $('[data-submit="order"]'); if (!f) return
  const p = C.prices.find((x) => d10(x.d) === f.date.value), q = Number(f.qty.value)
  const side = $('#side-seg [aria-pressed="true"]')?.dataset.v
  $('#preview').textContent = p ? `체결가는 그날 종가 ${won(p.close)}로 자동 기록돼요. 예상 금액 ${won(p.close * q)} (수수료 0.1% 별도, ${side === 'buy' ? '매수' : '매도'})` : '이 날짜는 시세가 없어서 주문할 수 없어요(휴장일이거나 조회 기간 밖).'
}
acts.pickAccount = async (el) => { C.accId = Number(el.value); C.acc = await get(`/api/accounts/${C.accId}`); drawOrderBox() }
acts.order = async (f) => {
  const side = $('#side-seg [aria-pressed="true"]').dataset.v
  try {
    await api('POST', `/api/accounts/${C.accId}/trades`, { code: C.code, side, trade_date: f.date.value, qty: f.qty.value, rule_id: f.rule.value ? Number(f.rule.value) : null, memo: f.memo.value })
    const [acc, mine] = await Promise.all([get(`/api/accounts/${C.accId}`), get(`/api/companies/${C.code}/my-trades`)])
    C.acc = acc; C.mine = mine
    drawCompanyChart(); drawOrderBox(); msg($('#order-msg'), '주문이 체결됐어요 ✓', true)
  } catch (e) { msg($('#order-msg'), e.message) }
}

function drawBtBox() {
  const box = $('#bt-box'); if (!box) return
  if (!C.rules.length) { box.innerHTML = '<h3>이 종목으로 백테스트</h3><p class="mute">규칙이 있어야 과거 시세에 돌려 볼 수 있어요.</p><a class="btn-sm" href="#/rules">규칙 만들기</a>'; return }
  box.innerHTML = `<h3>이 종목으로 백테스트</h3><form data-submit="runBt" class="form">
    <label>규칙<select name="rule">${C.rules.map((r) => `<option value="${r.rule_id}">${esc(r.name)}</option>`).join('')}</select></label>
    <label>기간<select name="period">${Object.entries(PERIOD).map(([v, l]) => `<option value="${v}" ${v === '1y' ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
    <button class="btn">백테스트 실행</button><p class="msg" id="bt-msg"></p></form>`
}
acts.runBt = async (f) => {
  try {
    const run = await api('POST', `/api/rules/${f.rule.value}/backtests`, { company_code: C.code, period: f.period.value })
    C.runs.unshift({ ...run }); C.runId = run.run_id; C.run = run
    drawCompanyTab(); msg($('#bt-msg'), '백테스트 완료 ✓', true)
  } catch (e) { msg($('#bt-msg'), e.message) }
}

// ───────── 규칙 목록·만들기·수정 ─────────
const RU = { rules: [], editId: null }
app.addEventListener('input', (e) => { const t = e.target.closest('[data-input]'); if (t && acts[t.dataset.input]) acts[t.dataset.input](t, e) })

async function pageRules() {
  const t = ++token
  loading()
  try {
    const rules = await get('/api/rules')
    if (stale(t)) return
    RU.rules = rules; RU.editId = null
    renderRules()
  } catch (e) { fail(e) }
}

const PARAM = { ma_cross: ['이동평균 기간(일)', 2, 250, 1], dip_buy: ['하락률(% 이상)', 1, 30, 0.5], breakout: ['신고가 기준 기간(일)', 2, 250, 1] }

function ruleForm(r) {
  const v = r || { name: '', entry_type: 'ma_cross', entry_param: 20, take_profit_pct: 8, stop_loss_pct: 4, max_hold_days: 20 }
  const [pl, mn, mx, st] = PARAM[v.entry_type]
  return `<form data-submit="saveRule" class="form" id="rule-form">
    ${r ? '' : `<div class="presets"><span class="mute small">예시로 채우기</span>${PRESETS.map((p, i) => `<button type="button" class="chip" data-act="preset" data-i="${i}">${esc(p.name)}</button>`).join('')}</div>`}
    <label>규칙 이름<input name="name" maxlength="60" required value="${esc(v.name)}" data-input="rulePreview"></label>
    <fieldset><legend>언제 살까? (진입 조건)</legend>
      <label>조건<select name="entry_type" data-change="ruleType">${Object.entries(ENTRY).map(([k, l]) => `<option value="${k}" ${k === v.entry_type ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
      <label><span id="param-label">${pl}</span><input name="entry_param" type="number" min="${mn}" max="${mx}" step="${st}" required value="${Number(v.entry_param)}" data-input="rulePreview"></label></fieldset>
    <fieldset><legend>언제 팔까? (청산 조건)</legend>
      <label>익절(% 오르면)<input name="take_profit_pct" type="number" min="0.5" max="200" step="0.5" required value="${Number(v.take_profit_pct)}" data-input="rulePreview"></label>
      <label>손절(% 내리면)<input name="stop_loss_pct" type="number" min="0.5" max="50" step="0.5" required value="${Number(v.stop_loss_pct)}" data-input="rulePreview"></label>
      <label>최대 보유일<input name="max_hold_days" type="number" min="1" max="250" step="1" required value="${Number(v.max_hold_days)}" data-input="rulePreview"></label></fieldset>
    <p class="rule-preview" id="rule-preview"></p>
    <div class="row"><button class="btn">${r ? '수정 저장' : '규칙 만들기'}</button>${r ? '<button type="button" class="btn ghost" data-act="cancelEdit">취소</button>' : ''}</div><p class="msg" id="rule-msg"></p></form>`
}
const formRule = (f) => ({ name: f.name.value, entry_type: f.entry_type.value, entry_param: Number(f.entry_param.value), take_profit_pct: Number(f.take_profit_pct.value), stop_loss_pct: Number(f.stop_loss_pct.value), max_hold_days: Number(f.max_hold_days.value) })

function renderRules() {
  const editing = RU.rules.find((r) => r.rule_id === RU.editId)
  app.innerHTML = `<div class="page"><h1>내 규칙</h1><p class="mute">규칙 = <b>언제 살지</b> + <b>언제 팔지</b>. 한 번 정해 두면 과거 시세에 돌려 볼 수 있어요(백테스트).</p>
    <div class="notes-page" style="margin-top:14px">
      <div class="notes-side">
        <div class="card pad"><h3>${editing ? '규칙 수정' : '새 규칙'}</h3>${ruleForm(editing)}</div>
      </div>
      <div class="notes-main">${RU.rules.length ? `<div class="rule-list">${RU.rules.map((r) => `<div class="card pad rule-card ${r.rule_id === RU.editId ? 'on' : ''}">
        <div class="ed-top"><a class="rule-name" href="#/rules/${r.rule_id}">${esc(r.name)}</a><span class="tag">${r.entry_label}</span><span class="grow"></span>
          <a class="btn-sm" href="#/rules/${r.rule_id}">백테스트 →</a><button class="btn-sm ghost" data-act="editRule" data-id="${r.rule_id}">수정</button><button class="btn-sm ghost danger" data-act="delRule" data-id="${r.rule_id}">삭제</button></div>
        <p class="rule-text">${esc(r.text)}</p><p class="mute small">백테스트 ${r.run_count}번 · 이 규칙으로 한 모의 거래 ${r.trade_count}건</p></div>`).join('')}</div>
        <p style="margin-top:12px"><button class="btn ghost" data-act="addPresets">예시 규칙 3개 한 번에 담기</button></p>` : `<div class="card pad"><p>아직 규칙이 없어요. 왼쪽에서 만들거나, 예시 규칙으로 시작해 보세요.</p><button class="btn" data-act="addPresets">예시 규칙 3개 담기</button></div>`}
        <p class="msg" id="list-msg"></p></div></div></div>`
  acts.rulePreview()
}
acts.rulePreview = () => { const f = $('#rule-form'); if (f) $('#rule-preview').textContent = `👉 ${ruleText(formRule(f))}` }
acts.ruleType = (el) => {
  const f = $('#rule-form'), [pl, mn, mx, st] = PARAM[el.value]
  $('#param-label').textContent = pl; Object.assign(f.entry_param, { min: mn, max: mx, step: st })
  f.entry_param.value = { ma_cross: 20, dip_buy: 4, breakout: 20 }[el.value]; acts.rulePreview()
}
acts.preset = (b) => { const f = $('#rule-form'), p = PRESETS[b.dataset.i]; for (const k of Object.keys(p)) f[k].value = p[k]; acts.ruleType(f.entry_type); f.entry_param.value = p.entry_param; acts.rulePreview() }
acts.saveRule = async (f) => {
  try {
    if (RU.editId) await api('PUT', `/api/rules/${RU.editId}`, formRule(f)); else await api('POST', '/api/rules', formRule(f))
    RU.rules = await get('/api/rules'); RU.editId = null; renderRules(); msg($('#list-msg'), '저장했어요 ✓', true)
  } catch (e) { msg($('#rule-msg'), e.message) }
}
acts.editRule = (b) => { RU.editId = Number(b.dataset.id); renderRules(); window.scrollTo(0, 0) }
acts.cancelEdit = () => { RU.editId = null; renderRules() }
acts.delRule = (b) => confirmTwice(b, '정말 삭제?', async () => {
  try { await api('DELETE', `/api/rules/${b.dataset.id}`); RU.rules = await get('/api/rules'); RU.editId = null; renderRules(); msg($('#list-msg'), '삭제했어요(백테스트 기록도 함께 지워져요).', true) } catch (e) { msg($('#list-msg'), e.message) }
})
acts.addPresets = async () => {
  let made = 0
  for (const p of PRESETS) { try { await api('POST', '/api/rules', p); made++ } catch (e) { /* 이미 있는 이름은 건너뛰어요 */ } }
  RU.rules = await get('/api/rules'); renderRules(); msg($('#list-msg'), made ? `${made}개를 담았어요 ✓` : '이미 모두 담겨 있어요.', true)
}

// ───────── 규칙 상세: 백테스트 ─────────
const RD = { rule: null, companies: [], runs: [], run: null, signals: [], report: null, period: '1y', prices: {} }

async function pageRule(id) {
  const t = ++token
  loading()
  try {
    const [rule, companies, runs, signals, report] = await Promise.all([get(`/api/rules/${id}`), get('/api/companies'), get(`/api/rules/${id}/backtests`), get(`/api/rules/${id}/signals`), get(`/api/rules/${id}/report`)])
    if (stale(t)) return
    Object.assign(RD, { rule, companies, runs, signals, report, run: runs[0] ? await get(`/api/backtests/${runs[0].run_id}`) : null })
    if (RD.run && !RD.prices[RD.run.code]) RD.prices[RD.run.code] = await get(`/api/companies/${RD.run.code}/prices?days=800`)
    if (stale(t)) return
    renderRule()
  } catch (e) { fail(e) }
}

function renderRule() {
  const r = RD.rule, rep = RD.report
  const row = (l, a, b, c = '') => `<tr><td>${l}</td><td class="num ${c && a != null ? tone(a) : ''}">${c === 'pct' ? pct(a) : a ?? '-'}</td><td class="num ${c && b != null ? tone(b) : ''}">${c === 'pct' ? pct(b) : b ?? '-'}</td></tr>`
  app.innerHTML = `<div class="page"><p class="small"><a class="link" href="#/rules">← 내 규칙</a></p>
    <div class="ed-top"><h1>${esc(r.name)}</h1><span class="tag">${r.entry_label}</span></div><p class="rule-text">${esc(r.text)}</p>
    <div class="card pad" style="margin-top:14px"><h3>백테스트 실행</h3><p class="mute small">이 규칙을 과거 시세에 그대로 적용하면 어떻게 됐을지 계산해요. 신호가 난 <b>다음 날 시가</b>에 사고, 수수료 0.1%(사고팔 때 각각)를 반영해요.</p>
      <form data-submit="runRule" class="row form-inline"><select name="code">${RD.companies.map((c) => `<option value="${c.code}" ${RD.run?.code === c.code ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select>
        <select name="period">${Object.entries(PERIOD).map(([v, l]) => `<option value="${v}" ${v === RD.period ? 'selected' : ''}>${l}</option>`).join('')}</select><button class="btn">실행</button></form><p class="msg" id="run-msg"></p></div>
    <div id="run-view"></div>
    <h2 class="sec-head">실행 기록</h2>${RD.runs.length ? `<div class="scroll card"><table><thead><tr><th>종목</th><th>기간</th><th>거래</th><th>승률</th><th>누적</th><th>그냥 보유</th><th></th></tr></thead><tbody>
      ${RD.runs.map((x) => `<tr class="${RD.run?.run_id === x.run_id ? 'me' : ''}"><td>${esc(x.company_name)}</td><td>${d10(x.start_date)} ~ ${d10(x.end_date)}</td><td class="num">${x.trade_count}</td><td class="num">${x.trade_count ? Math.round((x.win_count / x.trade_count) * 100) + '%' : '-'}</td>
      <td class="num ${tone(x.total_return)}">${pct(x.total_return)}</td><td class="num ${tone(x.benchmark_return)}">${pct(x.benchmark_return)}</td>
      <td><button class="btn-sm ghost" data-act="viewRun" data-id="${x.run_id}">보기</button> <button class="btn-sm ghost danger" data-act="delRun" data-id="${x.run_id}">삭제</button></td></tr>`).join('')}</tbody></table></div>` : '<p class="empty">아직 실행한 적이 없어요.</p>'}
    <div class="two-col"><div><h2 class="sec-head">오늘의 신호</h2>${RD.signals.length ? `<div class="card pad"><p class="mute small">가장 최근 거래일에 진입 조건이 맞은 종목이에요.</p><div class="chips">${RD.signals.map((s) => `<a class="chip" href="#/c/${s.code}">${esc(s.name)} <span class="${tone(s.change_rate)}">${pct(s.change_rate)}</span></a>`).join('')}</div></div>` : '<p class="empty">오늘은 조건이 맞은 종목이 없어요.</p>'}</div>
      <div><h2 class="sec-head">백테스트 vs 실제 모의투자</h2><div class="card"><table><thead><tr><th></th><th>백테스트(과거)</th><th>실제 모의투자</th></tr></thead><tbody>
        ${row('종목 수', rep.backtest.companies, '')}${row('거래 수', rep.backtest.trade_count, rep.actual.trade_count)}${row('승률(%)', rep.backtest.win_rate, rep.actual.win_rate)}${row('거래당 평균 수익률', rep.backtest.avg_return, rep.actual.avg_return, 'pct')}</tbody></table>
        <p class="mute small pad">${rep.actual.trade_count < 5 ? '실제 거래가 5건보다 적어서 비교는 참고만 하세요. ' : ''}모의 주문에서 이 규칙을 선택하고 <b>매도</b>하면 여기에 쌓여요. 백테스트는 종목마다 가장 최근 실행만 합쳐요.</p></div></div></div></div>`
  drawRuleRun()
}
function drawRuleRun() {
  const box = $('#run-view'); if (!box) return
  const r = RD.run
  if (!r) { box.innerHTML = ''; return }
  box.innerHTML = `<h2 class="sec-head">${esc(r.company_name)} 결과 <span class="mute small">${PERIOD[RD.period] ? '' : ''}${d10(r.start_date)} ~ ${d10(r.end_date)}</span></h2>${runStats(r)}
    <div class="card chart-card" style="margin:14px 0"><div class="chart" id="rchart"></div><div class="chart-legend small mute"><span><i class="lg up"></i> 이익 거래</span><span><i class="lg down"></i> 손실 거래</span><span>● 매수 ○ 매도</span></div></div>${runTrades(r.trades)}`
  const px = (RD.prices[r.code] || []).filter((p) => d10(p.d) >= d10(r.start_date))
  drawChart($('#rchart'), px, { segments: r.trades })
}
acts.runRule = async (f) => {
  RD.period = f.period.value
  try {
    const run = await api('POST', `/api/rules/${RD.rule.rule_id}/backtests`, { company_code: f.code.value, period: f.period.value })
    if (!RD.prices[run.code]) RD.prices[run.code] = await get(`/api/companies/${run.code}/prices?days=800`)
    const [runs, report] = await Promise.all([get(`/api/rules/${RD.rule.rule_id}/backtests`), get(`/api/rules/${RD.rule.rule_id}/report`)])
    Object.assign(RD, { run, runs, report }); renderRule(); msg($('#run-msg'), '완료 ✓', true)
  } catch (e) { msg($('#run-msg'), e.message) }
}
acts.viewRun = async (b) => {
  RD.run = await get(`/api/backtests/${b.dataset.id}`)
  if (!RD.prices[RD.run.code]) RD.prices[RD.run.code] = await get(`/api/companies/${RD.run.code}/prices?days=800`)
  renderRule(); $('#run-view').scrollIntoView({ behavior: 'smooth' })
}
acts.delRun = (b) => confirmTwice(b, '정말?', async () => {
  await api('DELETE', `/api/backtests/${b.dataset.id}`)
  const id = RD.rule.rule_id, [runs, report] = await Promise.all([get(`/api/rules/${id}/backtests`), get(`/api/rules/${id}/report`)])
  RD.runs = runs; RD.report = report
  if (RD.run && RD.run.run_id === Number(b.dataset.id)) RD.run = runs[0] ? await get(`/api/backtests/${runs[0].run_id}`) : null
  renderRule()
})

// ───────── 모의투자 ─────────
const AC = { accounts: [], id: null, d: null, trades: [], companies: [], rules: [], prices: {}, side: 'buy', renaming: false }

async function pageAccount(id) {
  const t = ++token
  loading()
  try {
    const [accounts, companies, rules] = await Promise.all([get('/api/accounts'), get('/api/companies'), get('/api/rules')])
    if (stale(t)) return
    Object.assign(AC, { accounts, companies, rules, renaming: false, id: accounts.find((a) => a.account_id === Number(id))?.account_id ?? accounts[0]?.account_id ?? null })
    await loadAccount(); if (stale(t)) return
    renderAccount()
  } catch (e) { fail(e) }
}
async function loadAccount() {
  if (!AC.id) { AC.d = null; AC.trades = []; return }
  ;[AC.d, AC.trades] = await Promise.all([get(`/api/accounts/${AC.id}`), get(`/api/accounts/${AC.id}/trades`)])
}
function renderAccount() {
  const d = AC.d
  app.innerHTML = `<div class="page"><h1>모의투자</h1><p class="mute">가상의 돈으로 사고팔아 보는 연습장이에요. 체결가는 그날의 종가, 수수료는 거래대금의 0.1%예요.</p>
    <div class="toolbar" style="padding:8px 0"><div class="seg">${AC.accounts.map((a) => `<button data-act="pickAcc" data-id="${a.account_id}" aria-pressed="${a.account_id === AC.id}">${esc(a.name)}</button>`).join('')}</div>
      <form data-submit="newAcc" class="row form-inline"><input name="name" placeholder="새 계좌 이름" maxlength="40" required style="width:140px"><input name="cash" type="number" min="100000" step="100000" value="10000000" required style="width:130px" aria-label="시작 금액"><button class="btn-sm">+ 계좌 만들기</button></form></div><p class="msg" id="acc-msg"></p>
    ${d ? accountBody(d) : '<div class="card pad"><p>계좌가 없어요. 위에서 이름을 적고 <b>+ 계좌 만들기</b>를 눌러 주세요.</p></div>'}</div>`
  if (d) { acts.tradePreview() }
}
function accountBody(d) {
  return `<div class="stats">${statBox('총 자산', won(d.equity), `시작 ${won(d.initial_cash)}`)}${statBox('평가 손익', `${d.pnl > 0 ? '+' : ''}${num(d.pnl)}원`, pct(d.pnl_pct), tone(d.pnl))}
    ${statBox('현금', won(d.cash))}${statBox('주식 평가액', won(d.stock_value))}${statBox('실현 손익', `${d.realized_pnl > 0 ? '+' : ''}${num(d.realized_pnl)}원`, '판 것에서 번 돈', tone(d.realized_pnl))}</div>
    <p class="small audit ${d.audit.cash_ok && d.audit.holdings_ok ? 'ok' : 'bad'}">${d.audit.cash_ok && d.audit.holdings_ok ? '✓ 장부 검증: 현금과 보유 수량이 거래 내역으로 다시 계산한 값과 일치해요.' : '⚠ 장부가 거래 내역과 맞지 않아요.'}
      ${AC.renaming ? `<form data-submit="renameAcc" class="row form-inline" style="display:inline-flex"><input name="name" value="${esc(d.name)}" maxlength="40" required><button class="btn-sm">저장</button></form>` : `<button class="btn-sm ghost" data-act="startRename">이름 바꾸기</button>`}
      <button class="btn-sm ghost danger" data-act="delAcc">계좌 삭제</button></p>
    <h2 class="sec-head">보유 종목</h2>${d.holdings.length ? `<div class="scroll card"><table><thead><tr><th>종목</th><th>수량</th><th>평균단가</th><th>현재가</th><th>평가금액</th><th>손익</th><th>수익률</th><th>비중</th></tr></thead><tbody>
      ${d.holdings.map((h) => `<tr><td><a class="link" href="#/c/${h.code}">${esc(h.name)}</a></td><td class="num">${num(h.qty)}</td><td class="num">${num(h.avg_cost)}</td><td class="num">${num(h.price)}</td><td class="num">${num(h.value)}</td>
      <td class="num ${tone(h.pnl)}">${h.pnl > 0 ? '+' : ''}${num(h.pnl)}</td><td class="num ${tone(h.pnl_pct)}">${pct(h.pnl_pct)}</td><td class="num"><span class="wbar"><i style="width:${Math.min(100, h.weight)}%"></i></span> ${h.weight}%</td></tr>`).join('')}</tbody></table></div>` : '<p class="empty">보유한 종목이 없어요. 아래에서 주문해 보세요.</p>'}
    <h2 class="sec-head">주문하기</h2><div class="card pad"><form data-submit="trade" class="form-grid">
      <label>종목<select name="code" data-change="tradePreview">${AC.companies.map((c) => `<option value="${c.code}">${esc(c.name)}</option>`).join('')}</select></label>
      <div class="seg" role="group" id="tside"><button type="button" data-act="tside" data-v="buy" aria-pressed="${AC.side === 'buy'}">매수</button><button type="button" data-act="tside" data-v="sell" aria-pressed="${AC.side === 'sell'}">매도</button></div>
      <label>날짜<input type="date" name="date" value="${d10(AC.companies[0]?.trade_date || '')}" max="${d10(AC.companies[0]?.trade_date || '')}" data-change="tradePreview"></label>
      <label>수량(주)<input type="number" name="qty" min="1" step="1" value="1" data-change="tradePreview" data-input="tradePreview"></label>
      <label>규칙<select name="rule"><option value="">규칙 없음</option>${AC.rules.map((r) => `<option value="${r.rule_id}">${esc(r.name)}</option>`).join('')}</select></label>
      <label>메모<input name="memo" maxlength="200" placeholder="(선택)"></label>
      <div class="full"><p class="mute small" id="tpreview"></p><button class="btn">주문하기</button> <span class="msg" id="trade-msg"></span></div></form></div>
    <h2 class="sec-head">거래 내역</h2>${AC.trades.length ? `<div class="scroll card"><table><thead><tr><th>날짜</th><th>종목</th><th>구분</th><th>체결가</th><th>수량</th><th>수수료</th><th>규칙</th><th>메모</th><th></th></tr></thead><tbody>
      ${AC.trades.map((t) => `<tr><td>${d10(t.trade_date)}</td><td><a class="link" href="#/c/${t.code}">${esc(t.company_name)}</a></td><td class="${t.side === 'buy' ? 'up' : 'down'}">${t.side === 'buy' ? '매수' : '매도'}</td><td class="num">${num(t.price)}</td><td class="num">${num(t.qty)}</td><td class="num">${num(t.fee)}</td>
      <td>${t.rule_name ? `<a class="link" href="#/rules/${t.rule_id}">${esc(t.rule_name)}</a>` : '<span class="mute">-</span>'}</td><td><input class="memo" value="${esc(t.memo)}" maxlength="200" data-change="memo" data-id="${t.trade_id}" aria-label="메모"></td>
      <td><button class="btn-sm ghost danger" data-act="delTrade" data-id="${t.trade_id}">삭제</button></td></tr>`).join('')}</tbody></table></div><p class="msg" id="tlist-msg"></p>` : '<p class="empty">아직 거래가 없어요.</p>'}`
}
acts.pickAcc = (b) => { location.hash = `#/account/${b.dataset.id}` }
acts.newAcc = async (f) => {
  try { const a = await api('POST', '/api/accounts', { name: f.name.value, initial_cash: Number(f.cash.value) }); go(`#/account/${a.account_id}`) } catch (e) { msg($('#acc-msg'), e.message) }
}
acts.startRename = () => { AC.renaming = true; renderAccount() }
acts.renameAcc = async (f) => {
  try { await api('PUT', `/api/accounts/${AC.id}`, { name: f.name.value }); AC.accounts = await get('/api/accounts'); AC.renaming = false; await loadAccount(); renderAccount() } catch (e) { msg($('#acc-msg'), e.message) }
}
acts.delAcc = (b) => confirmTwice(b, '거래도 모두 사라져요. 정말?', async () => { await api('DELETE', `/api/accounts/${AC.id}`); go('#/account') })
acts.tside = (b) => { AC.side = b.dataset.v; $$('#tside button').forEach((x) => x.setAttribute('aria-pressed', x === b)); acts.tradePreview() }
acts.tradePreview = async () => {
  const f = $('[data-submit="trade"]'); if (!f) return
  const code = f.code.value
  if (!AC.prices[code]) AC.prices[code] = await get(`/api/companies/${code}/prices?days=800`)
  const p = AC.prices[code].find((x) => d10(x.d) === f.date.value), q = Number(f.qty.value) || 0
  const el = $('#tpreview'); if (!el) return
  el.textContent = p ? `체결가: ${f.date.value} 종가 ${won(p.close)} · 거래대금 ${won(p.close * q)} · 수수료 약 ${won(p.close * q * 0.001)}` : '이 날짜는 시세가 없어요(휴장일이거나 데이터 밖).'
}
acts.trade = async (f) => {
  try {
    await api('POST', `/api/accounts/${AC.id}/trades`, { code: f.code.value, side: AC.side, trade_date: f.date.value, qty: f.qty.value, rule_id: f.rule.value ? Number(f.rule.value) : null, memo: f.memo.value })
    AC.accounts = await get('/api/accounts'); await loadAccount(); renderAccount(); msg($('#trade-msg'), '체결됐어요 ✓', true)
  } catch (e) { msg($('#trade-msg'), e.message) }
}
acts.memo = async (el) => { try { await api('PUT', `/api/accounts/${AC.id}/trades/${el.dataset.id}`, { memo: el.value }) } catch (e) { msg($('#tlist-msg'), e.message) } }
acts.delTrade = (b) => confirmTwice(b, '정말?', async () => {
  try { await api('DELETE', `/api/accounts/${AC.id}/trades/${b.dataset.id}`); await loadAccount(); renderAccount() } catch (e) { msg($('#tlist-msg'), e.message) }
})

// ───────── 검색 · 주소 이동 ─────────
let allCompanies = null
const search = $('#search'), list = $('#search-list')
search.addEventListener('input', async () => {
  const q = search.value.trim().toLowerCase()
  if (!q) return (list.hidden = true)
  if (!allCompanies) allCompanies = await get('/api/companies')
  const hits = allCompanies.filter((c) => c.name.toLowerCase().includes(q) || c.code.includes(q)).slice(0, 8)
  list.innerHTML = hits.length ? hits.map((c) => `<li><button data-code="${c.code}">${esc(c.name)} <span class="mute small">${c.code}</span></button></li>`).join('') : '<li class="mute pad small">검색 결과가 없어요.</li>'
  list.hidden = false
})
list.addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) { location.hash = `#/c/${b.dataset.code}`; search.value = ''; list.hidden = true } })
document.addEventListener('click', (e) => { if (!e.target.closest('.search')) list.hidden = true })

function route() {
  const h = location.hash.replace(/^#/, '') || '/', m = h.split('/').filter(Boolean)
  document.querySelectorAll('[data-nav]').forEach((a) => a.classList.toggle('active', a.dataset.nav === ({ c: 'home', rules: 'rules', account: 'account' }[m[0]] ?? 'home')))
  window.scrollTo(0, 0)
  if (m[0] === 'c' && m[1]) pageCompany(m[1])
  else if (m[0] === 'rules' && m[1]) pageRule(m[1])
  else if (m[0] === 'rules') pageRules()
  else if (m[0] === 'account') pageAccount(m[1])
  else pageHome()
}
window.addEventListener('hashchange', route)
route()
