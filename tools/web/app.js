'use strict';
// TWIN 前端：对话为中心。视图：对话（默认）、今天、资料库、设置。
// 这个文件是基础（工具函数、提示、下拉框、外观、路由、Markdown）；各页面在 chat / day / home / todo / pages.js 里
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const coarse = matchMedia('(pointer:coarse)').matches;
// 同一个 GET 还没回来时又要一次（比如首页几个小组件都要 /api/home），共用同一个请求
const inflight = {};
// opt.quiet：后台自动做的事（首页自动取要闻、今日建议）不弹“撤销”提示，用户没动手就不打扰
function api(u, b, opt) { if (b) { for (const k in inflight) delete inflight[k]; return api1(u, b, opt); } return inflight[u] ||= api1(u).finally(() => delete inflight[u]); }
async function api1(u, b, opt) {
  const r = await fetch(u, b ? { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Twin': '1' }, body: JSON.stringify(b) } : {});
  const j = await r.json().catch(() => ({}));
  if (r.status === 401 && !u.includes('password')) { location.reload(); throw new Error(j.error); }
  if (!r.ok) { const er = new Error(j.error || '出错了'); er.data = j; throw er; }
  if (j.undo_id && !(opt && opt.quiet)) { undoTip = { id: j.undo_id, t: Date.now() }; toast(j.undo_label || '已保存'); }
  return j;
}
// 每次写文件后都可以撤销：提示条上带一个“撤销”按钮（几秒内有效，之后到“改动历史”里撤）
let undoTip = null;
function toast(m, ms = 2600) {
  const t = $('#toast'), u = undoTip && Date.now() - undoTip.t < 1500 ? undoTip : null;
  t.innerHTML = `<span title="${esc(m)}">${esc(m)}</span>` + (u ? `<button type="button" class="tbtn" data-u="${esc(u.id)}">撤销</button>` : '');
  t.hidden = false; clearTimeout(t._h); t._h = setTimeout(() => t.hidden = true, u ? Math.max(ms, 7000) : ms);
  const b = t.querySelector('[data-u]'); if (b) b.onclick = () => { t.hidden = true; undoEntry(b.dataset.u); };
}
async function undoEntry(id, force) {
  try { const j = await api('/api/history/undo', { id, force: !!force }); undoTip = null; toast(j.message); route(); }
  catch (e) {
    if (!e.data || !e.data.changed) return toast(e.message, 7000);
    const m = modal(`<h3>文件后来又被改过</h3><p class="note">${esc(e.message)}。强制撤销会把这些文件恢复到那次改动之前，后来的改动也会一起没了（不过也会记进历史，还能再撤回来）。</p>
      <div class="row"><button class="btn" id="mx">算了</button><button class="btn primary" id="mok">强制撤销</button></div>`);
    m.querySelector('#mx').onclick = closeModal; m.querySelector('#mok').onclick = () => { closeModal(); undoEntry(id, true); };
  }
}
function modal(html) { const host = $('#modalHost'); host.innerHTML = `<div class="modal"><div class="mbox">${html}</div></div>`; return host.querySelector('.mbox'); }
// 统一样式的对话框：标题 + ⓘ 说明 + 关闭，内容，底部按钮
// 右键菜单：rows = [[文字, 点了做什么, 快捷键提示?]]，贴着鼠标弹出，点别处或按键关掉
function popMenu(e, rows) { e.preventDefault(); e.stopPropagation(); document.querySelector('.hctx')?.remove();
  const m = document.createElement('div'); m.className = 'hctx'; m.setAttribute('role', 'menu');
  m.innerHTML = rows.map((r, i) => `<button type="button" role="menuitem" data-i="${i}"><span>${r[0]}</span>${r[2] ? `<kbd>${r[2]}</kbd>` : ''}</button>`).join('');
  document.body.append(m); m.style.left = Math.min(e.clientX, innerWidth - m.offsetWidth - 8) + 'px'; m.style.top = Math.min(e.clientY, innerHeight - m.offsetHeight - 8) + 'px';
  const off = ev => { if (!m.contains(ev.target) || ev.type === 'keydown') { m.remove(); document.removeEventListener('mousedown', off, true); document.removeEventListener('keydown', off, true); } };
  setTimeout(() => { document.addEventListener('mousedown', off, true); document.addEventListener('keydown', off, true); });
  m.onclick = ev => { const b = ev.target.closest('[data-i]'); if (!b) return; m.remove(); document.removeEventListener('mousedown', off, true); rows[+b.dataset.i][1](); } }
function dlg(title, help, body, foot, cls = '') { const m = modal(`<div class="hdh"><h3>${title}</h3>${help ? tip(help) : ''}<button type="button" class="hax" data-x aria-label="关闭">${lu('x', 16)}</button></div>
    <div class="hdb">${body}</div>${foot ? `<div class="hdf">${foot}</div>` : ''}`);
  m.classList.add('hdlg', ...cls.split(' ').filter(Boolean)); m.querySelector('[data-x]').onclick = closeModal; return m; }
// 关窗口时先淡出再拿掉；期间又开了新窗口的话，modal() 会直接换掉它
function closeModal() { const m = $('#modalHost .modal'); if (!m || m.classList.contains('out')) return;
  if (still()) return m.remove(); m.classList.add('out'); setTimeout(() => m.remove(), 140); }
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch (e) {
    const m = modal(`<h3>手动复制</h3><p class="note">浏览器不让自动复制。全选下面的内容复制。</p><textarea style="min-height:220px">${esc(text)}</textarea><div class="row"><button class="btn" id="mx">关闭</button></div>`);
    m.querySelector('#mx').onclick = closeModal; const t = m.querySelector('textarea'); t.focus(); t.select(); return false;
  }
}

// ----- 提示：一个小 i 图标，鼠标放上去（手机上点一下）才显示说明；带 data-tip 的元素（比如首页小组件）鼠标停留也用这个框 -----
const TIP_ICON = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.6v.1" stroke-linecap="round"/></svg>';
const tip = (html, label = '') => `<span class="qtip" tabindex="0" role="button" aria-label="说明">${TIP_ICON}${label ? `<em>${esc(label)}</em>` : ''}<span class="tiptext">${html}</span></span>`;
const tipBox = document.createElement('div'); tipBox.id = 'tipbox'; tipBox.setAttribute('role', 'tooltip'); tipBox.hidden = true; document.body.append(tipBox);
let tipFor = null, tipT = 0, tipAt = 0;
function showTip(el) {
  clearTimeout(tipT); const tx = el.querySelector('.tiptext'), html = tx ? tx.innerHTML : el.dataset.tip ? esc(el.dataset.tip).replace(/\n/g, '<br>') : ''; if (!html) return;
  if (tipFor !== el || tipBox.hidden) tipAt = Date.now();
  tipFor = el; tipBox.innerHTML = html; tipBox.hidden = false;
  const r = el.getBoundingClientRect(), b = tipBox.getBoundingClientRect();
  const x = Math.max(8, Math.min(r.left + r.width / 2 - b.width / 2, innerWidth - b.width - 8));
  let y = r.top - b.height - 8; if (y < 8) y = r.bottom + 8;
  tipBox.style.left = x + 'px'; tipBox.style.top = y + 'px';
}
function hideTip(now) { clearTimeout(tipT); tipT = setTimeout(() => { tipBox.hidden = true; tipFor = null; }, now ? 0 : 160); }
document.addEventListener('pointerover', e => { if (e.pointerType !== 'mouse') return; const t = e.target.closest('.qtip,[data-tip]'); if (t) showTip(t); else if (e.target.closest('#tipbox')) clearTimeout(tipT); });
document.addEventListener('pointerout', e => { if (e.pointerType !== 'mouse' || !e.target.closest('.qtip,[data-tip],#tipbox')) return; const to = e.relatedTarget; if (!(to && to.closest && to.closest('.qtip,[data-tip],#tipbox'))) hideTip(); });
document.addEventListener('focusin', e => { const t = e.target.closest && e.target.closest('.qtip'); if (t) showTip(t); });
document.addEventListener('focusout', e => { if (e.target.closest && e.target.closest('.qtip') && !tipBox.matches(':hover')) hideTip(); });
document.addEventListener('click', e => { const t = e.target.closest('.qtip');
  if (t) { e.preventDefault(); e.stopPropagation(); if (tipFor === t && !tipBox.hidden && Date.now() - tipAt > 400 && !matchMedia('(hover:hover)').matches) hideTip(true); else showTip(t); }
  else if (!e.target.closest('#tipbox')) hideTip(true); }, true);
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !tipBox.hidden) hideTip(true); });
addEventListener('scroll', () => { if (!tipBox.hidden) hideTip(true); }, true);
addEventListener('hashchange', () => hideTip(true));

