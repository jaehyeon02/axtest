"use strict";
/*
 * 대시보드 화면 스크립트 (라이브러리 없이 순수 JavaScript + SVG)
 * 이 화면은 FastAPI 가 제공하는 API 를 fetch 로 호출해서 결과를 그리기만 한다.
 *   GET  /companies, /prices, /notes, /statistics/*  → 조회
 *   POST /prices, /notes                              → 등록
 *   PUT  /notes/{id}                                  → 수정
 *   DELETE /prices/{id}, /notes/{id}                  → 삭제
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

/* ---------- 상태 ---------- */
const state = {
  companies: [],
  company: null,
  range: 120,          // 차트에 보여 줄 거래일 수 (0 = 전체)
  rank: "change-desc",
  prices: [],          // 선택한 종목의 시세 (오래된 날짜 → 최신 날짜)
  monthly: [],
  sectors: [],
  seq: 0,              // 종목을 빠르게 바꿀 때 늦게 도착한 응답을 버리기 위한 번호
};

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

/** 종가 선 + 거래량 막대. 마우스를 올리면 해당 날짜의 값을 보여 준다. */
function drawPriceChart(host, rows) {
  host.replaceChildren();
  if (!rows.length) {
    setMessage(host, "시세 데이터가 없습니다. 적재 스크립트를 실행하거나 아래에서 시세를 등록하세요.");
    return;
  }
  const W = Math.max(host.clientWidth, 320);
  const H = 320;
  const m = { l: 66, r: 14, t: 12, b: 28 };
  const pw = W - m.l - m.r;
  const ph = H - m.t - m.b;
  const volH = ph * 0.2;
  const priceH = ph - volH - 10;
  const n = rows.length;

  const closes = rows.map((r) => r.close_price);
  let lo = Math.min(...closes);
  let hi = Math.max(...closes);
  const pad = (hi - lo) * 0.08 || hi * 0.02 || 1;
  lo -= pad;
  hi += pad;
  const maxV = Math.max(...rows.map((r) => r.volume)) || 1;

  const x = (i) => m.l + (n === 1 ? pw / 2 : (i / (n - 1)) * pw);
  const y = (v) => m.t + priceH - ((v - lo) / (hi - lo)) * priceH;
  const vy = (v) => m.t + ph - (v / maxV) * volH;

  const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "종가와 거래량 차트" });

  const axis = svg("g", { class: "axis" });
  for (const t of niceTicks(lo, hi, 5)) {
    axis.append(svg("line", { class: "gridline", x1: m.l, x2: W - m.r, y1: y(t), y2: y(t) }));
    axis.append(svg("text", { x: m.l - 8, y: y(t) + 4, "text-anchor": "end" }, nf.format(Math.round(t))));
  }
  const labelCount = Math.min(W < 480 ? 3 : 6, n);   // 좁은 화면에서는 날짜 라벨을 줄여 겹침 방지
  for (let k = 0; k < labelCount; k++) {
    const i = labelCount === 1 ? 0 : Math.round((k * (n - 1)) / (labelCount - 1));
    const anchor = k === 0 ? "start" : k === labelCount - 1 ? "end" : "middle";
    axis.append(svg("text", { x: x(i), y: H - 8, "text-anchor": anchor }, rows[i].trade_date.slice(2).replace(/-/g, ".")));
  }
  s.append(axis);

  const bw = Math.max(1, Math.min(14, (pw / n) * 0.7));
  rows.forEach((r, i) => {
    s.append(svg("rect", { class: "vol", x: x(i) - bw / 2, y: vy(r.volume), width: bw, height: m.t + ph - vy(r.volume) }));
  });

  const line = rows.map((r, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(r.close_price).toFixed(1)}`).join(" ");
  const baseY = m.t + priceH;
  s.append(svg("path", { class: "area", d: `${line} L${x(n - 1).toFixed(1)},${baseY} L${x(0).toFixed(1)},${baseY} Z` }));
  s.append(svg("path", { class: "line", d: line }));

  const cross = svg("line", { class: "cross", y1: m.t, y2: m.t + ph, style: "display:none" });
  const dot = svg("circle", { class: "dot", r: 4.5, style: "display:none" });
  const tip = el("div", { class: "tip", style: "display:none" });
  const overlay = svg("rect", { x: m.l, y: m.t, width: pw, height: ph, fill: "transparent" });
  s.append(cross, dot, overlay);

  const show = (i) => {
    const r = rows[i];
    const prev = i > 0 ? rows[i - 1].close_price : null;
    const change = prev ? ((r.close_price - prev) / prev) * 100 : null;
    cross.setAttribute("x1", x(i));
    cross.setAttribute("x2", x(i));
    cross.style.display = "";
    dot.setAttribute("cx", x(i));
    dot.setAttribute("cy", y(r.close_price));
    dot.style.display = "";
    tip.replaceChildren(
      el("div", { text: r.trade_date }),
      el("div", { text: `종가 ${nf.format(r.close_price)}원` }),
      el("div", { text: change === null ? "등락률 -" : `등락률 ${change > 0 ? "+" : ""}${change.toFixed(2)}%` }),
      el("div", { text: `거래량 ${nf.format(r.volume)}` }),
    );
    tip.style.display = "";
    const px = (x(i) / W) * s.getBoundingClientRect().width;
    const left = px + 14 + tip.offsetWidth > host.clientWidth ? px - 14 - tip.offsetWidth : px + 14;
    tip.style.left = `${Math.max(0, left)}px`;
    tip.style.top = "8px";
  };
  const hide = () => {
    cross.style.display = "none";
    dot.style.display = "none";
    tip.style.display = "none";
  };
  overlay.addEventListener("pointermove", (ev) => {
    const box = overlay.getBoundingClientRect();
    const rel = (ev.clientX - box.left) / box.width;
    show(Math.min(n - 1, Math.max(0, Math.round(rel * (n - 1)))));
  });
  overlay.addEventListener("pointerleave", hide);

  host.append(s, tip);
}

/** 막대 차트. signed=true 면 양수는 빨강, 음수는 파랑. */
function drawBarChart(host, items, { height = 220, format = String, signed = false, label = "막대 차트" } = {}) {
  host.replaceChildren();
  if (!items.length) {
    setMessage(host, "표시할 데이터가 없습니다.");
    return;
  }
  const W = Math.max(host.clientWidth, 280);
  const H = height;
  const vals = items.map((it) => it.value);
  const lo = Math.min(0, ...vals);
  const hi = Math.max(0, ...vals);
  // 음수 막대 아래에 값 라벨이 들어갈 자리를 따로 남겨 두어 축 라벨과 겹치지 않게 한다
  const m = { l: 8, r: 8, t: 20, b: 26 + (lo < 0 && items.length <= 12 ? 16 : 0) };
  const pw = W - m.l - m.r;
  const ph = H - m.t - m.b;
  const span = hi - lo || 1;
  const y = (v) => m.t + ph - ((v - lo) / span) * ph;
  const slot = pw / items.length;
  const bw = Math.min(40, slot * 0.64);
  const every = Math.max(1, Math.ceil(items.length / Math.max(1, Math.floor(pw / 46))));

  const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": label });
  s.append(svg("line", { class: "baseline", x1: m.l, x2: W - m.r, y1: y(0), y2: y(0) }));
  items.forEach((it, i) => {
    const cx = m.l + slot * i + slot / 2;
    const y0 = y(0);
    const y1 = y(it.value);
    const cls = "bar" + (signed ? (it.value > 0 ? " up" : it.value < 0 ? " down" : "") : "");
    s.append(svg("rect", { class: cls, x: cx - bw / 2, y: Math.min(y0, y1), width: bw, height: Math.max(1, Math.abs(y1 - y0)), rx: 2 },
      svg("title", {}, `${it.label}: ${format(it.value)}`)));
    if (items.length <= 12) {
      s.append(svg("text", { class: "val", x: cx, y: it.value >= 0 ? y1 - 5 : y1 + 13, "text-anchor": "middle" }, format(it.value)));
    }
    if (i % every === 0) {
      s.append(svg("g", { class: "axis" }, svg("text", { x: cx, y: H - 8, "text-anchor": "middle" }, it.label)));
    }
  });
  host.append(s);
}

/* ---------- 종목 선택 ---------- */
async function loadHealth() {
  const pill = $("#health");
  try {
    await api("/health");
    pill.textContent = "서버·DB 연결됨";
    pill.className = "pill ok";
  } catch (_) {
    pill.textContent = "서버 연결 실패";
    pill.className = "pill bad";
  }
}

async function loadCompanies() {
  const sel = $("#company");
  try {
    state.companies = await api("/companies" + qs({ limit: 500 }));
  } catch (e) {
    setMessage($("#kpis"), `종목을 불러오지 못했습니다: ${e.message}`, "error");
    return false;
  }
  if (!state.companies.length) {
    setMessage($("#kpis"), "등록된 종목이 없습니다. backend 폴더에서 `python -m scripts.load_master` 를 실행하세요.");
    setMessage($("#chart-price"), "종목을 먼저 등록하세요.");
    return false;
  }
  sel.replaceChildren(...state.companies.map((c) => el("option", { value: c.company_id, text: `${c.name} (${c.code})` })));
  state.company = state.companies[0];
  sel.value = state.company.company_id;
  return true;
}

function selectCompany(company) {
  state.company = company;
  $("#company").value = company.company_id;
  return refreshCompany();
}

function selectByCode(code) {
  const c = state.companies.find((x) => x.code.trim() === String(code).trim());
  if (!c) return;
  selectCompany(c);
  window.scrollTo({ top: 0 });
}

/** 선택한 종목에 따라 달라지는 영역을 모두 새로 그린다. */
async function refreshCompany() {
  const c = state.company;
  const seq = ++state.seq;
  $("#company-meta").textContent = `${c.market_name}${c.sector_name ? " · " + c.sector_name : ""}`;
  await Promise.allSettled([loadPrices(c, seq), loadMonthly(c, seq), loadFinancials(c, seq), loadNotes(c, seq)]);
}

/** 시세·메모를 바꾼 뒤에는 통계도 달라지므로 같이 새로 읽는다. */
async function afterPriceChange() {
  await Promise.allSettled([refreshCompany(), loadGlobal()]);
}

/* ---------- 시세 · KPI ---------- */
function kpi(label, value, sub) {
  return el("div", { class: "kpi" },
    el("div", { class: "k", text: label }),
    el("div", { class: "v" }, value),
    el("div", { class: "s" }, sub));
}

const visiblePrices = () => (state.range > 0 ? state.prices.slice(-state.range) : state.prices);

async function loadPrices(c, seq) {
  try {
    const rows = await api("/prices" + qs({ code: c.code, limit: 1000 })); // 최신순
    if (seq !== state.seq) return;
    state.prices = rows.slice().reverse();
    renderRecent(rows.slice(0, 10));
    await renderPriceArea(c, seq);
  } catch (e) {
    if (seq !== state.seq) return;
    state.prices = [];
    setMessage($("#chart-price"), `시세를 불러오지 못했습니다: ${e.message}`, "error");
    setMessage($("#kpis"), "");
  }
}

async function renderPriceArea(c, seq) {
  const rows = visiblePrices();
  drawPriceChart($("#chart-price"), rows);
  const kpis = $("#kpis");
  if (!rows.length) {
    setMessage(kpis, "이 종목의 시세 데이터가 없습니다.");
    return;
  }
  try {
    // 요약 통계는 DB(GROUP BY)가 계산한다. 화면에 보이는 기간의 첫 날짜부터 요청한다.
    const s = await api("/statistics/summary" + qs({ code: c.code, start: rows[0].trade_date }));
    if (seq !== state.seq) return;
    const last = rows[rows.length - 1];
    const prev = rows.length > 1 ? rows[rows.length - 2] : null;
    const change = prev && prev.close_price ? ((last.close_price - prev.close_price) / prev.close_price) * 100 : null;
    kpis.replaceChildren(
      kpi("최근 종가", fmtWon(last.close_price), [chgNode(change), ` · ${last.trade_date}`]),
      kpi("평균 종가", fmtWon(s.avg_close), `${s.first_date} ~ ${s.last_date}`),
      kpi("최고 종가", fmtWon(s.max_close), "기간 내"),
      kpi("최저 종가", fmtWon(s.min_close), "기간 내"),
      kpi("평균 거래량", fmtInt(s.avg_volume), "주 / 일"),
      kpi("거래일수", `${fmtInt(s.trading_days)}일`, "기간 내"),
    );
  } catch (e) {
    if (seq !== state.seq) return;
    setMessage(kpis, `요약을 불러오지 못했습니다: ${e.message}`, "error");
  }
}

function renderRecent(rows) {
  const host = $("#table-recent");
  if (!rows.length) {
    setMessage(host, "등록된 시세가 없습니다.");
    return;
  }
  host.replaceChildren(
    el("div", { class: "muted", text: "최근 시세 10건" }),
    table(
      [{ label: "거래일" }, { label: "종가", right: true }, { label: "거래량", right: true }, { label: "", right: true }],
      rows.map((r) => ({
        cells: [
          r.trade_date,
          fmtInt(r.close_price),
          fmtInt(r.volume),
          el("button", { type: "button", class: "btn small danger", text: "삭제", "aria-label": `${r.trade_date} 시세 삭제`, onclick: (ev) => deletePrice(r.price_id, ev.currentTarget) }),
        ],
      })),
    ),
  );
}

async function deletePrice(id, btn) {
  btn.disabled = true;
  try {
    await api(`/prices/${id}`, { method: "DELETE" });
    toast("시세를 삭제했습니다.");
    await afterPriceChange();
  } catch (e) {
    toast(e.message, true);
    btn.disabled = false;
  }
}

/* ---------- 월별 · 업종 · 순위 · 변동성 · 재무 ---------- */
function drawMonthly(rows) {
  const recent = rows.slice(-24);
  drawBarChart($("#chart-monthly"), recent.map((r) => ({ label: r.month.slice(2).replace("-", "."), value: Number(r.avg_close) })),
    { format: fmtInt, label: "월별 평균 종가 차트" });
  $("#table-monthly").replaceChildren(table(
    [{ label: "월" }, { label: "거래일", right: true }, { label: "평균 종가", right: true }, { label: "최고가", right: true }, { label: "최저가", right: true }, { label: "거래량 합계", right: true }],
    rows.slice().reverse().map((r) => ({ cells: [r.month, fmtInt(r.trading_days), fmtInt(r.avg_close), fmtInt(r.high), fmtInt(r.low), fmtInt(r.total_volume)] })),
  ));
}

async function loadMonthly(c, seq) {
  try {
    const rows = await api("/statistics/monthly" + qs({ code: c.code }));
    if (seq !== state.seq) return;
    state.monthly = rows;
    drawMonthly(rows);
  } catch (e) {
    if (seq !== state.seq) return;
    state.monthly = [];
    const none = e.status === 404;
    setMessage($("#chart-monthly"), none ? "월별 통계를 만들 시세 데이터가 없습니다." : `불러오지 못했습니다: ${e.message}`, none ? "empty" : "error");
    $("#table-monthly").replaceChildren();
  }
}

function drawSectors(rows) {
  const chart = $("#chart-sector");
  const tbl = $("#table-sector");
  if (!rows.length) {
    setMessage(chart, "업종 통계가 없습니다. 시세 데이터와 업종이 지정된 종목이 필요합니다.");
    tbl.replaceChildren();
    return;
  }
  drawBarChart(chart, rows.map((r) => ({ label: r.sector, value: Number(r.avg_change_pct ?? 0) })),
    { signed: true, format: (v) => `${v.toFixed(2)}%`, label: "업종별 평균 등락률 차트" });
  tbl.replaceChildren(table(
    [{ label: "업종" }, { label: "종목 수", right: true }, { label: "평균 등락률", right: true }, { label: "평균 거래량", right: true }],
    rows.map((r) => ({ cells: [r.sector, fmtInt(r.companies), chgNode(r.avg_change_pct), fmtInt(r.avg_volume)] })),
  ));
}

async function loadSectors() {
  try {
    state.sectors = await api("/statistics/sectors" + qs({ days: 30 }));
    drawSectors(state.sectors);
  } catch (e) {
    state.sectors = [];
    setMessage($("#chart-sector"), `불러오지 못했습니다: ${e.message}`, "error");
    $("#table-sector").replaceChildren();
  }
}

const RANKS = {
  "change-desc": { metric: "change", order: "desc" },
  "change-asc": { metric: "change", order: "asc" },
  "volume-desc": { metric: "volume", order: "desc" },
};

async function loadRanking() {
  const host = $("#table-ranking");
  try {
    const rows = await api("/statistics/ranking" + qs({ ...RANKS[state.rank], limit: 5 }));
    if (!rows.length) {
      setMessage(host, "순위를 만들 데이터가 없습니다.");
      return;
    }
    host.replaceChildren(table(
      [{ label: "종목" }, { label: "날짜" }, { label: "종가", right: true }, { label: "등락률", right: true }, { label: "거래량", right: true }],
      rows.map((x) => ({ data: x, cells: [`${x.name} (${x.code})`, x.trade_date, fmtInt(x.close_price), chgNode(x.change_pct), fmtInt(x.volume)] })),
      { onRowClick: (row) => selectByCode(row.data.code) },
    ));
  } catch (e) {
    setMessage(host, `불러오지 못했습니다: ${e.message}`, "error");
  }
}

async function loadVolatile() {
  const host = $("#table-volatile");
  try {
    const rows = await api("/statistics/volatile" + qs({ threshold: 4, days: 180, min_days: 3 }));
    if (!rows.length) {
      setMessage(host, "조건에 맞는 종목이 없습니다.");
      return;
    }
    host.replaceChildren(table(
      [{ label: "종목" }, { label: "큰 변동 일수", right: true }, { label: "최대 변동폭", right: true }],
      rows.map((x) => ({ data: x, cells: [`${x.name} (${x.code})`, `${fmtInt(x.move_days)}일`, fmtPct(x.max_abs_change)] })),
      { onRowClick: (row) => selectByCode(row.data.code) },
    ));
  } catch (e) {
    setMessage(host, `불러오지 못했습니다: ${e.message}`, "error");
  }
}

const loadGlobal = () => Promise.allSettled([loadSectors(), loadRanking(), loadVolatile()]);

async function loadFinancials(c, seq) {
  const host = $("#table-fin");
  try {
    const rows = await api("/statistics/financial-ratios" + qs({ code: c.code }));
    if (seq !== state.seq) return;
    if (!rows.length) {
      setMessage(host, "재무 데이터가 없습니다. `python -m scripts.collect_dart` 를 실행하세요.");
      return;
    }
    host.replaceChildren(table(
      [{ label: "연도" }, { label: "매출액", right: true }, { label: "영업이익", right: true }, { label: "당기순이익", right: true }, { label: "영업이익률", right: true }, { label: "부채비율", right: true }, { label: "ROE", right: true }],
      rows.map((r) => ({ cells: [String(r.fiscal_year), fmtBig(r.revenue), fmtBig(r.operating_profit), fmtBig(r.net_income), fmtPct(r.operating_margin_pct), fmtPct(r.debt_ratio_pct), fmtPct(r.roe_pct)] })),
    ));
  } catch (e) {
    if (seq !== state.seq) return;
    setMessage(host, `불러오지 못했습니다: ${e.message}`, "error");
  }
}

/* ---------- 메모 (등록 · 조회 · 수정 · 삭제) ---------- */
async function loadNotes(c, seq) {
  const list = $("#notes");
  try {
    const rows = await api("/notes" + qs({ company_id: c.company_id, limit: 50 }));
    if (seq !== state.seq) return;
    renderNotes(rows);
  } catch (e) {
    if (seq !== state.seq) return;
    list.replaceChildren(el("li", { class: "error", text: `불러오지 못했습니다: ${e.message}` }));
  }
}

function renderNotes(rows) {
  const list = $("#notes");
  if (!rows.length) {
    list.replaceChildren(el("li", { class: "empty", text: "등록된 메모가 없습니다." }));
    return;
  }
  list.replaceChildren(...rows.map(noteItem));
}

function noteItem(n) {
  const li = el("li", { class: "note" });

  const view = () => {
    li.replaceChildren(
      el("div", { class: "t", text: n.title }),
      el("div", { class: "c", text: n.content }),
      el("div", { class: "m", text: String(n.created_at).replace("T", " ").slice(0, 16) }),
      el("div", { class: "acts" },
        el("button", { type: "button", class: "btn small", text: "수정", onclick: edit }),
        el("button", { type: "button", class: "btn small danger", text: "삭제", onclick: remove })),
    );
  };

  const edit = () => {
    const title = el("input", { type: "text", maxlength: 100, required: true, "aria-label": "제목" });
    title.value = n.title;
    const content = el("textarea", { rows: 3, required: true, "aria-label": "내용" });
    content.value = n.content;
    const msg = el("span", { class: "form-msg", role: "alert" });
    const form = el("form", {
      onsubmit: async (ev) => {
        ev.preventDefault();
        try {
          const updated = await api(`/notes/${n.note_id}`, { method: "PUT", body: JSON.stringify({ title: title.value, content: content.value }) });
          Object.assign(n, updated);
          toast("메모를 수정했습니다.");
          view();
        } catch (e) {
          msg.textContent = e.message;
        }
      },
    }, title, content,
    el("div", { class: "form-actions" },
      el("button", { type: "submit", class: "btn primary small", text: "저장" }),
      el("button", { type: "button", class: "btn small", text: "취소", onclick: view }),
      msg));
    li.replaceChildren(form);
    title.focus();
  };

  const remove = async () => {
    try {
      await api(`/notes/${n.note_id}`, { method: "DELETE" });
      toast("메모를 삭제했습니다.");
      await loadNotes(state.company, state.seq);
    } catch (e) {
      toast(e.message, true);
    }
  };

  view();
  return li;
}

/* ---------- 폼 · 이벤트 ---------- */
function todayLocal() {
  return new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function bindForms() {
  const priceForm = $("#price-form");
  priceForm.elements.trade_date.value = todayLocal();
  priceForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.currentTarget;
    const msg = $("#price-msg");
    const btn = $("button[type=submit]", form);
    msg.className = "form-msg";
    msg.textContent = "";
    if (!state.company) {
      msg.textContent = "먼저 종목을 선택하세요.";
      return;
    }
    const f = Object.fromEntries(new FormData(form));
    const body = {
      company_id: state.company.company_id,
      trade_date: f.trade_date,
      open_price: Number(f.open_price),
      high_price: Number(f.high_price),
      low_price: Number(f.low_price),
      close_price: Number(f.close_price),
      volume: Number(f.volume),
    };
    btn.disabled = true;
    try {
      await api("/prices", { method: "POST", body: JSON.stringify(body) });
      toast("시세를 등록했습니다.");
      form.reset();
      form.elements.trade_date.value = todayLocal();
      await afterPriceChange();
    } catch (e) {
      msg.textContent = e.message;   // 409(날짜 중복), 422(고가<저가 등) 메시지를 그대로 보여 준다
    } finally {
      btn.disabled = false;
    }
  });

  const noteForm = $("#note-form");
  noteForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.currentTarget;
    const msg = $("#note-msg");
    const btn = $("button[type=submit]", form);
    msg.textContent = "";
    if (!state.company) {
      msg.textContent = "먼저 종목을 선택하세요.";
      return;
    }
    const f = Object.fromEntries(new FormData(form));
    btn.disabled = true;
    try {
      await api("/notes", { method: "POST", body: JSON.stringify({ company_id: state.company.company_id, title: f.title, content: f.content }) });
      toast("메모를 등록했습니다.");
      form.reset();
      await loadNotes(state.company, state.seq);
    } catch (e) {
      msg.textContent = e.message;
    } finally {
      btn.disabled = false;
    }
  });
}

function bindEvents() {
  $("#company").addEventListener("change", (ev) => {
    const c = state.companies.find((x) => String(x.company_id) === ev.target.value);
    if (c) selectCompany(c);
  });
  $("#range").addEventListener("change", (ev) => {
    state.range = Number(ev.target.value);
    if (state.company && state.prices.length) renderPriceArea(state.company, state.seq);
  });
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
      state.rank = btn.dataset.rank;
      loadRanking();
    });
  });
  let timer;
  window.addEventListener("resize", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {   // 창 크기가 바뀌면 SVG 를 새 너비로 다시 그린다
      if (state.prices.length) drawPriceChart($("#chart-price"), visiblePrices());
      if (state.monthly.length) drawMonthly(state.monthly);
      if (state.sectors.length) drawSectors(state.sectors);
    }, 150);
  });
}

async function init() {
  for (const id of ["#chart-price", "#chart-monthly", "#chart-sector", "#table-ranking", "#table-volatile", "#table-fin", "#table-recent"]) {
    setMessage($(id), "불러오는 중…");
  }
  bindForms();
  bindEvents();
  loadHealth();
  const hasCompanies = await loadCompanies();
  const globals = loadGlobal();
  if (hasCompanies) await refreshCompany();
  else {
    for (const id of ["#chart-monthly", "#table-fin", "#table-recent"]) setMessage($(id), "종목이 없습니다.");
    $("#notes").replaceChildren();
  }
  await globals;
}

init();
