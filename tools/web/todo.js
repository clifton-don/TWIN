'use strict';
// 待办页：今天视图、项目视图、子任务
// 普通 <script>，和 app.js 共用全局变量和函数；index.html 里按 app → chat → day → home → todo → pages 的顺序加载

let bShowDone = false, dayPick = 0, subOpen = null, subBusy = false, subNote = null;  // subNote = "任务:子任务"，正在补说明的那一步
// 子任务：任务名下面一串小圆点，点一下实心 = 做完；全做完任务自动完成
function subsHtml(t, open, hoverAdd) {
  const ss = t.subs || [];
  if (!ss.length && !open && !(hoverAdd && t.status !== '✓ 已完成')) return '';
  return `<ul class="subs ${open ? 'open' : ''} ${ss.length ? '' : 'none'}">${ss.map((x, j) => `<li class="${x.done ? 'on' : ''}"><button type="button" class="dot" data-sub="${t.i}:${j}" role="checkbox" aria-checked="${x.done}" aria-label="${esc(x.text)}"></button><span ${x.done ? `data-subedit="${t.i}:${j}" title="点一下补一句说明"` : ''}><span class="st">${esc(x.text)}</span>${x.note ? `<small>${esc(x.note)}</small>` : ''}</span><button type="button" class="sx" data-subren="${t.i}:${j}" title="改这一步" aria-label="改子任务">${lu('pencil', 12)}</button><button type="button" class="sx" data-subx="${t.i}:${j}" title="删掉这一步" aria-label="删掉子任务">✕</button></li>${subNote === `${t.i}:${j}` ? subNoteHtml(t.i, j, x.note) : ''}`).join('')}
    ${t.status !== '✓ 已完成' ? `<li class="subadd"><span class="dot ghost"></span><input data-subadd="${t.i}" placeholder="加一步，回车保存" aria-label="加子任务"></li>` : ''}</ul>`;
}
// 做完一步：下面冒出一行“补一句”，回车存、Esc 跳过；做完的步骤点文字也能补/改。最后一步勾完 = 任务完成，弹完成记录
const subNoteHtml = (i, j, v) => `<li class="subnote"><input data-subnote="${i}:${j}" value="${esc(v || '')}" placeholder="补一句：怎么做的、遇到什么（回车保存，Esc 跳过）" aria-label="子任务说明"></li>`;
function bindSubs(root, tasks, act, after) {
  // 一次只存一个改动，并且等页面按新内容重画完才收下一个：不然两个改动都按旧的子任务列表算，后存的会把先存的冲掉
  const T = i => tasks.find(x => x.i === +i), save = async (t, subs) => { if (subBusy) return; subBusy = true;
    try { return await act({ type: 'set_subtasks', i: t.i, subs }); } finally { subBusy = false; } };
  root.querySelectorAll('[data-sub]').forEach(el => el.onclick = async () => { if (subBusy) return; const [i, j] = el.dataset.sub.split(':'), t = T(i), on = !t.subs[+j].done;
    const subs = t.subs.map((x, k) => k === +j ? { ...x, done: on } : x), all = on && subs.every(x => x.done);
    subNote = on && !all ? `${i}:${j}` : null;
    if (await save(t, subs) && all) reviewDlg(t.path, t, after); });
  const noteIn = inp => { const [i, j] = inp.dataset.subnote.split(':'), t = T(i), v0 = t.subs[+j].note || ''; let gone = false;
    const end = v => { if (gone) return; gone = true; subNote = null;
      if (v === undefined || v === v0) return inp.closest('li').remove();
      save(t, t.subs.map((x, k) => k === +j ? { ...x, note: v } : x)); };
    inp.onkeydown = e => { if (e.isComposing) return; if (e.key === 'Enter') end(inp.value.trim()); if (e.key === 'Escape') end(); };
    inp.onblur = () => end(inp.value.trim()); };
  root.querySelectorAll('[data-subnote]').forEach(noteIn);
  // 改一步：文字原地变成输入框，回车或点别处保存，Esc 不改
  root.querySelectorAll('[data-subren]').forEach(el => el.onclick = () => { const [i, j] = el.dataset.subren.split(':'), t = T(i), li = el.closest('li'), sp = li.querySelector('span');
    if (li.querySelector('.subren')) return;
    const inp = document.createElement('input'); inp.className = 'subren'; inp.value = t.subs[+j].text; inp.setAttribute('aria-label', '子任务');
    sp.hidden = true; sp.after(inp); inp.focus(); inp.select(); let gone = false;
    const end = ok => { if (gone) return; gone = true; const v = inp.value.trim();
      if (ok && v && v !== t.subs[+j].text) return save(t, t.subs.map((x, k) => k === +j ? { ...x, text: v } : x));
      inp.remove(); sp.hidden = false; };
    inp.onkeydown = e => { if (e.isComposing) return; if (e.key === 'Enter') end(true); if (e.key === 'Escape') end(false); };
    inp.onblur = () => end(true); });
  root.querySelectorAll('[data-subedit]').forEach(el => el.onclick = () => { const li = el.closest('li'), [i, j] = el.dataset.subedit.split(':');
    if (li.nextElementSibling?.classList.contains('subnote')) return;
    subNote = `${i}:${j}`; li.insertAdjacentHTML('afterend', subNoteHtml(i, j, T(i).subs[+j].note)); const inp = li.nextElementSibling.querySelector('input'); noteIn(inp); inp.focus(); });
  root.querySelectorAll('[data-subx]').forEach(el => el.onclick = () => { const [i, j] = el.dataset.subx.split(':'), t = T(i);
    save(t, t.subs.filter((x, k) => k !== +j)); });
  root.querySelectorAll('[data-subadd]').forEach(el => el.onkeydown = e => { if (e.key !== 'Enter' || e.isComposing || !el.value.trim()) return;
    const t = T(el.dataset.subadd); subOpen = t.i; save(t, [...t.subs, { text: el.value.trim(), done: false }]); });
  root.querySelectorAll('[data-split]').forEach(el => el.onclick = () => { subOpen = subOpen === +el.dataset.split ? null : +el.dataset.split;
    const li = el.closest('li.row'), t = T(el.dataset.split), tx = li.querySelector('.tx'), old = tx.querySelector('.subs'); if (old) old.remove();
    if (subOpen === t.i || t.subs.length) { tx.insertAdjacentHTML('beforeend', subsHtml(t, subOpen === t.i)); bindSubs(li, tasks, act, after); }
    const inp = li.querySelector('[data-subadd]'); if (inp && subOpen === t.i) inp.focus(); });
}
// 点到任务行外面：收起“加一步”输入行
document.addEventListener('pointerdown', e => { if (subOpen == null || e.target.closest('li.row')) return;
  subOpen = null; document.querySelectorAll('.subs.open').forEach(u => { u.classList.remove('open'); if (document.activeElement?.closest('.subs') === u) document.activeElement.blur(); }); }, true);