// ----- 下拉框：原生的弹出列表太丑，换成自己画的菜单；原来的 select 还在（藏起来），取值、change 事件都照旧 -----
const CHECK = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
const FOLDER = '<svg class="ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>';
const CHEV = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>';
let fmenu = null;
function fancy(sel) {
  if (!sel) return;
  if (!sel._fs) {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'fsel ' + sel.className + (sel.closest('.cbar') ? '' : ' boxed'); b.setAttribute('aria-haspopup', 'listbox');
    if (sel.style.cssText) b.style.cssText = sel.style.cssText;
    b.setAttribute('aria-label', sel.getAttribute('aria-label') || ''); if (sel.id) b.dataset.for = sel.id;
    sel.after(b); sel.classList.add('fs-native'); sel.tabIndex = -1; sel._fs = b;
    b.onclick = () => fmenu && fmenu.sel === sel ? closeFmenu() : openFmenu(sel);
    b.onkeydown = e => { if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); openFmenu(sel); } };
    sel.addEventListener('change', () => fsLabel(sel));
    if (sel.form) sel.form.addEventListener('reset', () => setTimeout(() => fsLabel(sel)));
    new MutationObserver(() => fsLabel(sel)).observe(sel, { childList: true, subtree: true });
  }
  fsLabel(sel);
}
function fsLabel(sel) { const o = sel.options[sel.selectedIndex]; sel._fs.innerHTML = (sel.dataset.icon || '') + `<span>${esc(o ? o.dataset.short || o.text : '')}</span>${CHEV}`; sel._fs.disabled = sel.disabled; }
function closeFmenu() { if (!fmenu) return; fmenu.m.remove(); fmenu.btn.setAttribute('aria-expanded', 'false'); fmenu = null; }
function openFmenu(sel) {
  openMenu(sel._fs, [...sel.options].map(o => o.text), sel.selectedIndex, k => { if (k !== sel.selectedIndex) { sel.selectedIndex = k; sel.dispatchEvent(new Event('change', { bubbles: true })); } }, sel);
}
// 通用菜单：贴着 btn 弹出，选中第 k 项时调 pick(k)
function openMenu(btn, labels, cur, pick, sel) {
  if (fmenu && fmenu.btn === btn) return closeFmenu();  // 再点一次同一个按钮就收起
  closeFmenu(); const m = document.createElement('div'); m.className = 'fmenu'; m.setAttribute('role', 'listbox');
  m.innerHTML = labels.map((t, k) => `<button type="button" role="option" data-k="${k}" class="${k === cur ? 'on' : ''}" aria-selected="${k === cur}"><span>${esc(t)}</span>${k === cur ? CHECK : ''}</button>`).join('');
  document.body.append(m); fmenu = { m, btn, sel, t: Date.now() }; btn.setAttribute('aria-expanded', 'true');
  const r = btn.getBoundingClientRect(); m.style.minWidth = Math.max(r.width, sel ? 160 : 96) + 'px';
  const h = m.offsetHeight, w = m.offsetWidth, below = innerHeight - r.bottom - 8, above = r.top - 8;
  const up = (h > below && above > below) || r.top > innerHeight * 0.6; m.style.maxHeight = Math.min(340, up ? above - 6 : below - 6) + 'px';
  m.style.left = Math.max(8, Math.min(r.left, innerWidth - w - 8)) + 'px';
  m.style.top = (up ? Math.max(8, r.top - Math.min(h, above - 6) - 6) : r.bottom + 6) + 'px';
  const items = [...m.querySelectorAll('[data-k]')];
  (items[cur] || items[0]).focus();
  m.onclick = e => { const x = e.target.closest('[data-k]'); if (!x) return; closeFmenu(); if (btn.isConnected) btn.focus(); pick(+x.dataset.k); };
  m.onkeydown = e => { const i = items.indexOf(document.activeElement);
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); items[(i + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length].focus(); }
    else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeFmenu(); btn.focus(); }
    else if (e.key === 'Tab') closeFmenu(); };
}
document.addEventListener('pointerdown', e => { if (fmenu && !e.target.closest('.fmenu') && e.target !== fmenu.btn && !fmenu.btn.contains(e.target)) closeFmenu(); }, true);
addEventListener('resize', closeFmenu);
addEventListener('scroll', e => { if (fmenu && !fmenu.m.contains(e.target) && Date.now() - fmenu.t > 200) closeFmenu(); }, true);  // 刚打开时的滚动多半是点按钮前的惯性，不算
addEventListener('hashchange', closeFmenu);
// 旧页面（#view）和弹窗里的下拉框都自动换掉；新页面（Preact 管的）不动
let fsQ = 0;
new MutationObserver(() => { if (fsQ) return; fsQ = requestAnimationFrame(() => { fsQ = 0; document.querySelectorAll('#view select:not(.fs-native), #modalHost select:not(.fs-native)').forEach(fancy); }); })
  .observe(document.body, { childList: true, subtree: true });

