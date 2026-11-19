// TWIN 新界面（Preact + htm，不用打包，离线可用）。
// 这里管：侧栏、手机底部三个入口、Ctrl K 快速入口、资料首页、项目、资产、人脉。
// 其他页面（对话、今天、暂存箱、文档、设置……）暂时还是 app.js / chat.js / home.js / todo.js / pages.js 里的老写法，按页慢慢搬过来。
// 用到老写法里的全局（app.js、day.js）：pref、setPref、api、toast、modal、closeModal、setTitle、route、chat、pendingAsk、files、PSTATUS、dueTag、shortName、bLink、libLink。
import { html, render as mount, useState, useEffect, useLayoutEffect, useRef, useMemo } from '/static/preact-htm.js';

const bus = new EventTarget();
const hashNow = () => decodeURIComponent(location.hash.slice(1));
function useHash() {
  const [h, set] = useState(hashNow());
  useEffect(() => { const f = () => set(hashNow()); addEventListener('hashchange', f); return () => removeEventListener('hashchange', f); }, []);
  return h;
}
function useBus(name, fn) { useEffect(() => { bus.addEventListener(name, fn); return () => bus.removeEventListener(name, fn); }, []); }
// 读过的数据记在内存里：切回某页时先用上次的数据马上画出来，同时在后台取最新的再换上（不用等“读取中”）
const memo = new Map();
function fetchData(url) { return api(url).then(x => { memo.set(url, x); return x; }); }
function useData(url) {
  const [d, setD] = useState(() => memo.get(url) || null);
  const load = () => fetchData(url).then(setD).catch(e => toast(e.message));
  useEffect(() => { setD(memo.get(url) || null); load(); }, [url]);
  return [d, load];
}
const raw = s => html`<span dangerouslySetInnerHTML=${{ __html: s }}></span>`;

// ---------------- 图标 ----------------
const I = (d, w = 16) => html`<svg width=${w} height=${w} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">${d}</svg>`;
const IC = {
  chat: html`<path d="M4 5h16v11H9l-5 4z"/>`,
  todo: html`<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>`,
  shelf: html`<path d="M4 19V5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2z"/>`,
  plus: html`<path d="M12 5v14M5 12h14"/>`,
  search: html`<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>`,
  gear: html`<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>`,
  hist: html`<path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2"/>`,
  back: html`<path d="M15 5l-7 7 7 7"/>`,
  sun: html`<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6 19 19M5 19l1.4-1.4M17.6 6.4 19 5"/>`,
  moon: html`<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>`,
  news: html`<path d="M4 5h13v14H6a2 2 0 0 1-2-2zM17 9h3v8a2 2 0 0 1-2 2"/><path d="M7 9h7M7 13h7M7 16h4"/>`,
  home: html`<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>`,
  // 整理标题（Lucide wand-sparkles）
  wand: html`<path d="m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.2 1.2 0 0 0 1.72 0L21.64 5.36a1.2 1.2 0 0 0 0-1.72"/><path d="m14 7 3 3"/><path d="M5 6v4"/><path d="M19 14v4"/><path d="M10 2v2"/><path d="M7 8H3"/><path d="M21 16h-4"/><path d="M11 3H9"/>`,
  // 插件（Lucide puzzle）
  plug: html`<path d="M15.39 4.39a1 1 0 0 0 1.68-.474 2.5 2.5 0 1 1 3.014 3.015 1 1 0 0 0-.474 1.68l1.683 1.682a2.414 2.414 0 0 1 0 3.414L19.61 15.39a1 1 0 0 1-1.68-.474 2.5 2.5 0 1 0-3.014 3.015 1 1 0 0 1 .474 1.68l-1.683 1.682a2.414 2.414 0 0 1-3.414 0L8.61 19.61a1 1 0 0 0-1.68.474 2.5 2.5 0 1 1-3.014-3.015 1 1 0 0 0 .474-1.68l-1.683-1.682a2.414 2.414 0 0 1 0-3.414L4.39 8.61a1 1 0 0 1 1.68.474 2.5 2.5 0 1 0 3.014-3.015 1 1 0 0 1-.474-1.68l1.683-1.682a2.414 2.414 0 0 1 3.414 0z"/>`,
  pulse: html`<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>`,
  lock: html`<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>`,
};

// 白天 / 黑夜切换：和设置、历史、锁定放在一起，样式一样
function ModeBtn() {
  const get = () => document.documentElement.dataset.mode === 'dark';
  const [dark, setDark] = useState(get());
  useEffect(() => { const o = new MutationObserver(() => setDark(get())); o.observe(document.documentElement, { attributes: true, attributeFilter: ['data-mode'] }); return () => o.disconnect(); }, []);
  const t = dark ? '切到白天' : '切到黑夜';
  return html`<button type="button" class="ib" data-modetoggle title=${t} aria-label=${t}>${I(dark ? IC.sun : IC.moon, 17)}</button>`;
}

