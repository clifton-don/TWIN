'use strict';
// 待办和今天用的小零件（截止、优先级、勾选、添加框）、今日建议、图标、作息条
// 普通 <script>，和 app.js 共用全局变量和函数；index.html 里按 app → chat → day → home → todo → pages 的顺序加载

// ---------------- 今天 ----------------
function dueTag(t) {
  if (t.days == null) return t.due ? `<span class="due">${esc(t.due)}</span>` : '';
  const txt = t.days < 0 ? `过期 ${-t.days} 天` : t.days === 0 ? '今天' : t.days === 1 ? '明天' : `还剩 ${t.days} 天`;
  return `<span class="due ${t.days <= 1 ? 'hot' : t.days <= 7 ? 'warm' : ''}" title="${esc(t.due)} 截止">${esc(txt)}</span>`;
}
const isoOf = t => { if (t.days == null) return ''; const d = new Date(); d.setDate(d.getDate() + t.days); return d.toLocaleDateString('sv'); };
// 截止日期：点一下就地改，清空就是去掉截止
const dueBtn = (t, attrs, cls = '') => `<button type="button" class="duebtn ${cls}" data-iso="${isoOf(t)}" ${attrs} title="点一下改截止日期">${dueTag(t) || '<span class="due nodue">设截止</span>'}</button>`;
function bindDue(root, fn) {
  root.querySelectorAll('.duebtn').forEach(b => b.onclick = e => { e.preventDefault(); e.stopPropagation();
    const inp = document.createElement('input'); inp.type = 'date'; inp.className = 'datepick'; inp.value = b.dataset.iso; b.replaceWith(inp); inp.focus();
    try { inp.showPicker(); } catch (er) {}
    let done = false; const go = () => { if (done) return; done = true; if (inp.value !== b.dataset.iso) fn(b, inp.value); else inp.replaceWith(b); };
    inp.onchange = go; inp.onblur = go; inp.onkeydown = ev => { if (ev.key === 'Enter') go(); if (ev.key === 'Escape') { done = true; inp.replaceWith(b); } }; });
}
// 优先级：点一下弹出菜单
const priBtn = (p, attrs) => `<button type="button" class="pribtn" data-p="${esc(p || '')}" ${attrs} title="点一下改优先级">${pri(p || '—')}</button>`;
function bindPri(root, fn) {
  const P = ['P0', 'P1', 'P2', 'P3'];
  root.querySelectorAll('.pribtn').forEach(b => b.onclick = e => { e.preventDefault(); e.stopPropagation();
    if (fmenu && fmenu.btn === b) return closeFmenu();
    openMenu(b, P, P.indexOf(b.dataset.p), k => { if (P[k] !== b.dataset.p) fn(b, P[k]); }); });
}
const pri = p => p ? `<span class="pri ${esc(p)}">${esc(p)}</span>` : '';
const BUBBLE = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z"/></svg>';
// 今天页顶部的一周条：每天一格，数字是那天要交几件，小点是优先级（红 P0、橙 P1、灰其他）
// 今天要做：过期、今天到期；零散待办没有项目能托着，标了 P0 就一直算今天要做，直到做完或降级
const isNow = x => x.doing || (x.days != null && x.days <= 0) || (x.loose && x.priority === 'P0');
// 一周日期条：点一天就在下面看那天要交的（pick = 选中的那天，-1 是过期，0 是今天）
const dayLabel = k => { const d = new Date(); d.setDate(d.getDate() + k); return { label: k === -1 ? '过期' : k === 0 ? '今天' : k === 1 ? '明天' : '周' + '日一二三四五六'[d.getDay()], sub: `${d.getMonth() + 1}/${d.getDate()}`, iso: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }; };
function weekStrip(all, pick = 0) {
  const cols = [], late = all.filter(x => x.days != null && x.days < 0);
  if (late.length) cols.push({ ...dayLabel(-1), k: -1, its: late, cls: 'late' + (pick === -1 ? ' now' : '') });
  for (let k = 0; k < 7; k++) cols.push({ ...dayLabel(k), k, its: all.filter(x => x.days === k), cls: (k === pick ? 'now' : '') + (k === 0 && pick !== 0 ? ' today' : '') });
  return `<div class="wstrip" role="list" aria-label="未来 7 天每天要交几件，点一天看那天的任务">${cols.map(c => {
    const names = c.its.map(x => `· ${x.text}${x.board ? '（' + x.board + '）' : ''}`).join('\n');
    return `<div class="wc ${c.cls} ${c.its.length ? '' : 'zero'}" role="listitem" tabindex="0" data-wd="${c.k}" aria-current="${c.k === pick}" title="${esc(c.label + (c.sub ? ' ' + c.sub : '') + (c.its.length ? '\n' + names : '：没有要交的') + '\n点一下看这天')}" aria-label="${esc(c.label)} ${c.its.length} 件">
      <span class="wl">${c.label}</span><b>${c.its.length || ''}</b><span class="wdots">${c.its.slice(0, 6).map(x => `<i class="${esc(x.priority || '')}"></i>`).join('')}</span></div>`; }).join('')}</div>`;
}
const shortName = n => n.split(/[（(]/)[0].trim();
const bLink = p => `#b/${encodeURIComponent(p)}`;
const chk = (on, attrs, cls = '') => `<span class="chk ${on ? 'on' : ''} ${cls}" role="checkbox" aria-checked="${on}" tabindex="0" ${attrs}></span>`;
function bindChecks(root, fn) {
  root.querySelectorAll('.chk[data-k]').forEach(el => { if (!el.hasAttribute('aria-label')) { const t = el.closest('li')?.querySelector('.tx'); el.setAttribute('aria-label', '完成：' + ((t && (t.firstChild?.textContent || t.textContent)) || '').trim().slice(0, 60)); }
    const go = () => { fn(el); const on = !el.classList.contains('on'); el.classList.toggle('on', on); el.setAttribute('aria-checked', on); el.closest('.row')?.classList.toggle('done', on); }; el.onclick = go;
    el.onkeydown = e => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); go(); } }; });
}
function addRow(id, ph) {
  return `<button class="addbtn" type="button" data-open="${id}">＋ 添加</button>
    <form class="addrow" id="${id}" hidden><select aria-label="优先级"><option>P0</option><option selected>P1</option><option>P2</option></select>
    <input placeholder="${ph}" aria-label="内容"><input type="date" aria-label="截止"><button class="btn sm">保存</button></form>`;
}
function bindAdd(root, id, fn) {
  const f = root.querySelector('#' + id), b = root.querySelector(`[data-open="${id}"]`); if (!f) return;
  b.onclick = () => { f.hidden = false; b.hidden = true; f.querySelector('input').focus(); };
  const [sel, txt, date] = f.querySelectorAll('select,input');
  f.onsubmit = e => { e.preventDefault(); const t = txt.value.trim(); if (t) fn({ text: t, priority: sel.value, due: date.value }); };
  txt.onkeydown = e => { if (e.key === 'Escape') { f.hidden = true; b.hidden = false; } };
}
// 点到添加框外面（下拉菜单不算）就收起，写了一半的字留着，再点“添加”还在
document.addEventListener('pointerdown', e => { if (e.target.closest('.fmenu')) return;
  document.querySelectorAll('form.addrow:not([hidden])').forEach(f => { if (f.contains(e.target)) return; f.hidden = true; const b = document.querySelector(`[data-open="${f.id}"]`); if (b) b.hidden = false; }); }, true);