let aiCfg = { providers: [], active: '', presets: [] }, files = [];
// AI 设置一分钟内不重复取；设置页里总是取最新的
async function loadAi(force) { if (!force && loadAi.t && Date.now() - loadAi.t < 60000) return aiCfg; aiCfg = await api('/api/ai/config'); loadAi.t = Date.now(); return aiCfg; }
function provSelect(id) {
  if (!aiCfg.providers.length) return '';
  return `<select id="${id}" aria-label="用哪家 AI">${aiCfg.providers.map(p => `<option value="${esc(p.id)}" ${p.id === aiCfg.active ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}</select>`;
}

// ---------------- 外观（每台设备单独记住）----------------
const ACCENTS = { mono: ['黑白', '#1b1b1a', '#e6e6e3'], blue: ['蓝', '#2f5bd3', '#8aa8ff'], green: ['绿', '#2f7a4f', '#7cc39c'],
  purple: ['紫', '#6a4fd0', '#ab98ff'], orange: ['橙', '#c45a22', '#f0a070'], rose: ['玫红', '#c23a6b', '#f08cb0'] };
function pref(k, d) { try { return localStorage.getItem('twin.' + k) || d; } catch (e) { return d; } }
function setPref(k, v) { try { localStorage.setItem('twin.' + k, v); } catch (e) {} }
const darkMq = matchMedia('(prefers-color-scheme: dark)');
function applyLook() {
  const mode = pref('mode', 'auto'), dark = mode === 'dark' || (mode === 'auto' && darkMq.matches);
  const root = document.documentElement; root.dataset.mode = dark ? 'dark' : 'light';
  const c = ACCENTS[pref('accent', 'mono')] || ACCENTS.mono, col = dark ? c[2] : c[1];
  root.style.setProperty('--accent', col);
  root.style.setProperty('--on-accent', dark ? '#18191b' : '#ffffff');
  document.querySelectorAll('meta[name=theme-color]').forEach(m => m.content = dark ? '#1e1f21' : '#ffffff');
}
// 重新播放一个动画 class；ms 后自动去掉（每个 class 各有一个计时器）
const still = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
function replay(el, cls, ms) { if (!el) return; clearTimeout(el['_' + cls]); el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls);
  if (ms) el['_' + cls] = setTimeout(() => el.classList.remove(cls), ms); }
// 白天黑夜切换（浏览器支持 View Transitions 时）：点按钮切换的，新颜色从按钮中心一圈扩散开（边缘清晰）；系统自动切换的，整页渐变。
// 切换那一下先关掉所有 CSS 过渡：不然新颜色是“正在过渡中”被拍下来的，动画结束后页面还在慢慢变色，看着像闪一下
function switchLook(fn, from) {
  const root = document.documentElement, run = () => { root.classList.add('notrans'); fn(); void root.offsetWidth; };
  const done = () => requestAnimationFrame(() => { root.classList.remove('notrans', 'ripple'); });
  if (!document.startViewTransition || still()) { run(); return done(); }
  root.classList.toggle('ripple', !!from);
  const t = document.startViewTransition(run); t.finished.finally(done);
  if (!from) return;
  const b = from.getBoundingClientRect(), x = b.left + b.width / 2, y = b.top + b.height / 2, r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
  t.ready.then(() => root.animate({ clipPath: [`circle(0 at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] }, { duration: 360, easing: 'cubic-bezier(.3,.6,.4,1)', pseudoElement: '::view-transition-new(root)' }));
}
darkMq.addEventListener('change', () => switchLook(() => { applyLook(); drawModeBtns(); })); applyLook();
const SUN = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6 19 19M5 19l1.4-1.4M17.6 6.4 19 5"/></svg>';
const MOON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>';
function drawModeBtns() {
  const dark = document.documentElement.dataset.mode === 'dark';
  document.querySelectorAll('.modeBtn').forEach(b => { b.innerHTML = dark ? SUN : MOON; b.title = b.ariaLabel = dark ? '切到白天' : '切到黑夜'; });
}
document.addEventListener('click', e => { const btn = e.target.closest('.modeBtn,[data-modetoggle]'); if (!btn) return;
  setPref('mode', document.documentElement.dataset.mode === 'dark' ? 'light' : 'dark'); switchLook(() => { applyLook(); drawModeBtns(); }, btn);
  document.querySelectorAll('[data-m]').forEach(x => x.classList.toggle('on', x.dataset.m === pref('mode', 'auto')));
});
darkMq.addEventListener('change', drawModeBtns); drawModeBtns();

