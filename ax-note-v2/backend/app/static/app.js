/* AX 근거노트 화면 (프레임워크 없이 순수 JavaScript). 주소의 #/ 뒤 경로로 화면을 바꿔요.
   #/  홈   #/c/005930  종목   #/ask  질문하기   #/notes  내 노트 */
'use strict'

// ───────── 공통 도구 ─────────
const $ = (s, r = document) => r.querySelector(s)
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
const won = (n) => `${Math.round(n).toLocaleString('ko-KR')}원`
const rate = (r) => `${r > 0 ? '+' : r < 0 ? '-' : ''}${Math.abs(r).toFixed(2)}%`
const tone = (r) => (r > 0 ? 'up' : r < 0 ? 'down' : 'flat') // 한국 관례: 상승 빨강, 하락 파랑
const eok = (n) => (n >= 10000 ? `${(n / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}조` : `${Math.round(n).toLocaleString('ko-KR')}억`)
const shortDate = (d) => `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}`
const SENT = { pos: '호재', neg: '악재', neu: '일반' } // 내 자료에서 사용자가 직접 표시하는 값
const STANCE = { pos: '긍정', neu: '중립', neg: '부정' }
const DOC = { news: '내 자료', filing: '공시' }

function clientId() {
  try {
    let id = localStorage.getItem('axnote-client-id')
    if (!id) {
      id = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()) + Math.random().toString(16).slice(2)
      localStorage.setItem('axnote-client-id', id)
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
let view = '' // 지금 보이는 화면: home | company | notes
let routeToken = 0 // 화면이 바뀐 뒤 늦게 도착한 응답은 버려요

function toast(msg) {
  const el = $('.toast')
  if (el) {
    el.textContent = msg
    setTimeout(() => el.textContent === msg && (el.textContent = ''), 2500)
  }
}

// ───────── 노트 담기 (종목 화면) ─────────
const tray = { code: null, notes: [], activeId: null }

async function loadTray(code) {
  tray.code = code
  tray.notes = await get(`/api/notes?company_code=${code}`)
  if (!tray.notes.find((n) => n.note_id === tray.activeId)) tray.activeId = tray.notes[0]?.note_id ?? null
}
const activeNote = () => tray.notes.find((n) => n.note_id === tray.activeId)
const addedDocs = () => new Set((activeNote()?.evidence ?? []).filter((e) => e.kind === 'document').map((e) => e.document.doc_id))
const addedPrices = () => new Set((activeNote()?.evidence ?? []).filter((e) => e.kind === 'price').map((e) => e.price.price_id))

async function createTrayNote(name, title) {
  const n = await api('POST', '/api/notes', { company_code: tray.code, title: title || `${name} 분석 노트` })
  tray.notes.unshift(n)
  tray.activeId = n.note_id
  return n
}

async function addEvidence(payload, name) {
  try {
    if (!activeNote()) await createTrayNote(name)
    const n = await api('POST', `/api/notes/${tray.activeId}/evidence`, payload)
    tray.notes = tray.notes.map((x) => (x.note_id === n.note_id ? n : x))
    return '노트에 담았어요 ✓'
  } catch (e) {
    return e.message
  }
}

function notebarHTML() {
  const a = activeNote()
  return `<div class="notebar" role="group" aria-label="노트 선택">
    <span class="small mute">담을 노트</span>
    <select id="tray-select" aria-label="담을 노트" ${tray.notes.length ? '' : 'disabled'}>
      ${tray.notes.length ? tray.notes.map((n) => `<option value="${n.note_id}" ${n.note_id === tray.activeId ? 'selected' : ''}>${esc(n.title)}</option>`).join('') : '<option>아직 없음 (담으면 자동으로 만들어요)</option>'}
    </select>
    <button type="button" class="btn-sm" data-act="tray-new">+ 새 노트</button>
    ${a ? `<span class="small mute">근거 ${a.evidence.length}개</span><a class="small link" href="#/notes?open=${a.note_id}">노트 열기 →</a>` : ''}
    <span class="toast" role="status"></span>
  </div>`
}
function refreshNotebar() {
  const el = $('.notebar')
  if (el) el.outerHTML = notebarHTML()
}

// ───────── 문서 카드(공시 / 내 자료) ─────────
function docHTML(d, o = {}) {
  const added = o.addedSet?.has(d.doc_id)
  const mine = d.user_added
  return `<article class="doc ${mine ? d.sentiment : 'neu'}" data-doc="${d.doc_id}">
    <div class="doc-head">
      <span class="tag ${mine ? 'mine' : 'filing'}">${mine ? '내 자료' : '공시'}</span>
      ${mine && d.sentiment !== 'neu' ? `<span class="sent ${d.sentiment}">${SENT[d.sentiment]}</span>` : ''}
      <span class="mute small doc-meta">${d.published_date} · ${esc(d.source)}</span>
    </div>
    <button type="button" class="doc-title" aria-expanded="false" data-act="doc-toggle">${esc(d.title)}</button>
    <div class="doc-body" hidden>${d.body ? `<p>${esc(d.body)}</p>` : ''}${d.url && /^https?:\/\//.test(d.url) ? `<a class="link small" href="${esc(d.url)}" target="_blank" rel="noopener noreferrer">원문 보기 ↗</a>` : ''}</div>
    ${o.add || o.edit ? `<div class="doc-actions">
      ${o.add ? `<button type="button" class="btn-sm" data-act="add-doc" data-id="${d.doc_id}" ${added ? 'disabled' : ''}>${added ? '✓ 담았어요' : '+ 노트에 담기'}</button>` : ''}
      ${o.edit && mine ? `<button type="button" class="btn-sm ghost" data-act="doc-edit" data-id="${d.doc_id}">수정</button><button type="button" class="btn-sm ghost danger" data-act="doc-del" data-id="${d.doc_id}">삭제</button>` : ''}
    </div>` : ''}
  </article>`
}

// ───────── 관심종목 ─────────
const W = { codes: new Set(), list: [] }
async function loadWatch() {
  W.list = await get('/api/watchlist')
  W.codes = new Set(W.list.map((w) => w.company.code))
}
const starHTML = (code) => `<button type="button" class="star ${W.codes.has(code) ? 'on' : ''}" data-act="star" data-code="${code}" aria-pressed="${W.codes.has(code)}" aria-label="관심종목" title="관심종목">${W.codes.has(code) ? '★' : '☆'}</button>`

// ───────── 주가 차트(SVG 문자열) ─────────
const CW = 900, CH = 330, CM = { l: 70, r: 14, t: 14 }, PRICE_B = 232, VOL_T = 252, VOL_B = 296

function chartGeom(prices) {
  const n = prices.length
  const lo = Math.min(...prices.map((p) => p.low)), hi = Math.max(...prices.map((p) => p.high))
  const pad = (hi - lo) * 0.06, minY = lo - pad, maxY = hi + pad
  const vmax = Math.max(...prices.map((p) => p.volume))
  const x = (i) => CM.l + (i / Math.max(n - 1, 1)) * (CW - CM.l - CM.r)
  const y = (v) => CM.t + (1 - (v - minY) / (maxY - minY)) * (PRICE_B - CM.t)
  return { n, x, y, minY, maxY, vmax }
}

function chartHTML(prices, events, selected) {
  if (!prices.length) return '<p class="mute">시세 데이터가 없어요.</p>'
  const g = chartGeom(prices)
  const idx = Object.fromEntries(prices.map((p, i) => [p.trade_date, i]))
  const line = prices.map((p, i) => `${g.x(i).toFixed(1)},${g.y(p.close).toFixed(1)}`).join(' ')
  const ticks = Array.from({ length: 5 }, (_, k) => g.minY + ((g.maxY - g.minY) * k) / 4)
  const months = []
  prices.forEach((p, i) => (i === 0 || p.trade_date.slice(5, 7) !== prices[i - 1].trade_date.slice(5, 7)) && months.push(i))
  const step = Math.ceil(months.length / 8)
  const vis = events.filter((e) => idx[e.trade_date] != null)
  return `<div class="chart" id="chart">
  <svg viewBox="0 0 ${CW} ${CH}" role="group" aria-label="주가 차트. 급등락일 ${vis.length}번">
    <defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--accent)" stop-opacity="0.18"/><stop offset="1" stop-color="var(--accent)" stop-opacity="0"/></linearGradient></defs>
    ${ticks.map((t) => `<line x1="${CM.l}" x2="${CW - CM.r}" y1="${g.y(t)}" y2="${g.y(t)}" class="grid"/><text x="${CM.l - 8}" y="${g.y(t)}" text-anchor="end" dominant-baseline="middle" class="tick">${Math.round(t).toLocaleString('ko-KR')}</text>`).join('')}
    <polygon points="${CM.l},${PRICE_B} ${line} ${CW - CM.r},${PRICE_B}" fill="url(#area)"/>
    <polyline points="${line}" class="price-line"/>
    ${prices.map((p, i) => { const h = (p.volume / g.vmax) * (VOL_B - VOL_T); return `<rect x="${g.x(i) - 1}" y="${VOL_B - h}" width="2" height="${h}" class="vol"/>` }).join('')}
    <text x="${CM.l - 8}" y="${VOL_T + 8}" text-anchor="end" class="tick">거래량</text>
    ${months.filter((_, k) => k % step === 0).map((i) => `<text x="${g.x(i)}" y="${CH - 10}" text-anchor="middle" class="tick">${Number(prices[i].trade_date.slice(5, 7))}월</text>`).join('')}
    <g id="hover" pointer-events="none" style="display:none"><line class="cross" y1="${CM.t}" y2="${VOL_B}"/><circle r="4" class="hover-dot"/></g>
    ${vis.map((e) => {
      const i = idx[e.trade_date], on = selected === e.price_id, cx = g.x(i), cy = g.y(e.close)
      return `<g class="marker ${tone(e.ret_pct)} ${on ? 'on' : ''}" tabindex="0" role="button" aria-pressed="${on}" data-act="event" data-id="${e.price_id}" aria-label="${e.trade_date} ${rate(e.ret_pct)} 급${e.ret_pct > 0 ? '등' : '락'}, 관련 문서 ${e.docs.length}건">
        <circle cx="${cx}" cy="${cy}" r="16" class="hit"/>${on ? `<circle cx="${cx}" cy="${cy}" r="12" class="halo"/>` : ''}<circle cx="${cx}" cy="${cy}" r="${on ? 8 : 6}" class="dot"/></g>`
    }).join('')}
  </svg>
  <div class="chart-tip" id="tip" hidden></div>
  <div class="chart-legend small mute"><span><i class="lg up"></i> 급등한 날</span><span><i class="lg down"></i> 급락한 날</span><span>점을 누르면 그날 나온 뉴스·공시가 열려요 (${shortDate(prices[0].trade_date)} ~ ${shortDate(prices[prices.length - 1].trade_date)})</span></div>
</div>`
}

function bindChart(prices) {
  const box = $('#chart')
  if (!box || !prices.length) return
  const g = chartGeom(prices), svg = $('svg', box), hv = $('#hover'), tip = $('#tip')
  svg.addEventListener('mousemove', (e) => {
    const r = svg.getBoundingClientRect(), px = ((e.clientX - r.left) / r.width) * CW
    const i = Math.min(g.n - 1, Math.max(0, Math.round(((px - CM.l) / (CW - CM.l - CM.r)) * (g.n - 1))))
    const p = prices[i]
    hv.style.display = ''
    $('line', hv).setAttribute('x1', g.x(i)); $('line', hv).setAttribute('x2', g.x(i))
    $('circle', hv).setAttribute('cx', g.x(i)); $('circle', hv).setAttribute('cy', g.y(p.close))
    tip.hidden = false
    tip.style.left = `${(g.x(i) / CW) * 100}%`
    tip.innerHTML = `<b>${p.trade_date}</b><span class="num">${won(p.close)}</span><span class="mute small num">거래량 ${p.volume.toLocaleString('ko-KR')}</span>`
  })
  svg.addEventListener('mouseleave', () => { hv.style.display = 'none'; tip.hidden = true })
  svg.querySelectorAll('.marker').forEach((m) => m.addEventListener('keydown', (e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), m.dispatchEvent(new MouseEvent('click', { bubbles: true })))))
}

// ───────── 재무 ─────────
function barsHTML(title, rows, field, color) {
  const max = Math.max(...rows.map((r) => Math.max(r[field], 0)), 1), W = 420, H = 170, bw = W / rows.length
  return `<figure class="bars"><figcaption>${title}</figcaption><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${title}"><line x1="0" x2="${W}" y1="${H - 26}" y2="${H - 26}" class="grid"/>
  ${rows.map((r, i) => {
    const h = (Math.max(r[field], 0) / max) * (H - 62), last = i === rows.length - 1
    return `<g><title>${r.fiscal_year}년 ${eok(r[field])}원</title><rect x="${i * bw + 8}" y="${H - 26 - h}" width="${bw - 16}" height="${h}" rx="4" fill="${color}" opacity="${last ? 1 : 0.55}"/>
    ${last ? `<text x="${i * bw + bw / 2}" y="${H - 32 - h}" text-anchor="middle" class="bar-val">${eok(r[field])}</text>` : ''}
    <text x="${i * bw + bw / 2}" y="${H - 8}" text-anchor="middle" class="tick">${r.fiscal_year}</text></g>`
  }).join('')}</svg></figure>`
}
function finHTML(rows) {
  const asc = [...rows].reverse()
  return `<div class="fin"><div class="fin-bars">${barsHTML('연간 매출', asc, 'revenue', 'var(--accent)')}${barsHTML('연간 영업이익', asc, 'operating_profit', 'var(--accent-2)')}</div>
  <div class="scroll"><table><thead><tr><th>연도</th><th>매출(억원)</th><th>영업이익(억원)</th><th>영업이익률</th><th>매출 성장률</th></tr></thead><tbody>
  ${rows.map((r) => `<tr><td>${r.fiscal_year}년</td><td class="num">${Math.round(r.revenue).toLocaleString('ko-KR')}</td><td class="num">${Math.round(r.operating_profit).toLocaleString('ko-KR')}</td><td class="num">${r.op_margin == null ? '-' : r.op_margin.toFixed(1) + '%'}</td><td class="num ${r.rev_growth == null ? '' : tone(r.rev_growth)}">${r.rev_growth == null ? '-' : pct(r.rev_growth)}</td></tr>`).join('')}
  </tbody></table></div></div>`
}

// ───────── 홈 ─────────
function cardHTML(c) {
  return `<div class="company-card"><a class="cc-link" href="#/c/${c.code}"><span class="cc-name">${esc(c.name)}</span><span class="mute num small">${c.code}</span><span class="num cc-price">${c.price != null ? won(c.price) : '-'}</span><span class="num ${tone(c.change_rate)}">${c.price != null ? rate(c.change_rate) : ''}</span></a>${starHTML(c.code)}</div>`
}

async function pageHome(tok) {
  app.innerHTML = '<main class="page"><p class="panel-loading">불러오는 중…</p></main>'
  const [companies, status] = await Promise.all([get('/api/companies'), get('/api/status'), loadWatch()])
  if (tok !== routeToken) return
  Object.assign(H, { companies, status })
  drawHome()
}
const H = {}
function drawHome() {
  const { companies, status } = H
  const bySector = {}
  companies.forEach((c) => (bySector[c.sector] ||= []).push(c))
  const banner = status.is_sample
    ? `<div class="banner warn" role="note"><b>샘플 데이터예요.</b> 지금 보이는 시세·재무·공시는 개발용 가상 값이에요. 실데이터는 <code>python -m app.ingest all</code> 로 받아요.</div>`
    : `<div class="banner ok" role="note"><b>실데이터</b> (${esc(status.source)}) · 마지막 시세 ${status.last_price_date ?? '-'} · 공시 ${status.counts.filing.toLocaleString('ko-KR')}건</div>`
  app.innerHTML = `<main class="page">
    <section class="hero"><h1>주가가 움직인 날, <em>공시</em>가 말해 줘요</h1>
      <p>주가가 크게 오르내린 날의 공시를 한눈에 찾고, 내 판단의 근거를 노트에 모아 보세요.</p></section>
    ${banner}
    <div class="sec-head"><h2>내 관심종목</h2><span class="mute small">★ 을 누르면 여기에 모여요</span></div>
    ${W.list.length ? `<div class="cards">${W.list.map((w) => cardHTML(w.company)).join('')}</div>` : '<p class="cards-empty">아직 없어요. 아래 종목에서 ☆ 를 눌러 보세요.</p>'}
    <div class="sec-head"><h2>종목 둘러보기</h2><span class="mute small">종목을 누르면 주가 차트에 급등락일과 그날의 공시가 함께 나와요</span></div>
    ${Object.entries(bySector).map(([s, list]) => `<div class="sector-block"><div class="sector-name">${esc(s)}</div><div class="cards">${list.map(cardHTML).join('')}</div></div>`).join('')}
  </main>`
}

// ───────── 종목 ─────────
const TABS = ['주가·공시', '분석', '재무·업종비교', '공시·내 자료']
const RANGES = [['3개월', 63], ['6개월', 126], ['1년', 250]]
const C = {} // 종목 화면 상태

async function pageCompany(tok, code) {
  app.innerHTML = '<main class="page"><p class="panel-loading">불러오는 중…</p></main>'
  try {
    const [company, prices, events, monthly, fins, docs, analysis, peers] = await Promise.all([
      get(`/api/companies/${code}`), get(`/api/companies/${code}/prices`), get(`/api/companies/${code}/events`),
      get(`/api/companies/${code}/monthly`), get(`/api/companies/${code}/financials`), get(`/api/companies/${code}/documents`),
      get(`/api/companies/${code}/analysis`).catch(() => null), get(`/api/companies/${code}/peers`).catch(() => []),
      loadTray(code), loadWatch(),
    ])
    if (tok !== routeToken) return
    Object.assign(C, { code, company, prices, events, monthly, fins, docs, analysis, peers, tab: TABS[0], range: 250, sel: null, docType: '', form: null })
    drawCompany()
  } catch (e) {
    if (tok === routeToken) app.innerHTML = '<main class="page"><p class="table-empty">종목 정보를 불러오지 못했어요. <a class="link" href="#/">홈으로 돌아가기</a></p></main>'
  }
}

function docFormHTML(init) {
  const f = init || { published_date: C.prices.at(-1)?.trade_date ?? '', sentiment: 'neu', title: '', body: '', source: '', url: '' }
  return `<form class="docform card" id="docform">
    <div class="row">
      <input type="date" name="published_date" value="${f.published_date}" aria-label="날짜" required />
      <select name="sentiment" aria-label="호재·악재">${Object.entries(SENT).map(([k, v]) => `<option value="${k}" ${f.sentiment === k ? 'selected' : ''}>${v}</option>`).join('')}</select>
      <input name="source" value="${esc(f.source === '직접 입력' ? '' : f.source)}" placeholder="출처(예: 한국경제)" maxlength="60" aria-label="출처" />
      <span class="grow"></span>
      <button type="button" class="btn ghost" data-act="form-cancel">취소</button>
      <button type="submit" class="btn">${init ? '수정 저장' : '추가'}</button>
    </div>
    <input name="title" value="${esc(f.title)}" placeholder="제목 (예: 기사 제목)" maxlength="200" required aria-label="제목" />
    <input name="url" value="${esc(f.url ?? '')}" placeholder="링크 (https://… 선택)" maxlength="300" aria-label="링크" />
    <textarea name="body" placeholder="내가 확인한 내용·메모 (선택)" rows="3" maxlength="5000" aria-label="본문">${esc(f.body)}</textarea>
    <p class="err small" id="docform-err"></p>
  </form>`
}

const pct = (v, plus = true) => (v == null ? '-' : `${plus && v > 0 ? '+' : ''}${v.toFixed(2)}%`)

function analysisHTML() {
  const a = C.analysis
  if (!a) return '<p class="table-empty">시세 데이터가 없어요.</p>'
  const stat = (label, value, cls, hint) => `<div class="stat card"><span class="mute small">${label}</span><b class="num ${cls || ''}">${value}</b><span class="mute small">${hint}</span></div>`
  return `<div class="stats">
    ${Object.entries(a.returns).map(([k, v]) => stat(`${k} 수익률`, pct(v), v == null ? '' : tone(v), '지금 종가 ÷ 그때 종가')).join('')}
    ${stat('최대 낙폭(1년)', pct(a.mdd, false), a.mdd ? 'down' : '', '최고가 대비 가장 크게 내려간 폭')}
    ${stat('변동성(연환산)', a.volatility_annual == null ? '-' : `${a.volatility_annual}%`, '', `하루 평균 ±${a.volatility_daily ?? '-'}% 출렁임`)}
    ${stat('120일선 괴리율', pct(a.ma120_gap), a.ma120_gap == null ? '' : tone(a.ma120_gap), a.ma120 ? `120일 평균 ${won(a.ma120)}` : '120거래일 데이터 필요')}
  </div><p class="mute small" style="margin-top:12px">기준일 ${a.trade_date} · 윈도 함수(<code>LAG</code>, <code>MAX OVER</code>, <code>AVG OVER</code>)로 계산한 값이에요. 투자 권유가 아니에요.</p>`
}

function peersHTML() {
  if (!C.peers.length) return ''
  const me = C.company.code
  return `<h3 style="margin:22px 0 8px">같은 업종 비교 <span class="mute small">(최신 연도 · 업종 ${C.peers[0].n}개 회사)</span></h3>
  <div class="scroll card"><table><thead><tr><th>회사</th><th>영업이익률</th><th>순위</th><th>매출 성장률</th><th>순위</th></tr></thead><tbody>
  ${C.peers.map((p) => `<tr class="${p.code === me ? 'me' : ''}"><td>${esc(p.name)} <span class="mute small">${p.fiscal_year}</span></td><td class="num">${p.op_margin ?? '-'}%</td><td class="num">${p.margin_rank}위</td><td class="num ${p.rev_growth == null ? '' : tone(p.rev_growth)}">${p.rev_growth == null ? '-' : pct(p.rev_growth)}</td><td class="num">${p.growth_rank}위</td></tr>`).join('')}
  <tr class="avg"><td>업종 평균</td><td class="num">${C.peers[0].avg_margin ?? '-'}%</td><td></td><td class="num">${C.peers[0].avg_growth == null ? '-' : pct(C.peers[0].avg_growth)}</td><td></td></tr>
  </tbody></table></div>`
}

function companyBody() {
  if (C.tab === TABS[0]) {
    const shown = C.prices.slice(-C.range)
    const first = shown[0]?.trade_date
    const evs = C.events.filter((e) => e.trade_date >= first)
    const sel = evs.find((e) => e.price_id === C.sel) ?? null
    const panel = sel
      ? `<div class="ep-head"><h3>${sel.trade_date}</h3><button type="button" class="btn-sm ghost" data-act="event-close">닫기</button></div>
         <div><span class="ep-ret num ${tone(sel.ret_pct)}">${rate(sel.ret_pct)}</span> <span class="mute small num">${won(sel.prev_close)} → ${won(sel.close)}</span></div>
         <button type="button" class="btn-sm" data-act="add-price" data-id="${sel.price_id}" ${addedPrices().has(sel.price_id) ? 'disabled' : ''}>${addedPrices().has(sel.price_id) ? '✓ 이 날 담았어요' : '+ 이 날을 노트에 담기'}</button>
         <h4>이 시기에 나온 공시·내 자료</h4>
         ${sel.docs.length ? sel.docs.map((d) => docHTML(d, { add: true, addedSet: addedDocs() })).join('') : '<p class="mute small">이 날 전후 공시가 없어요. 직접 찾은 기사는 「공시·내 자료」 탭에서 추가할 수 있어요.</p>'}`
      : `<h3>급등락일 ${evs.length}번</h3><p class="mute small">차트의 점을 누르거나 아래에서 골라 보세요. 하루 4% 이상 움직인 날이에요.</p>
         <div class="event-list">${evs.map((e) => `<button type="button" data-act="event" data-id="${e.price_id}"><span class="num">${e.trade_date}</span><span class="num ${tone(e.ret_pct)}">${rate(e.ret_pct)}</span></button>`).join('') || '<p class="mute small">이 기간엔 없어요.</p>'}</div>`
    return `<div class="event-layout">
      <section class="card chart-card">
        <div class="toolbar"><div class="seg" role="group" aria-label="기간">${RANGES.map(([n, v]) => `<button type="button" data-act="range" data-v="${v}" aria-pressed="${C.range === v}">${n}</button>`).join('')}</div><span class="mute small">급등락 기준: 하루 4% 이상</span></div>
        ${chartHTML(shown, evs, C.sel)}
        <details class="monthly"><summary>월별 통계 보기 (SQL GROUP BY)</summary><div class="scroll"><table><thead><tr><th>월</th><th>평균 종가</th><th>최저</th><th>최고</th><th>거래량 합</th></tr></thead><tbody>
          ${C.monthly.map((m) => `<tr><td>${m.ym}</td><td class="num">${won(m.avg_close)}</td><td class="num">${won(m.low)}</td><td class="num">${won(m.high)}</td><td class="num">${Math.round(m.volume).toLocaleString('ko-KR')}</td></tr>`).join('')}</tbody></table></div></details>
      </section>
      <aside class="card event-panel" aria-label="급등락일 이슈">${panel}</aside></div>`
  }
  if (C.tab === TABS[1]) return `<h2 style="margin-bottom:12px">가격 흐름 분석</h2>${analysisHTML()}`
  if (C.tab === TABS[2]) return `<h2 style="margin-bottom:12px">연간 재무</h2>${C.fins.length ? finHTML(C.fins) : '<p class="table-empty">재무 데이터가 없어요.</p>'}${peersHTML()}`
  const list = C.docs.filter((d) => !C.docType || (C.docType === 'mine' ? d.user_added : !d.user_added))
  return `<div class="docs-tab">
    <div class="row"><div class="seg" role="group" aria-label="종류">${[['', '전체'], ['filing', '공시'], ['mine', '내 자료']].map(([k, n]) => `<button type="button" data-act="doctype" data-v="${k}" aria-pressed="${C.docType === k}">${n}</button>`).join('')}</div>
      <span class="grow"></span><button type="button" class="btn" data-act="form-new">+ 내 자료 추가</button></div>
    <p class="mute small">공시는 OpenDART에서 수집한 원본이라 고칠 수 없어요. 기사·메모는 직접 확인한 것만 「내 자료」로 추가해 근거로 쓰세요.</p>
    ${C.form ? docFormHTML(C.form === 'new' ? null : C.form) : ''}
    <div class="doclist">${list.map((d) => docHTML(d, { add: true, edit: true, addedSet: addedDocs() })).join('') || '<p class="table-empty">문서가 없어요.</p>'}</div></div>`
}

function drawCompany() {
  const c = C.company
  app.innerHTML = `<main class="page">
    <div class="company-head"><h1>${esc(c.name)}</h1><span class="mute small">${c.code} · ${esc(c.sector)}</span>${starHTML(c.code)}</div>
    <div class="num price">${c.price != null ? won(c.price) : '-'} <span class="small ${tone(c.change_rate)}">${c.price != null ? rate(c.change_rate) : ''}</span></div>
    ${notebarHTML()}
    <div class="tabs" role="tablist">${TABS.map((t) => `<button type="button" role="tab" data-act="tab" data-v="${t}" aria-selected="${C.tab === t}">${t}</button>`).join('')}</div>
    <div id="company-body">${companyBody()}</div></main>`
  afterBody()
}
function afterBody() {
  if (C.tab === TABS[0]) bindChart(C.prices.slice(-C.range))
}
function drawBody() {
  $('#company-body').innerHTML = companyBody()
  document.querySelectorAll('.tabs [role=tab]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.v === C.tab)))
  refreshNotebar()
  afterBody()
}

// ───────── 내 노트 ─────────
const N = {}

async function pageNotes(tok, params) {
  const [companies, notes] = await Promise.all([get('/api/companies'), get('/api/notes')])
  if (tok !== routeToken) return
  Object.assign(N, { companies, notes, openId: Number(params.get('open')) || notes[0]?.note_id || null, confirm: false })
  drawNotes()
}
const openNote = () => N.notes.find((n) => n.note_id === N.openId)
function drawNotes() {
  const n = openNote()
  app.innerHTML = `<main class="page notes-page"><div class="notes-side"><h1>내 노트</h1>
    <form class="newnote card" id="newnote"><select name="company_code" aria-label="종목">${N.companies.map((c) => `<option value="${c.code}">${esc(c.name)}</option>`).join('')}</select>
      <input name="title" placeholder="새 노트 제목" maxlength="120" required aria-label="새 노트 제목" /><button type="submit" class="btn">+ 새 노트</button></form>
    <ul class="note-list">${N.notes.map((x) => `<li><button type="button" data-act="note-open" data-id="${x.note_id}" aria-current="${x.note_id === N.openId}"><b>${esc(x.title)}</b><span class="mute small">${esc(x.company_name)} · 근거 ${x.evidence.length}개</span><span class="stance ${x.stance}">${STANCE[x.stance]}</span></button></li>`).join('')}</ul>
    ${N.notes.length ? '' : '<p class="mute small">노트가 없어요. 위에서 만들거나, 종목 화면에서 뉴스·공시를 담아 보세요.</p>'}</div>
    <div class="notes-main">${n ? editorHTML(n) : '<p class="cards-empty">노트를 고르거나 새로 만들어 보세요.</p>'}</div></main>`
}
function editorHTML(n) {
  return `<section class="card editor">
    <div class="ed-top"><a class="link small" href="#/c/${n.company_code}">${esc(n.company_name)} 보러 가기 →</a><span class="mute small">수정 ${n.updated_at.slice(0, 16).replace('T', ' ')}</span></div>
    <input class="ed-title" id="ed-title" value="${esc(n.title)}" maxlength="120" aria-label="제목" />
    <div class="seg" role="group" aria-label="내 생각">${Object.entries(STANCE).map(([k, v]) => `<button type="button" data-act="stance" data-v="${k}" aria-pressed="${n.stance === k}">${v}</button>`).join('')}</div>
    <textarea id="ed-memo" rows="8" maxlength="5000" aria-label="메모" placeholder="내 생각을 적어 보세요. 아래 근거는 종목 화면이나 질문하기에서 담을 수 있어요.">${esc(n.memo)}</textarea>
    <div class="row"><button type="button" class="btn" data-act="note-save">저장</button><span class="toast" role="status"></span><span class="grow"></span>
      ${N.confirm ? '<span class="small err">정말 삭제할까요?</span><button type="button" class="btn danger" data-act="note-del-yes">삭제</button><button type="button" class="btn ghost" data-act="note-del-no">취소</button>' : '<button type="button" class="btn ghost danger" data-act="note-del">노트 삭제</button>'}</div>
    <h3>담은 근거 ${n.evidence.length}개</h3>
    ${n.evidence.length ? '' : '<p class="mute small">아직 없어요. 종목 화면에서 뉴스·공시 또는 급등락일을 담아 보세요.</p>'}
    <ul class="ev-list">${n.evidence.map((e) => `<li>${e.kind === 'document' ? docHTML(e.document) : `<div class="price-ev"><b class="num">${e.price.trade_date}</b> 종가 <span class="num">${won(e.price.close)}</span> ${e.price.ret_pct != null ? `<span class="num ${tone(e.price.ret_pct)}">${rate(e.price.ret_pct)}</span>` : ''} <span class="mute small">(주가 변동일)</span></div>`}
      <div class="ev-foot"><input data-evc="${e.evidence_id}" value="${esc(e.comment)}" placeholder="이 근거에 대한 내 한 줄 메모" maxlength="300" aria-label="근거 메모" /><button type="button" class="btn-sm ghost danger" data-act="ev-del" data-id="${e.evidence_id}">빼기</button></div></li>`).join('')}</ul></section>`
}
function replaceNote(n) {
  N.notes = N.notes.map((x) => (x.note_id === n.note_id ? n : x)).sort((a, b) => b.updated_at.localeCompare(a.updated_at))
}

// ───────── 클릭 처리(한 곳에서) ─────────
document.addEventListener('click', async (e) => {
  const el = e.target.closest('[data-act]')
  if (!el) return
  const act = el.dataset.act, id = Number(el.dataset.id), v = el.dataset.v
  try {
    switch (act) {
      case 'doc-toggle': {
        const body = el.nextElementSibling, open = body.hidden
        body.hidden = !open
        return void el.setAttribute('aria-expanded', String(open))
      }
      case 'star': {
        const code = el.dataset.code
        W.list = await api(W.codes.has(code) ? 'DELETE' : 'PUT', `/api/watchlist/${code}`)
        W.codes = new Set(W.list.map((w) => w.company.code))
        if (view === 'home') return drawHome()
        return void ($('.company-head .star').outerHTML = starHTML(code))
      }
      case 'tray-new': await createTrayNote(C.company.name); return drawBody()
      case 'tab': C.tab = v; return drawBody()
      case 'range': C.range = Number(v); C.sel = null; return drawBody()
      case 'event': C.sel = C.sel === id ? null : id; return drawBody()
      case 'event-close': C.sel = null; return drawBody()
      case 'doctype': C.docType = v; return drawBody()
      case 'add-doc': {
        const msg = await addEvidence({ doc_id: id }, C.company.name)
        drawBody()
        return toast(msg)
      }
      case 'add-price': {
        const msg = await addEvidence({ price_id: id }, C.company.name)
        drawBody()
        return toast(msg)
      }
      case 'form-new': C.form = 'new'; return drawBody()
      case 'form-cancel': C.form = null; return drawBody()
      case 'doc-edit': C.form = C.docs.find((d) => d.doc_id === id); return drawBody()
      case 'doc-del': {
        if (!confirm('이 자료를 삭제할까요?')) return
        await api('DELETE', `/api/documents/${id}`)
        C.docs = C.docs.filter((d) => d.doc_id !== id)
        C.events = await get(`/api/companies/${C.code}/events`)
        await loadTray(C.code)
        return drawBody()
      }
      case 'note-open': N.openId = id; N.confirm = false; return drawNotes()
      case 'stance': { const n = await api('PUT', `/api/notes/${N.openId}`, { stance: v }); replaceNote(n); return drawNotes() }
      case 'note-save': {
        const n = await api('PUT', `/api/notes/${N.openId}`, { title: $('#ed-title').value.trim() || openNote().title, memo: $('#ed-memo').value })
        replaceNote(n); drawNotes(); return toast('저장했어요 ✓')
      }
      case 'note-del': N.confirm = true; return drawNotes()
      case 'note-del-no': N.confirm = false; return drawNotes()
      case 'note-del-yes':
        await api('DELETE', `/api/notes/${N.openId}`)
        N.notes = N.notes.filter((x) => x.note_id !== N.openId); N.openId = N.notes[0]?.note_id ?? null; N.confirm = false
        return drawNotes()
      case 'ev-del': { const n = await api('DELETE', `/api/notes/${N.openId}/evidence/${id}`); replaceNote(n); return drawNotes() }
    }
  } catch (err) {
    toast(err.message)
  }
})

document.addEventListener('submit', async (e) => {
  e.preventDefault()
  const f = e.target
  try {
    if (f.id === 'newnote') {
      const n = await api('POST', '/api/notes', { company_code: f.company_code.value, title: f.title.value.trim() })
      N.notes.unshift(n); N.openId = n.note_id; return drawNotes()
    }
    if (f.id === 'docform') {
      const body = { title: f.title.value.trim(), body: f.body.value.trim(), sentiment: f.sentiment.value, published_date: f.published_date.value,
                     source: f.source.value.trim() || '직접 입력', ...(f.url.value.trim() ? { url: f.url.value.trim() } : {}) }
      try {
        if (C.form === 'new') {
          C.docs.unshift(await api('POST', '/api/documents', { ...body, company_code: C.code }))
        } else {
          const d = await api('PUT', `/api/documents/${C.form.doc_id}`, body)
          C.docs = C.docs.map((x) => (x.doc_id === d.doc_id ? d : x))
        }
      } catch (err) { return void ($('#docform-err').textContent = err.message) }
      C.docs.sort((a, b) => b.published_date.localeCompare(a.published_date) || b.doc_id - a.doc_id)
      C.events = await get(`/api/companies/${C.code}/events`)
      C.form = null
      return drawBody()
    }
  } catch (err) {
    toast(err.message)
  }
})

// 근거 메모는 입력칸을 벗어날 때 저장해요.
document.addEventListener('focusout', async (ev) => {
  const el = ev.target
  if (!el.dataset || !el.dataset.evc) return
  try {
    const n = await api('PUT', `/api/notes/${N.openId}/evidence/${el.dataset.evc}`, { comment: el.value })
    N.notes = N.notes.map((x) => (x.note_id === n.note_id ? n : x))
  } catch (err) { toast(err.message) }
})

document.addEventListener('change', (e) => {
  if (e.target.id === 'tray-select') { tray.activeId = Number(e.target.value); drawBody() }
})

// ───────── 검색창 ─────────
const sInput = $('#search'), sList = $('#search-list')
let sTimer
sInput.addEventListener('input', () => {
  clearTimeout(sTimer)
  const q = sInput.value.trim()
  if (!q) return void (sList.hidden = true)
  sTimer = setTimeout(async () => {
    const rs = await get(`/api/companies?q=${encodeURIComponent(q)}`).catch(() => [])
    sList.innerHTML = rs.length
      ? rs.map((c) => `<li><button type="button" data-go="${c.code}"><span>${esc(c.name)}</span><span class="mute small">${esc(c.sector)}</span><span class="num">${c.price != null ? won(c.price) : '-'}</span><span class="num ${tone(c.change_rate)}">${c.price != null ? rate(c.change_rate) : ''}</span></button></li>`).join('')
      : '<li class="empty">검색 결과가 없어요</li>'
    sList.hidden = false
  }, 250)
})
sList.addEventListener('click', (e) => {
  const b = e.target.closest('[data-go]')
  if (b) { sList.hidden = true; sInput.value = ''; location.hash = `#/c/${b.dataset.go}` }
})
sInput.addEventListener('keydown', (e) => e.key === 'Enter' && sList.querySelector('[data-go]')?.click())
document.addEventListener('mousedown', (e) => !e.target.closest('.search') && (sList.hidden = true))

// ───────── 라우터 ─────────
async function route() {
  const tok = ++routeToken
  const [path, qs = ''] = (location.hash.slice(1) || '/').split('?')
  const params = new URLSearchParams(qs)
  document.querySelectorAll('[data-nav]').forEach((a) => a.classList.toggle('active', a.dataset.nav === (path === '/' || path.startsWith('/c/') ? 'home' : path.slice(1))))
  window.scrollTo(0, 0)
  try {
    let m
    if (path === '/') { view = 'home'; await pageHome(tok) }
    else if ((m = path.match(/^\/c\/(\w+)$/))) { view = 'company'; await pageCompany(tok, m[1]) }
    else if (path === '/notes') { view = 'notes'; await pageNotes(tok, params) }
    else app.innerHTML = '<main class="page"><p class="table-empty">없는 화면이에요. <a class="link" href="#/">홈으로</a></p></main>'
  } catch (err) {
    if (tok === routeToken) app.innerHTML = `<main class="page"><p class="table-empty">불러오지 못했어요: ${esc(err.message)}</p></main>`
  }
}
window.addEventListener('hashchange', route)
route()

