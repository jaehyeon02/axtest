"use strict";
/*
 * 종목 신호등 대시보드 (라이브러리 없이 순수 JavaScript + SVG)
 * 신호등과 이동평균은 DB 뷰가 계산해 두었고, 이 화면은 API 결과를 그리기만 한다.
 *   GET  /signals, /signals/{code}, /signals/{code}/series, /signals/returns, /signals/sectors
 *   GET/POST/DELETE /members, /watchlist, /trades   GET /trades/portfolio
 */

/* ---------- 작은 도우미 ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const nf = new Intl.NumberFormat("ko-KR");
const SVG_NS = "http://www.w3.org/2000/svg";

function el(tag, props = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return node;
}

function svg(tag, attrs = {}, ...kids) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return node;
}

const fmtInt = (v) => (v === null || v === undefined ? "-" : nf.format(v));
const fmtWon = (v) => (v === null || v === undefined ? "-" : nf.format(Math.round(v)) + "원");
const fmtPct = (v) => (v === null || v === undefined ? "-" : Number(v).toFixed(2) + "%");

function fmtBig(v) {
  if (v === null || v === undefined) return "-";
  const a = Math.abs(v);
  if (a >= 1e12) return (v / 1e12).toFixed(1) + "조";
  if (a >= 1e8) return nf.format(Math.round(v / 1e8)) + "억";
  return nf.format(v);
}

/** 등락률: 상승은 빨강(▲), 하락은 파랑(▼) */
function chgNode(v) {
  if (v === null || v === undefined) return "-";
  const n = Number(v);
  const cls = n > 0 ? "up" : n < 0 ? "down" : "";
  const arrow = n > 0 ? "▲" : n < 0 ? "▼" : "–";
  return el("span", { class: cls, text: `${arrow} ${Math.abs(n).toFixed(2)}%` });
}

let toastTimer;
function toast(message, isError = false) {
  const t = $("#toast");
  t.textContent = message;
  t.className = "show" + (isError ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = ""; }, 2800);
}

function setMessage(host, text, cls = "empty") {
  host.replaceChildren(el("div", { class: cls, text }));
}

/* ---------- API 호출 ---------- */
class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

/** FastAPI 오류 응답({"detail": ...})을 사람이 읽을 문장으로 바꾼다. */
function detailText(body) {
  const d = body && body.detail;
  if (!d) return "요청에 실패했습니다.";
  if (Array.isArray(d)) {
    return d.map((e) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join(" / ");
  }
  return String(d);
}

async function api(path, options = {}) {
  const init = { ...options };
  if (options.body !== undefined) init.headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const res = await fetch(path, init);
  if (res.status === 204) return null;
  let body = null;
  try { body = await res.json(); } catch (_) { /* 본문이 없는 응답 */ }
  if (!res.ok) throw new ApiError(res.status, detailText(body));
  return body;
}

function qs(params) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== "") p.set(k, v);
  }
  const s = p.toString();
  return s ? "?" + s : "";
}

/* ---------- 표 ---------- */
function table(cols, rows, { onRowClick } = {}) {
  const head = el("thead", {}, el("tr", {}, cols.map((c) => el("th", { class: c.right ? "r" : "", scope: "col", text: c.label }))));
  const body = el("tbody", {}, rows.map((row) => {
    const tr = el("tr", { class: onRowClick ? "click" : "" }, row.cells.map((cell, i) => el("td", { class: cols[i].right ? "r" : "" }, cell)));
    if (onRowClick) {
      tr.tabIndex = 0;
      tr.addEventListener("click", () => onRowClick(row));
      tr.addEventListener("keydown", (e) => { if (e.key === "Enter") onRowClick(row); });
    }
    return tr;
  }));
  return el("table", {}, head, body);
}

/* ---------- 차트 (SVG) ---------- */
function niceTicks(min, max, count = 5) {
  const span = max - min;
  if (!(span > 0)) return [min];
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-6; v += step) {
    ticks.push(Math.round(v / step) * step);
  }
  return ticks;
}