// ---------------- 路由 ----------------
function setTitle(t) { $('#topTitle').textContent = t; document.title = t === 'TWIN' ? 'TWIN' : `${t} · TWIN`; }
function closeNav() { document.body.classList.remove('nav-open'); }
$('#menuBtn').onclick = () => document.body.classList.add('nav-open');
$('#scrim').onclick = closeNav;
// 侧栏折叠（“全页面”）：首页默认收起，其他页默认展开，两边各记各的。手机上侧栏本来就是抽屉，不受影响
const narrow = matchMedia('(max-width:860px)');
const isHome = () => { const v = location.hash.slice(1).split('/')[0]; return !v || v === 'home'; };
function applySide() { document.body.classList.toggle('side-hidden', isHome() ? pref('homeSide', '0') !== '1' : pref('sideOff', '0') === '1'); }
window.toggleSide = () => { if (narrow.matches) return document.body.classList.add('nav-open');
  const hide = !document.body.classList.contains('side-hidden'); isHome() ? setPref('homeSide', hide ? '0' : '1') : setPref('sideOff', hide ? '1' : '0');
  // 只有手动收起、展开时才滑动（换页时首页和其他页面侧栏状态不同，直接切换）。
  // 做法（FLIP）：记下页面里各块的位置和宽度 → 按新状态排好版 → 宽度没变的块从原位置平移（横竖一起）到新位置。
  // 宽度变了的块（跟着窗口伸缩的容器）往里找宽度不变的块，所以居中的内容挪半个侧栏宽、靠左的挪一整个，换行的卡片斜着走。
  // 有边框背景的伸缩块（输入框）整块平移，不然边框会跳。会滚动的伸缩区域（整页、消息区、文档正文）原地不动（滚动条不跟着跑），
  // 只是动画期间把它的可见范围往左多伸一个侧栏宽（负外边距 + 同样大的内边距，里面排版不变），从左边滑进来的内容才不会被切掉。
  // 固定位置的元素（首页右上角按钮）不管；子块太多（长对话）整块走，不一个个算，不然会卡。只动 transform，不逐帧重新排版
  const box = $('#nview').hidden ? $('#view') : $('#nview'), W = box.clientWidth;
  toggleSide.anims?.forEach(a => a.finish()); toggleSide.anims = [];  // 上一次还没滑完就又点：先让它走完再量，不然位置量错
  const at = c => { const r = c.getBoundingClientRect(); return [r.left, r.top]; };
  const plan = (el, d) => [...el.children].slice(0, 150).filter(c => getComputedStyle(c).position !== 'fixed').map(c => ({ c, p: at(c), w: c.offsetWidth, kids: d < 5 ? plan(c, d + 1) : [] }));
  const tree = [{ c: box, p: at(box), w: box.offsetWidth, kids: plan(box, 0) }]; applySide(); if (still()) return;
  const o = { duration: 280, easing: 'cubic-bezier(.3,.7,.3,1)' }, dx = document.body.classList.contains('side-hidden') ? 260 : -260;
  // 先把所有块的新位置都量完，再一起开始动画（先动了外层，里面量到的位置就带上了外层的平移）
  // 有背景或底线、但没左边框的伸缩条（文档页“新建”那一栏）也不平移：右端停住，左端用裁剪跟着左边的栏伸缩
  // 没有子块的伸缩块（首页大时钟、日期这种一整行文字）按文字对齐方式算：居中的按中点平移，靠右的按右端，不然文字会被拽一下
  const moves = [], wide = [], walk = (n, bx, by) => { const [x, y] = at(n.c), w = n.c.offsetWidth, dy = n.p[1] - y, cs = getComputedStyle(n.c), al = cs.textAlign;
    const dx = n.p[0] - x + (n.kids.length || Math.abs(w - n.w) < 2 ? 0 : al === 'center' ? (n.w - w) / 2 : al === 'right' || al === 'end' ? n.w - w : 0);
    const fixed = Math.abs(w - n.w) < 2 || n.w < W * .4 || n.kids.length > 30 || !n.kids.length;  // 窄的栏（文件栏）整体平移，里面不再拆开
    const scroll = !fixed && cs.overflowX !== 'visible', band = !fixed && !scroll && cs.borderLeftStyle === 'none' && (cs.backgroundColor !== 'rgba(0, 0, 0, 0)' || cs.borderBottomStyle !== 'none');
    const own = fixed || (!scroll && !band && cs.borderLeftStyle !== 'none');
    if (scroll || band) wide.push([n.c, parseFloat(cs.marginLeft) || 0, parseFloat(cs.paddingLeft) || 0, band && Math.max(dx, 0), band && Math.max(-dx, 0)]);
    else if (own && Math.abs(dx - bx) + Math.abs(dy - by) > 1) moves.push([n.c, dx - bx, dy - by]);
    if (!fixed) n.kids.forEach(k => own && !scroll ? walk(k, dx, dy) : walk(k, bx, by)); };
  tree.forEach(n => walk(n, 0, 0));
  toggleSide.anims = moves.map(([el, x, y]) => el.animate([{ transform: `translate(${x}px,${y}px)` }, { transform: 'none' }], o));
  wide.forEach(([el, m, p, a, e]) => { if (a === false) e = 260; else toggleSide.anims.push(el.animate([{ clipPath: `inset(0 0 0 ${a}px)` }, { clipPath: `inset(0 0 0 ${e}px)` }], o));
    Object.assign(el.style, { marginLeft: m - e + 'px', paddingLeft: p + e + 'px', overflowX: 'hidden' }); });
  Promise.all(toggleSide.anims.map(a => a.finished)).finally(() => wide.forEach(([el]) => Object.assign(el.style, { marginLeft: '', paddingLeft: '', overflowX: '' })));
  toggleSide.anims.push($('#side').animate([{ transform: `translateX(${dx}px)`, visibility: 'visible' }, { transform: 'none', visibility: 'visible' }], o));
  if (dx > 0) $('#sideOpen').animate([{ opacity: 0 }, { opacity: 0, offset: .7 }, { opacity: 1 }], o); };  // 收起：侧栏滑走后“展开”按钮才出现