// ---------------- 待办：今天和各个项目是同一堆任务。顶上一排选看哪一份（今天 / 零散待办 / 某个项目），下面是同一种任务行 ----------------
const P4 = ['P0', 'P1', 'P2', 'P3'];
const subCount = t => (t.subs || []).length ? `<span class="subn" title="子任务完成 ${t.sub_done}/${t.subs.length}">${t.sub_done}/${t.subs.length}</span>` : '';
// 一行任务：勾选框的颜色就是优先级（红 P0、橙 P1、灰 P2）；右边只有截止，其他操作都在“⋯”里（右键整行也行）
// 进行中 = 动手了还没做完。拆了步骤的按子任务自动算（勾了一部分就是）；没拆的鼠标移上去点“进行中”。任务名加粗、后面一个小圆点
const DOING_ST = '进行中';
function taskRow(t, k) {
  const done = t.status === DONE_ST, doing = t.status === DOING_ST;
  return `<li class="row tk ${done ? 'done' : ''} ${doing ? 'doing' : ''}">${chk(done, `data-k data-t="${k}"`, done ? '' : esc(t.priority || ''))}
    <span class="tx">${esc(t.task)}${doing ? '<i class="dg" title="进行中"></i>' : ''}${t.subN ? `<span class="subn" title="子任务完成 ${t.subD}/${t.subN}">${t.subD}/${t.subN}</span>` : ''}${!done && t.pushes?.length >= 2 ? `<span class="push" title="截止一再往后推：\n${esc(t.pushes.map(p => `${p.on.slice(5)} 把 ${p.from.slice(5)} 改到 ${p.to.slice(5)}`).join('\n'))}">推迟 ${t.pushes.length} 次</span>` : ''}${t.note ? `<small>${esc(t.note)}</small>` : ''}${t.review ? `<small class="rv">${esc(t.review)}</small>` : ''}${Array.isArray(t.subs) ? subsHtml(t, subOpen === t.i, true) : ''}</span>
    ${done || t.subN ? '' : `<button type="button" class="tdo" data-doing data-t="${k}" aria-pressed="${doing}" title="${doing ? '取消进行中' : '标成进行中'}">进行中</button>`}
    ${done ? (t.done_on ? `<span class="due">${esc(t.done_on.slice(5))} 完成</span>` : '') : dueBtn(t, `data-t="${k}"`)}
    <button type="button" class="ib tkm" data-more data-t="${k}" title="更多" aria-label="更多">${lu('ellipsis', 16)}</button></li>`;
}
function bindTasks(root, T, boards, reload) {
  const act = async a => { try { await api('/api/action', { action: a }); reload(); return true; } catch (e) { toast(e.message, 6000); } };
  const at = el => T[+el.dataset.t], s = (t, type, x) => () => act({ type, path: t.path, i: t.i, ...x });
  bindChecks(root, async el => { const t = at(el), fin = t.status !== DONE_ST;
    if (await act({ type: 'set_task', path: t.path, i: t.i, status: fin ? DONE_ST : '未开始' }) && fin) reviewDlg(t.path, t, reload); });
  bindDue(root, (el, due) => s(at(el), 'set_task_due', { due })());
  root.querySelectorAll('[data-doing]').forEach(el => el.onclick = () => { const t = at(el); s(t, 'set_task', { status: t.status === DOING_ST ? '未开始' : DOING_ST })(); });
  // 今天页拿不到备注，就只改名字，不动备注
  const edit = t => { const hasN = t.note !== undefined, m = dlg('改任务', '', `<div class="hafl"><label class="haf"><span>任务</span><span class="hain"><input id="tkT" value="${esc(t.task)}"></span></label>
      ${hasN ? `<label class="haf"><span>备注</span><span class="hain"><input id="tkN" value="${esc(t.note)}" placeholder="可以空着"></span></label>` : ''}</div>`,
      `<button class="btn ghost" data-x2>取消</button><button class="btn primary" id="mok">保存</button>`, 'hdsmall'), T0 = m.querySelector('#tkT');
    const save = () => { if (!T0.value.trim()) return toast('任务名不能空'); closeModal(); s(t, 'edit_task', { text: T0.value.trim(), ...(hasN ? { note: m.querySelector('#tkN').value.trim() } : {}) })(); };
    m.querySelector('[data-x2]').onclick = closeModal; m.querySelector('#mok').onclick = save;
    m.querySelectorAll('input').forEach(x => x.onkeydown = e => { if (e.key === 'Enter' && !e.isComposing) save(); }); T0.focus(); T0.select(); };
  const menu = (e, t) => { const done = t.status === DONE_ST, to = boards.filter(b => b.path !== t.path);
    // 改回没做完点勾，加步骤在任务下面（鼠标移上去出现），菜单里不再重复
    popMenu(e, [...(done ? [[t.review ? '改完成记录' : '写完成记录', () => reviewDlg(t.path, t, reload)]]
        : [['优先级…', () => popMenu(e, P4.map(p => [p + (p === t.priority ? ' ✓' : ''), s(t, 'set_task_priority', { priority: p })]))],
          // 手机上没有“鼠标移上去”，加步骤还留在菜单里
          ...(Array.isArray(t.subs) && matchMedia('(hover: none)').matches ? [['加步骤', () => { subOpen = t.i; reload(); }]] : [])]),
      ['改名和备注', () => edit(t)],
      ...(to.length ? [['移到…', () => popMenu(e, to.map(b => [esc(b.loose ? '零散待办' : shortName(b.name)), s(t, 'move_task', { to: b.path })]))]] : []),
      ['删除', () => { if (confirm(`删掉任务“${t.task}”？可以在改动历史里撤销。`)) s(t, 'del_task')(); }]]); };
  root.querySelectorAll('[data-more]').forEach(el => { const t = at(el); el.onclick = e => menu(e, t);
    el.closest('.row').oncontextmenu = e => { if (!e.target.closest('input')) menu(e, t); }; });
}
async function viewTodo(path) {
  const ok = fresh(); await loadAi().catch(() => {}); if (!ok()) return;
  if (viewTodo.p !== path) { subOpen = null; dayPick = 0; viewTodo.p = path; }  // 换了页面再回来，默认还是看今天
  if (!$('#tdnav')) $('#view').innerHTML = `<div class="wrap page"><nav class="tdnav" id="tdnav" aria-label="待办"></nav><div id="tdmain"></div></div>`;
  let h, b; try { [h, b] = await Promise.all([api('/api/home'), path ? api('/api/board?path=' + encodeURIComponent(path)) : null]); }
  catch (e) { if (ok()) { toast(e.message); if (path) location.hash = 'today'; } return; }
  if (!ok() || !$('#tdnav')) return;
  inboxBadge(h.inbox);
  const boards = h.boards || [], next = h.next || {}, all = boards.flatMap(x => next[x.path] || []), reload = () => viewTodo(path);
  const nav = (href, on, label, n, dot) => `<a href="${href}" class="${on ? 'on' : ''}">${dot != null ? `<i class="pdot ${esc(dot)}"></i>` : ''}<span>${esc(label)}</span>${n ? `<em>${n}</em>` : ''}</a>`;
  const ended = (h.inactive || []).filter(x => x.status === 'done'), old = (h.inactive || []).filter(x => x.status !== 'done'), cur = ended.find(x => x.path === path);
  $('#tdnav').innerHTML = nav('#today', !path, '今天', all.filter(isNow).length)
    + boards.map(x => nav(bLink(x.path), x.path === path, x.loose ? '零散待办' : shortName(x.name), x.total - x.done, x.loose ? '' : x.priority || '')).join('')
    + (old.length ? `<button type="button" class="${old.some(x => x.path === path) ? 'on' : ''}" id="tdOld" title="暂停、放弃、归档的项目">${esc(old.find(x => x.path === path) ? shortName(old.find(x => x.path === path).name) : `其他 ${old.length}`)} ▾</button>` : '')
    + (ended.length ? `<button type="button" class="${cur ? 'on' : ''}" id="tdEnd" title="标成已完成的项目">${cur ? esc(shortName(cur.name)) : `已结项 ${ended.length}`}</button>` : '')
    + `<button type="button" id="tdLib" title="所有项目，包括做完的">项目库</button><button type="button" id="tdNew" title="新建项目" aria-label="新建项目">${lu('plus', 14)}</button>`;
  $('#tdLib').onclick = projLib;
  if (ended.length) $('#tdEnd').onclick = () => endedDlg(ended);
  $('#tdNew').onclick = newProject;
  if (old.length) $('#tdOld').onclick = e => popMenu(e, old.map(x => [`${esc(shortName(x.name))} · ${esc(PSTATUS[x.status] || x.status)}`, () => { location.hash = bLink(x.path); }]));
  const main = $('#tdmain');
  if (!path) {
    setTitle('今天');
    const d = new Date(), hasAi = aiCfg.providers.length, u = h.upgrade, hl = h.health || {}, w = h.weekly;
    // 今天要做：过期、今天到期的（加上标了 P0 的零散待办）；一件都没有就列最近要交的 3 件
    // 日期条上点了别的天：只看那天要交的（过期 = 所有过期的）
    if (dayPick === -1 && !all.some(x => x.days < 0)) dayPick = 0;
    const dl = dayLabel(dayPick);
    let picked = dayPick === 0 ? all.filter(isNow) : all.filter(x => x.days != null && (dayPick === -1 ? x.days < 0 : x.days === dayPick)), soon = false;
    if (dayPick === 0 && !picked.length) { soon = true; picked = all.filter(x => x.days != null).sort((a, c) => a.days - c.days).slice(0, 3); }
    const T = picked.map(x => ({ path: x.path, i: x.i, task: x.text, priority: x.priority, due: x.due, days: x.days, status: x.doing ? DOING_ST : '未开始', subN: x.subs, subD: x.sub_done }));
    // 只在有事要处理时才出提示
    const tips = [hl.red || hl.amber ? `<a class="tip ${hl.red ? 'red' : 'amber'}" href="#health">体检：${[hl.red && `${hl.red} 个要马上处理`, hl.amber && `${hl.amber} 个要留意`].filter(Boolean).join('，')}</a>` : '',
      h.inbox ? `<a class="tip" href="#inbox">暂存箱 ${h.inbox} 件没归档</a>` : '',
      ...(h.expiring || []).map(x => `<a class="tip ${x.days < 0 ? 'red' : x.days <= 7 ? 'amber' : ''}" href="#assets/${esc(x.path)}">${esc(x.name)} ${x.days < 0 ? `已过期 ${-x.days} 天` : x.days === 0 ? '今天到期' : `还剩 ${x.days} 天到期`}</a>`),
      w && h.weekly_new ? `<a class="tip new" href="${libLink(w.path)}">新周报：${esc(w.title.replace(/^周报\s*/, ''))}</a>` : ''].filter(Boolean);
    fillIn(main, `<div class="dayhead"><h1>${dayPick > 0 ? dl.label : '今天'}</h1><span class="sub">${(x => `${x.getMonth() + 1} 月 ${x.getDate()} 日 · 星期${'日一二三四五六'[x.getDay()]}`)(dayPick > 0 ? new Date(dl.iso + 'T00:00') : d)}</span></div><div id="tbody">
      ${tips.length ? `<div class="tips">${tips.join('')}</div>` : ''}<div id="dayband" class="rh"></div>${weekStrip(all, dayPick)}
      ${dayPick ? `<div class="gl daypick">${dayPick === -1 ? '过期没做完的' : `${dl.label} ${dl.sub} 要交的`} ${T.length} 件<button type="button" class="linkbtn" id="dayBack">回到今天</button></div>` : soon && T.length ? '<div class="gl">今天没有到期的，最近要交的是这几件</div>' : ''}
      ${T.length ? `<div class="tgrid">${boards.map(x => [x, T.filter(t => t.path === x.path)]).filter(g => g[1].length).map(([x, ts]) => `<div class="tgrp"><a class="tgh" href="${bLink(x.path)}">${esc(x.loose ? '零散待办' : shortName(x.name))}</a>
        <ul class="list tdl">${ts.map(t => taskRow(t, T.indexOf(t))).join('')}</ul></div>`).join('')}</div>` : `<p class="note">${dayPick ? '这天没有要交的。' : '今天没有要做的事。'}</p>`}
      ${addRow('addTodo', '加一条零散待办，回车保存')}
      <div class="more">${h.decisions.length ? `<details><summary>待决策 ${h.decisions.length}</summary><ul class="list">${h.decisions.map(x => `<li class="row dec"><span class="tx clamp" title="${esc(x.text)}">${esc(x.text)}</span><button class="btn sm" data-ask="${esc(x.text)}">问 AI</button><button class="btn sm" data-dec="${esc(x.text)}">定了</button><button class="btn sm" data-decdel="${esc(x.text)}">删掉</button></li>`).join('')}</ul></details>` : ''}
        ${h.brief ? `<details class="briefbox"><summary>今日简报</summary><div class="md brief">${render(h.brief, true)}</div></details>` : ''}</div>
      ${hasAi ? `<div class="factions">${w && !w.has_ai ? '<button class="btn sm" id="wkBtn">让 AI 点评上周</button>' : ''}<button class="btn sm" id="briefBtn">${h.brief ? '重新生成简报' : '生成今日简报'}</button><button class="btn sm" id="upBtn" title="复盘升级：上次${u.last || '还没有'}">开始复盘升级</button></div>` : ''}
      <p class="foot"><a href="${libLink('00_Crown/Goals.md')}">长期目标</a> · <a href="#history">改动历史</a>${w && !h.weekly_new ? ` · <a href="${libLink(w.path)}">上周周报</a>` : ''} · 复盘升级：上次${u.last || '还没有'}${hasAi ? '' : ' · <a href="#settings">接入 AI 后可生成简报</a>'}</p></div>`);
    const act = async a => { try { await api('/api/action', { action: a }); reload(); } catch (e) { toast(e.message, 6000); } };
    bindTasks(main, T, boards, reload);
    bindAdd(main, 'addTodo', a => act({ type: 'add_todo', ...a }));
    // 看的是以后某天：新加的待办截止默认就填那天
    const ad = main.querySelector('#addTodo input[type=date]'); if (ad && dayPick > 0) ad.value = dl.iso;
    const pickDay = k => { dayPick = k; reload(); };
    main.querySelectorAll('[data-wd]').forEach(el => { el.onclick = () => pickDay(+el.dataset.wd); el.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pickDay(+el.dataset.wd); } }; });
    const db = $('#dayBack'); if (db) db.onclick = () => pickDay(0);
    main.querySelectorAll('[data-ask]').forEach(x => x.onclick = () => { pendingAsk = `帮我想想这个决定：${x.dataset.ask}`; location.hash = 'c'; });
    // 待决策：定了 → 写一句结论，记进近期事件；删掉 → 直接移走
    main.querySelectorAll('[data-dec]').forEach(x => x.onclick = () => { const m = modal(`<h3>这件事定了</h3><p class="note">${esc(x.dataset.dec)}</p>
        <div class="field"><label>怎么定的</label><input id="decr" placeholder="比如：这学期先不投第二篇，专心毕业设计"></div><p class="note">会从待决策里移走，记进决策端的“近期事件”。</p>
        <div class="row"><button class="btn" id="mx">取消</button><button class="btn primary" id="mok">记下</button></div>`);
      m.querySelector('#mx').onclick = closeModal; m.querySelector('#decr').focus();
      m.querySelector('#mok').onclick = () => { const r = m.querySelector('#decr').value.trim(); if (!r) return m.querySelector('#decr').focus(); closeModal(); act({ type: 'decision_close', match: x.dataset.dec, exact: 1, result: r }); }; });
    main.querySelectorAll('[data-decdel]').forEach(x => x.onclick = () => act({ type: 'decision_close', match: x.dataset.decdel, exact: 1 }));
    tipsFold($('#tbody .tips')); drawDay();
    const bb = $('#briefBtn'); if (bb) bb.onclick = async () => { bb.textContent = '生成中…'; bb.disabled = true; try { await api('/api/brief', {}); reload(); } catch (e) { toast(e.message, 7000); bb.textContent = '生成今日简报'; bb.disabled = false; } };
    const ub = $('#upBtn'); if (ub) ub.onclick = upgradeFlow;
    const wb = $('#wkBtn'); if (wb) wb.onclick = async () => { wb.textContent = 'AI 正在写…'; wb.disabled = true;
      try { const j = await api('/api/weekly', { ai: true }); location.hash = 'lib/' + encodeURIComponent(j.path); } catch (e) { toast(e.message, 7000); wb.textContent = '让 AI 点评上周'; wb.disabled = false; } };
    return;
  }
  // 一个项目（或零散待办）：标题 + 一行信息，下面是任务；项目级的设置都在标题右边的“⋯”里
  const L = b.loose, name = L ? '零散待办' : shortName(b.name), act = async a => { try { await api('/api/action', { action: { ...a, path: b.path } }); await reload(); return true; } catch (e) { toast(e.message, 6000); } };
  setTitle(name);
  const T = b.tasks.map(t => ({ ...t, path: b.path, subN: t.subs.length, subD: t.sub_done })), open = T.filter(t => t.status !== DONE_ST), done = T.filter(t => t.status === DONE_ST)
    .sort((x, y) => (y.done_on || '').localeCompare(x.done_on || '') || y.i - x.i);  // 已完成：最近做完的在上面，没记日期的老任务排最后
  const row = t => taskRow(t, T.indexOf(t));
  fillIn(main, `<div class="dayhead"><h1 id="pName" class="${L ? '' : 'ren'}" title="${esc(L ? '' : '点一下改名')}">${esc(name)}</h1><span class="sp"></span><button type="button" class="ib" id="pMore" title="项目设置" aria-label="项目设置">${lu('ellipsis', 18)}</button></div>
    <p class="pmeta">${L ? '不属于任何项目的小事' : `${pri(b.priority)}${b.status && b.status !== 'active' ? `<span>${esc(PSTATUS[b.status] || b.status)}</span>` : ''}<span>截止 ${dueBtn({ due: b.due, days: b.days }, 'data-board')}</span><span>${b.done}/${b.total} 完成</span>
      ${(b.links || []).map(l => `<a href="${esc(l.url)}" target="_blank" rel="noopener" title="${esc(l.url)}">${esc(l.name)}</a>`).join('')}`}</p>
    ${!L && b.total && b.done === b.total && (b.status || 'active') === 'active' ? `<p class="note">任务都做完了，项目结束了吗？<button type="button" class="btn sm" id="pDone">标成已完成</button></p>` : ''}
    ${open.length ? `<ul class="list tdl">${open.map(row).join('')}</ul>` : ''}
    ${b.has_table ? addRow('addTask', L ? '加一条零散待办，回车保存' : '加一个任务，回车保存') : '<p class="note">这个文件还没有任务表。</p>'}
    ${done.length ? `<div class="tgd"><button class="linkbtn" id="tgDone">${bShowDone ? '收起已完成' : `已完成 ${done.length}`}</button></div>${bShowDone ? `<ul class="list tdl">${done.map(row).join('')}</ul>` : ''}` : ''}
    ${L ? '' : timelineBox(b.path)}`);
  bindTimeline(main);
  bindTasks(main, T, boards, reload);
  bindAdd(main, 'addTask', a => act({ type: 'add_task', ...a }));
  bindSubs(main, T, act, reload);
  if (subNote) main.querySelector(`[data-subnote="${subNote}"]`)?.focus();
  else if (subOpen != null) main.querySelector(`[data-subadd="${subOpen}"]`)?.focus();
  if (!L) bindDue(main.querySelector(".pmeta"), (el, due) => act({ type: "set_board_due", due }));
  const ren = () => renameProject(b, reload); if (!L) $('#pName').onclick = ren;
  const tg = $('#tgDone'); if (tg) tg.onclick = () => { bShowDone = !bShowDone; reload(); };
  // 不自动关项目：任务做完不等于项目结束（可能还要加任务），只给一个一键关闭
  const pd = $('#pDone'); if (pd) pd.onclick = () => act({ type: 'set_board_status', status: 'done' });
  $('#pMore').onclick = e => popMenu(e, [...(L ? [] : [
    ['改名', ren],
    ['优先级…', () => popMenu(e, P4.map(p => [p + (p === b.priority ? ' ✓' : ''), () => act({ type: 'set_board_priority', priority: p })]))],
    ['状态…', () => popMenu(e, Object.entries(PSTATUS).map(([k, l]) => [l + (k === (b.status || 'active') ? ' ✓' : ''), () => act({ type: 'set_board_status', status: k })]))],
    ['加链接', () => addLink(b, reload)],
    ...((b.links || []).length ? [['删链接…', () => popMenu(e, b.links.map(l => [esc(l.name), () => { if (confirm(`删掉链接“${l.name}”？可以在改动历史里撤销。`)) act({ type: 'del_board_link', url: l.url }); }]))]] : []),
    ['和 AI 聊这个项目', async () => { const c = (await api('/api/chats').catch(() => [])).find(c => c.project === b.path || (!c.project && c.auto === b.path));
      if (c) location.hash = 'c/' + c.id; else { pendingProj = b.path; location.hash = 'c'; } }],
    ['删除项目…', () => delProj(b)]]),
    ['打开文件', () => { location.hash = libLink(b.path); }]]);
}
// 项目库：03_Projects 下所有项目（有 index.md 或 board.md 的文件夹），按分类排，可以搜；有板块的点开是待办，没有的点开是说明
async function projLib() { let ps; try { ps = await api('/api/projects'); } catch (e) { return toast(e.message); }
  const m = dlg(`项目库 · ${ps.length} 个`, '有任务板块的点开是待办，做完的点开是项目说明。', `<div class="hain">${lu('search', 15)}<input id="plQ" placeholder="搜项目名、主控、传感器…"></div><div id="plL" class="plib"></div>`, '', 'hdwide');
  const draw = q => { const hit = ps.filter(p => !q || (p.group + p.name).toLowerCase().includes(q)), gs = [...new Set(hit.map(p => p.group))];
    m.querySelector('#plL').innerHTML = gs.map(g => `<div class="lbl">${esc(g || '项目')}</div>${hit.filter(p => p.group === g).map(p => `<div class="plrow"><a href="${p.board ? bLink(p.path) : libLink(p.path)}">${esc(p.name.replace(/_/g, ' '))}${p.board ? '<em>板块</em>' : ''}</a><button type="button" class="ib pldel" data-del="${esc(p.path)}" data-tip="删除这个项目" aria-label="删除 ${esc(p.name)}">${lu('trash', 15)}</button></div>`).join('')}`).join('') || '<p class="note">没找到。</p>';
    m.querySelectorAll('#plL a').forEach(a => a.onclick = closeModal);
    // 删除：这一行就地变成确认，不另开弹窗
    m.querySelectorAll('[data-del]').forEach(b => b.onclick = () => { const p = ps.find(x => x.path === b.dataset.del), row = b.closest('.plrow');
      row.classList.add('ask'); row.innerHTML = `<span><b>删除“${esc(p.name.replace(/_/g, ' '))}”？</b><small>整个文件夹（说明、板块、代码）挪到 <code>.trash/项目/</code>，不会真删，想恢复就拖回 03_Projects。</small></span>
        <button type="button" class="btn sm" data-no>取消</button><button type="button" class="btn sm danger" data-yes>删除</button>`;
      row.querySelector('[data-no]').onclick = () => draw(q);
      row.querySelector('[data-yes]').onclick = async () => { try { toast((await api('/api/project/delete', { path: p.path })).message, 7000); } catch (e) { return toast(e.message, 6000); }
        ps = ps.filter(x => x !== p); m.querySelector('h3').textContent = `项目库 · ${ps.length} 个`; draw(q); afterDel(p.path); }; }); };
  const q = m.querySelector('#plQ'); q.oninput = () => draw(q.value.trim().toLowerCase()); q.focus(); draw(''); }