/* ---------- 신호등 ---------- */
const SIG = {
  good: { mark: "●", text: "좋음", cls: "sg-good" },
  normal: { mark: "◐", text: "보통", cls: "sg-normal" },
  caution: { mark: "▲", text: "주의", cls: "sg-caution" },
  na: { mark: "–", text: "부족", cls: "sg-na" },
};
const SIG_NAMES = { sig_trend: "추세", sig_volume: "거래량", sig_position: "가격 위치", sig_momentum: "단기 흐름" };

function sigNode(value) {
  const s = SIG[value] || SIG.na;
  return el("span", { class: "sg " + s.cls, title: s.text }, el("span", { "aria-hidden": "true", text: s.mark }), " " + s.text);
}

/** 신호 값 → 초보자용 설명 문장 (기준 숫자는 sql/01_schema.sql 의 v_latest_signal 과 같다) */
function explain(d) {
  const f1 = (v) => (v === null || v === undefined ? "-" : Number(v).toFixed(1));
  const t = {
    good: "5일·20일·60일 평균이 위에서부터 차례로 놓인 상승 흐름이에요.",
    normal: "5일·20일·60일 평균이 한 방향으로 정렬되지는 않았어요.",
    caution: "5일·20일·60일 평균이 아래에서부터 차례로 놓인 하락 흐름이에요.",
    na: "평균을 구할 시세가 60거래일보다 적어요.",
  };
  const v = {
    good: `거래량이 최근 20일 평균의 ${f1(d.volume_ratio)}배로 늘었어요.`,
    normal: `거래량이 최근 20일 평균과 비슷해요(${f1(d.volume_ratio)}배).`,
    caution: `거래량이 최근 20일 평균의 ${f1(d.volume_ratio)}배로 줄었어요.`,
    na: "거래량 비교에 쓸 시세가 부족해요.",
  };
  const p = {
    good: `52주 범위의 아래쪽(${f1(d.pos_52w)}%)이라 가격대가 낮은 편이에요.`,
    normal: `52주 범위의 가운데쯤(${f1(d.pos_52w)}%)이에요.`,
    caution: `52주 범위의 위쪽(${f1(d.pos_52w)}%)이라 가격대가 높은 편이에요.`,
    na: "52주 위치를 계산할 시세가 부족해요(60거래일 필요).",
  };
  const m = {
    good: `최근 1주 동안 ${f1(d.ret_1w)}% 올랐어요.`,
    normal: `최근 1주 변화가 ${f1(d.ret_1w)}%로 크지 않아요.`,
    caution: `최근 1주 동안 ${f1(d.ret_1w)}% 내렸어요.`,
    na: "1주 수익률을 계산할 시세가 부족해요.",
  };
  return {
    sig_trend: t[d.sig_trend] || t.na, sig_volume: v[d.sig_volume] || v.na,
    sig_position: p[d.sig_position] || p.na, sig_momentum: m[d.sig_momentum] || m.na,
  };
}

/* ---------- 상태 ---------- */
const state = { member: null, signals: [], watch: new Map(), code: null, seq: 0, ret: "1m" };

/* ---------- 회원 ---------- */
async function loadMembers(selectId) {
  const members = await api("/members");
  const sel = $("#member");
  sel.replaceChildren(...members.map((m) => el("option", { value: m.member_id, text: m.nickname })));
  if (!members.length) { state.member = null; return; }
  const keep = selectId ?? state.member ?? members[0].member_id;
  sel.value = String(members.some((m) => m.member_id === keep) ? keep : members[0].member_id);
  state.member = Number(sel.value);
}

async function loadMine() {
  const host = $("#watch-body"), pf = $("#pf-body");
  if (state.member === null) {
    state.watch = new Map();
    setMessage(host, "회원을 먼저 만드세요 (위의 닉네임 입력).");
    setMessage(pf, "회원을 먼저 만드세요.");
    renderSignals();
    return;
  }
  const [watch, folio, trades] = await Promise.all([
    api("/watchlist" + qs({ member_id: state.member })),
    api("/trades/portfolio" + qs({ member_id: state.member })),
    api("/trades" + qs({ member_id: state.member, limit: 8 })),
  ]);
  state.watch = new Map(watch.map((w) => [w.code, w.watch_id]));
  renderSignals();
  renderWatch(watch);
  renderPortfolio(folio, trades);
}