// 提示：小 i 图标，鼠标放上去才显示（显示逻辑在 app.js，对新旧页面都管用）
const Tip = ({ label, children }) => html`<span class="qtip" tabindex="0" role="button" aria-label="说明">${raw(TIP_ICON)}${label ? html`<em>${label}</em>` : ''}<span class="tiptext">${children}</span></span>`;

// ---------------- 侧栏 ----------------
const SHELF = [['inbox', '暂存箱'], ['assets', '资产'], ['people', '人脉'], ['lib', '文档']];
function section(v) {
  if (!v || v === 'home' || v === 'news') return 'home';
  if (v === 'c') return 'chat';
  if (v === 'today' || v === 'projects' || v === 'b') return 'today';
  if (['shelf', 'inbox', 'assets', 'people', 'lib'].includes(v) || v.endsWith('.md')) return 'shelf';
  return '';
}
function Side() {
  const h = useHash(), v = h.split('/')[0], sec = section(v), sub = v.endsWith('.md') ? 'lib' : v;
  const [chats, setChats] = useState([]), [inbox, setInbox] = useState(inboxBadge.n || 0);
  const loadChats = () => api('/api/chats').then(setChats).catch(() => {});
  useEffect(loadChats, []);
  const [ver, setVer] = useState('');
  useEffect(() => { api('/api/version').then(j => setVer(j.version || '')).catch(() => {}); }, []);
  useBus('chats', loadChats); useBus('inbox', e => setInbox(e.detail));
  const del = (e, id) => { e.preventDefault(); e.stopPropagation();
    const m = modal(`<h3>删除这段对话？</h3><p class="note">删除后找不回来。</p><div class="row"><button class="btn" id="mx">取消</button><button class="btn primary" id="mok">删除</button></div>`);
    m.querySelector('#mx').onclick = closeModal;
    m.querySelector('#mok').onclick = async () => { await api('/api/chat/delete', { id }); closeModal(); if (chat.id === id) location.hash = 'c'; loadChats(); }; };
  // 右键对话：重命名 / 整理标题 / 删除，不用把鼠标挪到小按钮上
  const rename = c => { const m = dlg('重命名对话', '', `<div class="hafl"><label class="haf"><span>标题</span><span class="hain"><input id="rnT" value="${esc(c.title || '')}" maxlength="60"></span></label></div>`,
      `<button class="btn ghost" data-x2>取消</button><button class="btn primary" id="mok">保存</button>`, 'hdsmall'), inp = m.querySelector('#rnT');
    const ok = async () => { const t = inp.value.trim(); if (!t) return toast('标题不能空');
      try { const j = await api('/api/chat/rename', { id: c.id, title: t }); if (chat.id === c.id) { chat.title = j.title; chat.titled = j.titled; } closeModal(); loadChats(); } catch (e) { toast(e.message, 6000); } };
    m.querySelector('[data-x2]').onclick = closeModal; m.querySelector('#mok').onclick = ok;
    inp.onkeydown = e => { if (e.key === 'Enter' && !e.isComposing) ok(); }; inp.focus(); inp.select(); };
  // 固定标题的对话（比如雅思答疑）不能改名，也不让 AI 整理
  const menu = (e, c) => popMenu(e, [...(c.fixed ? [] : [['重命名', () => rename(c)], ...(c.talked ? [['用 AI 整理标题', () => tidyOne(e, c)]] : [])]), ['删除', () => del(e, c.id)]]);
  // 资料下面那几项默认收起：进到资料里的页面时自动展开一次，之后随时可以点小箭头收起或展开
  // 整理标题：只在点的时候花 token；整理过、之后没聊新内容的跳过（服务器端也会再查一次）
  const [tidying, setTidy] = useState('');
  const retitle = async ids => { let n = 0;
    for (const id of ids) { setTidy(id);
      try { const j = await api('/api/chat/retitle', { id }); if (!j.skipped) n++; if (chat.id === id) { chat.title = j.title; chat.titled = j.titled; } }
      catch (e) { toast(e.message, 6000); break; } }
    setTidy(''); loadChats(); if (ids.length > 1) toast(n ? `整理好 ${n} 个标题` : '标题都是最新的'); };
  const stale = chats.filter(c => c.talked && !c.fresh && !c.fixed);
  const tidyOne = (e, c) => { e.preventDefault(); e.stopPropagation(); if (c.fresh) return toast('这段对话之后没聊新内容，标题不用再整理'); retitle([c.id]); };
  const [showSub, setShow] = useState(pref('shelfOpen', '') === '1' || sec === 'shelf');
  useEffect(() => { if (sec === 'shelf') setShow(true); }, [sec]);
  const fold = () => { setShow(!showSub); setPref('shelfOpen', showSub ? '' : '1'); };
  const item = (href, key, label, icon, extra) => html`<a href=${href} class=${sec === key ? 'on' : ''}>${I(icon)}<span>${label}</span>${extra}</a>`;
  return html`
    <div class="brand"><b>TWIN</b>${ver ? html`<a class="ver" href=${'#lib/' + encodeURIComponent('CHANGELOG.md')} title=${'版本 ' + ver + '，点开看修改日志'}>${ver.replace(/-beta$/, '')} beta</a>` : ''}<button type="button" class="sidex" title="收起侧栏，页面铺满" aria-label="收起侧栏" onClick=${() => window.toggleSide?.()}><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/><path d="m16 15-3-3 3-3"/></svg></button></div>
    <button type="button" class="kbtn" onClick=${() => bus.dispatchEvent(new Event('palette'))}>${I(IC.search)}<span>搜索</span><kbd>Ctrl K</kbd></button>
    <nav class="nav nav2">
      ${item('#home', 'home', '首页', IC.home)}
      ${item('#c', 'chat', '对话', IC.chat)}
      ${item('#today', 'today', '待办', IC.todo)}
      <button type="button" class=${'navbtn' + (sec === 'shelf' && !showSub ? ' on' : '')} aria-expanded=${showSub} onClick=${fold}>${I(IC.shelf)}<span>资料</span>
        ${!showSub && inbox ? html`<span class="badge">${inbox}</span>` : ''}<span class=${'fold' + (showSub ? ' open' : '')} aria-hidden="true">${I(html`<path d="M9 6l6 6-6 6"/>`, 14)}</span></button>
      <div class="subnav" hidden=${!showSub}>${SHELF.map(([k, n]) => html`<a href=${'#' + k} class=${sub === k ? 'on' : ''}>${n}${k === 'inbox' && inbox ? html`<span class="badge">${inbox}</span>` : ''}</a>`)}</div>
    </nav>
    <div class="hist-h"><span>最近对话</span>${stale.length ? html`<button type="button" class="newc tidy" disabled=${!!tidying} title=${`用 AI 按内容整理 ${stale.length} 个对话的标题（整理过、没新内容的不算）`} aria-label="整理标题" onClick=${() => retitle(stale.map(c => c.id))}>${I(IC.wand, 14)}<span>${tidying ? '整理中…' : stale.length}</span></button>` : ''}<a href="#c" class="newc" title="新对话" aria-label="新对话">${I(IC.plus, 14)}</a></div>
    <div id="hist">${chats.length ? chats.map(c => html`<a class=${'h-item' + (h === 'c/' + c.id ? ' on' : '')} href=${'#c/' + c.id} onContextMenu=${e => menu(e, c)}>
        <span>${tidying === c.id ? '整理中…' : c.title || '新对话'}</span>${c.talked && !c.fixed ? html`<button type="button" class=${'tbtn' + (c.fresh ? ' done' : '')} title=${c.fresh ? '标题已经整理过' : '用 AI 按内容整理标题'} aria-label="整理标题" onClick=${e => tidyOne(e, c)}>${I(IC.wand, 13)}</button>` : ''}<button type="button" aria-label="删除这段对话" onClick=${e => del(e, c.id)}>✕</button></a>`)
      : html`<p class="note" style="padding:0 12px">还没有对话</p>`}</div>
    <${Drawer} v=${v} />`;
}

