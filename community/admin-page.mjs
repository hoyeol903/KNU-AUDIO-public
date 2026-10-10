import {mascot, font} from './admin-assets.mjs';

export const adminPage = String.raw`<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>크누아 관리자</title>
<style>
:root{color-scheme:light;--ink:#1A1417;--sub:#6E6267;--muted:#8A7D83;--wine:#8B1E3F;--line:#EAE3E6;--danger:#B3261E}
*{box-sizing:border-box}body{margin:0;background:#E9E4E5;color:var(--ink);font:15px/1.6 'Pretendard Variable',Pretendard,-apple-system,BlinkMacSystemFont,system-ui,sans-serif;letter-spacing:-.2px;word-break:keep-all;-webkit-font-smoothing:antialiased}button,input,textarea{font:inherit;letter-spacing:inherit;color:inherit}button{cursor:pointer;border:1px solid var(--line);background:#fff;border-radius:14px;min-height:44px;padding:9px 15px;font-weight:750}button:active{background:#F4F0F1}button:disabled{cursor:default;opacity:.45}button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #C47A92;outline-offset:3px}input,textarea{width:100%;min-width:0;border:1px solid var(--line);border-radius:14px;background:#FBF9FA;padding:13px 16px;font-size:16px}input:focus,textarea:focus{border-color:var(--wine);background:#fff}h1,h2,h3,p{margin:0}h1{font-size:30px;line-height:1.25;font-weight:800;letter-spacing:-.8px}h2{font-size:21px;line-height:1.4;font-weight:800}h3{font-size:17px;line-height:24px;font-weight:750}.sub{color:var(--sub);font-size:14px;line-height:1.5}.muted{color:var(--muted);font-size:12.5px}.eyebrow{font-size:12px;color:var(--wine);font-weight:800;letter-spacing:1.2px}.primary{background:var(--wine);border-color:var(--wine);color:#fff}.primary:active{background:#6A1530}.danger{color:var(--danger);border-color:#F1D3D1}.danger.primary{background:var(--danger);border-color:var(--danger);color:#fff}.error{color:var(--danger)!important}main{max-width:480px;min-height:100vh;min-height:100dvh;margin:auto;background:#fff}#login{min-height:100vh;min-height:100dvh;padding:54px 24px calc(24px + env(safe-area-inset-bottom));display:flex;flex-direction:column;gap:28px}.login-heading{display:grid;gap:10px}.fields{display:grid;gap:16px}label{display:grid;gap:8px;font-size:13px;font-weight:700;color:#4A3F44}#loginError{font-size:13.5px;font-weight:600}#mascot{width:140px;height:140px;align-self:center;margin-top:auto;max-width:100%}.login-cta{position:sticky;bottom:0;padding-top:12px;background:#fff}#login button{width:100%;height:54px;border-radius:16px;font-size:16px}#toolbar{position:sticky;top:0;z-index:2;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:16px 20px 8px;background:#fff}.tools{display:flex;gap:6px}.tools button{font-size:13px;padding:6px 12px;border-radius:22px}#refresh{width:44px;padding:8px;display:grid;place-items:center}svg{flex:none}#panel{padding:16px 20px calc(116px + env(safe-area-inset-bottom))}.heading{display:grid;gap:8px;margin-bottom:18px}.count-label{font-size:13px;font-weight:700;color:var(--sub);margin-bottom:4px;overflow-wrap:anywhere}.pagination-note{font-size:12px;color:var(--muted);margin:8px 0}.row{padding:16px 0 18px;border-top:1px solid var(--line);display:grid;gap:8px}.row-head{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12.5px;color:var(--sub)}.badge{display:inline-flex;align-items:center;border-radius:12px;min-height:24px;padding:1px 9px;font-size:12px;font-weight:800;white-space:nowrap;flex:none;background:#E8F3EC;color:#1F6B43}.badge.closed{background:#F1EDEE;color:var(--sub)}.badge.hidden{background:#2A2226;color:#fff}.report-count{font-size:12.5px;font-weight:800;color:var(--wine);white-space:nowrap;flex:none}.latest{margin-left:auto;color:var(--muted);font-size:12px;white-space:nowrap}.title-button{display:block;border:0;border-radius:4px;padding:0;min-height:0;text-align:left;font-size:17px;line-height:24px;font-weight:750;overflow-wrap:anywhere}.meta{font-size:13.5px;color:var(--sub);overflow-wrap:anywhere}.reason{display:grid;gap:8px;padding:12px 14px;background:#FBF3EC;border-radius:14px;color:#6B3E22;font-size:13.5px;line-height:20px;overflow-wrap:anywhere}.reason-line{display:flex;gap:10px;align-items:baseline}.reason-line p{flex:1;min-width:0;white-space:pre-wrap}.reason-line time{color:#A08876;font-size:12px;white-space:nowrap;flex:none}.expand{justify-self:start;min-height:44px;border:0;background:none;padding:0;font-size:12.5px;color:#8B4A22}.actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding-top:4px}.actions button{min-height:44px;font-size:14px;border-radius:12px}.empty{border-top:1px solid var(--line);padding:48px 12px;text-align:center;display:grid;gap:8px}.empty b{font-size:16px}.empty span{font-size:13.5px;color:var(--sub)}.more{width:100%;height:46px;margin-top:8px;font-size:14px;color:#4A3F44}.search{display:flex;gap:8px;margin-bottom:16px}.search input{flex:1;background:#F4F0F1;height:46px}.search button{background:var(--ink);color:white;height:46px;flex:none}.post-row{width:100%;border:0;border-top:1px solid var(--line);border-radius:0;padding:16px 0;display:flex;gap:12px;align-items:center;text-align:left;font-weight:400}.post-body{min-width:0;flex:1;display:grid;gap:6px}.post-row .row-head{gap:6px}.post-row .meta{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.post-row h3{font-size:16.5px;overflow-wrap:anywhere}.post-row[data-hidden=true] h3{color:var(--sub)}.chevron{font-size:26px;color:#B3A6AC;flex:none}.order{display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:14px;background:#F4F0F1;border-radius:16px;margin-bottom:20px;font-size:12.5px;font-weight:700;color:var(--muted)}.order b{color:white;background:var(--wine);border-radius:14px;padding:2px 9px}#fixedForm{display:grid;gap:10px}textarea{resize:vertical;min-height:174px;line-height:25px;font-size:15.5px}.fixed-meta{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}#fixedCount{white-space:nowrap;font-weight:700}.notice{background:#FBEFF3;padding:12px 14px;border-radius:14px;color:#5A2236;font-size:13.5px;line-height:20px;margin-top:6px}#fixedSave{height:52px;border-radius:16px;margin-top:6px;font-size:15.5px}#fixedStatus{font-size:13.5px;color:#1F6B43;white-space:pre-wrap}.tabs{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:480px;background:#fff;border-top:1px solid var(--line);padding:10px 12px calc(10px + env(safe-area-inset-bottom));display:grid;grid-template-columns:repeat(3,minmax(0,1fr));z-index:3}.tabs button{border:0;background:transparent;display:grid;justify-items:center;gap:4px;color:var(--muted);font-size:12px;min-height:64px;padding:8px 4px}.tabs button[aria-selected=true]{color:var(--wine);background:#FBEFF3}.tab-icon{position:relative;display:inline-flex}.tab-badge{position:absolute;top:-7px;left:15px;background:var(--wine);color:white;min-width:18px;height:18px;padding:0 5px;border-radius:10px;font-size:10px;font-weight:800;line-height:18px}#message{position:fixed;bottom:calc(100px + env(safe-area-inset-bottom));left:50%;transform:translateX(-50%);width:max-content;max-width:min(440px,calc(100vw - 32px));padding:12px 16px;border-radius:14px;background:#2A2226;color:white;box-shadow:0 8px 30px #1A141726;font-size:13.5px;z-index:10;overflow-wrap:anywhere;white-space:pre-wrap}body:has(#login:not([hidden])) #message{bottom:calc(94px + env(safe-area-inset-bottom))}dialog{border:0;color:var(--ink);background:#fff;padding:0;font:inherit;box-shadow:0 24px 60px #1A141740}dialog::backdrop{background:#1A141766}#detail{max-width:480px;width:100%;max-height:85vh;max-height:85dvh;margin:auto auto 0;border-radius:24px 24px 0 0;overflow-y:auto}#detailContent{padding:10px 20px calc(24px + env(safe-area-inset-bottom));display:grid;gap:12px}.handle{width:36px;height:4px;border-radius:4px;background:#D9D0D4;margin:0 auto}.sheet-head{display:flex;justify-content:space-between;align-items:center;gap:12px}.sheet-head h2{font-size:14px;color:var(--sub)}.sheet-head button{border:0;border-radius:22px;padding:6px 12px}.intro{white-space:pre-wrap;overflow-wrap:anywhere;font-size:15px;line-height:24px;padding:14px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);color:#4A3F44}#detail .actions button{height:50px;font-size:15px}#confirmation{width:calc(100% - 40px);max-width:350px;border-radius:24px;padding:24px 20px 18px;margin:auto}#confirmation h2{font-size:20px}#confirmation p{color:var(--sub);font-size:14px;margin-top:10px}#confirmation .actions{margin-top:18px}#confirmation .actions button{height:48px}html:has(dialog[open]){overflow:hidden}[hidden]{display:none!important}@media(max-height:650px){#login{padding-top:24px;gap:20px}#mascot{width:100px;height:100px}}@media(prefers-reduced-motion:no-preference){button{transition:background .15s,color .15s}}
</style>
</head>
<body>
<main>
<form id="login">
<div class="login-heading">
<span class="eyebrow">KNU AUDIO</span>
<h1>크누아 관리자</h1>
<p class="sub">관리자 계정으로만 접속할 수 있어요.</p>
</div>
<div class="fields">
<label>아이디<input name="username" autocomplete="username" required maxlength="80">
</label>
<label>비밀번호<input name="password" type="password" autocomplete="current-password" required maxlength="256">
</label>
<p id="loginError" class="error" role="alert" hidden>
</p>
</div>
<canvas id="mascot" width="280" height="280" aria-hidden="true">
</canvas>
<div class="login-cta">
<button class="primary" type="submit">로그인</button>
</div>
</form>
<header id="toolbar" hidden>
<span class="eyebrow">KNU AUDIO 관리자</span>
<div class="tools">
<button id="refresh" type="button" aria-label="새로고침">
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7">
</path>
</svg>
</button>
<button id="logout" type="button">로그아웃</button>
</div>
</header>
<div id="panel" hidden>
<section id="reportsPanel" role="tabpanel" aria-labelledby="reportsTab">
<div class="heading">
<h1 tabindex="-1">신고</h1>
<p class="sub">최근 신고부터 보여요.<br>신고만으로 글이 삭제되지는 않아요.</p>
</div>
<p id="reportsLabel" class="count-label">신고된 글 0</p>
<div id="reports">
</div>
<p id="reportsNote" class="pagination-note" hidden>건수는 지금까지 불러온 신고 기준이에요.</p>
<button id="reportMore" class="more" type="button" hidden>신고 더 보기</button>
</section>
<section id="postsPanel" role="tabpanel" aria-labelledby="postsTab" hidden>
<div class="heading">
<h1 tabindex="-1">게시물</h1>
<p class="sub">신고되지 않은 글과 숨긴 글도 관리해요.</p>
</div>
<form id="search" class="search">
<input name="query" aria-label="게시물 제목 검색" placeholder="제목으로 검색" maxlength="80">
<button type="submit">검색</button>
</form>
<p id="postsLabel" class="count-label">전체 게시물 0</p>
<div id="posts">
</div>
<p id="postsNote" class="pagination-note" hidden>건수는 지금까지 불러온 게시물 기준이에요.</p>
<button id="postMore" class="more" type="button" hidden>게시물 더 보기</button>
</section>
<section id="fixedPanel" role="tabpanel" aria-labelledby="fixedTab" hidden>
<div class="heading">
<h1 tabindex="-1">고정 멘트</h1>
<p class="sub">모든 사용자 브리핑에 들어가는<br>공통 응원 멘트예요.</p>
</div>
<div class="order" aria-label="브리핑 재생 순서">
<span>인사·날씨</span>
<span>›</span>
<span>공지</span>
<span>›</span>
<span>학식</span>
<span>›</span>
<b>응원 멘트</b>
<span>›</span>
<span>마무리</span>
</div>
<form id="fixedForm">
<label for="fixedText">마무리 인사 전에 들려줄 멘트</label>
<textarea id="fixedText" rows="6" maxlength="500" required disabled>
</textarea>
<div class="fixed-meta muted">
<span id="fixedAt">마지막 저장 · 불러오는 중</span>
<span id="fixedCount">0 / 500자</span>
</div>
<p class="notice">저장한 문장은 <b>다음 정기 음성 생성</b>이 끝나면 반영돼요. 그때까지는 기존 음성이 재생됩니다.</p>
<p id="fixedStatus" role="status" aria-live="polite">
</p>
<button id="fixedSave" class="primary" type="submit" disabled>멘트 저장</button>
</form>
</section>
</div>
<nav id="tabs" class="tabs" role="tablist" aria-label="관리자 메뉴" hidden>
<button id="reportsTab" type="button" role="tab" aria-controls="reportsPanel" aria-selected="true" data-tab="reports">
<span class="tab-icon">
<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
<path d="M5 21V3m0 1c5-4 9 4 14 0v10c-5 4-9-4-14 0">
</path>
</svg>
<span id="reportBadge" class="tab-badge" hidden>0</span>
</span>신고</button>
<button id="postsTab" type="button" role="tab" aria-controls="postsPanel" aria-selected="false" tabindex="-1" data-tab="posts">
<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
<rect x="5" y="3" width="14" height="18" rx="2">
</rect>
<path d="M9 8h6m-6 4h6m-6 4h4">
</path>
</svg>게시물</button>
<button id="fixedTab" type="button" role="tab" aria-controls="fixedPanel" aria-selected="false" tabindex="-1" data-tab="fixed">
<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
<path d="M7 4h10l-1 8 3 3H5l3-3-1-8zm5 11v6">
</path>
</svg>고정 멘트</button>
</nav>
</main>
<p id="message" role="status" aria-live="polite" hidden>
</p>
<dialog id="detail" aria-labelledby="detailTitle">
<div id="detailContent">
</div>
</dialog>
<dialog id="confirmation" role="alertdialog" aria-labelledby="confirmTitle" aria-describedby="confirmBody">
<h2 id="confirmTitle">
</h2>
<p id="confirmBody">
</p>
<div class="actions">
<button id="confirmCancel" type="button" autofocus>취소</button>
<button id="confirmDo" class="primary" type="button">확인</button>
</div>
</dialog>
<script nonce="__NONCE__">
const $ = (s) => document.querySelector(s);
const login = $("#login"), panel = $("#panel"), toolbar = $("#toolbar"), tabs = $("#tabs"), message = $("#message"), search = $("#search");
const fixedForm = $("#fixedForm"), fixedText = $("#fixedText"), fixedSave = $("#fixedSave"), fixedStatus = $("#fixedStatus"), detail = $("#detail"), confirmation = $("#confirmation");
const posts = /* @__PURE__ */ new Map(), expanded = /* @__PURE__ */ new Set(), pending = /* @__PURE__ */ new Set(), revisions = /* @__PURE__ */ new Map(), deleted = /* @__PURE__ */ new Set();
const lists = { reports: { container: $("#reports"), more: $("#reportMore"), cursor: null, items: [], version: 0 }, meetings: { container: $("#posts"), more: $("#postMore"), cursor: null, items: [], version: 0 } };
let query = "", searchVersion = 0, sessionVersion = 0, fixedVersion = null, fixedOriginal = "", fixedRequest = 0, fixedSaving = false, detailId = null, choice = null, toastTimer;
function node(tag, value = "", className) {
  const el = document.createElement(tag);
  el.textContent = value;
  if (className) el.className = className;
  return el;
}
function button(label, fn, className) {
  const b = node("button", label, className);
  b.type = "button";
  b.addEventListener("click", fn);
  return b;
}
function say(e) {
  const value = e instanceof Error ? e.message : String(e || "");
  clearTimeout(toastTimer);
  message.textContent = value;
  message.hidden = !value;
  if (value) toastTimer = setTimeout(() => {
    message.hidden = true;
  }, 6500);
}
function selectTab(name, focus = false) {
  for (const b of tabs.querySelectorAll("[data-tab]")) {
    const active = b.dataset.tab === name;
    b.setAttribute("aria-selected", String(active));
    b.tabIndex = active ? 0 : -1;
    $("#" + b.getAttribute("aria-controls")).hidden = !active;
    if (active && focus) b.focus();
  }
}
for (const b of tabs.querySelectorAll("[data-tab]")) {
  b.addEventListener("click", () => selectTab(b.dataset.tab));
  b.addEventListener("keydown", (e) => {
    const all = [...tabs.querySelectorAll("[data-tab]")], i = all.indexOf(b);
    let next;
    if (e.key === "ArrowRight") next = (i + 1) % all.length;
    if (e.key === "ArrowLeft") next = (i + all.length - 1) % all.length;
    if (e.key === "Home") next = 0;
    if (e.key === "End") next = all.length - 1;
    if (next !== void 0) {
      e.preventDefault();
      selectTab(all[next].dataset.tab, true);
    }
  });
}
function closeDetail() {
  detail.close();
  detailId = null;
}
function signedIn(ok) {
  sessionVersion++;
  login.hidden = ok;
  panel.hidden = !ok;
  toolbar.hidden = !ok;
  tabs.hidden = !ok;
  $("#loginError").hidden = true;
  login.elements.password.value = "";
  if (!ok) {
    confirmation.close();
    choice = null;
    closeDetail();
    posts.clear();
    expanded.clear();
    pending.clear();
    revisions.clear();
    deleted.clear();
    query = "";
    searchVersion++;
    search.reset();
    fixedRequest++;
    fixedText.value = "";
    fixedText.disabled = true;
    fixedVersion = null;
    fixedOriginal = "";
    fixedSaving = false;
    fixedStatus.textContent = "";
    $("#fixedAt").textContent = "마지막 저장 · 불러오는 중";
    countFixed();
    for (const list of Object.values(lists)) {
      list.version++;
      list.cursor = null;
      list.items = [];
      list.container.replaceChildren();
      list.more.hidden = true;
      list.more.disabled = false;
    }
    $("#reportBadge").hidden = true;
    say("");
    selectTab("reports");
  }
}
async function api(path, method = "GET", body) {
  const session = sessionVersion;
  const r = await fetch("/admin/api/" + path, { method, credentials: "same-origin", cache: "no-store", headers: { "Content-Type": "application/json" }, body: body === void 0 ? void 0 : JSON.stringify(body) });
  const d = await r.json();
  if (session !== sessionVersion) throw Error("이전 요청을 취소했어요.");
  if (!r.ok) {
    if (r.status === 401) {
      const expired = !panel.hidden;
      signedIn(false);
      if (expired) say(d.error || "관리자 로그인이 필요해요.");
    }
    throw Error(d.error || "요청 실패");
  }
  return d;
}
function time(value, full = false) {
  if (!value) return full ? "아직 저장하지 않음" : "시각 없음";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "시각 없음";
  return date.toLocaleString("ko-KR", { timeZone: "Asia/Seoul", ...full ? {} : { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false } });
}
function badge(post) {
  return node("span", post.hidden ? "숨김" : post.closed ? "모집 마감" : "공개", "badge" + (post.hidden ? " hidden" : post.closed ? " closed" : ""));
}
function category(post) {
  return { study: "스터디", club: "소모임", dating: "과팅" }[post.category] || "교류";
}
function meta(post) {
  return [post.when, post.where].filter(Boolean).join(" · ") || "일시·장소 미등록";
}
function groups() {
  const map = /* @__PURE__ */ new Map();
  for (const item of lists.reports.items) {
    if (deleted.has(item.post.id)) continue;
    if (!map.has(item.post.id)) map.set(item.post.id, []);
    map.get(item.post.id).push(item);
  }
  return map;
}
function actions(post, inSheet = false) {
  const el = node("div", "", "actions");
  el.dataset.id = post.id;
  const hide = button(post.hidden ? "숨김 해제" : "글 숨기기", () => ask(post.id, false)), del = button(inSheet ? "영구 삭제" : "삭제", () => ask(post.id, true), "danger");
  for (const b of [hide, del]) {
    b.dataset.postId = post.id;
    b.dataset.action = b === hide ? "hide" : "delete";
    b.disabled = pending.has(post.id);
  }
  el.append(hide, del);
  return el;
}
function empty(container, title, description) {
  const el = node("div", "", "empty");
  el.append(node("b", title), node("span", description));
  container.append(el);
}
function renderReports() {
  const container = lists.reports.container;
  container.replaceChildren();
  const grouped = groups();
  $("#reportsLabel").textContent = "신고된 글 " + grouped.size;
  $("#reportBadge").textContent = String(grouped.size);
  $("#reportBadge").hidden = !grouped.size;
  $("#reportsNote").hidden = !lists.reports.cursor;
  for (const [id, items] of grouped) {
    const post = posts.get(id);
    if (!post) continue;
    const row = node("article", "", "row");
    row.dataset.id = id;
    const head = node("div", "", "row-head");
    head.append(badge(post), node("span", "신고 " + items.length + "건", "report-count"), node("time", time(items[0].reportedAt), "latest"));
    const title = button(post.title, () => openDetail(id), "title-button");
    title.dataset.postId = id;
    title.disabled = pending.has(id);
    const reason = node("div", "", "reason"), shown = expanded.has(id) ? items : items.slice(0, 1);
    for (const item of shown) {
      const line = node("div", "", "reason-line");
      line.append(node("p", item.reason), node("time", time(item.reportedAt)));
      reason.append(line);
    }
    if (items.length > 1) {
      const toggle = button(expanded.has(id) ? "접기" : "신고 " + items.length + "건 모두 보기", () => {
        expanded.has(id) ? expanded.delete(id) : expanded.add(id);
        renderReports();
        const next = [...container.querySelectorAll("article")].find((el) => el.dataset.id === id)?.querySelector(".expand");
        next?.focus();
      }, "expand");
      toggle.dataset.postId = id;
      toggle.disabled = pending.has(id);
      toggle.setAttribute("aria-expanded", String(expanded.has(id)));
      reason.append(toggle);
    }
    row.append(head, title, node("p", meta(post), "meta"), reason, actions(post));
    container.append(row);
  }
  if (!grouped.size) empty(container, "접수된 신고가 없어요", "새 신고가 오면 여기에 먼저 보여요.");
}
function renderPosts() {
  const container = lists.meetings.container;
  container.replaceChildren();
  const grouped = groups(), ids = lists.meetings.items.filter((id) => posts.has(id) && !deleted.has(id));
  $("#postsLabel").textContent = (query ? "‘" + query + "’ 검색 결과 " : "전체 게시물 ") + ids.length;
  $("#postsNote").hidden = !lists.meetings.cursor;
  for (const id of ids) {
    const post = posts.get(id), row = button("", () => openDetail(id), "post-row"), body = node("span", "", "post-body"), head = node("span", "", "row-head");
    row.dataset.id = id;
    row.dataset.postId = id;
    row.dataset.hidden = String(!!post.hidden);
    row.disabled = pending.has(id);
    head.append(badge(post), node("span", category(post)));
    if (grouped.has(id)) head.append(node("span", "· 신고 " + grouped.get(id).length, "report-count"));
    body.append(head, node("h3", post.title), node("span", meta(post), "meta"));
    row.append(body, node("span", "›", "chevron"));
    container.append(row);
  }
  if (!ids.length) empty(container, "게시물이 없어요", query ? "다른 검색어로 찾아보세요." : "새 모집글이 올라오면 여기에 보여요.");
}
function renderDetail() {
  const post = posts.get(detailId);
  if (!post) {
    if (detail.open) closeDetail();
    return;
  }
  const content = $("#detailContent"), head = node("div", "", "sheet-head");
  content.replaceChildren();
  head.append(node("h2", "게시물 상세"), button("닫기", closeDetail));
  const status = node("div", "", "row-head");
  status.append(badge(post), node("span", category(post)), node("span", "· " + (post.college || "단과대학 미등록")));
  const title = node("h2", post.title);
  title.id = "detailTitle";
  content.append(node("div", "", "handle"), head, status, title, node("p", meta(post), "meta"), node("p", post.intro || "소개가 없어요.", "intro"));
  const reports = groups().get(post.id);
  if (reports) content.append(node("p", "신고 " + reports.length + "건 · 최근 “" + reports[0].reason + "”", "reason"));
  content.append(actions(post, true));
}
function render() {
  renderReports();
  renderPosts();
  if (detail.open) renderDetail();
  syncPending();
}
function openDetail(id) {
  if (pending.has(id)) return;
  detailId = id;
  renderDetail();
  detail.showModal();
}
function syncPending() {
  for (const b of document.querySelectorAll("[data-post-id]")) b.disabled = pending.has(b.dataset.postId);
  $("#confirmDo").disabled = !!choice && pending.has(choice.id);
  $("#confirmCancel").disabled = !!choice && pending.has(choice.id);
}
function ask(id, remove) {
  if (pending.has(id) || !posts.has(id)) return;
  const post = posts.get(id);
  choice = { id, remove, hidden: !post.hidden };
  $("#confirmTitle").textContent = remove ? "이 글을 영구 삭제할까요?" : choice.hidden ? "이 글을 일반 이용자에게 숨길까요?" : "이 글을 다시 공개할까요?";
  $("#confirmBody").textContent = remove ? "신청 내역과 신고도 함께 삭제되며 되돌릴 수 없어요." : post.title;
  const b = $("#confirmDo");
  b.textContent = remove ? "삭제" : choice.hidden ? "숨기기" : "공개";
  b.classList.toggle("danger", remove);
  syncPending();
  confirmation.showModal();
}
$("#confirmCancel").addEventListener("click", () => {
  confirmation.close();
  choice = null;
});
confirmation.addEventListener("cancel", (e) => {
  if (choice && pending.has(choice.id)) e.preventDefault();
  else choice = null;
});
for (const dialog of [detail, confirmation]) dialog.addEventListener("click", (e) => {
  if (e.target !== dialog) return;
  const rect = dialog.getBoundingClientRect();
  if (e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom) return;
  if (dialog === confirmation) {
    if (choice && pending.has(choice.id)) return;
    choice = null;
    dialog.close();
  } else closeDetail();
});
detail.addEventListener("close", () => {
  if (!detail.open) detailId = null;
});
$("#confirmDo").addEventListener("click", async () => {
  if (!choice || pending.has(choice.id)) return;
  const operation = { ...choice }, session = sessionVersion, { id, remove, hidden } = operation;
  pending.add(id);
  revisions.set(id, (revisions.get(id) || 0) + 1);
  syncPending();
  try {
    await api("meetings/" + id, remove ? "DELETE" : "PUT", remove ? { confirmId: id } : { hidden });
    if (session !== sessionVersion) return;
    if (remove) {
      deleted.add(id);
      posts.delete(id);
      lists.reports.items = lists.reports.items.filter((item) => item.post.id !== id);
      lists.meetings.items = lists.meetings.items.filter((value) => value !== id);
      expanded.delete(id);
      if (detailId === id) closeDetail();
    } else {
      const post = posts.get(id);
      if (post) post.hidden = hidden;
    }
    confirmation.close();
    choice = null;
    render();
    const restored = [...document.querySelectorAll("[data-post-id][data-action=hide]")].filter((b) => b.dataset.postId === id);
    if (!remove) restored.at(detail.open ? -1 : 0)?.focus();
    else if (!detail.open) $("#reportsTab[aria-selected=true],#postsTab[aria-selected=true]")?.focus();
    say(remove ? "게시물을 삭제했어요." : hidden ? "글을 숨겼어요." : "숨김을 해제했어요.");
  } catch (e) {
    if (session === sessionVersion || panel.hidden) say(e);
  } finally {
    if (session === sessionVersion) {
      pending.delete(id);
      syncPending();
    }
  }
});
async function load(kind, reset = true) {
  const list = lists[kind];
  if (!reset && (list.more.disabled || !list.cursor)) return;
  const request = ++list.version, session = sessionVersion, searchAt = searchVersion, snapshot = new Map(revisions), pendingAtStart = new Set(pending);
  list.more.disabled = true;
  list.container.setAttribute("aria-busy", "true");
  try {
    const params = new URLSearchParams();
    if (kind === "meetings" && query) params.set("q", query);
    if (!reset) params.set("cursor", list.cursor);
    const data = await api(kind + "?" + params);
    if (request !== list.version || session !== sessionVersion || panel.hidden || kind === "meetings" && searchAt !== searchVersion) return;
    if (reset) list.items = [];
    list.cursor = data.nextCursor;
    list.more.hidden = !list.cursor;
    for (const item of data.items) {
      const incoming = kind === "reports" ? item.post : item, id = incoming.id;
      if (deleted.has(id)) continue;
      const old = posts.get(id), post = { ...old, ...incoming };
      if (kind === "reports" && old && Object.hasOwn(old, "closed")) post.closed = old.closed;
      if (old && (pending.has(id) || pendingAtStart.has(id) || revisions.get(id) !== snapshot.get(id))) post.hidden = old.hidden;
      posts.set(id, post);
      if (kind === "reports") list.items.push(item);
      else if (!list.items.includes(id)) list.items.push(id);
    }
    render();
  } finally {
    if (request === list.version && session === sessionVersion) {
      list.more.disabled = false;
      list.container.removeAttribute("aria-busy");
    }
  }
}
function countFixed() {
  const value = fixedText.value;
  $("#fixedCount").textContent = value.length + " / 500자";
  fixedSave.disabled = fixedSaving || fixedVersion === null || !value.trim() || value.trim() === fixedOriginal || value.length > 500;
}
async function loadFixed() {
  const request = ++fixedRequest, session = sessionVersion;
  const data = await api("fixed-message");
  if (request !== fixedRequest || session !== sessionVersion || panel.hidden) return;
  fixedText.value = data.text;
  fixedOriginal = data.text.trim();
  fixedVersion = data.updatedAt;
  fixedText.disabled = false;
  fixedStatus.textContent = "";
  fixedStatus.classList.remove("error");
  $("#fixedAt").textContent = "마지막 저장 · " + time(data.updatedAt, true);
  countFixed();
}
fixedText.addEventListener("input", countFixed);
fixedForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (fixedSave.disabled) return;
  const session = sessionVersion, request = ++fixedRequest;
  fixedSaving = true;
  fixedText.disabled = true;
  countFixed();
  try {
    const data = await api("fixed-message", "PUT", { text: fixedText.value, updatedAt: fixedVersion });
    if (session !== sessionVersion || request !== fixedRequest) return;
    fixedVersion = data.updatedAt;
    fixedOriginal = data.text.trim();
    fixedText.value = data.text;
    $("#fixedAt").textContent = "마지막 저장 · " + time(data.updatedAt, true);
    fixedStatus.classList.remove("error");
    fixedStatus.textContent = "저장했어요. 다음 정기 음성 생성 후 새 멘트를 들을 수 있어요.";
  } catch (e2) {
    if (session === sessionVersion && request === fixedRequest) {
      fixedStatus.classList.add("error");
      fixedStatus.textContent = e2.message;
    } else if (panel.hidden) say(e2);
  } finally {
    if (session === sessionVersion) {
      fixedSaving = false;
      fixedText.disabled = fixedVersion === null;
      countFixed();
    }
  }
});
async function reload() {
  const session = sessionVersion;
  $("#refresh").disabled = true;
  const results = await Promise.allSettled([load("reports"), load("meetings"), fixedSaving ? Promise.resolve() : loadFixed()]);
  if (session === sessionVersion) {
    $("#refresh").disabled = false;
    const failure = results.find((r) => r.status === "rejected");
    if (failure) say(failure.reason);
  }
}
login.addEventListener("submit", async (e) => {
  e.preventDefault();
  const b = login.querySelector("button");
  b.disabled = true;
  $("#loginError").hidden = true;
  try {
    await api("login", "POST", { username: login.elements.username.value, password: login.elements.password.value });
    signedIn(true);
    say("");
    await reload();
  } catch (e2) {
    $("#loginError").textContent = e2.message;
    $("#loginError").hidden = false;
  } finally {
    login.elements.password.value = "";
    b.disabled = false;
  }
});
search.addEventListener("submit", (e) => {
  e.preventDefault();
  query = search.elements.query.value.trim();
  searchVersion++;
  load("meetings").catch((e2) => {
    if (!panel.hidden) say(e2);
  });
});
$("#refresh").addEventListener("click", reload);
$("#logout").addEventListener("click", async () => {
  const b = $("#logout");
  b.disabled = true;
  try {
    await api("logout", "POST");
    signedIn(false);
    say("로그아웃했어요.");
  } catch (e) {
    say(e);
  } finally {
    b.disabled = false;
    $("#refresh").disabled = false;
  }
});
for (const [kind, list] of Object.entries(lists)) list.more.addEventListener("click", () => load(kind, false).catch((e) => {
  if (!panel.hidden) say(e);
}));
function bytes(base64) {
  return Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
}
const face = new FontFace("Pretendard Variable", bytes("${font}"), { weight: "100 900", style: "normal", display: "swap" });
face.load().then((loaded) => document.fonts.add(loaded)).catch(() => {
});
createImageBitmap(new Blob([bytes("${mascot}")], { type: "image/webp" })).then((bitmap) => {
  const canvas = $("#mascot");
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
}).catch(() => {
  $("#mascot").hidden = true;
});
const loginButton = login.querySelector("button");
loginButton.disabled = true;
loginButton.textContent = "로그인 확인 중…";
api("session").then(() => {
  signedIn(true);
  return reload();
}).catch((e) => {
  if (e.message !== "관리자 로그인이 필요해요.") say(e);
}).finally(() => {
  loginButton.disabled = false;
  loginButton.textContent = "로그인";
});
</script>
</body>
</html>`;