// 已结项：做完的项目单独收在这里，按结项日期倒序、按年分组
function endedDlg(list) {
  const ps = list.slice().sort((a, b) => (b.ended || '').localeCompare(a.ended || '')), ys = [...new Set(ps.map(p => (p.ended || '').slice(0, 4)))];
  const m = dlg(`已结项 · ${ps.length} 个`, '标成已完成的项目都收在这里，点开还能看任务、记录和链接。想重新做，在项目页右上角“⋯”里改状态。',
    `<div class="plib">${ys.map(y => `<div class="lbl">${y ? y + ' 年' : '没记日期'}</div>${ps.filter(p => (p.ended || '').slice(0, 4) === y).map(p => `<div class="plrow"><a href="${bLink(p.path)}">${esc(shortName(p.name))}<span class="sp"></span><small>${p.ended ? esc(p.ended.slice(5)) + ' 结项 · ' : ''}${p.done}/${p.total} 项</small></a></div>`).join('')}`).join('')}</div>`, '', 'hdwide');
  m.querySelectorAll('a').forEach(a => a.onclick = closeModal);
}
// 删完项目：正开着这个项目就回到“今天”，否则刷新待办页的项目标签
const afterDel = path => { if (location.hash === bLink(path)) location.hash = 'today'; else if (/^#(today|b\/)/.test(location.hash)) route(); };
// 项目页“更多”里的删除：确认后删
function delProj(b) { const m = dlg(`删除“${esc(shortName(b.name))}”？`, '', `<p class="note" style="margin:0">整个项目文件夹（说明、板块、代码）会挪到 <code>.trash/项目/</code>，不会真删。想恢复就把文件夹拖回 <code>03_Projects</code>。</p>`,
    '<span style="flex:1"></span><button class="btn" data-no>取消</button><button class="btn danger" data-yes>删除项目</button>');
  m.querySelector('[data-no]').onclick = closeModal;
  m.querySelector('[data-yes]').onclick = async () => { try { toast((await api('/api/project/delete', { path: b.path })).message, 7000); closeModal(); afterDel(b.path); } catch (e) { toast(e.message, 6000); } }; }
// 项目链接：在线进度表、仓库、提交地址……点一下在新标签页打开
// 项目改名：大标题原地变成输入框，回车或点别处保存，Esc 不改
function renameProject(b, after) {
  const h = $('#pName'); if (!h || h.querySelector('input')) return;
  const old = b.name; h.innerHTML = `<input class="pren" value="${esc(old)}" aria-label="项目名">`; const i = h.querySelector('input'); i.focus(); i.select();
  let done = false; const fin = async keep => { if (done) return; done = true; const v = i.value.trim();
    if (keep || !v || v === old) return after();
    try { await api('/api/action', { action: { type: 'set_board_name', path: b.path, name: v } }); toast('改好了'); } catch (e) { toast(e.message, 6000); } after(); };
  i.onkeydown = e => { if (e.key === 'Enter' && !e.isComposing) fin(); else if (e.key === 'Escape') fin(true); }; i.onblur = () => fin();
}
// 新建项目：自己填名字、放哪、截止、优先级就建好；想让 AI 帮忙拆任务再点“让 AI 帮我填”
async function newProject() {
  const ps = await api('/api/project/parents').catch(() => ['03_Projects']);
  const m = dlg('新建项目', '', `<div class="field"><label>项目名</label><input id="npN" placeholder="比如 智能台灯"></div>
    <div class="field"><label>放在哪</label><select id="npP">${ps.map(p => `<option value="${esc(p)}">${esc(p.replace(/^03_Projects\/?/, '') || '项目（不分类）')}</option>`).join('')}</select></div>
    <div class="npr"><div class="field"><label>最终截止（可以不填）</label><input id="npD" type="date"></div>
    <div class="field"><label>优先级</label><select id="npR">${P4.map(p => `<option${p === 'P2' ? ' selected' : ''}>${p}</option>`).join('')}</select></div></div>`,
    `<button type="button" class="btn" id="npAi">让 AI 帮我填</button><span class="sp"></span><button type="button" class="btn" data-x2>取消</button><button type="button" class="btn primary" id="npOk">建好</button>`);
  const n = m.querySelector('#npN'); n.focus();
  m.querySelector('[data-x2]').onclick = closeModal;
  m.querySelector('#npAi').onclick = () => { closeModal(); pendingAsk = '帮我新建一个项目：' + n.value.trim(); location.hash = 'c'; };
  const ok = async () => { const name = n.value.trim(); if (!name) return n.focus();
    try { const j = await api('/api/action', { action: { type: 'project_create', name, parent: m.querySelector('#npP').value, due: m.querySelector('#npD').value, priority: m.querySelector('#npR').value } });
      closeModal(); const rel = (j.message || '').split('：').pop(); location.hash = rel.endsWith('.md') ? bLink(rel) : 'today'; } catch (e) { toast(e.message, 6000); } };
  m.querySelector('#npOk').onclick = ok; n.onkeydown = e => { if (e.key === 'Enter' && !e.isComposing) ok(); };
}
function addLink(b, after) {
  const m = modal(`<h3>给“${esc(shortName(b.name))}”加一个链接</h3><p class="note">比如在线进度表、代码仓库、网盘、提交地址。存在 board.md 的“链接”一节里，同一个地址再加一次就是改名字。</p>
    <div class="field"><label>名字</label><input id="ln" placeholder="在线进度表"></div><div class="field"><label>地址</label><input id="lu" placeholder="https://…" inputmode="url"></div>
    <div class="row"><button class="btn" id="mx">取消</button><button class="btn primary" id="mok">保存</button></div>`);
  const u = m.querySelector('#lu'), n = m.querySelector('#ln'); n.focus();
  m.querySelector('#mx').onclick = closeModal;
  const save = async () => { if (!/^https?:\/\//.test(u.value.trim())) { toast('地址要以 http:// 或 https:// 开头'); return u.focus(); }
    try { await api('/api/action', { action: { type: 'set_board_link', path: b.path, name: n.value || '链接', url: u.value.trim() } }); closeModal(); after(); } catch (e) { toast(e.message, 6000); } };
  m.querySelector('#mok').onclick = save; [n, u].forEach(x => x.onkeydown = e => { if (e.key === 'Enter' && !e.isComposing) save(); });
}
// 完成记录：打勾后问一句做得怎么样，可以跳过；存在任务表的“完成记录”列
function reviewDlg(path, t, after) {
  const m = dlg(t.review ? '改完成记录' : '做完了，记一句？', '', `<p class="note">${esc(t.task || t.text)}</p><textarea id="rvT" rows="3" placeholder="比如：比预想顺利，花了一小时；下次先备好料">${esc(t.review || '')}</textarea>`,
    `<button class="btn ghost" data-x2>${t.review ? '取消' : '跳过'}</button><button class="btn primary" id="mok">保存</button>`, 'hdsmall'), T = m.querySelector('#rvT');
  const save = async () => { const v = T.value.trim(); if (!v && !t.review) return closeModal(); closeModal();
    try { toast((await api('/api/action', { action: { type: 'task_review', path, i: t.i, text: v } })).message); after && after(); } catch (e) { toast(e.message, 6000); } };
  m.querySelector('[data-x2]').onclick = closeModal; m.querySelector('#mok').onclick = save;
  T.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); save(); } }; T.focus();
}