// 侧栏底部：最左边一个按钮打开抽屉（设置、插件、改动历史、体检、锁定），点外面或选完就收起；白天黑夜常用，单独放右边
function Drawer({ v }) {
  const [open, setOpen] = useState(false), ref = useRef();
  useEffect(() => { if (!open) return; const f = e => { if (!ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('pointerdown', f, true); return () => document.removeEventListener('pointerdown', f, true); }, [open]);
  const go = (href, label, icon) => html`<a href=${href} class=${v === href.slice(1) ? 'on' : ''} onClick=${() => setOpen(false)}>${I(icon, 16)}<span>${label}</span></a>`;
  return html`<div class="side-foot" ref=${ref}>
    ${open ? html`<div class="sdrw" role="menu">
      ${go('#settings', '设置', IC.gear)}
      <button type="button" onClick=${() => { setOpen(false); window.plugDlg?.(); }}>${I(IC.plug, 16)}<span>插件</span></button>
      ${go('#history', '改动历史', IC.hist)}
      ${go('#health', '体检', IC.pulse)}
      <hr/>
      <button type="button" onClick=${async () => { await api('/api/logout', {}); location.reload(); }}>${I(IC.lock, 16)}<span>锁定</span></button></div>` : ''}
    <button type="button" class=${'sfb ib' + (open ? ' on' : '')} title="设置和更多" aria-label="设置和更多" aria-expanded=${open} onClick=${() => setOpen(!open)}>${I(IC.gear, 17)}</button>
    <span class="sp"></span><${ModeBtn} /></div>`;
}

// 手机底部：首页、对话、待办、资料
function Tabs() {
  const sec = section(useHash().split('/')[0]);
  const t = (href, key, label, icon) => html`<a href=${href} class=${sec === key ? 'on' : ''}>${I(icon, 22)}<span>${label}</span></a>`;
  return html`${t('#home', 'home', '首页', IC.home)}${t('#c', 'chat', '对话', IC.chat)}${t('#today', 'today', '待办', IC.todo)}${t('#shelf', 'shelf', '资料', IC.shelf)}`;
}

// ---------------- Ctrl K 快速入口 ----------------
let newDraft = null; // 从快速入口新建卡片时带过去的名字
function Palette() {
  const [open, setOpen] = useState(false), [q, setQ] = useState(''), [sel, setSel] = useState(0), [data, setData] = useState(null);
  const inp = useRef();
  const pack = ([hm, a, p]) => ({ boards: [...hm.boards, ...(hm.inactive || [])], assets: a.items, people: p.items });
  const show = q0 => { setOpen(true); setQ(typeof q0 === 'string' ? q0 : ''); setSel(0);
    const urls = ['/api/home', '/api/cards?kind=assets', '/api/cards?kind=people'];
    if (urls.every(u => memo.has(u))) setData(pack(urls.map(u => memo.get(u))));  // 先用记住的，马上能搜
    Promise.all(urls.map(fetchData)).then(r => setData(pack(r))).catch(() => setData(d => d || { boards: [], assets: [], people: [] })); };
  useBus('palette', e => show(e.detail));
  useEffect(() => {
    const k = e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); open ? setOpen(false) : show(); } };
    addEventListener('keydown', k); return () => removeEventListener('keydown', k);
  }, [open]);
  useEffect(() => { if (open && inp.current) inp.current.focus(); }, [open]);
  const rows = useMemo(() => buildRows(q.trim(), data), [q, data]);
  if (!open) return null;
  const close = () => setOpen(false);
  const run = r => { close(); r.run(); };
  const key = e => {
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowDown') { e.preventDefault(); setSel(s => Math.min(s + 1, rows.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSel(s => Math.max(s - 1, 0)); }
    else if (e.key === 'Enter' && !e.isComposing && rows[sel]) { e.preventDefault(); run(rows[sel]); }
  };
  return html`<div class="pal" onClick=${e => e.target === e.currentTarget && close()}>
    <div class="pbox" role="dialog" aria-label="快速入口">
      <label class="pin">${I(IC.search, 18)}<input ref=${inp} value=${q} placeholder="搜项目、任务、资产、人、文档" aria-label="搜索"
        onInput=${e => { setQ(e.target.value); setSel(0); }} onKeyDown=${key}/></label>
      ${q.trim() ? html`<div class="plist">${rows.map((r, i) => html`<button type="button" class=${'prow' + (i === sel ? ' on' : '')} onMouseMove=${() => i !== sel && setSel(i)} onClick=${() => run(r)}>
          <span class="pt">${r.title}${r.sub ? html`<small> · ${r.sub}</small>` : ''}</span><span class="pe">${r.kind}</span></button>`)}
        ${!rows.length ? html`<p class="note" style="padding:12px">${data ? '没找到。' : '读取中…'}</p>` : ''}</div>` : ''}
    </div></div>`;
}
const go = hash => { if (location.hash === hash) route(); else location.hash = hash; };
const askAi = text => { pendingAsk = text; go('#c'); };
function buildRows(q, d) {
  const out = [], ql = q.toLowerCase(), hit = (...s) => s.some(x => String(x || '').toLowerCase().includes(ql));
  // 只管搜：没输入时不列东西，常用入口侧栏都有
  if (!d || !ql) return out;
  const B = d.boards, take = (arr, max) => arr.slice(0, max).forEach(x => out.push(x));
  take(B.filter(b => hit(b.name)).map(b => ({ kind: '项目', title: shortName(b.name), sub: `${b.open.length} 件没做${b.status !== 'active' ? ' · ' + (PSTATUS[b.status] || b.status) : ''}`, run: () => go(bLink(b.path)) })), 4);
  take(B.flatMap(b => (b.links || []).filter(l => hit(l.name, shortName(b.name) + l.name)).map(l => ({ kind: '链接', title: l.name, sub: shortName(b.name), run: () => window.open(l.url, '_blank', 'noopener') }))), 4);
  take(B.flatMap(b => b.open.filter(t => hit(t.task)).map(t => ({ kind: '任务', title: t.task, sub: shortName(b.name), run: () => go(bLink(b.path)) }))), 4);
  take(d.assets.filter(c => hit(c.name, c.model)).map(c => ({ kind: '资产', title: c.name, sub: c.model, run: () => go('#assets/' + c.path) })), 3);
  take(d.people.filter(c => hit(c.name, c.city)).map(c => ({ kind: '人', title: c.name, sub: c.city, run: () => go('#people/' + c.path) })), 3);
  take(files.filter(f => hit(f.title, f.path)).map(f => ({ kind: '文档', title: f.title || f.path.split('/').at(-1), sub: f.path.split('/').slice(-2, -1)[0], run: () => go(libLink(f.path)) })), 4);
  out.push({ kind: '问 AI', title: `“${q}”`, run: () => askAi(q) });
  return out;
}