// ----- 今日建议：AI 每天按进度、目标和长期方向给几条，采纳就写进待办 / 待决策 -----
const SUG_KIND = { todo: '待办', decision: '待决策', idea: '以后再看' };
function sugHtml(sg, hasAi) {
  if (!hasAi && !sg) return '';
  const its = sg ? sg.items.map((x, i) => ({ ...x, i })).filter(x => x.state !== 'skipped') : [];
  return `<section class="sec sug" id="sugBox"><div class="sh"><h2>${lu('lightbulb')}今日建议</h2>${tip('AI 结合项目进度、目标和你的长期方向写一份。自动：每天第一次打开首页或待办时生成一次；手动：点了才生成，省 token。只对这台设备生效。看得到的资料和对话里一样，私密内容不发。<br>采纳后写进零散待办或待决策（“以后再看”的按 P3 放进零散待办），可以撤销。')}${hasAi ? `<span class="seg sugmode" title="今日建议怎么生成">${[['1', '自动'], ['', '手动']].map(([k, n]) => `<button type="button" data-sauto="${k}" class="${sugAuto() === !!k ? 'on' : ''}">${n}</button>`).join('')}</span>` : ''}${hasAi && sg ? `<button class="btn sm" id="sugRe">重新生成</button>` : ''}</div>
    ${!sg ? `<div class="sugempty"><p class="note" id="sugWait">AI 结合你的项目、目标和长期方向给几条建议。${sugAuto() ? '' : '点了才生成，省 token。'}</p><button class="btn primary" id="sugRe">生成今天的建议</button></div>` : `${sg.summary ? `<p class="sugsum">${esc(sg.summary)}</p>` : ''}
    <ul class="suglist">${its.map(x => `<li class="${x.state === 'adopted' ? 'on' : ''}"><span class="sk">${esc(x.area || SUG_KIND[x.kind])}</span>
      <div class="st"><b>${esc(x.title)}</b><small>${esc(x.why)}</small></div>
      ${x.state === 'adopted' ? `<span class="sdone">已加入${SUG_KIND[x.kind]}</span>` : `<button class="btn sm" data-sok="${x.i}" title="写进${SUG_KIND[x.kind]}">采纳</button><button class="btn sm" data-sno="${x.i}">不要</button>`}</li>`).join('') || '<li class="note">今天的建议都处理完了。</li>'}</ul>`}</section>`;
}
const sugAuto = () => pref('sugAuto', '') === '1';
const onceToday = k => { const d = today(); try { if (localStorage.getItem('twin.' + k) === d) return false; localStorage.setItem('twin.' + k, d); } catch (e) { /* 存不了就照常生成 */ } return true; };
function bindSug(root, sg, hasAi, redo) {
  const gen = async btn => { if (btn) { btn.textContent = '生成中…'; btn.disabled = true; } const w = $('#sugWait'); if (w) w.textContent = 'AI 正在想今天的建议…';
    try { const p = $('#prov'); await api('/api/suggest', { provider_id: p && p.value }); redo(); }
    catch (e) { const w2 = $('#sugWait'); if (w2) w2.textContent = '没生成出来：' + e.message; if (btn) { btn.textContent = '重新生成'; btn.disabled = false; } } };
  const re = root.querySelector('#sugRe'); if (re) re.onclick = () => gen(re);
  // 自动：一天只自动生成一次（首页小组件和待办页共用这个记号），生成失败也不反复重试
  root.querySelectorAll('[data-sauto]').forEach(b => b.onclick = () => { setPref('sugAuto', b.dataset.sauto); root.querySelectorAll('[data-sauto]').forEach(x => x.classList.toggle('on', x === b));
    toast(b.dataset.sauto ? '今日建议改成自动：每天第一次打开时生成' : '今日建议改成手动：点了才生成'); if (b.dataset.sauto && !sg && re && onceToday('sug')) gen(re); });
  if (!sg && hasAi && re && sugAuto() && onceToday('sug')) gen(re);
  const mark = async (i, adopt) => { try { await api('/api/suggest/mark', { date: sg.date, i, adopt }); redo(); } catch (e) { toast(e.message, 6000); } };
  root.querySelectorAll('[data-sok]').forEach(b => b.onclick = () => mark(+b.dataset.sok, true));
  root.querySelectorAll('[data-sno]').forEach(b => b.onclick = () => mark(+b.dataset.sno, false));
}
// 首页“今日建议”小组件点开的框；生成、采纳后就地刷新框和小组件
const sugNew = sg => (sg ? sg.items.filter(x => !x.state || x.state === 'new') : []);
function sugDlg(sg, box) { const hasAi = aiCfg.providers.length;
  const m = modal(`${sugHtml(sg, hasAi) || '<p class="note">接入 AI 后才有今日建议。</p>'}<div class="row"><button class="btn" id="mx">关闭</button></div>`);
  m.querySelector('#mx').onclick = closeModal;
  bindSug(m, sg, hasAi, async () => { const nsg = (await api('/api/home')).suggest; WIDGETS.sug.draw(box, nsg); sugDlg(nsg, box); }); }