/* ---------- 신호등 목록 ---------- */
async function loadSignals() {
  const host = $("#sig-body");
  try {
    state.signals = await api("/signals" + qs({ sector: $("#f-sector").value, order_by: $("#f-order").value }));
    renderSignals();
  } catch (e) { setMessage(host, e.message, "error"); }
}

function renderSignals() {
  const host = $("#sig-body");
  if (!state.signals.length) {
    setMessage(host, "종목이 없습니다. `python -m scripts.load_master` 로 종목을 적재하세요.");
    return;
  }
  const cols = [
    { label: "관심" }, { label: "종목" }, { label: "업종" }, { label: "종가", right: true }, { label: "등락", right: true },
    { label: "추세" }, { label: "거래량" }, { label: "가격 위치" }, { label: "단기 흐름" }, { label: "1개월", right: true },
  ];
  const rows = state.signals.map((s) => {
    const watched = state.watch.has(s.code);
    const star = el("button", {
      type: "button", class: "star" + (watched ? " on" : ""), "aria-pressed": String(watched),
      "aria-label": `${s.name} 관심종목 ${watched ? "해제" : "추가"}`, text: watched ? "★" : "☆",
      onclick: (ev) => { ev.stopPropagation(); toggleWatch(s, ev.currentTarget); },
    });
    return {
      code: s.code,
      cells: [star, el("span", {}, el("strong", { text: s.name }), el("span", { class: "muted", text: " " + s.code })),
        s.sector_name || "-", s.close_price === null ? "-" : fmtInt(s.close_price), chgNode(s.change_pct),
        sigNode(s.sig_trend), sigNode(s.sig_volume), sigNode(s.sig_position), sigNode(s.sig_momentum),
        s.ret_1m === null ? "-" : chgNode(s.ret_1m)],
    };
  });
  const t = table(cols, rows, { onRowClick: (r) => selectStock(r.code) });
  host.replaceChildren(t);
}

async function toggleWatch(s, btn) {
  if (state.member === null) { toast("회원을 먼저 만드세요.", true); return; }
  btn.disabled = true;
  try {
    if (state.watch.has(s.code)) {
      await api(`/watchlist/${state.watch.get(s.code)}`, { method: "DELETE" });
      toast(`${s.name} 관심종목에서 뺐어요.`);
    } else {
      const company = (await api("/companies" + qs({ q: s.name }))).find((c) => c.code === s.code);
      await api("/watchlist", { method: "POST", body: JSON.stringify({ member_id: state.member, company_id: company.company_id }) });
      toast(`${s.name} 관심종목에 담았어요.`);
    }
    await loadMine();
  } catch (e) { toast(e.message, true); btn.disabled = false; }
}

/* ---------- 종목 상세 ---------- */
async function selectStock(code) {
  state.code = code;
  const seq = ++state.seq;
  const host = $("#detail-body");
  setMessage(host, "불러오는 중…");
  try {
    const d = await api(`/signals/${code}`);
    if (seq !== state.seq) return;
    $("#detail-title").textContent = `${d.name} (${d.code})`;
    if (d.close_price === null) {
      setMessage(host, "이 종목은 시세 데이터가 없어 신호등을 계산할 수 없어요. `scripts.collect_prices` 로 시세를 적재하세요.");
      return;
    }
    const series = await api(`/signals/${code}/series` + qs({ limit: 120 }));
    if (seq !== state.seq) return;
    const why = explain(d);
    const kpis = el("div", { class: "kpis" },
      kpi("종가", fmtWon(d.close_price), `${d.trade_date} 기준`),
      kpi("1주 수익률", chgNode(d.ret_1w)), kpi("1개월 수익률", chgNode(d.ret_1m)), kpi("3개월 수익률", chgNode(d.ret_3m)),
      kpi("52주 위치", d.pos_52w === null ? "-" : d.pos_52w.toFixed(1) + "%", d.pos_52w === null ? "시세 60거래일 필요" : `${fmtInt(d.low_52w)} ~ ${fmtInt(d.high_52w)}`));
    const list = el("ul", { class: "why" }, Object.keys(SIG_NAMES).map((k) =>
      el("li", {}, el("span", { class: "why-name", text: SIG_NAMES[k] }), sigNode(d[k]), el("span", { text: why[k] }))));
    const chart = el("div", { class: "chart" });
    host.replaceChildren(kpis, list, el("h3", { text: "종가와 이동평균" }), chart);
    drawSeries(chart, series);
  } catch (e) { if (seq === state.seq) setMessage(host, e.message, "error"); }
}