$('#sideOpen').onclick = () => window.toggleSide();
let leaveGuard = null;
const NEW_VIEWS = new Set(['shelf', 'assets', 'people']);
// 每次换页 route.gen 加一。老页面取完数据先看一眼 fresh()，换过页就不再往界面里写，免得盖住新页面
const fresh = () => { const g = route.gen; return () => g === route.gen; };
function route() {
  if (leaveGuard && !leaveGuard()) return;
  leaveGuard = null; route.gen = (route.gen || 0) + 1;
  const h = decodeURIComponent(location.hash.slice(1));
  closeNav();
  // 项目页（#b/…）和今天是同一个“待办”页，换来换去不清空左边那栏
  const v0 = h.split('/')[0], v = v0 === 'b' || v0 === 'projects' ? 'today' : v0, view = $('#view');
  // 页面缓存：离开一个老页面时记下它当时的样子（和滚动位置）；再回来先原样显示，新数据到了再换掉，不会先白一下再出来
  if (route.lastH != null && route.lastH !== h) {
    if (SNAP_VIEWS.has(route.last) && view.firstChild) { SNAP.delete(route.lastH); SNAP.set(route.lastH, { html: view.innerHTML, top: view.scrollTop }); if (SNAP.size > 24) SNAP.delete(SNAP.keys().next().value); }
    if (!route.last || route.last === 'home') viewHome.save?.();
  }
  route.lastH = h;
  const snap = v !== route.last && SNAP.get(h);
  // 有缓存的页面淡入整个 #view（不是里面的内容），新数据中途换上来也不会重新淡入一次（那样看着是闪一下）
  if (snap) { view.innerHTML = snap.html; view.scrollTop = snap.top; view.classList.add('stale'); replay(view, 'vfade', 300); }
  // 换到另一个老页面、又没有缓存时先清空 #view：不然上一页的内容会先淡入一次，再被新页面盖掉，看着就是闪一下
  else if (v !== route.last && !NEW_VIEWS.has(v) && !(v === 'inbox' && viewInbox.d)) view.innerHTML = '';
  // 没缓存时数据回来才有内容：淡入一直开着，等内容画上再收（最多等 1.5 秒），这样晚到的内容也是淡入，不是弹出来
  if (v !== route.last && !snap) replay(NEW_VIEWS.has(v) ? $('#nview') : view, 'enter', NEW_VIEWS.has(v) ? 300 : 1500);
  route.last = v;
  document.body.dataset.v = v; applySide();
  // 侧栏、资料、项目、资产、人脉是新界面（ui.js，Preact）画的；其他页面还是这里的老写法
  // 新旧页面各用一个容器：#nview 归 Preact，#view 归老页面，互不覆盖。老页面晚到的数据只会写进藏起来的 #view
  if (NEW_VIEWS.has(v)) { if (!window.TwinUI) { route.pending = true; return; }
    $('#view').hidden = true; $('#view').innerHTML = ''; $('#nview').hidden = false; return TwinUI.mount(v, h.slice(v.length + 1)); }
  window.TwinUI?.unmount(); $('#nview').hidden = true; $('#view').hidden = false;
  const g = route.gen; Promise.resolve(showView(v, h)).finally(() => { if (g !== route.gen) return; view.classList.remove('stale');
    if (!snap && view.classList.contains('enter')) { clearTimeout(view._enter); view._enter = setTimeout(() => view.classList.remove('enter'), 300); } });
}
const SNAP = new Map(), SNAP_VIEWS = new Set(['today', 'news', 'lib', 'history', 'health']);
function showView(v, h) {
  if (v === 'today') return viewTodo(h.startsWith('b/') ? h.slice(2) : null);
  if (v === 'news') return viewNews();
  if (!v || v === 'home') return viewHome();
  if (v === 'lib') return viewLib(h.slice(4) || null);
  if (v === 'settings') return viewSettings();
  if (v === 'inbox') return viewInbox();
  if (v === 'history') return viewHistory();
  if (v === 'health') return viewHealth();
  if (h.endsWith('.md')) return viewLib(h);
  return viewChat(v === 'c' ? h.slice(2) : null);
}
window.onhashchange = route;