// 图标：Lucide（ISC 开源协议，https://lucide.dev），只抄了用到的几个
const LU = {
  history: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
  pencil: '<path d="M21.2 6.8a2.8 2.8 0 0 0-4-4L3.8 16.2a2 2 0 0 0-.5.8l-1.3 4.4a.5.5 0 0 0 .6.6l4.4-1.3a2 2 0 0 0 .8-.5z"/><path d="m15 5 4 4"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><path d="M10 11v6M14 11v6"/>',
  lock: '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
  palette: '<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>',
  bot: '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
  puzzle: '<path d="M15.39 4.39a1 1 0 0 0 1.68-.474 2.5 2.5 0 1 1 3.014 3.015 1 1 0 0 0-.474 1.68l1.683 1.682a2.414 2.414 0 0 1 0 3.414L19.61 15.39a1 1 0 0 1-1.68-.474 2.5 2.5 0 1 0-3.014 3.015 1 1 0 0 1 .474 1.68l-1.683 1.682a2.414 2.414 0 0 1-3.414 0L8.61 19.61a1 1 0 0 0-1.68.474 2.5 2.5 0 1 1-3.014-3.015 1 1 0 0 0 .474-1.68l-1.683-1.682a2.414 2.414 0 0 1 0-3.414L4.39 8.61a1 1 0 0 1 1.68.474 2.5 2.5 0 1 0 3.014-3.015 1 1 0 0 1-.474-1.68l1.683-1.682a2.414 2.414 0 0 1 3.414 0z"/>',
  shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
  monitor: '<rect width="20" height="14" x="2" y="3" rx="2"/><path d="M8 21h8M12 17v4"/>',
  'moon-star': '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9"/><path d="M20 3v4"/><path d="M22 5h-4"/>',
  'panel-left-close': '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/><path d="m16 15-3-3 3-3"/>',
  'panel-left-open': '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/><path d="m14 9 3 3-3 3"/>',
  'chevron-down': '<path d="m6 9 6 6 6-6"/>', 'check': '<path d="M20 6 9 17l-5-5" />', 'copy': '<rect width="14" height="14" x="8" y="8" rx="2" ry="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />', 'wand': '<path d="m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.2 1.2 0 0 0 1.72 0L21.64 5.36a1.2 1.2 0 0 0 0-1.72" /><path d="m14 7 3 3" /><path d="M5 6v4" /><path d="M19 14v4" /><path d="M10 2v2" /><path d="M7 8H3" /><path d="M21 16h-4" /><path d="M11 3H9" />', 'link': '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />', 'type': '<polyline points="4 7 4 4 20 4 20 7" /><line x1="9" x2="15" y1="20" y2="20" /><line x1="12" x2="12" y1="4" y2="20" />',
  'play': '<polygon points="6 3 20 12 6 21 6 3"/>',
  'x': '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  'maximize-2': '<path d="M15 3h6v6"/><path d="m21 3-7 7"/><path d="m3 21 7-7"/><path d="M9 21H3v-6"/>',
  'minimize-2': '<path d="m14 10 7-7"/><path d="M20 10h-6V4"/><path d="m3 21 7-7"/><path d="M4 14h6v6"/>',
  'ellipsis': '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
  'message-square': '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  'panel-left': '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/>',
  'maximize': '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>',
  'newspaper': '<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  star: '<path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z"/>',
  'chevron-left': '<path d="m15 18-6-6 6-6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  cloud: '<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>',
  'cloud-sun': '<path d="M12 2v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="M20 12h2"/><path d="m19.07 4.93-1.41 1.41"/><path d="M15.947 12.65a4 4 0 0 0-5.925-4.128"/><path d="M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6Z"/>',
  'cloud-moon': '<path d="M10.188 8.5A6 6 0 0 1 16 4a1 1 0 0 0 6 6 6 6 0 0 1-3 5.197"/><path d="M13 16a3 3 0 1 1 0 6H7a5 5 0 1 1 4.9-6Z"/>',
  'cloud-rain': '<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M16 14v6"/><path d="M8 14v6"/><path d="M12 16v6"/>',
  'cloud-drizzle': '<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M8 19v1"/><path d="M8 14v1"/><path d="M16 19v1"/><path d="M16 14v1"/><path d="M12 21v1"/><path d="M12 16v1"/>',
  'cloud-lightning': '<path d="M6 16.326A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 .5 8.973"/><path d="m13 12-3 5h4l-3 5"/>',
  'cloud-snow': '<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M8 15h.01"/><path d="M8 19h.01"/><path d="M12 17h.01"/><path d="M12 21h.01"/><path d="M16 15h.01"/><path d="M16 19h.01"/>',
  'cloud-fog': '<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M16 17H7"/><path d="M17 21H9"/>',
  snowflake: '<line x1="2" x2="22" y1="12" y2="12"/><line x1="12" x2="12" y1="2" y2="22"/><path d="m20 16-4-4 4-4"/><path d="m4 8 4 4-4 4"/><path d="m16 4-4 4-4-4"/><path d="m8 20 4-4 4 4"/>',
  sunrise: '<path d="M12 2v8"/><path d="m4.93 10.93 1.41 1.41"/><path d="M2 18h2"/><path d="M20 18h2"/><path d="m19.07 10.93-1.41 1.41"/><path d="M22 22H2"/><path d="m8 6 4-4 4 4"/><path d="M16 18a4 4 0 0 0-8 0"/>',
  sunset: '<path d="M12 10V2"/><path d="m4.93 10.93 1.41 1.41"/><path d="M2 18h2"/><path d="M20 18h2"/><path d="m19.07 10.93-1.41 1.41"/><path d="M22 22H2"/><path d="m16 6-4 4-4-4"/><path d="M16 18a4 4 0 0 0-8 0"/>',
  utensils: '<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/><path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>',
  umbrella: '<path d="M22 12a10.06 10.06 1 0 0-20 0Z"/><path d="M12 12v8a2 2 0 0 0 4 0"/><path d="M12 2v1"/>',
  lightbulb: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
  'list-checks': '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>',
  'graduation-cap': '<path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>',
  'folder-kanban': '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/><path d="M8 10v4"/><path d="M12 10v2"/><path d="M16 10v6"/>',
};
const lu = (n, w = 16) => `<svg class="lu" width="${w}" height="${w}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${LU[n] || LU.cloud}</svg>`;
// 晚上把“晴 / 多云”换成月亮
const wxIcon = (n, h) => { const night = h != null && (h % 24 >= 19 || h % 24 < 6); return night && n === 'sun' ? 'moon' : night && n === 'cloud-sun' ? 'cloud-moon' : LU[n] ? n : 'cloud'; };
// 作息时段的图标：按开始时间猜
const blockIcon = b => { const m = mins(b.start); return /饭|餐/.test(b.name) ? 'utensils' : m < 12 * 60 && m >= 5 * 60 ? 'sunrise' : m < 18 * 60 && m >= 12 * 60 ? 'sun' : m < 23 * 60 && m >= 18 * 60 ? 'sunset' : 'moon'; };