async function upgradeFlow() {
  let text; try { text = (await api('/api/upgrade/preview', {})).text; } catch (e) { return toast(e.message, 7000); }
  const m = modal(`<h3>复盘升级 · 先看要发给 AI 的内容</h3><p class="note">下面就是全部要发出的内容：你的反馈、回看结果和可调的打分规则。不含金额、项目细节和私密段落。</p>
    <pre class="pv">${esc(text)}</pre><div class="row"><button class="btn" id="mx">取消</button><button class="btn primary" id="mgo">发给 AI</button></div>`);
  m.querySelector('#mx').onclick = closeModal;
  m.querySelector('#mgo').onclick = async () => { m.classList.add('busy'); m.querySelector('#mgo').textContent = 'AI 正在复盘…'; let r;
    try { r = await api('/api/upgrade/run', {}); } catch (e) { m.classList.remove('busy'); m.querySelector('#mgo').textContent = '发给 AI'; return toast(e.message, 7000); }
    const L = r.lessons || [], C = r.rule_changes || [], R = r.remove_lessons || [];
    const mm = modal(`<h3>勾选你同意的</h3><p>${esc(r.summary || '')}</p>
      ${L.length ? '<div class="lbl">新增经验教训</div>' + L.map((l, i) => `<label class="opt"><input type="checkbox" data-l="${i}" checked><span>${esc(l.text)}<small>${esc(l.reason || '')}</small></span></label>`).join('') : ''}
      ${C.length ? '<div class="lbl">调整打分规则</div>' + C.map((c, i) => `<label class="opt"><input type="checkbox" data-c="${i}"><span><code>${esc(c.key)}</code> ${esc(c.from)} → <b>${esc(c.to)}</b><small>${esc(c.reason || '')}</small></span></label>`).join('') : ''}
      ${R.length ? '<div class="lbl">删掉旧经验</div>' + R.map((x, i) => `<label class="opt"><input type="checkbox" data-r="${i}"><span>${esc(x)}</span></label>`).join('') : ''}
      ${!L.length && !C.length && !R.length ? '<p class="note">AI 认为证据还不够，这次没有建议。多用几天、多回看几个决定再来。</p>' : ''}
      <div class="row"><button class="btn" id="mx2">关闭</button>${L.length || C.length || R.length ? '<button class="btn primary" id="mok">应用选中的</button>' : ''}</div>`);
    mm.querySelector('#mx2').onclick = closeModal;
    const ok = mm.querySelector('#mok'); if (ok) ok.onclick = async () => { const pick = k => [...mm.querySelectorAll(`[data-${k}]`)].filter(x => x.checked).map(x => +x.dataset[k]);
      try { const j = await api('/api/upgrade/apply', { lessons: pick('l').map(i => L[i].text), changes: pick('c').map(i => C[i]), removes: pick('r').map(i => R[i]), summary: r.summary || '' });
        closeModal(); toast(`已升级：新增 ${j.lessons} 条经验${j.rules.length ? '，规则：' + j.rules.join('、') : ''}`, 6000); viewTodo(null); } catch (e) { toast(e.message, 7000); } }; };
}