// ---------------- Markdown ----------------
const LV = { public: '公开 · 会上传摘要', internal: '内部 · 只在本地', private: '私密 · 只在本地', secret: '机密 · 只在本地' };
let libCur = null, chkIdx = 0, pbIdx = 0;
function resolveWiki(name) {
  name = name.split('|')[0].split('#')[0].trim(); const want = name.endsWith('.md') ? name : name + '.md';
  return (files.find(f => f.path === want) || files.find(f => f.path.endsWith('/' + want)) || files.find(f => f.path.split('/').at(-1) === want.split('/').at(-1)) || {}).path;
}
function resolveRel(href) {
  if (/^[a-z]+:/i.test(href)) return null; href = decodeURI(href.split('#')[0]);
  const parts = (libCur || '').split('/').slice(0, -1);
  for (const s of href.split('/')) { if (s === '..') parts.pop(); else if (s && s !== '.') parts.push(s); }
  return parts.join('/');
}
const libLink = p => `#lib/${encodeURIComponent(p)}`;
function inline(s) {
  s = esc(s);
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  // 斜体：*文字* 或 _文字_（星号后面、前面紧挨着字，“2 * 3 * 4”这种不算；下划线两边不能是字母数字，免得 file_name 被吃掉）
  s = s.replace(/(^|[^*\w])\*(?=\S)([^*\n]*?\S)\*(?![*\w])/g, '$1<em>$2</em>').replace(/(^|[^\w])_(?=\S)([^_\n]*?\S)_(?!\w)/g, '$1<em>$2</em>');
  s = s.replace(/\[\[([^\]]+)\]\]/g, (m, n) => { const p = resolveWiki(n.replace(/&amp;/g, '&')); const f = !n.includes('|') && n.includes('/') && files.find(x => x.path === p); const label = f ? esc(f.title) : n.split('|').at(-1);
    return p ? `<a href="${libLink(p)}">${label}</a>` : `<a class="missing" title="还没有这个文件">${label}</a>`; });
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, t, h) => { const raw = h.replace(/&amp;/g, '&');
    if (/^https?:/.test(raw)) return `<a href="${h}" target="_blank" rel="noopener">${t}</a>`;
    const p = resolveRel(raw); return p && p.endsWith('.md') ? `<a href="${libLink(p)}">${t}</a>` : `<a class="missing" title="本地文件：${esc(p || raw)}">${t}</a>`; });
  s = s.replace(/[☐☑]/g, c => `<span class="chk${c === '☑' ? ' on' : ''}" role="checkbox" aria-checked="${c === '☑'}" tabindex="0" data-i="${chkIdx++}"></span>`);
  return s;
}
// 表格一格只能写一行，任务表里的子任务用 <br> 分行：这里换成真的换行（代码片段里的不动）
const cellBr = h => h.split(/(<code>.*?<\/code>)/).map((p, i) => i % 2 ? p : p.replace(/&lt;br\s*\/?&gt;/gi, '<br>')).join('');
function cell(c, tag) { c = c.trim(); if (tag === 'td' && /^P[0-3]$/.test(c)) return `<td><span class="pill ${c}">${c}</span></td>`; return `<${tag}>${cellBr(inline(c))}</${tag}>`; }
function render(text, nested) {
  if (!nested) chkIdx = pbIdx = 0; let html = '', meta = ''; text = String(text).replace(/\r\n?/g, '\n'); // Windows 换行
  const fm = text.match(/^---\n([\s\S]*?)\n---\n?/);
  if (fm) { text = text.slice(fm[0].length); const lv = (fm[1].match(/privacy:\s*(\w+)/) || [])[1] || 'secret';
    meta = `<div class="meta"><span class="chip lv ${lv}">${LV[lv] || lv}</span>` + fm[1].split('\n').filter(l => l.trim() && !/^privacy:/.test(l)).map(l => `<span class="chip">${esc(l.replace(/\s+#.*$/, ''))}</span>`).join('') + '</div>'; }
  const L = text.split('\n'); let i = 0, list = null; const close = () => { if (list) { html += `</${list}>`; list = null; } };
  while (i < L.length) { const l = L[i]; let m;
    if (/^<!--\s*private\s*-->/i.test(l.trim())) { close(); const buf = []; i++; while (i < L.length && !/<!--\s*\/private\s*-->/i.test(L[i])) buf.push(L[i++]); i++;
      html += `<div class="privblock" data-pb="${pbIdx++}"><div class="tag"><span>私密段落 · 只在本地可见，不会上传</span><button type="button" class="btn sm pbed">改这段</button></div><div class="pbody">${render(buf.join('\n'), true)}</div></div>`; continue; }
    if (/^<!--.*-->$/.test(l.trim())) { i++; continue; }
    if (l.startsWith('```')) { close(); const buf = []; i++; while (i < L.length && !L[i].startsWith('```')) buf.push(L[i++]); i++; html += `<pre><code>${esc(buf.join('\n'))}</code></pre>`; continue; }
    if (m = l.match(/^(#{1,6})\s+(.*)/)) { close(); html += `<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`; i++; continue; }
    if (/^\s*\|.*\|\s*$/.test(l) && i + 1 < L.length && /^\s*\|[\s:|-]+\|\s*$/.test(L[i + 1])) { close();
      const cells = r => r.trim().replace(/^\||\|$/g, '').split('|');
      html += '<div class="tbl"><table><thead><tr>' + cells(l).map(c => cell(c, 'th')).join('') + '</tr></thead><tbody>'; i += 2;
      while (i < L.length && /^\s*\|.*\|\s*$/.test(L[i])) { const row = L[i]; html += `<tr${row.includes('☑') ? ' class="done"' : ''}>` + cells(row).map(c => cell(c, 'td')).join('') + '</tr>'; i++; }
      html += '</tbody></table></div>'; continue; }
    if (m = l.match(/^>\s?(.*)/)) { close(); const buf = [m[1]]; i++; while (i < L.length && /^>/.test(L[i])) buf.push(L[i++].replace(/^>\s?/, '')); html += `<blockquote>${buf.map(inline).join('<br>')}</blockquote>`; continue; }
    // 有序列表接着原来的编号：AI 常在 1. 2. 3. 之间插例句段落，每段重新开一个列表时用 start 接上，不会变成 1. 1. 1.
    if (m = l.match(/^(\s*)([-*]|\d+\.)\s+(.*)/)) { const t = /\d/.test(m[2]) ? 'ol' : 'ul'; if (list !== t) { close(); html += t === 'ol' && parseInt(m[2]) > 1 ? `<ol start="${parseInt(m[2])}">` : `<${t}>`; list = t; }
      html += `<li${m[1].length ? ` style="margin-left:${m[1].length * 8}px"` : ''}>${inline(m[3])}</li>`; i++; continue; }
    if (/^\s*[-*]\s*$/.test(l) || !l.trim()) { close(); i++; continue; }
    close(); const buf = [l]; i++;
    while (i < L.length && L[i].trim() && !/^(#|>|\||```|\s*[-*]\s|\s*\d+\.\s|<!--)/.test(L[i])) buf.push(L[i++]);
    html += `<p>${buf.map(inline).join('<br>')}</p>`; }
  close(); return meta + html;
}