// ---------------- 页面公用 ----------------
// 数据还没到时的灰色占位条，比“读取中…”看着稳
function Skel({ rows = 4, cards }) {
  return html`<div class=${'skel' + (cards ? ' cards' : '')} aria-busy="true" aria-label="正在读取">${Array.from({ length: rows }, (_, i) => html`<span style=${{ animationDelay: i * 60 + 'ms' }}></span>`)}</div>`;
}
function Head({ title, sub, back, children }) {
  return html`<header class="nhead">${back ? html`<a class="nback" href=${back} aria-label="返回">${I(IC.back, 20)}</a>` : ''}
    <h1>${title}</h1>${sub ? html`<span class="sub">${sub}</span>` : ''}<span class="sp"></span>${children}</header>`;
}

// 资料首页：暂存箱、项目、资产、人脉、文档放在一起
function Shelf() {
  const [a] = useData('/api/cards?kind=assets'), [p] = useData('/api/cards?kind=people'), [ib] = useData('/api/inbox');
  useEffect(() => setTitle('资料'), []);
  const n = { assets: a && `${a.items.length} 张`, people: p && `${p.items.length} 位`,
    inbox: ib && (ib.items.length ? `${ib.items.length} 件没归档` : '空的'), lib: files.length ? `${files.length} 篇` : '' };
  const desc = { inbox: '先放进来，之后再归档', assets: '设备、账号、工具，私密', people: '谁擅长什么、上次联系，私密', lib: '所有 md 文档' };
  return html`<div class="wrap page"><${Head} title="资料"/>
    <div class="shelf">${SHELF.map(([k, name]) => html`<a href=${'#' + k}><b>${name}</b><span>${desc[k]}</span><em>${n[k] || ''}</em></a>`)}</div>
    <div class="shelf mini"><a href="#settings"><b>设置</b></a><a href="#history"><b>改动历史</b></a><a href="#lib" onClick=${e => { e.preventDefault(); window.plugDlg?.(); }}><b>插件</b></a><a href="#health"><b>体检</b></a></div></div>`;
}