function kpi(label, value, sub) {
  return el("div", { class: "kpi" }, el("div", { class: "k", text: label }), el("div", { class: "v" }, value), sub ? el("div", { class: "s", text: sub }) : null);
}

/** 종가 선 + 5/20/60일 이동평균 선. 마우스를 올리면 그 날의 값을 보여 준다. */
function drawSeries(host, rows) {
  host.replaceChildren();
  if (rows.length < 2) { setMessage(host, "차트를 그릴 시세가 부족합니다."); return; }
  const W = Math.max(host.clientWidth || 640, 280), H = 260;
  const m = { l: 56, r: 12, t: 12, b: 26 };
  const vals = rows.flatMap((r) => [r.close_price, r.ma5, r.ma20, r.ma60]).filter((v) => v !== null);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.06 || 1; lo -= pad; hi += pad;
  const x = (i) => m.l + (i / (rows.length - 1)) * (W - m.l - m.r);
  const y = (v) => m.t + (1 - (v - lo) / (hi - lo)) * (H - m.t - m.b);
  const line = (key, cls) => {
    let d = "", pen = false;
    rows.forEach((r, i) => { if (r[key] === null) { pen = false; return; } d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(r[key]).toFixed(1)}`; pen = true; });
    return svg("path", { d, class: cls });
  };
  const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "종가와 이동평균 선 차트" });
  for (const t of niceTicks(lo, hi, 4)) {
    s.append(svg("line", { x1: m.l, x2: W - m.r, y1: y(t), y2: y(t), class: "gridline" }),
      svg("text", { x: m.l - 6, y: y(t) + 4, "text-anchor": "end", class: "axis" }, nf.format(t)));
  }
  const n = Math.min(W < 480 ? 3 : 5, rows.length);
  s.append(svg("g", { class: "axis" }, Array.from({ length: n }, (_, k) => {
    const i = Math.round((k * (rows.length - 1)) / (n - 1));
    return svg("text", { x: x(i), y: H - 6, "text-anchor": k === 0 ? "start" : k === n - 1 ? "end" : "middle" }, rows[i].trade_date.slice(2));
  })));
  s.append(line("ma60", "l-ma60"), line("ma20", "l-ma20"), line("ma5", "l-ma5"), line("close_price", "line"));
  const cross = svg("line", { y1: m.t, y2: H - m.b, class: "cross", visibility: "hidden" });
  const tip = el("div", { class: "tip", hidden: true });
  const hit = svg("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent" });
  hit.addEventListener("mousemove", (ev) => {
    const box = s.getBoundingClientRect();
    const px = ((ev.clientX - box.left) / box.width) * W;
    const i = Math.max(0, Math.min(rows.length - 1, Math.round(((px - m.l) / (W - m.l - m.r)) * (rows.length - 1))));
    const r = rows[i];
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
    tip.replaceChildren(el("div", { text: r.trade_date }), el("div", { text: "종가 " + fmtInt(r.close_price) }),
      el("div", { text: `5일 ${fmtInt(r.ma5)} · 20일 ${fmtInt(r.ma20)}` }), el("div", { text: "60일 " + fmtInt(r.ma60) }));
    tip.hidden = false;
    tip.style.left = Math.min(Math.max(((x(i) / W) * box.width) + 12, 0), box.width - 150) + "px";
    tip.style.top = "8px";
  });
  hit.addEventListener("mouseleave", () => { cross.setAttribute("visibility", "hidden"); tip.hidden = true; });
  s.append(cross, hit);
  const legend = el("div", { class: "legend" }, el("span", { class: "lg c0", text: "종가" }), el("span", { class: "lg c5", text: "5일" }),
    el("span", { class: "lg c20", text: "20일" }), el("span", { class: "lg c60", text: "60일" }));
  host.append(legend, s, tip);
}

/* ---------- 관심종목 / 포트폴리오 ---------- */
function renderWatch(rows) {
  const host = $("#watch-body");
  if (!rows.length) { setMessage(host, "관심종목이 없어요. 위 표에서 ☆ 를 눌러 담아 보세요."); return; }
  const cols = [{ label: "종목" }, { label: "종가", right: true }, { label: "등락", right: true }, { label: "추세" }, { label: "" }];
  host.replaceChildren(table(cols, rows.map((w) => ({
    code: w.code,
    cells: [el("strong", { text: w.name }), fmtInt(w.close_price), chgNode(w.change_pct), sigNode(w.sig_trend),
      el("button", { type: "button", class: "btn small", text: "해제", "aria-label": `${w.name} 관심종목 해제`,
        onclick: async (ev) => { ev.stopPropagation(); try { await api(`/watchlist/${w.watch_id}`, { method: "DELETE" }); await loadMine(); } catch (e) { toast(e.message, true); } } })],
  })), { onRowClick: (r) => selectStock(r.code) }));
}

function renderPortfolio(folio, trades) {
  const host = $("#pf-body");
  const t = folio.total;
  const summary = el("div", { class: "kpis" }, kpi("평가금액", fmtWon(t.market_value)), kpi("평가손익", el("span", { class: t.pnl > 0 ? "up" : t.pnl < 0 ? "down" : "", text: (t.pnl > 0 ? "+" : "") + fmtWon(t.pnl) })),
    kpi("수익률", t.pnl_pct === null ? "-" : chgNode(t.pnl_pct)));
  const cols = [{ label: "종목" }, { label: "수량", right: true }, { label: "평균 매수가", right: true }, { label: "현재가", right: true }, { label: "손익률", right: true }];
  const hold = folio.holdings.length
    ? table(cols, folio.holdings.map((h) => ({ code: h.code, cells: [el("strong", { text: h.name }), fmtInt(h.qty), fmtInt(h.avg_cost), fmtInt(h.close_price), h.pnl_pct === null ? "-" : chgNode(h.pnl_pct)] })), { onRowClick: (r) => selectStock(r.code) })
    : el("div", { class: "empty", text: "보유 종목이 없어요. 아래에서 모의 매수를 기록해 보세요." });
  const names = new Map(state.signals.map((s) => [s.code, s.name]));
  const tcols = [{ label: "날짜" }, { label: "구분" }, { label: "종목" }, { label: "수량", right: true }, { label: "가격", right: true }, { label: "" }];
  const tl = trades.length
    ? table(tcols, trades.map((x) => ({ cells: [x.trade_date, x.side === "BUY" ? "매수" : "매도", companyName(x.company_id), fmtInt(x.quantity), fmtInt(x.price),
        el("button", { type: "button", class: "btn small danger", text: "삭제", "aria-label": `${x.trade_date} 거래 삭제`, onclick: () => deleteTrade(x.trade_id) })] })))
    : null;
  host.replaceChildren(summary, hold, tl ? el("h3", { text: "최근 거래" }) : null, tl);
}

let companyIndex = new Map();
const companyName = (id) => companyIndex.get(id)?.name ?? `#${id}`;

async function deleteTrade(id) {
  try { await api(`/trades/${id}`, { method: "DELETE" }); toast("거래를 삭제했어요."); await loadMine(); }
  catch (e) { toast(e.message, true); }
}

/* ---------- 순위 / 업종 ---------- */
async function loadRank() {
  const host = $("#rank-body");
  try {
    const rows = await api("/signals/returns" + qs({ period: state.ret, limit: 5 }));
    if (!rows.length) { setMessage(host, "수익률을 계산할 시세가 아직 부족해요."); return; }
    host.replaceChildren(table([{ label: "종목" }, { label: "업종" }, { label: "수익률", right: true }],
      rows.map((r) => ({ code: r.code, cells: [el("strong", { text: r.name }), r.sector_name || "-", chgNode(r.ret_pct)] })), { onRowClick: (r) => selectStock(r.code) }));
  } catch (e) { setMessage(host, e.message, "error"); }
}

async function loadSectorTable() {
  const host = $("#sector-body");
  try {
    const rows = await api("/signals/sectors");
    if (!rows.length) { setMessage(host, "업종 데이터가 없어요."); return; }
    host.replaceChildren(table([{ label: "업종" }, { label: "종목 수", right: true }, { label: "평균 1개월", right: true }, { label: "추세 좋음", right: true }, { label: "추세 주의", right: true }],
      rows.map((r) => ({ cells: [r.sector, fmtInt(r.companies), r.avg_ret_1m === null ? "-" : chgNode(r.avg_ret_1m), fmtInt(r.good_trend_cnt), fmtInt(r.caution_trend_cnt)] }))));
  } catch (e) { setMessage(host, e.message, "error"); }
}

/* ---------- 폼 / 이벤트 ---------- */
const todayLocal = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

function bindEvents() {
  $("#member").addEventListener("change", (e) => { state.member = Number(e.target.value); loadMine().catch((x) => toast(x.message, true)); });
  $("#f-sector").addEventListener("change", loadSignals);
  $("#f-order").addEventListener("change", loadSignals);
  for (const b of document.querySelectorAll(".tab[data-ret]")) {
    b.addEventListener("click", () => {
      state.ret = b.dataset.ret;
      document.querySelectorAll(".tab[data-ret]").forEach((x) => x.classList.toggle("active", x === b));
      loadRank();
    });
  }
  $("#member-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const input = ev.currentTarget.elements.nickname;
    try {
      const m = await api("/members", { method: "POST", body: JSON.stringify({ nickname: input.value }) });
      input.value = "";
      await loadMembers(m.member_id);
      await loadMine();
      toast(`${m.nickname} 님으로 시작해요.`);
    } catch (e) { toast(e.status === 409 ? "이미 있는 닉네임이에요." : e.message, true); }
  });
  const tf = $("#trade-form");
  tf.elements.trade_date.value = todayLocal();
  tf.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const msg = $("#trade-msg"); msg.textContent = ""; msg.className = "form-msg";
    if (state.member === null) { msg.textContent = "회원을 먼저 만드세요."; return; }
    const f = tf.elements;
    const company = companyIndex.get(Number(f.company_id.value));
    const price = f.price.value === "" ? company?.close : Number(f.price.value);
    if (price === undefined || price === null) { msg.textContent = "가격을 입력하세요 (시세가 없는 종목입니다)."; return; }
    const btn = tf.querySelector("button[type=submit]"); btn.disabled = true;
    try {
      await api("/trades", { method: "POST", body: JSON.stringify({
        member_id: state.member, company_id: Number(f.company_id.value), trade_date: f.trade_date.value,
        side: f.side.value, quantity: Number(f.quantity.value), price, memo: f.memo.value.trim() || null }) });
      f.quantity.value = ""; f.price.value = ""; f.memo.value = "";
      msg.textContent = "기록했어요."; msg.className = "form-msg ok";
      await loadMine();
    } catch (e) { msg.textContent = e.message; } finally { btn.disabled = false; }
  });
}

