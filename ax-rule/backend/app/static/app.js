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
// ov = { segments: [{entry_date, exit_date, return_pct}], marks: [{d, side, text}] }
function drawChart(box, prices, ov = {}) {
  const n = prices.length
  if (n < 2) return (box.innerHTML = '<p class="empty">시세가 없어요.</p>')
  const W = 760, H = 300, L = 62, R = 10, T = 10, B = 26
  const cl = prices.map((p) => p.close), lo = Math.min(...cl), hi = Math.max(...cl), pad = (hi - lo) * 0.08 || 1
  const y0 = lo - pad, y1 = hi + pad
  const X = (i) => L + (i / (n - 1)) * (W - L - R)
  const Y = (v) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B)
  const idx = new Map(prices.map((p, i) => [d10(p.d), i]))
  const line = prices.map((p, i) => `${X(i).toFixed(1)},${Y(p.close).toFixed(1)}`).join(' ')
  const grid = [0, 1, 2, 3].map((k) => { const v = y0 + ((y1 - y0) * k) / 3; return `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" class="grid"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" class="tick">${num(v)}</text>` }).join('')
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
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="주가 차트">${grid}${ticks}<polyline points="${line}" class="price-line"/>${segs}${marks}
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
    tip.innerHTML = `<b>${d10(p.d)}</b><span>종가 ${num(p.close)}원</span>${(byDate[d10(p.d)] || []).map((t) => `<span class="mute">${esc(t)}</span>`).join('')}`
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

// ───────── 홈 ─────────
async function pageHome() {
  const t = ++token
  loading()
  try {
    const [companies, status, accounts, signals, rules] = await Promise.all([get('/api/companies'), get('/api/status'), get('/api/accounts'), get('/api/signals'), get('/api/rules')])
    if (stale(t)) return
    const acc = accounts.length ? await get(`/api/accounts/${accounts[0].account_id}`) : null
    if (stale(t)) return
    const sectors = {}
    companies.forEach((c) => (sectors[c.sector] = (sectors[c.sector] || []).concat(c)))
    app.innerHTML = `<div class="page">
      ${status.is_sample ? '<div class="banner warn">지금 보이는 시세는 <b>개발용 가상 샘플</b>이에요. 실제 시세를 쓰려면 README 의 수집 방법(<code>python -m app.ingest all</code>)을 보세요.</div>' : `<div class="banner ok">실제 시세 기준: ${d10(status.last_price_date)}</div>`}
      <section class="hero"><h1>규칙을 만들고, 과거에 <em>검증</em>하고, 가상의 돈으로 <em>실행</em>해요</h1>
        <ol class="flow">
          <li><a href="#/rules"><span class="no">1</span><b>규칙 만들기</b><span class="mute small">언제 사고 언제 팔지 정해요</span></a></li>
          <li><a href="#/rules${rules[0] ? '/' + rules[0].rule_id : ''}"><span class="no">2</span><b>백테스트</b><span class="mute small">과거 시세에 돌려 봐요</span></a></li>
          <li><a href="#/account"><span class="no">3</span><b>모의투자</b><span class="mute small">가상의 돈으로 해 봐요</span></a></li>
          <li><a href="#/rules"><span class="no">4</span><b>비교하기</b><span class="mute small">백테스트와 실제 결과를 견줘요</span></a></li>
        </ol></section>
      <div class="home-grid">
        <section class="card pad"><h3>내 모의투자 계좌</h3>${acc ? `
          <p class="big num">${won(acc.equity)} <span class="${tone(acc.pnl)}">${pct(acc.pnl_pct)}</span></p>
          <p class="mute small">현금 ${won(acc.cash)} · 보유 ${acc.holdings.length}종목 · <a class="link" href="#/account">자세히 →</a></p>` : `
          <p class="mute">아직 계좌가 없어요. 가상의 돈 1,000만 원으로 시작해 볼까요?</p><a class="btn-sm" href="#/account">계좌 만들기</a>`}</section>
        <section class="card pad"><h3>오늘의 신호</h3>${!rules.length ? `<p class="mute">규칙을 만들면 오늘 진입 조건이 맞은 종목이 여기 떠요.</p><a class="btn-sm" href="#/rules">규칙 만들기</a>`
          : signals.length ? signals.map((s) => `<div class="sig"><a class="link" href="#/rules/${s.rule_id}">${esc(s.rule_name)}</a><div class="chips">${s.companies.map((c) => `<a class="chip" href="#/c/${c.code}">${esc(c.name)}</a>`).join('')}</div></div>`).join('')
          : '<p class="mute">오늘은 진입 조건이 맞은 종목이 없어요.</p>'}</section>
      </div>
      <h2 class="sec-head">종목</h2>
      ${Object.entries(sectors).map(([s, list]) => `<div class="sector-block"><div class="sector-name">${esc(s)}</div><div class="cards">${list.map(cardHTML).join('')}</div></div>`).join('')}
    </div>`
  } catch (e) { fail(e) }
}
const cardHTML = (c) => `<a class="company-card cc-link" href="#/c/${c.code}"><span class="cc-name">${esc(c.name)} <span class="mute small">${c.code}</span></span>
  <span class="cc-price num">${c.price == null ? '-' : won(c.price)}</span><span class="num ${tone(c.change_rate)}">${pct(c.change_rate)}</span></a>`