// ---------------- 资产、人脉：卡片墙或列表，点开在右边看详情（手机上是整页） ----------------
const DOT = { in_use: 'ok', idle: 'mute', lent: 'warm', broken: 'hot', sold: 'gone' };
const listVal = v => Array.isArray(v) ? v.map(x => String(x).replace(/^\[\[(?:.*\|)?([^\]]*)\]\]$/, '$1')).join('、') : v || '';
const qState = {};
const AVATAR = { device: '💻', digital: '🔑', tool: '🛠', parts: '🔌', physical: '📦', lease: '🏠' };
function Cards({ kind, sub }) {
  const [d, load] = useData('/api/cards?kind=' + kind), st = qState[kind] || (qState[kind] = { q: '', g: '' }), [, bump] = useState(0);
  useEffect(() => setTitle(kind === 'people' ? '人脉' : '资产'), [kind]);
  // 详情开着时按 Esc 关掉
  useEffect(() => { if (!sub) return; const k = e => { if (e.key === 'Escape' && !document.querySelector('.pal') && !e.target.closest('input,textarea,select')) location.hash = kind; };
    addEventListener('keydown', k); return () => removeEventListener('keydown', k); }, [sub, kind]);
  if (!d) return html`<div class="wrap page"><${Skel} rows=${6} cards/></div>`;
  const S = d.schema, F = Object.fromEntries(S.fields.map(f => [f.key, f]));
  const opt = (k, v) => ((F[k].options || []).find(o => o[0] === v) || [v, v])[1];
  const set = (k, v) => { st[k] = v; bump(x => x + 1); };
  const shown = d.items.filter(c => (!st.g || c[S.group] === st.g) &&
    (!st.q || JSON.stringify([...S.fields.map(f => c[f.key]), c.body]).toLowerCase().includes(st.q.toLowerCase())));
  const count = g => d.items.filter(c => c[S.group] === g).length;
  const cur = sub === 'new' ? 'new' : d.items.find(c => c.path === sub);
  const right = c => S.badge !== S.group ? c[S.badge] && html`<span class=${'st ' + (DOT[c[S.badge]] || '')}><i></i>${opt(S.badge, c[S.badge])}</span>`
    : html`<span class="st">${c.last_contact || ''}</span>`;
  const row = c => html`<a href=${`#${kind}/${c.path}`} class=${'crow' + (cur === c ? ' on' : '')}>
    <span class="cn"><b>${c.name}</b><small>${[S.sub.map(k => listVal(c[k])).filter(Boolean).join(' · ') || c.summary, c.log.length ? c.log.at(-1) : ''].filter(Boolean).join(' · ')}</small></span>${right(c)}</a>`;
  const avatar = c => kind === 'people' ? (c.name || '?').slice(0, 1) : AVATAR[c.category] || '📦';
  const card = c => html`<a href=${`#${kind}/${c.path}`} class=${'ccard' + (cur === c ? ' on' : '')}>
    <span class="ctop"><span class="cav" aria-hidden="true">${avatar(c)}</span>
      <span class="cname">${c.name}<small>${S.sub.map(k => listVal(c[k])).filter(Boolean).join(' · ') || c.summary}</small></span>
      ${c[S.badge] ? html`<span class=${'cbadge ' + (S.badge !== S.group ? (DOT[c[S.badge]] || '') : '')}>${opt(S.badge, c[S.badge])}</span>` : ''}</span>
    ${S.meta.some(k => listVal(c[k])) ? html`<span class="cmeta">${S.meta.map(k => listVal(c[k]) ? html`<span><i>${F[k].label}</i>${listVal(c[k])}</span>` : '')}</span>` : ''}
    ${c.log.length ? html`<span class="clog">${c.log.at(-1)}</span>` : ''}</a>`;
  const setMode = m => { setPref('cards.' + kind, m); bump(x => x + 1); };
  const asCards = pref('cards.' + kind, 'card') === 'card';
  const groups = S.groups.map(g => [g, shown.filter(c => c[S.group] === g[0])]).filter(x => x[1].length);
  const saved = p => { load(); if (p && p !== sub) location.hash = `${kind}/${p}`; };
  return html`<div class=${'split' + (cur ? ' has-sel' : '') + (asCards ? ' cards' : '')}>
    <section class="slist">
      <${Head} title=${S.title} sub=${`${d.items.length} · 私密，只在本机`} back="#shelf">
        <div class="vtog" role="group" aria-label="显示方式"><button type="button" class=${asCards ? 'on' : ''} onClick=${() => setMode('card')}>卡片</button><button type="button" class=${asCards ? '' : 'on'} onClick=${() => setMode('list')}>列表</button></div>
        <button class="btn primary sq" title=${'新' + S.noun} aria-label=${'新' + S.noun} onClick=${() => { newDraft = ''; location.hash = kind + '/new'; }}>${I(IC.plus, 18)}</button></${Head}>
      <label class="filt">${I(IC.search, 15)}<input type="search" value=${st.q} placeholder=${kind === 'people' ? '筛选名字、在哪、擅长' : '筛选名字、型号'} onInput=${e => set('q', e.target.value)}/></label>
      <div class="chipsrow"><button type="button" class=${!st.g ? 'on' : ''} onClick=${() => set('g', '')}>全部 ${d.items.length}</button>
        ${S.groups.filter(g => count(g[0])).map(g => html`<button type="button" class=${st.g === g[0] ? 'on' : ''} onClick=${() => set('g', g[0])}>${g[1]} ${count(g[0])}</button>`)}</div>
      <div class="cl">${groups.map(([g, xs]) => html`<div class="gh">${g[1]} · ${xs.length}</div>${asCards ? html`<div class="cgrid">${xs.map(card)}</div>` : xs.map(row)}`)}
        ${!shown.length ? html`<p class="note pad">${d.items.length ? '没有符合的。' : `还没有${S.noun}。点右上角 + 新建。`}</p>` : ''}</div>
      <p class="foot pad"><${Tip} label="文件存在哪">每张卡是 <code>${kind === 'assets' ? '06_Assets' : '05_Network'}</code> 下的一个 md 文件，Obsidian 里改也行，改动都能在<a href="#history">改动历史</a>里撤销。<//>
        ${kind === 'assets' ? html` · <button class="btn sm" onClick=${() => importAssets(load)}>从旧的资产总清单导入</button>` : ''}</p>
    </section>
    ${asCards && cur ? html`<a class="dscrim" href=${'#' + kind} aria-label="关闭详情"></a>` : ''}
    <section class="sdetail">${cur === 'new' ? html`<${NewCard} key="new" kind=${kind} S=${S} onSaved=${saved}/>`
      : cur ? html`<${Detail} key=${cur.path} kind=${kind} S=${S} c=${cur} onSaved=${saved}/>`
      : html`<div class="empty">${sub ? '找不到这张卡片了，可能被移走或删掉了。' : `点左边一张${S.noun}卡片，在这里看和改。`}</div>`}</section></div>`;
}
async function importAssets(done) {
  if (!confirm('把 Asset_List.md 里已经填了内容的行变成一张张卡片，再从表里拿掉这些行。只有名字的行留在表里，传感器那节不导入。可以在改动历史里撤销。现在导入？')) return;
  try { const r = await api('/api/cards/import', {}); toast(r.message); done(); } catch (e) { toast(e.message, 6000); }
}

// 下拉：和老页面一样用自己画的菜单（openMenu 在 app.js），不弹浏览器原生的列表
const CHEVD = html`<path d="m6 9 6 6 6-6"/>`;
function Pick({ opts, value, onPick, cls = 'kvsel', label = '' }) {
  const i = Math.max(0, opts.findIndex(o => o[0] === (value || ''))), cur = opts[i];
  return html`<button type="button" class=${cls} aria-label=${label} aria-haspopup="listbox"
    onClick=${e => openMenu(e.currentTarget, opts.map(o => o[1]), i, k => opts[k][0] !== (value || '') && onPick(opts[k][0]))}>
    <span class=${cur && cur[0] ? '' : 'mute'}>${cur ? cur[1] : ''}</span>${I(CHEVD, 14)}</button>`;
}
function Field({ f, value, onSave }) {
  const [ed, setEd] = useState(false), shown = listVal(value), box = useRef();
  useLayoutEffect(() => { if (ed && box.current) { box.esc = false; box.current.focus(); box.current.select(); } }, [ed]);
  const kv = (dd, cls = '') => html`<div class=${'kv' + (f.wide ? ' wide' : '')}><dt>${f.label}</dt><dd class=${cls}>${dd}</dd></div>`;
  if (f.type === 'readonly') return kv(shown || f.hint || '—', 'mute');
  const done = e => { setEd(false); if (box.esc) return; const v = e.target.value.trim(); if (v !== shown) onSave(v); };
  if (f.type === 'select') return kv(html`<${Pick} label=${f.label} opts=${[['', f.blank || '未选'], ...f.options]} value=${f.options.some(o => o[0] === value) ? value : ''} onPick=${onSave}/>`);
  return html`<div class=${'kv' + (f.wide ? ' wide' : '')}><dt>${f.label}</dt><dd>${ed
    ? html`<input ref=${box} value=${shown} placeholder=${f.hint || ''} onBlur=${done} onKeyDown=${e => { if (e.key === 'Enter' && !e.isComposing) e.target.blur(); if (e.key === 'Escape') { e.stopPropagation(); box.esc = true; e.target.blur(); } }}/>`
    : html`<button type="button" class=${'kvb' + (shown ? '' : ' mute')} onClick=${() => setEd(true)}>${shown || '点一下填写'}</button>`}</dd></div>`;
}
function Detail({ kind, S, c, onSaved }) {
  const [log, setLog] = useState(''), [body, setBody] = useState(c.body), [name, setName] = useState(c.name);
  const save = async (fields, b) => { try { const r = await api('/api/cards/save', { kind, path: c.path, fields, body: b }); onSaved(r.path); } catch (e) { toast(e.message, 6000); } };
  const addLog = async () => { if (!log.trim()) return; try { await api('/api/cards/log', { kind, path: c.path, text: log }); setLog(''); onSaved(c.path); } catch (e) { toast(e.message, 6000); } };
  const del = async () => { if (!confirm(`删掉“${c.name}”这张卡片？可以在改动历史里撤销。`)) return;
    try { const r = await api('/api/cards/delete', { kind, path: c.path }); toast(r.message); location.hash = kind; onSaved(); } catch (e) { toast(e.message, 6000); } };
  const badge = S.badge !== S.group && S.fields.find(f => f.key === S.badge);
  const rest = S.fields.filter(f => f.key !== 'name' && !(badge && f.key === S.badge));
  const logs = (c.log_all || c.log).slice().reverse();
  return html`<div class="dpane">
    <div class="dtop"><a class="nback" href=${'#' + kind} aria-label="返回">${I(IC.back, 20)}</a><span class="crumb">${S.title} · ${(S.groups.find(g => g[0] === c[S.group]) || ['', '未分类'])[1]}</span>
      <span class="sp"></span><a class="btn sm" href=${libLink(c.path)}>打开文件</a><button class="btn sm danger" onClick=${del}>删除</button></div>
    <input class="dname" value=${name} aria-label="名字" onInput=${e => setName(e.target.value)} onBlur=${() => name.trim() && name !== c.name && save({ name })} onKeyDown=${e => e.key === 'Enter' && e.target.blur()}/>
    ${badge ? html`<div class="seg" role="radiogroup" aria-label=${badge.label}>${badge.options.map(o => html`<button type="button" role="radio" aria-checked=${c[S.badge] === o[0]}
      class=${c[S.badge] === o[0] ? 'on' : ''} onClick=${() => c[S.badge] !== o[0] && save({ [S.badge]: o[0] })}>${o[1]}</button>`)}</div>` : ''}
    <dl class="kvs">${rest.map(f => html`<${Field} key=${f.key} f=${f} value=${c[f.key]} onSave=${v => save({ [f.key]: v })}/>`)}</dl>
    ${kind === 'people' && c.ai === 'yes' && c.ai_line ? html`<div class="aisum"><b>AI 看到的就是这一行</b>${c.ai_line}</div>` : ''}
    <div class="dsec"><div class="lbl">记录</div>
    <form class="logadd" onSubmit=${e => { e.preventDefault(); addLog(); }}><input value=${log} onInput=${e => setLog(e.target.value)}
      placeholder=${kind === 'people' ? '记一笔，比如：电话聊了南瓜的图案' : '记一笔，比如：借给小王了'} aria-label="记一笔"/><button class="send" aria-label="保存记录" disabled=${!log.trim()}>${I(html`<path d="M12 19V5M5 12l7-7 7 7"/>`, 16)}</button></form>
    ${logs.length ? html`<ol class="logs">${logs.map(l => { const m = l.match(/^(\d{4}-\d{2}-\d{2})\s+(.*)$/);
      return html`<li><span>${m ? m[1].slice(5) : ''}</span><span>${m ? m[2] : l}</span></li>`; })}</ol>` : ''}</div>
    <details class="dbody"><summary>正文（备注、用途，md 格式）</summary><textarea rows="10" value=${body} onInput=${e => setBody(e.target.value)}></textarea>
      <div class="row"><span class="sp"></span><button class="btn sm primary" disabled=${body === c.body} onClick=${() => save({}, body)}>保存正文</button></div></details>
  </div>`;
}
function NewCard({ kind, S, onSaved }) {
  const [v, setV] = useState({ name: newDraft || '', [S.group]: S.groups[0][0] }), nameRef = useRef();
  useEffect(() => { newDraft = null; nameRef.current && nameRef.current.focus(); }, []);
  const F = S.fields.filter(f => f.type !== 'readonly' && ['name', S.group, S.badge, ...S.sub].includes(f.key));
  const ok = async e => { e.preventDefault(); if (!v.name.trim()) return toast('先写名字');
    try { const r = await api('/api/cards/save', { kind, path: '', fields: v }); onSaved(r.path); } catch (er) { toast(er.message, 6000); } };
  return html`<form class="dpane" onSubmit=${ok}>
    <div class="dtop"><a class="nback" href=${'#' + kind} aria-label="返回">${I(IC.back, 20)}</a><span class="crumb">新${S.noun}</span></div>
    ${F.map(f => html`<div class="field"><label>${f.label}</label>${f.type === 'select'
      ? html`<${Pick} cls="fsel boxed" label=${f.label} opts=${[...(f.key !== S.group ? [['', f.blank || '未选']] : []), ...f.options]} value=${v[f.key] || ''} onPick=${x => setV({ ...v, [f.key]: x })}/>`
      : html`<input ref=${f.key === 'name' ? nameRef : null} value=${listVal(v[f.key])} placeholder=${f.hint || ''} onInput=${e => setV({ ...v, [f.key]: e.target.value })}/>`}</div>`)}
    <div class="row"><a class="btn" href=${'#' + kind}>取消</a><button class="btn primary">建好</button></div>
    <p class="note">别的字段建好以后在详情里点一下就能填。</p></form>`;
}

// ---------------- 挂到 #nview（老页面用 #view，两边分开） ----------------
const VIEWS = { shelf: Shelf, assets: Cards, people: Cards };
let mounted = false;
const TwinUI = {
  bus, views: new Set(Object.keys(VIEWS)),
  mount(v, rest) { const V = VIEWS[v]; mounted = true; mount(html`<${V} kind=${v} sub=${rest}/>`, document.getElementById('nview')); },
  unmount() { if (mounted) { mount(null, document.getElementById('nview')); mounted = false; } },
};
window.TwinUI = TwinUI;
mount(html`<${Side}/>`, document.getElementById('side'));
mount(html`<${Tabs}/>`, document.getElementById('tabs'));
mount(html`<${Palette}/>`, document.getElementById('pal'));
if (route.pending) route();
// 空闲时先把 Ctrl K 和资料页要用的数据取好
(window.requestIdleCallback || (f => setTimeout(f, 800)))(() => ['/api/home', '/api/cards?kind=assets', '/api/cards?kind=people', '/api/inbox'].forEach(u => fetchData(u).catch(() => {})));