// ---------------- 项目时间线：不用手写，从项目文件夹的文件修改时间和 git 记录整理出来；只在本机算，不发给 AI ----------------
function timelineBox(path) {
  return `<details class="tline" data-tl="${esc(path)}" ${pref('tlOpen', '') === '1' ? 'open' : ''}><summary>${lu('history', 15)}<b>项目时间线</b><small>从文件和 git 记录自动整理 · 只在本机</small></summary><div class="tlb note">展开后整理…</div></details>`;
}
function bindTimeline(root) {
  root.querySelectorAll('details.tline').forEach(d => {
    const load = async fresh => { const b = d.querySelector('.tlb'); b.className = 'tlb note'; b.textContent = '整理中…';
      try { drawTimeline(b, await api('/api/project/timeline?path=' + encodeURIComponent(d.dataset.tl) + (fresh ? '&fresh=1' : '')), () => load(true)); }
      catch (e) { b.textContent = e.message; } };
    d.ontoggle = () => { setPref('tlOpen', d.open ? '1' : ''); if (d.open && !d.dataset.loaded) { d.dataset.loaded = '1'; load(); } };
    if (d.open) { d.dataset.loaded = '1'; load(); } });
}
function drawTimeline(el, t, refresh) {
  if (!t.files && !t.commits) { el.textContent = '这个项目文件夹里还没有别的文件（代码、图纸、文档放进来就会自动整理）。'; return; }
  const max = Math.max(1, ...t.months.map(m => m.files));
  const kinds = m => m.files ? `${m.files} 个文件改过${m.kinds.length ? '：' + m.kinds.map(([k, n]) => `${esc(k)} ${n}`).join('、') : ''}` : '没有文件改动';
  el.className = 'tlb';
  el.innerHTML = `<p class="tlsum">${esc(t.start)} 开始，最近一次 ${esc(t.last)} · ${t.files} 个文件${t.commits ? ` · ${t.commits} 次提交` : ''}${t.truncated ? ' · 文件太多，只看了前 20000 个' : ''}<button type="button" class="linkbtn" data-tlr>重新整理</button></p>
    ${t.versions.length ? `<div class="tlv">${t.versions.map(v => `<span><b>${esc(v.name)}</b><small>${esc(v.from)} 到 ${esc(v.to)} · ${v.files} 个文件</small></span>`).join('')}</div>` : ''}
    <ol class="tll">${t.months.slice().reverse().map(m => `<li><span class="tlm">${esc(m.month)}</span><div class="tlc">
      <div class="tlbar"><i style="width:${Math.max(3, Math.round(m.files / max * 100))}%"></i></div><small>${kinds(m)}</small>
      ${m.commits.length ? `<ul class="tlg">${m.commits.map(c => `<li><time>${esc(c.date.slice(5))}</time>${esc(c.msg)}</li>`).join('')}${m.more ? `<li class="note">还有 ${m.more} 条提交</li>` : ''}</ul>` : ''}</div></li>`).join('')}</ol>
    <p class="note">文件时间是最后修改的时间：整个文件夹拷贝过的话可能都挤在同一天，git 记录不受影响。</p>`;
  el.querySelector('[data-tlr]').onclick = refresh;
}