// ───────── 종목 ─────────
const C = { code: '', info: null, prices: [], days: 365, rules: [], runs: [], runId: null, run: null, accounts: [], accId: null, acc: null, mine: [], showMine: true }

async function pageCompany(code) {
  const t = ++token
  loading()
  try {
    const [info, rules, accounts] = await Promise.all([get(`/api/companies/${code}`), get('/api/rules'), get('/api/accounts')])
    if (stale(t)) return
    Object.assign(C, { code, info, rules, accounts, days: 365, runId: null, run: null, accId: accounts[0]?.account_id ?? null })
    const [prices, mine, runsByRule] = await Promise.all([get(`/api/companies/${code}/prices?days=365`), get(`/api/companies/${code}/my-trades`), Promise.all(rules.map((r) => get(`/api/rules/${r.rule_id}/backtests`)))])
    if (stale(t)) return
    C.prices = prices; C.mine = mine
    C.runs = runsByRule.flat().filter((r) => r.code === code).sort((a, b) => b.run_id - a.run_id)
    C.acc = C.accId ? await get(`/api/accounts/${C.accId}`) : null
    if (stale(t)) return
    renderCompany()
  } catch (e) { fail(e) }
}

function renderCompany() {
  const c = C.info, last = C.prices[C.prices.length - 1]
  app.innerHTML = `<div class="page">
    <div class="company-head"><h1>${esc(c.name)}</h1><span class="mute">${c.code} · ${esc(c.sector)}</span></div>
    <div class="company-head"><span class="price num">${won(c.price)}</span><span class="num ${tone(c.change_rate)}">${pct(c.change_rate)}</span><span class="mute small">${d10(c.trade_date)} 종가</span></div>
    <div class="event-layout" style="margin-top:16px">
      <div>
        <div class="card chart-card">
          <div class="toolbar">${seg('days', [[90, '3개월'], [183, '6개월'], [365, '1년'], [800, '전체']], C.days)}
            <label class="small"><input type="checkbox" data-change="toggleMine" ${C.showMine ? 'checked' : ''}> 내 거래 표시</label>
            <span class="grow"></span>
            <label class="small mute">백테스트 보기 <select data-change="pickRun" id="run-pick"><option value="">없음</option>${C.runs.map((r) => `<option value="${r.run_id}" ${r.run_id === C.runId ? 'selected' : ''}>${esc(ruleName(r.rule_id))} · ${d10(r.start_date)}~ · ${r.trade_count}번</option>`).join('')}</select></label></div>
          <div class="chart" id="chart"></div>
          <div class="chart-legend small mute"><span><i class="lg up"></i> 이익 구간</span><span><i class="lg down"></i> 손실 구간</span><span><i class="tri buy"></i> 내 매수</span><span><i class="tri sell"></i> 내 매도</span></div>
        </div>
        <div id="run-box"></div>
      </div>
      <div class="side">
        <div class="card pad" id="order-box"></div>
        <div class="card pad" id="bt-box"></div>
      </div>
    </div></div>`
  drawCompanyChart(); drawRunBox(); drawOrderBox(); drawBtBox()
}
const ruleName = (id) => C.rules.find((r) => r.rule_id === id)?.name ?? '(삭제된 규칙)'

async function drawCompanyChart() {
  const box = $('#chart'); if (!box) return
  const from = C.prices.length ? C.prices[C.prices.length - 1].d : null
  const since = from ? new Date(new Date(d10(from)).getTime() - C.days * 864e5).toISOString().slice(0, 10) : ''
  const shown = C.prices.filter((p) => d10(p.d) >= since)
  const ov = { segments: C.run ? C.run.trades : [], marks: C.showMine ? C.mine.map((m) => ({ d: m.trade_date, side: m.side, text: `${m.side === 'buy' ? '내 매수' : '내 매도'} ${m.qty}주 (${m.account_name})` })) : [] }
  drawChart(box, shown, ov)
}

acts.days = async (b) => {
  C.days = Number(b.dataset.v)
  if (C.days > 365 && C.prices.length < 600) C.prices = await get(`/api/companies/${C.code}/prices?days=800`)
  renderCompany()
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
    renderCompany(); msg($('#bt-msg'), '백테스트 완료 ✓', true)
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