// 作息条：今天页只放这一条细条 + 现在该做什么；天气在侧栏（ui.js），这里只在要带伞、加衣时出一个小提示
const left = m => m >= 60 ? `${Math.floor(m / 60)} 小时${m % 60 ? ` ${m % 60} 分` : ''}` : `${m} 分钟`;
const mins = s => { const [a, b] = String(s).split(':').map(Number); return a * 60 + (b || 0); };
// 先用上次的天气和作息马上画（同一帧内，不会先空一下），新数据回来再画一遍
async function drawDay() {
  if (drawDay.d) paintDay(drawDay.d);
  let d; try { d = await api('/api/weather'); } catch (e) { return; }
  drawDay.d = d; paintDay(d);
}
function paintDay(d) {
  const box = $('#dayband'); if (!box) return;
  const w = d.weather, bl = (d.rhythm || {}).blocks || [], nudges = (d.rhythm || {}).nudges || [];
  const t0 = bl.length ? mins(bl[0].start) : 0, norm = m => (m < t0 ? m + 1440 : m);
  const segs = bl.map(b => { const a = norm(mins(b.start)); let e = norm(mins(b.end)); if (e <= a) e += 1440; return { ...b, a, e }; });
  const d0 = new Date(), nowM = norm(d0.getHours() * 60 + d0.getMinutes()), cur = segs.find(x => nowM >= x.a && nowM < x.e);
  const span = segs.length ? segs.at(-1).e - segs[0].a : 1;
  const nudge = nudges.length ? nudges[(d0.getDate() * 24 + d0.getHours()) % nudges.length] : '';
  // 窄的时段（不到 1.5 小时）只放图标，名字在鼠标停留提示里
  box.innerHTML = segs.length ? `<div class="rhbar" role="img" aria-label="作息：${segs.map(x => `${x.start}-${x.end} ${x.name}`).join('，')}">${segs.map(x => `<i class="${x === cur ? 'on' : ''}" style="flex:${x.e - x.a}" title="${esc(x.start)}-${esc(x.end)} ${esc(x.name)}：${esc(x.what)}">${lu(blockIcon(x), 14)}${x.e - x.a >= 90 ? `<span>${esc(x.name)}</span>` : ''}</i>`).join('')}${cur ? `<b class="rhnow" style="left:${((nowM - segs[0].a) / span * 100).toFixed(1)}%"></b>` : ''}</div>
` : '';
  // 现在做什么、带伞加衣、休息提醒都做成标题下面那排小提示，样式统一
  const lt = w && (w.local_tips || [])[0], tp = $('#tbody .tips') || (() => { const x = document.createElement('div'); x.className = 'tips'; $('#tbody').prepend(x); return x; })();
  tp.querySelectorAll('.wxtip').forEach(x => x.remove());
  if (lt) { const a = document.createElement('button'); a.type = 'button'; a.className = 'tip wxtip'; a.innerHTML = `${lu(/伞/.test(lt) ? 'umbrella' : wxIcon(w.now.icon, d0.getHours()), 13)}${esc(lt.replace(/。$/, ''))}`;
    a.onclick = () => { location.hash = '#home'; }; tp.appendChild(a); }
  if (segs.length) tp.insertAdjacentHTML('afterbegin', `<span class="tip wxtip">${lu(cur ? blockIcon(cur) : 'moon', 13)}${cur ? `${esc(cur.what.replace(/^[^：:]{1,8}[：:]\s*/, ''))} · 剩 ${left(cur.e - nowM)}` : `作息外，明天 ${esc(segs[0].start)} 开始`}</span>`);
  if (nudge) tp.insertAdjacentHTML('beforeend', `<span class="tip wxtip">${lu('lightbulb', 13)}${esc(nudge.replace(/。$/, ''))}</span>`);
  tipsFold(tp);
}
// 标题下面那排小提示可以收起：红色的（要马上处理的）一直露着，其余收进“更多提示”，收没收记在本机
function tipsFold(tp) {
  if (!tp) return; tp.querySelector('.tgl')?.remove();
  const n = [...tp.children].filter(x => !x.classList.contains('red')).length;
  if (!tp.children.length) return tp.remove();
  const fold = pref('tipsFold', '1') === '1'; tp.classList.toggle('fold', fold); if (!n) return;
  const b = document.createElement('button'); b.type = 'button'; b.className = 'tip tgl'; b.setAttribute('aria-expanded', !fold);
  b.innerHTML = fold ? `${n} 条提示${lu('chevron-down', 13)}` : `收起${lu('chevron-down', 13)}`;
  b.onclick = () => { setPref('tipsFold', fold ? '0' : '1'); tipsFold(tp); }; tp.append(b);
}