async function loadHealth() {
  const pill = $("#health");
  try { await api("/health"); pill.textContent = "서버·DB 연결됨"; pill.className = "pill ok"; }
  catch (_) { pill.textContent = "서버 연결 실패"; pill.className = "pill bad"; }
}

async function init() {
  bindEvents();
  await loadHealth();
  try {
    const [companies, signals] = await Promise.all([api("/companies" + qs({ limit: 500 })), api("/signals")]);
    const close = new Map(signals.map((s) => [s.code, s.close_price]));
    companyIndex = new Map(companies.map((c) => [c.company_id, { name: c.name, close: close.get(c.code) }]));
    $("#trade-company").replaceChildren(...companies.map((c) => el("option", { value: c.company_id, text: `${c.name} (${c.code})` })));
    const sectors = [...new Set(signals.map((s) => s.sector_name).filter(Boolean))].sort();
    $("#f-sector").append(...sectors.map((s) => el("option", { value: s, text: s })));
    state.signals = signals;
    await loadMembers();
    await Promise.allSettled([loadSignals(), loadMine(), loadRank(), loadSectorTable()]);
    const first = signals.find((s) => s.close_price !== null) || signals[0];
    if (first) selectStock(first.code);
  } catch (e) { setMessage($("#sig-body"), e.message, "error"); }
}

document.addEventListener("DOMContentLoaded", init);
