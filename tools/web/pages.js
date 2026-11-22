'use strict';
// 资料库、暂存箱、改动历史、体检、第一次使用向导、设置、启动
// 普通 <script>，和 app.js 共用全局变量和函数；index.html 里按 app → chat → day → home → todo → pages 的顺序加载

// ---------------- 资料库 ----------------
const TRUNKS = { '_INBOX': '暂存箱', '00_Crown': '决策端', '01_Skills': '技能', '02_Life': '生活', '03_Projects': '项目', '04_Milestones': '经历', '05_Network': '人脉', '06_Assets': '资产', '07_Decisions': '决策记录', '_RULES': '规则', '_TEMPLATES': '模板' };
const caret = '<svg class="caret" viewBox="0 0 10 10" aria-hidden="true"><path d="M3 1l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>';
let libText = '', libMtime = '', editing = false;
async function viewLib(path) {
  setTitle('资料库');
  if (!$('#libroot')) {
    $('#view').innerHTML = `<div class="lib" id="libroot"><div class="tree"><input id="lq" placeholder="搜索全部文档（按相关度排）" aria-label="搜索"><div id="tnav"></div></div>
      <div class="docpane" id="dpane"><div class="docbar"><button class="btn" id="backBtn" hidden>← 目录</button><span class="path" id="dpath"></span>
      <button class="btn" id="editBtn" hidden>编辑</button><button class="btn" id="newBtn">新建</button></div><div class="doc" id="doc"></div></div></div>`;
    files = await api('/api/tree'); if (!$('#tnav')) return; drawTree();
    let st; $('#lq').oninput = e => { clearTimeout(st); const v = e.target.value.trim(); st = setTimeout(async () => { if (!v) return drawTree();
      const r = await api('/api/search?q=' + encodeURIComponent(v));
      $('#tnav').innerHTML = r.map(f => `<a class="hit" href="${libLink(f.path)}"><span class="dot ${f.privacy}"></span> ${esc(f.title)}<small>${esc(f.snippet || f.path)}</small></a>`).join('') || '<p class="note">没有找到。</p>'; }, 250); };
    drawModeBtns(); $('#editBtn').onclick = toggleEdit; $('#newBtn').onclick = newFile; $('#backBtn').onclick = () => { location.hash = 'lib'; };
  }
  editing = false; libCur = path; $('#libroot').classList.toggle('reading', !!path);
  $('#backBtn').hidden = !path || !matchMedia('(max-width:860px)').matches;
  markTree();
  if (!path) { $('#dpath').textContent = ''; $('#editBtn').hidden = true; $('#doc').innerHTML = '<p class="note">从左边选一个文件。平时不用来这里，直接在对话里说就行。</p>'; return; }
  const ok = fresh(); let j;
  try { j = await api('/api/file?path=' + encodeURIComponent(path)); } catch (e) { if (ok() && $('#doc')) $('#doc').innerHTML = `<p>打不开 <code>${esc(path)}</code>：${esc(e.message)}</p>`; return; }
  if (!ok() || !$('#doc')) return;
  libText = j.text.replace(/\r\n?/g, '\n'); libMtime = j.mtime;
  $('#dpath').textContent = path; $('#editBtn').hidden = false; $('#editBtn').textContent = '编辑'; $('#editBtn').classList.remove('primary');
  drawDoc(); $('#dpane').scrollTop = 0;
}
function drawTree() {
  const root = {}; for (const f of files) { let n = root; const parts = f.path.split('/'); for (const p of parts.slice(0, -1)) n = (n[p + '/'] = n[p + '/'] || {}); n[parts.at(-1)] = f; }
  const link = (f, name) => `<a class="f" href="${libLink(f.path)}" data-p="${esc(f.path)}" title="${esc(f.title)}"><i class="dot ${f.privacy}"></i><span>${esc(name)}</span></a>`;
  const keys = n => Object.keys(n).sort((a, b) => (b.endsWith('/') - a.endsWith('/')) || a.localeCompare(b));
  const draw = (n, pre) => keys(n).map(k => k.endsWith('/') ? `<details class="dir"><summary>${caret}${esc(k.slice(0, -1))}</summary><div class="kids">${draw(n[k], pre + k)}</div></details>` : link(n[k], k.replace(/\.md$/, ''))).join('');
  let main = '', sys = '', docs = '';
  // 程序自带的说明（README、修改日志、使用步骤）收进一个默认折叠的“TWIN 说明”，不和你的资料混在一起
  for (const k of keys(root)) { if (!k.endsWith('/')) { if (root[k].doc) docs += link(root[k], k.replace(/\.md$/, '')); else sys += link(root[k], k.replace(/\.md$/, '')); continue; }
    const name = k.slice(0, -1); const html = `<details class="trunk" ${name === '00_Crown' ? 'open' : ''}><summary>${caret}<span class="zh">${esc(TRUNKS[name] || name)}</span><span class="code">${esc(name)}</span></summary><div class="kids">${draw(root[k], k)}</div></details>`;
    if (name.startsWith('_')) sys = html + sys; else main += html; }
  if (docs) sys += `<details class="trunk"><summary>${caret}<span class="zh">TWIN 说明</span><span class="code">程序自带</span></summary><div class="kids">${docs}</div></details>`;
  $('#tnav').innerHTML = main + `<div style="border-top:1px solid var(--rule);margin-top:10px;padding-top:8px">${sys}</div>`; markTree();
}
function markTree() { document.querySelectorAll('#tnav .f').forEach(a => { const on = a.dataset.p === libCur; a.classList.toggle('on', on);
  if (on) { let d = a.parentElement; while (d && d.id !== 'tnav') { if (d.tagName === 'DETAILS') d.open = true; d = d.parentElement; } } }); }
function drawDoc() {
  // 项目的说明页（03_Projects/…/index.md）下面也放时间线：做完的项目没有任务板块，回看经历、写简历时在这里看
  const isProj = /^03_Projects\/.+\/index\.md$/.test(libCur || '');
  $('#doc').innerHTML = reviewPanel() + render(libText) + (isProj ? timelineBox(libCur) : '') + '<div id="related"></div>';
  if (isProj) bindTimeline($('#doc'));
  const cur = libCur; api('/api/related?path=' + encodeURIComponent(cur)).then(r => { const el = $('#related'); if (!el || libCur !== cur || !r.length) return;
    el.innerHTML = `<div class="related"><div class="lbl">相关文档 · 本地按内容相似度找的</div>${r.map(x => `<a href="${libLink(x.path)}">${esc(x.title)}<small>${esc(x.path)}</small></a>`).join('')}</div>`; }).catch(() => {});
  document.querySelectorAll('#doc .chk').forEach(el => { el.onclick = () => toggleChk(+el.dataset.i); el.onkeydown = e => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); toggleChk(+el.dataset.i); } }; });
  const rb = $('#rvBtn'); if (rb) rb.onclick = saveReview;
  document.querySelectorAll('#doc .privblock .pbed').forEach(b => b.onclick = () => editPriv(b.closest('.privblock')));
}
// 私密段落原地改：只改 <!-- private --> 和 <!-- /private --> 中间的字，标记不动
function editPriv(el) {
  const eol = libText.includes('\r\n') ? '\r\n' : '\n', L = libText.split(/\r?\n/), at = [];
  for (let i = 0; i < L.length; i++) if (/^<!--\s*private\s*-->/i.test(L[i].trim())) { let j = i + 1; while (j < L.length && !/<!--\s*\/private\s*-->/i.test(L[j])) j++; at.push([i, j]); i = j; }
  const r = at[+el.dataset.pb]; if (!r) return;
  el.querySelector('.pbed').hidden = true; leaveGuard = () => confirm('还没保存，确定离开？');
  el.querySelector('.pbody').innerHTML = `<textarea class="pbta" spellcheck="false">${esc(L.slice(r[0] + 1, r[1]).join('\n'))}</textarea><div class="pbact"><button type="button" class="btn sm primary" data-ok>保存</button><button type="button" class="btn sm" data-no>取消</button><small>Ctrl+S 保存，Esc 取消</small></div>`;
  const ta = el.querySelector('.pbta'), done = () => { leaveGuard = null; drawDoc(); };
  const save = async () => { const t = [...L.slice(0, r[0] + 1), ...ta.value.replace(/\r/g, '').split('\n'), ...L.slice(r[1])].join(eol); leaveGuard = null; if (await saveDoc(t)) { drawDoc(); toast('已保存'); } };
  const fit = () => { ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 4 + 'px'; }; fit(); ta.oninput = fit;
  ta.onkeydown = e => { if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); save(); } else if (e.key === 'Escape') done(); };
  el.querySelector('[data-ok]').onclick = save; el.querySelector('[data-no]').onclick = done; ta.focus();
}
async function saveDoc(text) { try { const j = await api('/api/file', { path: libCur, text, mtime: libMtime }); libText = text; libMtime = j.mtime; return true; } catch (e) { toast('没保存：' + e.message, 5000); return false; } }
async function toggleChk(n) { let k = 0; const t = libText.replace(/[☐☑]/g, c => k++ === n ? (c === '☐' ? '☑' : '☐') : c); if (await saveDoc(t)) drawDoc(); }
function toggleEdit() {
  if (!editing) { editing = true; leaveGuard = () => confirm('还没保存，确定离开？'); $('#editBtn').textContent = '保存'; $('#editBtn').classList.add('primary');
    $('#doc').innerHTML = `<textarea id="ed" spellcheck="false">${esc(libText)}</textarea>`;
    $('#ed').onkeydown = e => { if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); toggleEdit(); } }; $('#ed').focus(); }
  else saveDoc($('#ed').value).then(async ok => { if (ok) { editing = false; leaveGuard = null; $('#editBtn').textContent = '编辑'; $('#editBtn').classList.remove('primary'); drawDoc(); files = await api('/api/tree'); toast('已保存'); } });
}
function newFile() {
  const dir = libCur ? libCur.split('/').slice(0, -1).join('/') : '00_Crown';
  const m = modal(`<h3>新建文件</h3><p class="note">放在哪个分支、叫什么（英文名）</p><input id="np" value="${esc(dir)}/New_File.md"><div class="row"><button class="btn" id="mx">取消</button><button class="btn primary" id="mok">新建</button></div>`);
  m.querySelector('#mx').onclick = closeModal;
  m.querySelector('#mok').onclick = async () => { let p = m.querySelector('#np').value.trim(); if (!p.endsWith('.md')) p += '.md';
    const tpl = `---\ntype: \nupdated: ${today()}\nprivacy: internal\n---\n# ${p.split('/').at(-1).replace('.md', '')}\n\n`;
    try { await api('/api/file', { path: p, text: tpl, create: true }); closeModal(); files = await api('/api/tree'); drawTree(); location.hash = 'lib/' + encodeURIComponent(p); } catch (e) { toast(e.message); } };
}
function reviewPanel() {
  const fm = (libText.match(/^---\n([\s\S]*?)\n---/) || [])[1] || '';
  if (!/^type:\s*decision/m.test(fm) || /^status:\s*reviewed/m.test(fm)) return '';
  const rd = (fm.match(/^review_date:\s*(\S+)/m) || [])[1] || '', due = rd && rd <= today();
  return `<div class="panel" style="margin-bottom:18px;${due ? 'border-color:var(--p1)' : ''}"><div class="lbl">${due ? '到期了，回看一下这个决定' : '回看这个决定' + (rd ? `（计划 ${rd}）` : '')}</div>
    <div class="grid3" style="margin-top:8px"><div class="field"><label for="rv_c">最后选了什么</label><input id="rv_c" placeholder="接 / 不接…"></div>
    <div class="field"><label for="rv_w">谁判断得更准</label><select id="rv_w"><option>本地规则</option><option>AI</option><option>都准</option><option>都不准</option><option>还看不出来</option></select></div></div>
    <div class="field" style="margin-top:8px"><label for="rv_o">结果怎么样</label><textarea id="rv_o" placeholder="比如：实际花了 40 小时，客户中途加需求"></textarea></div>
    <div style="margin-top:8px"><button class="btn primary" id="rvBtn">保存回看</button></div></div>`;
}
async function saveReview() { try { await api('/api/review', { path: libCur, chosen: $('#rv_c').value, outcome: $('#rv_o').value, who_right: $('#rv_w').value }); toast('已保存回看'); viewLib(libCur); } catch (e) { toast(e.message, 6000); } }

// ---------------- 暂存箱 ----------------
const KIND = { text: '文本', image: '图片', pdf: 'PDF', zip: '压缩包', office: '文档', other: '文件' };
const kb = n => n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(0) + ' KB' : (n / 1048576).toFixed(1) + ' MB';
// 上次的列表先画出来，后台再取一次，有变化才重画，切过来不用等
async function viewInbox(again) {
  setTitle('暂存箱'); const ok = fresh();
  if (!again && viewInbox.d) drawInbox(viewInbox.d);
  const [d] = await Promise.all([api('/api/inbox').catch(e => (ok() && toast(e.message), null)), loadAi().catch(() => {})]);
  if (!d || !ok()) return;
  const same = JSON.stringify(d) === JSON.stringify(viewInbox.d) && $('.inboxpage');
  viewInbox.d = d; inboxBadge(d.items.length);
  // 正在打字或者正看着 AI 建议时，后台刷新不打断；自己刚操作完（again）总是重画
  if (again || (!same && !($('#note') && $('#note').value) && !document.querySelector('.isug .sugg'))) drawInbox(d);
}
function drawInbox(d) {
  const hasAi = aiCfg.providers.length > 0;
  const opts = sel => d.targets.map(t => `<option ${t === sel ? 'selected' : ''}>${esc(t)}</option>`).join('');
  const CLIP = '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" aria-hidden="true"><path d="M21 11.5l-8.6 8.6a5 5 0 01-7.1-7.1l8.6-8.6a3.3 3.3 0 014.7 4.7l-8.6 8.6a1.7 1.7 0 01-2.4-2.4l8-8"/></svg>';
  const TRASH = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/></svg>';
  $('#view').innerHTML = `<div class="wrap page inboxpage"><div class="dayhead"><h1>暂存箱</h1><span class="sub">临时放东西的地方，${d.items.length ? `${d.items.length} 件等你整理${d.items.some(x => x.age >= 7) ? `，${d.items.filter(x => x.age >= 7).length} 件放了一周以上` : ''}` : '都整理完了'}</span>${tip('文件可以拖到这个页面任何地方，或者直接复制到 <code>_INBOX</code> 文件夹。<br>AI 整理会发出：文本文件的内容（私密段落和疑似敏感值已去掉）、文件名、目录名和项目名。图片、PDF、Office 文件只发文件名；压缩包发里面的文件名列表，不解压。<br>归档和加任务都能在<a href="#history">改动历史</a>里撤销。')}${hasAi && d.items.length > 1 ? '<span class="sp"></span><button class="btn primary sm" id="allAi">全部 AI 整理</button>' : ''}</div>
    <div class="cap" id="drop"><textarea id="note" rows="1" placeholder="随手记一句，回车存进来"></textarea>
      <label class="ib" title="选文件" aria-label="选文件">${CLIP}<input type="file" id="fileIn" multiple hidden></label><button class="btn primary sm" id="saveNote">存</button></div>
    <ul class="list inbox">${d.items.map((it, i) => `<li class="ibx" data-i="${i}">
      <div class="ihead"><span class="ikind">${KIND[it.kind]}</span><span class="tx">${it.path ? `<a href="${libLink(it.path)}">${esc(it.name)}</a>` : esc(it.name)}<small>${esc(it.time)} · ${kb(it.size)}${it.age >= 7 ? ` · <b class="iold">放了 ${it.age} 天</b>` : ''}</small></span>
        <span class="iact">${hasAi ? '<button class="btn primary sm" data-ai>AI 整理</button>' : ''}<button class="btn sm" data-mv>归档到…</button><button class="ib" data-del title="删除" aria-label="删除">${TRASH}</button></span></div>
      ${it.preview ? `<p class="ipre">${esc(it.preview)}</p>` : ''}
      <div class="isug"></div></li>`).join('') || '<li class="note" style="padding:14px 0">暂存箱是空的。</li>'}</ul></div>`;
  const note = $('#note');
  const grow = () => { note.style.height = 'auto'; note.style.height = Math.min(note.scrollHeight, 200) + 'px'; };
  note.oninput = grow;
  $('#saveNote').onclick = async () => { if (!note.value.trim()) return note.focus(); try { await api('/api/inbox/note', { text: note.value }); viewInbox(true); } catch (e) { toast(e.message, 6000); } };
  note.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); $('#saveNote').click(); } };
  const up = async fl => { for (const f of fl) { const data = await new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = no; r.readAsDataURL(f); });
      try { await api('/api/inbox/upload', { name: f.name, data }); } catch (e) { toast(e.message, 6000); } } viewInbox(true); };
  $('#fileIn').onchange = e => up(e.target.files);
  // 整个页面都能拖文件进来
  const pg = $('.inboxpage'), dz = $('#drop');
  pg.ondragover = e => { if ([...e.dataTransfer.types].includes('Files')) { e.preventDefault(); dz.classList.add('over'); } };
  pg.ondragleave = e => { if (!pg.contains(e.relatedTarget)) dz.classList.remove('over'); };
  pg.ondrop = e => { e.preventDefault(); dz.classList.remove('over'); if (e.dataTransfer.files.length) up(e.dataTransfer.files); };
  const move = async (it, dest, name, newDir) => { try { await api('/api/inbox/move', { name: it.name, dest, new_name: name, new_dir: newDir || '' }); viewInbox(true); } catch (e) { toast(e.message, 6000); } };
  document.querySelectorAll('.ibx').forEach(li => { const it = d.items[+li.dataset.i], box = li.querySelector('.isug');
    const mv = li.querySelector('[data-mv]');
    mv.onclick = () => fmenu && fmenu.btn === mv ? closeFmenu() : openMenu(mv, d.targets, -1, k => move(it, d.targets[k]));
    li.querySelector('[data-del]').onclick = async () => { try { await api('/api/inbox/delete', { name: it.name }); viewInbox(true); } catch (e) { toast(e.message, 6000); } };
    const ab = li.querySelector('[data-ai]'); if (ab) ab.onclick = async () => { ab.textContent = 'AI 正在看…'; ab.disabled = true;
      let s; try { s = await api('/api/inbox/suggest', { name: it.name }); } catch (e) { ab.textContent = 'AI 整理'; ab.disabled = false; return toast(e.message, 7000); }
      ab.textContent = '重新整理'; ab.disabled = false;
      const ts = s.tasks || [];
      box.innerHTML = `<div class="sugg"><p class="sum">${esc(s.summary || '')} ${tip(`${s.reason ? esc(s.reason) + '<br>' : ''}置信度：${esc(s.confidence || '-')}`)}</p>
        <div class="sgrow"><span class="lbl">放到</span><select data-sd aria-label="放到哪个目录"><option value="">（请选目录）</option>${opts(s.dest)}</select></div>
        <div class="sgrow"><span class="lbl">新建文件夹</span><input data-sdir value="${esc(s.new_dir || '')}" placeholder="不用新建就空着" aria-label="在上面的目录下新建文件夹"></div>
        <div class="sgrow"><span class="lbl">文件名</span><input data-sn value="${esc(s.name || it.name)}" aria-label="文件名"></div>
        ${ts.length ? `<div class="stasks">${ts.map((t, j) => `<label class="srow"><input type="checkbox" data-t="${j}" checked><span class="st">加任务 · ${esc(shortName(t.project || ''))}：${esc(t.text)}${t.note ? `<small>${esc(t.note)}</small>` : ''}</span><em>${esc(t.priority || 'P1')}${t.due ? ' · ' + esc(t.due.slice(5)) : ''}</em></label>`).join('')}</div>` : ''}
        <div class="row"><button class="btn primary sm" data-go>归档${ts.length ? '并加任务' : ''}</button><button class="btn sm" data-x>取消</button></div></div>`;
      box.querySelector('[data-x]').onclick = () => { box.innerHTML = ''; ab.textContent = 'AI 整理'; };
      box.querySelector('[data-go]').onclick = async () => { const dest = box.querySelector('[data-sd]').value; if (!dest) return toast('先选一个目录');
        try { for (const c of box.querySelectorAll('[data-t]')) if (c.checked) { const t = ts[+c.dataset.t];
            await api('/api/action', { action: { type: 'task_add', project: t.project, text: t.text, priority: t.priority, due: t.due, note: t.note || '' }, via: 'ai' }); }
          await move(it, dest, box.querySelector('[data-sn]').value, box.querySelector('[data-sdir]').value.trim()); } catch (e) { toast(e.message, 7000); } }; };
  });
  // 全部整理：一件一件请 AI 给建议，都出来以后一次确认归档（没选目录的跳过）
  const all = $('#allAi'); if (all) all.onclick = async () => {
    if (all.dataset.go) { for (const g of [...document.querySelectorAll('.isug [data-go]')]) if (g.closest('.sugg').querySelector('[data-sd]').value) await g.onclick(); return; }
    all.disabled = true; const bs = [...document.querySelectorAll('.ibx [data-ai]')];
    for (const [i, b] of bs.entries()) { all.textContent = `AI 正在看 ${i + 1}/${bs.length}…`; if (!b.closest('.ibx').querySelector('.sugg')) await b.onclick(); }
    all.disabled = false; all.dataset.go = 1; all.textContent = '全部确认归档'; };
}

// ---------------- 改动历史 ----------------
const SRC = { 'AI': 'ai', '手动': 'me', '系统': 'sys', '撤销': 'undo', '别处': 'ext' };
async function viewHistory() {
  setTitle('改动历史');
  const ok = fresh(); let list; try { list = await api('/api/history'); } catch (e) { return ok() && toast(e.message); }
  if (!ok()) return;
  // 折叠：最近 7 天一天一组，再往前一周一组，30 天以前一月一组。只有今天默认展开，展开时才画里面的条目
  const pad = n => String(n).padStart(2, '0'), ds = x => `${x.getFullYear()}-${pad(x.getMonth() + 1)}-${pad(x.getDate())}`;
  const t0 = new Date(today() + 'T00:00'), ago = d => Math.round((t0 - new Date(d + 'T00:00')) / 864e5);
  const keyOf = d => { const n = ago(d);
    if (n < 7) return { k: d, name: n === 0 ? '今天' : n === 1 ? '昨天' : `${+d.slice(5, 7)} 月 ${+d.slice(8)} 日 · 星期${'日一二三四五六'[new Date(d + 'T00:00').getDay()]}` };
    if (n < 30) { const x = new Date(d + 'T00:00'); x.setDate(x.getDate() - (x.getDay() + 6) % 7); const e = new Date(x); e.setDate(e.getDate() + 6);
      return { k: 'w' + ds(x), name: `${x.getMonth() + 1}/${x.getDate()} – ${e.getMonth() + 1}/${e.getDate()} 这一周` }; }
    return { k: 'm' + d.slice(0, 7), name: `${d.slice(0, 4)} 年 ${+d.slice(5, 7)} 月` }; };
  const groups = [];
  for (const x of list) { const g = keyOf(x.time.slice(0, 10)); if (!groups.length || groups.at(-1).k !== g.k) groups.push({ ...g, xs: [] }); groups.at(-1).xs.push(x); }
  const row = (x, long) => `<li class="hrow ${x.undone ? 'undone' : ''}" data-id="${esc(x.id)}">
      <div class="hhead"><span class="src ${SRC[x.source] || ''}">${esc(x.source)}</span><span class="tx">${esc(x.label)}<small>${long ? x.time.slice(5, 10).replace('-', '/') + ' ' : ''}${x.time.slice(11, 16)} · ${x.files.map(f => esc(f.split('/').at(-1))).join('、')}</small></span>
      ${x.undone ? '<span class="due">已撤销</span>' : x.source === '撤销' ? '' : '<button class="btn sm" data-undo>撤销</button>'}</div><div class="hdiff"></div></li>`;
  const open = viewHistory.open || (viewHistory.open = new Set([today()]));
  $('#view').innerHTML = `<div class="wrap page"><div class="dayhead"><h1>改动历史</h1><span class="sub">网页和 AI 写过的每个文件</span>${tip('网页和 AI 的改动马上记；在 Obsidian、记事本里改的，或者 Claude 直接改的，网页开着时每 2 分钟自动发现一次，标成“别处”。<br>点一条看改了什么，撤销会把文件恢复到那次改动之前，撤销本身也能再撤回来。<br>最近 7 天按天分组，再往前按周，30 天以前按月；点组名展开。<br>只存在这台电脑的 <code>.history</code> 文件夹，保留半年。')}</div>
    ${groups.map((g, i) => `<details class="hgrp" data-g="${i}" data-k="${esc(g.k)}" ${open.has(g.k) ? 'open' : ''}><summary><span>${esc(g.name)}</span><small>${g.xs.length} 条</small></summary><ul class="list"></ul></details>`).join('') || '<p class="note">还没有改动。</p>'}</div>`;
  const fill = det => { const ul = det.querySelector('ul'); if (ul.childElementCount) return; const g = groups[+det.dataset.g];
    ul.innerHTML = g.xs.map(x => row(x, g.k.length > 10)).join('');
    ul.querySelectorAll('.hrow').forEach(bindRow); };
  document.querySelectorAll('.hgrp').forEach(det => { if (det.open) fill(det);
    det.ontoggle = () => { if (det.open) { open.add(det.dataset.k); fill(det); } else open.delete(det.dataset.k); }; });
  function bindRow(li) {
    li.querySelector('.hhead .tx').onclick = async () => { const box = li.querySelector('.hdiff'); if (box.innerHTML) { box.innerHTML = ''; return; }
      try { const d = await api('/api/history/diff?id=' + li.dataset.id);
        box.innerHTML = d.files.map(f => `<div class="dfile"><div class="dname">${esc(f.kind)} · ${f.path.endsWith('.md') ? `<a href="${libLink(f.path)}">${esc(f.path)}</a>` : esc(f.path)}</div><pre class="diff">${f.lines.map(l => `<span class="${l[0] === '+' ? 'add' : l[0] === '-' ? 'del' : l.startsWith('@@') ? 'hunk' : ''}">${esc(l)}</span>`).join('\n')}</pre></div>`).join(''); }
      catch (e) { toast(e.message); } };
    const u = li.querySelector('[data-undo]'); if (u) u.onclick = () => undoEntry(li.dataset.id);
  }
}

// ---------------- 体检 ----------------
const LVL = { red: '马上处理', amber: '留意', grey: '有空再弄' };
async function viewHealth() {
  setTitle('体检');
  const ok = fresh(); let d; try { d = await api('/api/health'); } catch (e) { return ok() && toast(e.message); }
  if (!ok()) return;
  const link = x => x.path.startsWith('#') ? x.path : x.board ? bLink(x.path) : libLink(x.path);
  const ign = async (key, on) => { try { await api('/api/health/ignore', { key, on }); viewHealth(); } catch (e) { toast(e.message); } };
  $('#view').innerHTML = `<div class="wrap page"><div class="dayhead"><h1>体检</h1><span class="sub">${esc(d.time)} 检查 · 全在本地算，不经过 AI</span>${tip('查的是：过期任务、14 天没动的项目、总览表和项目页对不上、断掉的链接、没写的分支总结、缺隐私级别的文件、非私密文件里的疑似身份证号/手机号/银行卡号/邮箱、暂存箱、到期没回看的决定。每周周报里也会带上体检结果。<br>点“忽略”的条目以后不再提示（存在本机 <code>tools/health_ignore.json</code>，随时可以恢复）。')}</div>
    ${d.issues.length ? ['red', 'amber', 'grey'].map(l => { const xs = d.issues.filter(x => x.level === l); return xs.length ? `<div class="gl"><span class="lvdot ${l}"></span>${LVL[l]} · ${xs.length}</div><ul class="list">${xs.map(x => `<li class="row"><span class="kind">${esc(x.kind)}</span>
      <a class="tx" href="${link(x)}">${esc(x.title)}<small>${esc(x.detail)}</small></a><button class="btn sm" data-ign="${esc(x.key)}" title="以后不再提示这一条">忽略</button></li>`).join('')}</ul>` : ''; }).join('') : '<p class="note">一切正常。</p>'}
    ${d.ignored.length ? `<details class="sec"><summary class="note">已忽略 ${d.ignored.length} 条</summary><ul class="list">${d.ignored.map(x => `<li class="row"><span class="kind">${esc(x.kind)}</span><span class="tx">${esc(x.title)}<small>${esc(x.detail)}</small></span><button class="btn sm" data-unign="${esc(x.key)}">恢复</button></li>`).join('')}</ul></details>` : ''}</div>`;
  document.querySelectorAll('[data-ign]').forEach(b => b.onclick = () => ign(b.dataset.ign, true));
  document.querySelectorAll('[data-unign]').forEach(b => b.onclick = () => ign(b.dataset.unign, false));
}

// ---------------- 第一次使用：称呼和个人画像、地点、作息，接 AI（除了称呼都能空着，以后在设置里补） ----------------
function setupWizard(p) {
  const st = { name: p.name || '', place: null, preset: '', portrait: { ...p.portrait } }; let k = 0;
  const fld = ([f, ph]) => `<label class="haf"><span>${esc(f)}</span><span class="hain"><input data-pf="${esc(f)}" maxlength="200" placeholder="${esc(ph)}" value="${esc(st.portrait[f] || '')}"></span></label>`;
  const steps = [
    ...p.fields.map(([t, why, fs], i) => [t, `${why}存在本机 <code>00_Crown/Profile.md</code>，会作为摘要给 AI，所以别写身份证号、电话、住址、金额。空着也行，以后慢慢补。`,
      () => (i ? '' : `<label class="haf"><span>称呼</span><span class="hain">${lu('type', 15)}<input id="wzN" maxlength="20" placeholder="比如：小明" value="${esc(st.name)}"></span></label>`) + fs.map(fld).join('')]),
    ['你在哪个城市', '用来查“今天”页和首页的天气。只把城市名发给 Open-Meteo 查坐标，不填住址。不填就用现在的。',
      () => `<p class="note">现在：${esc((st.place || p.place || {}).name || '还没有')}</p><div class="hain">${lu('search', 15)}<input id="wzQ" placeholder="输入城市，回车搜索"><button type="button" id="wzS">搜索</button></div><div class="hacat" id="wzR"></div>`],
    ['作息大概是什么样', '用来画“今天”页的时段条，提醒每个时段该做什么。选一个模板，之后在 <code>_RULES/Weather_Rhythm.md</code> 里细改。',
      () => `<div class="hacat" id="wzP">${['', ...p.presets].map(x => `<button type="button" data-p="${x}" class="${st.preset === x ? 'on' : ''}">${x || '保持现在的'}</button>`).join('')}</div>`],
    ['接一个 AI', 'DeepSeek、通义、Claude 等都行，填 API key 就能对话、写简报。不接也能用：待办、项目、文档、首页都在本机跑。',
      () => `<p class="note">可以现在去设置里接，也可以以后再说。</p>`]];
  const m = dlg('', '', '', '<button type="button" class="btn ghost" id="wzB">上一步</button><span style="flex:1"></span><button type="button" class="btn" id="wzK">以后再说</button><button type="button" class="btn primary" id="wzF">下一步</button>', 'hdsmall wz');
  const draw = () => { const [t, help, body] = steps[k];
    m.querySelector('.hdh h3').textContent = `${k + 1}/${steps.length} · ${t}`; m.querySelector('.hdh .qtip')?.remove(); m.querySelector('.hdh h3').insertAdjacentHTML('afterend', tip(help));
    m.querySelector('.hdb').innerHTML = body(); replay(m.querySelector('.hdb'), 'fade');
    m.querySelector('#wzB').hidden = !k; m.querySelector('#wzF').textContent = k === steps.length - 1 ? '完成' : '下一步';
    const n = m.querySelector('#wzN'); if (n) { n.focus(); n.oninput = () => st.name = n.value.trim(); n.onkeydown = e => { if (e.key === 'Enter' && !e.isComposing) next(); }; }
    const q = m.querySelector('#wzQ'); if (q) { q.focus(); const go = async () => { const r = m.querySelector('#wzR'); r.innerHTML = '<span class="note">搜索中…</span>';
        const j = await api('/api/geocode?q=' + encodeURIComponent(q.value)).catch(e => ({ results: [], error: e.message }));
        r.innerHTML = j.results.map((x, i) => `<button type="button" data-i="${i}">${esc(x.name)}</button>`).join('') || `<span class="note">${esc(j.error || '没找到，换个写法试试')}</span>`;
        r.querySelectorAll('[data-i]').forEach(b => b.onclick = () => { st.place = j.results[+b.dataset.i]; r.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); }); };
      m.querySelector('#wzS').onclick = go; q.onkeydown = e => { if (e.key === 'Enter' && !e.isComposing) go(); }; }
    m.querySelectorAll('[data-pf]').forEach(el => { el.oninput = () => st.portrait[el.dataset.pf] = el.value.trim(); el.onkeydown = e => { if (e.key === 'Enter' && !e.isComposing) next(); }; });
    if (!n && !q) m.querySelector('[data-pf]')?.focus();
    m.querySelectorAll('#wzP [data-p]').forEach(b => b.onclick = () => { st.preset = b.dataset.p; m.querySelectorAll('#wzP button').forEach(x => x.classList.toggle('on', x === b)); }); };
  const next = async () => { if (!k && !st.name) return toast('先写一个称呼');
    if (k < steps.length - 1) { k++; return draw(); } save(); };
  const save = async () => {
    try { const r = await api('/api/profile', st); setPref('name', r.name); closeModal(); toast('好了，以后在设置里能改'); route(); } catch (e) { toast(e.message); } };
  m.querySelector('#wzB').onclick = () => { k--; draw(); };
  m.querySelector('#wzK').onclick = () => st.name ? save() : closeModal();  // 填了称呼就把已填的存下来
  m.querySelector('#wzF').onclick = next;
  draw();
}

// ---------------- 设置 ----------------
// AI 服务商：一家一行（名字、模型、key 填没填、测试），点一行展开改；左边圆点是默认。draftAct：默认那家在 draftProv 里的位置；provOpen：展开的那行
let draftProv = [], draftAct = 0, provOpen = -1;
const provReset = () => { draftProv = aiCfg.providers.map(p => ({ ...p })); draftAct = Math.max(0, draftProv.findIndex(p => p.id === aiCfg.active)); };
async function viewSettings() { setTitle('设置'); const ok = fresh(); await loadAi(true); if (!ok()) return; provReset(); provOpen = -1; drawSettings(); }
// 左边分类、右边一行一项；记住上次看的分类（setTab）。手机上分类变成顶上一排
// 建议池：对 TWIN 本身的改进建议（_RULES/Suggestions.md）。记、删、复制给开发者，或者让 AI 合并排序
async function drawSugg() {
  const L = $('#sgL'), q = $('#sgQ'); let xs; try { xs = await api('/api/ideas'); } catch (e) { return toast(e.message); }
  if (!L || !L.isConnected) return;
  const list = () => xs.map((x, k) => `${k + 1}. ${x.text}${x.date ? `（${x.date}）` : ''}`).join('\n');
  L.innerHTML = xs.slice().reverse().map(x => `<div class="plrow idr"><span class="idt">${esc(x.text)}${x.date ? `<small>${esc(x.date.slice(5))}</small>` : ''}</span>
    <button type="button" class="ib pldel" data-del="${x.i}" data-tip="删掉" aria-label="删掉这条建议">${lu('trash', 15)}</button></div>`).join('') || '<p class="note">还没有建议。</p>';
  L.querySelectorAll('[data-del]').forEach(b => b.onclick = async () => { const x = xs[+b.dataset.del];
    try { toast((await api('/api/action', { action: { type: 'idea_del', i: x.i, text: x.text } })).message); drawSugg(); } catch (e) { toast(e.message, 6000); } });
  q.onkeydown = async e => { if (e.key !== 'Enter' || e.isComposing || !q.value.trim()) return;
    try { await api('/api/action', { action: { type: 'add_idea', text: q.value.trim() } }); q.value = ''; drawSugg(); } catch (er) { toast(er.message, 6000); } };
  const cp = $('#sgCopy'), ai = $('#sgAi'); cp.disabled = !xs.length; if (ai) { ai.disabled = xs.length < 2; ai.title = xs.length < 2 ? '至少两条才值得汇总' : ''; }
  cp.onclick = async () => { if (await copyText('对 TWIN 的改进建议：\n' + list())) toast(`已复制 ${xs.length} 条`); };
  if (ai) ai.onclick = () => { pendingAsk = `下面是我攒的对 TWIN 这个工具本身的改进建议。帮我汇总成一份可以直接发给开发者的清单：意思相近的合并，按对日常使用的帮助大小排序，每条写清楚现在哪里不顺、希望改成什么样。重复的、过时的告诉我，并提出从建议池拿掉。只整理下面这些，不要另编新的。\n\n${list()}`; pendingSend = true; location.hash = 'c'; };
}
const STABS = [['gen', '通用', 'sliders'], ['look', '外观', 'palette'], ['ai', 'AI 服务商', 'bot'], ['plug', '插件', 'puzzle'], ['sec', '隐私和安全', 'shield'], ['sugg', '建议池', 'lightbulb']];
const srow = (name, desc, ctl) => `<div class="srow"><div class="sl"><b>${name}</b>${desc ? `<small>${desc}</small>` : ''}</div>${ctl}</div>`;
function drawSettings() { const tab = STABS.some(t => t[0] === pref('setTab', '')) ? pref('setTab', '') : 'gen', T = STABS.find(t => t[0] === tab);
  const body = {
    gen: `${srow('个人画像', '称呼、身份、技能、方向、作息、天气地点，存在 <code>00_Crown/Profile.md</code>', '<button class="btn sm" id="wzBtn">补充或修改</button>')}
      ${srow('界面语言', '', `<div class="mseg" id="langSeg" translate="no">${[['zh', '中文'], ['en', 'English']].map(([k, n]) => `<button type="button" data-l="${k}" class="${(pref('lang', 'zh') === 'en' ? 'en' : 'zh') === k ? 'on' : ''}" style="width:auto;padding:0 12px">${n}</button>`).join('')}</div>`)}
      ${srow('开机自动启动', '<span id="asInfo">登录 Windows 后在后台打开 TWIN（不弹浏览器，右下角托盘有图标）。移动硬盘换了盘符也能找到，盘没插就什么都不做。</span>', '<button type="button" class="plsw" role="switch" aria-checked="false" id="asSw" aria-label="开机自动启动"><i></i></button>')}
      ${srow('版本', `<span id="upInfo">现在是 ${esc(upInfo.current || '')}</span>`, '<button class="btn sm" id="upChk">检查更新</button><button class="btn sm" id="upLocal" title="选一个别人发给你的 TWIN 空白版 zip，不用联网">用升级包</button><input type="file" id="upFile" accept=".zip" hidden><button class="btn sm primary" id="upGo" hidden>升级</button>')}`,
    look: `<p class="sdesc">只对这台设备生效。</p>
      ${srow('模式', '', `<div class="mseg" id="modeSeg">${[['auto', '跟随系统', 'monitor'], ['light', '白天', 'sun'], ['dark', '夜间', 'moon']].map(([k, n, ic]) => `<button type="button" data-m="${k}" class="${pref('mode', 'auto') === k ? 'on' : ''}" data-tip="${n}" aria-label="${n}">${lu(ic, 17)}</button>`).join('')}</div>`)}
      ${srow('主题色', '', `<div class="sw" id="accSw">${Object.entries(ACCENTS).map(([k, c]) => `<button type="button" data-a="${k}" class="${pref('accent', 'mono') === k ? 'on' : ''}" title="${c[0]}" aria-label="${c[0]}" style="--c:${c[1]};--cd:${c[2]}"><i></i>${c[0]}</button>`).join('')}</div>`)}`,
    ai: `<p class="sdesc">可以接多家，圆点是默认，对话框左下角能随时换。大多数服务商兼容 OpenAI 格式；Claude 选 Anthropic。${tip(`API key 存在这台电脑的 <code>${esc(aiCfg.config_path)}</code>，不在知识库里。换电脑要重新填。模型名以服务商官网为准。`, 'API key 存在哪')}</p>
      <div class="sai"><div class="provs">${draftProv.map((p, i) => `<div class="prov${provOpen === i ? ' open' : ''}" data-i="${i}">
        <div class="prow"><button type="button" class="pdot${i === draftAct ? ' on' : ''}" data-def="${i}" title="${i === draftAct ? '默认用这家' : '设为默认'}" aria-label="设为默认"></button>
          <button type="button" class="pmain" data-o="${i}"><b>${esc(p.name || '未命名')}</b>${i === draftAct ? '<span class="ptag">默认</span>' : ''}
            <small>${p.kind === 'anthropic' ? 'Anthropic' : 'OpenAI 兼容'} · ${esc(p.model || '没填模型')} · ${p.api_key ? 'key 已填' : '<em>还没填 key</em>'}</small></button>
          <button type="button" class="btn sm" data-t="${i}">测试</button>
          <button type="button" class="ib pchev" data-o="${i}" aria-label="${provOpen === i ? '收起' : '展开修改'}">${lu('chevron-down', 16)}</button></div>
        ${provOpen === i ? `<div class="pedit">
          <label class="fld"><span>名称</span><input data-f="name" value="${esc(p.name)}"></label>
          <label class="fld"><span>接口类型</span><select data-f="kind"><option value="openai" ${p.kind === 'openai' ? 'selected' : ''}>OpenAI 兼容</option><option value="anthropic" ${p.kind === 'anthropic' ? 'selected' : ''}>Anthropic</option></select></label>
          <label class="fld wide"><span>接口地址</span><input data-f="base_url" value="${esc(p.base_url)}"></label>
          <label class="fld"><span>模型</span><input data-f="model" value="${esc(p.model)}" placeholder="例如 deepseek-flash"></label>
          <label class="fld"><span>API key</span><input data-f="api_key" type="password" value="${esc(p.api_key)}" placeholder="sk-…" autocomplete="off"></label>
          <div class="pfoot"><button type="button" class="btn sm danger" data-d="${i}">删除这家</button></div></div>` : ''}</div>`).join('') || '<p class="note">还没有。从下面选一家添加。</p>'}</div>
      <div class="padd"><select id="preset">${aiCfg.presets.map((p, i) => `<option value="${i}">${esc(p.name)}</option>`).join('')}</select>
        <button class="btn" id="addProv">${lu('plus', 15)}添加</button><span style="flex:1"></span><button class="btn primary" id="saveProv">保存</button></div></div>`,
    plug: `<p class="sdesc">关着的插件和没装一样。开着的插件可能会在首页放一个小组件，右键能移走，“添加 → 小组件”里能加回来。</p>
      <div id="plugList"><p class="note">读取中…</p></div>
      <div class="plfl"><button class="btn sm" id="plInst">${lu('plus', 14)}安装插件</button><input type="file" id="plFile" accept=".zip" hidden>${tip('上传插件的 zip，装好默认关着。插件就是 <code>tools/plugins/</code> 里的一个文件夹，也可以直接拷进去或删掉，重启 TWIN 生效。怎么写插件见 <code>tools/plugins/README.md</code>。')}</div>`,
    sugg: `<p class="sdesc">对 TWIN 本身的修改和优化建议：缺什么功能、哪里不顺手。想到就记一条，AI 帮你干活时发现做不了的也会记在这里。攒几条可以汇总成一份清单，发给做 TWIN 的人，或者自己照着改。${tip('存在 <code>_RULES/Suggestions.md</code>，平时对话不会带上它。点“让 AI 汇总”时才把这几条发给 AI。')}</p>
      <div class="hain">${lu('plus', 15)}<input id="sgQ" placeholder="记一条建议，回车保存" aria-label="记一条建议"></div><div id="sgL" class="plib"><p class="note">读取中…</p></div>
      <div class="plfl"><button class="btn sm" id="sgCopy">复制全部</button>${aiCfg.providers.length ? '<button class="btn sm" id="sgAi">让 AI 汇总</button>' : ''}</div>`,
    sec: `${srow('自动锁定', '这么久没操作就锁上，在用不会锁；锁前 1 分钟顶上倒数，动一下就取消', `<select id="lockMin" class="fsel boxed">${[[5, '5 分钟'], [15, '15 分钟'], [30, '30 分钟'], [60, '1 小时']].map(([v, n]) => `<option value="${v}">${n}没操作</option>`).join('')}</select>`)}
      ${srow('访问密码', '忘了就删掉 <code>tools/.auth.json</code> 重新设置', '<button class="btn sm" id="pwBtn">修改密码</button>')}
      ${srow('隐私检查', '找出没标隐私等级的文件和写了明文密码、密钥的地方', '<button class="btn sm" id="scanBtn">检查</button>')}
      ${srow('上传包', '只打包 public 文件，含疑似敏感值的会被拒绝', '<button class="btn sm" id="packBtn">生成</button>')}`,
  }[tab];
  $('#view').innerHTML = `<div class="sets"><nav class="snav" aria-label="设置分类"><h1>设置</h1>${STABS.map(([k, n, ic]) => `<button type="button" data-st="${k}" class="${k === tab ? 'on' : ''}">${lu(ic, 17)}<span>${n}</span></button>`).join('')}</nav>
    <div class="smain"><h2>${T[1]}</h2>${body}</div></div>`;
  document.querySelectorAll('[data-st]').forEach(b => b.onclick = () => { setPref('setTab', b.dataset.st); provOpen = -1; drawSettings(); $('#view').scrollTop = 0; });
  $('.snav .on').scrollIntoView({ block: 'nearest', inline: 'nearest' });
  const on = id => $(id) || { set onclick(f) {}, set onchange(f) {} };  // 不在当前分类的控件：绑定时跳过
  if (tab === 'plug') { plugInst($('#view')); drawPlugins(); }
  if (tab === 'sugg') drawSugg();
  document.querySelectorAll('.prov[data-i] [data-f]').forEach(el => el.oninput = () => { draftProv[+el.closest('.prov').dataset.i][el.dataset.f] = el.value; });
  document.querySelectorAll('[data-d]').forEach(b => b.onclick = () => { const i = +b.dataset.d; draftProv.splice(i, 1); if (draftAct >= i && draftAct) draftAct--; provOpen = -1; drawSettings(); toast('删掉了，点“保存”才生效'); });
  document.querySelectorAll('[data-o]').forEach(b => b.onclick = () => { provOpen = provOpen === +b.dataset.o ? -1 : +b.dataset.o; drawSettings(); });
  document.querySelectorAll('[data-def]').forEach(b => b.onclick = () => { draftAct = +b.dataset.def; drawSettings(); });
  document.querySelectorAll('[data-t]').forEach(b => b.onclick = async () => { await saveProv(true); const p = aiCfg.providers[+b.dataset.t]; if (!p) return;
    b.textContent = '…'; try { const j = await api('/api/ai/test', { provider_id: p.id }); toast('连通了：' + j.answer, 5000); } catch (e) { toast(e.message, 9000); } b.textContent = '测试'; });
  on('#addProv').onclick = () => { draftProv.push({ ...aiCfg.presets[+$('#preset').value], api_key: '' }); provOpen = draftProv.length - 1; drawSettings(); $(`.prov[data-i="${provOpen}"] [data-f="api_key"]`)?.focus(); };
  on('#saveProv').onclick = () => saveProv(false);
  document.querySelectorAll('#langSeg button').forEach(b => b.onclick = () => { if (b.classList.contains('on')) return; setPref('lang', b.dataset.l); location.reload(); });
  document.querySelectorAll('#modeSeg button').forEach(b => b.onclick = () => { setPref('mode', b.dataset.m); switchLook(() => { applyLook(); drawModeBtns(); drawSettings(); }, b); });
  document.querySelectorAll('#accSw button').forEach(b => b.onclick = () => { setPref('accent', b.dataset.a); applyLook(); drawSettings(); });
  const run = cmd => async () => { toast('运行中…'); const j = await api('/api/run', { cmd }); toast(j.output, 9000); };
  const lm = $('#lockMin'); if (lm) api('/api/lock').then(j => { lm.value = j.min; fancy(lm); }).catch(() => {});
  if (lm) lm.onchange = async () => { try { lockTimer(await api('/api/lock', { min: +lm.value })); toast(`${lm.selectedOptions[0].text}就自动锁定`); } catch (e) { toast(e.message); } };
  on('#scanBtn').onclick = run('scan'); on('#packBtn').onclick = run('pack');
  drawUp(); on('#upChk').onclick = () => checkUp(true).then(drawUp);
  // 开机自动启动：开关先动，请求失败再弹回去；不支持（不是 Windows、还没有 TWIN.exe）就灰掉并说明原因
  const asw = $('#asSw'); if (asw) { const show = st => { asw.setAttribute('aria-checked', !!st.on); asw.disabled = !st.supported;
      if (!st.supported && st.why) $('#asInfo').textContent = st.why; };
    api('/api/autostart').then(show).catch(() => {});
    asw.onclick = async () => { const want = asw.getAttribute('aria-checked') !== 'true'; asw.setAttribute('aria-checked', want);
      try { show(await api('/api/autostart', { on: want })); toast(want ? '好了，以后登录 Windows 就会在后台打开 TWIN' : '已关掉开机自动启动'); }
      catch (e) { asw.setAttribute('aria-checked', !want); toast(e.message, 6000); } }; }
  const uf = $('#upFile'); if (uf) { on('#upLocal').onclick = () => uf.click();
    uf.onchange = async () => { const z = uf.files[0]; uf.value = ''; if (!z) return;
      if (!confirm(`用“${z.name}”升级？会先把现在的程序备份到 _export，资料、对话、密码都不动。`)) return;
      const b = $('#upLocal'); b.disabled = true; b.textContent = '安装中…';
      try { const data = await new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = no; r.readAsDataURL(z); });
        const r = await api('/api/update/local', { name: z.name, data });
        $('#upInfo').textContent = `已升级到 ${r.version}，在右下角托盘图标右键“退出 TWIN”，再双击 TWIN.exe 重开就生效。旧程序备份在 ${r.backup}。`; b.hidden = true; }
      catch (e) { toast(e.message, 8000); b.disabled = false; b.textContent = '用升级包'; } }; }
  on('#upGo').onclick = async () => { const b = $('#upGo'); b.disabled = true; b.textContent = '下载安装中…';
    try { const r = await api('/api/update/apply', {}); $('#upInfo').textContent = `已升级到 ${r.version}，在右下角托盘图标右键“退出 TWIN”，再双击 TWIN.exe 重开就生效。旧程序备份在 ${r.backup}。`; b.hidden = true; }
    catch (e) { toast(e.message, 8000); b.disabled = false; b.textContent = '升级'; } };
  on('#wzBtn').onclick = () => api('/api/profile').then(setupWizard).catch(e => toast(e.message));
  on('#pwBtn').onclick = () => { const m = modal(`<h3>修改密码</h3><input id="o" type="password" placeholder="原密码"><input id="n1" type="password" placeholder="新密码（至少 8 位）"><input id="n2" type="password" placeholder="再输一遍"><div class="row"><button class="btn" id="mx">取消</button><button class="btn primary" id="mok">修改</button></div>`);
    m.querySelector('#mx').onclick = closeModal;
    m.querySelector('#mok').onclick = async () => { const n = m.querySelector('#n1').value; if (n !== m.querySelector('#n2').value) return toast('两次输入的新密码不一样');
      try { await api('/api/password', { old: m.querySelector('#o').value, new: n }); closeModal(); toast('密码已修改'); } catch (e) { toast(e.message); } }; };
}
async function saveProv(quiet) {
  aiCfg = await api('/api/ai/config', { providers: draftProv, active: '' });
  const act = aiCfg.providers[draftAct]; if (act && act.id !== aiCfg.active) aiCfg = await api('/api/ai/config', { providers: aiCfg.providers, active: act.id });
  provReset(); if (!quiet) { toast('已保存'); drawSettings(); }
}

// ---------------- 插件：tools/plugins/ 里的，开着的才加载脚本；插件可以在 TwinPlugins[id].panel 里画自己的设置 ----------------
const loadPlugin = id => new Promise(ok => { if (document.querySelector(`script[data-plugin="${id}"]`)) return ok();
  const s = document.createElement('script'); s.src = `/plugin/${id}.js`; s.dataset.plugin = id; s.onload = () => { plugW(id); ok(); }; s.onerror = ok; document.body.append(s); });
// 插件有首页小组件的：第一次打开时自动放到首页一次（之后移走了就不再加）
const plugW = async id => { const w = window.TwinPlugins?.[id]?.widget; if (!w) return; let ls; setPref('plugWs', JSON.stringify({ ...plugWs(), [id]: w.name }));
  if (!pref('w.' + id + 'Added', '')) { setPref('w.' + id + 'Added', '1');
    ls = await api('/api/home/links').then(j => j.links.some(x => x.url === 'twin:' + id) ? j.links : api('/api/home/links', { action: 'add', name: w.name, url: 'twin:' + id }).then(r => r.links)).catch(() => null); }
  viewHome.plugW?.(id, w, ls); };
// 插件管理：侧栏抽屉里的“插件”打开。一个插件一张卡片，“设置”在卡片下面折叠展开，移除就在这一行确认
function plugDlg() { setPref('setTab', 'plug'); if (location.hash === '#settings') route(); else location.hash = 'settings'; }
// 安装插件：上传 zip
function plugInst(root) { const f = root.querySelector('#plFile'); root.querySelector('#plInst').onclick = () => f.click();
  f.onchange = async () => { const z = f.files[0]; f.value = ''; if (!z) return;
    const data = await new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = no; r.readAsDataURL(z); });
    try { const r = await api('/api/plugins/install', { name: z.name, data }); toast(`装好了“${r.plugins.find(x => x.id === r.id)?.name || r.id}”，默认关着，打开开关就能用`, 6000); drawPlugins(); } catch (e) { toast(e.message, 7000); } }; }
// 一行一个插件：名字、一句说明、设置（开着才有）、移除、开关。
// 关掉时调用插件自己的 stop() 收拾干净、拿掉脚本，不刷新页面；插件没写 stop 的，下次打开 TWIN 才彻底不加载
const unloadPlugin = id => { const ws = plugWs(); delete ws[id]; setPref('plugWs', JSON.stringify(ws)); viewHome.plugW?.(id, null); try { window.TwinPlugins?.[id]?.stop?.(); } catch (e) {} if (window.TwinPlugins) delete window.TwinPlugins[id]; document.querySelector(`script[data-plugin="${id}"]`)?.remove(); };
async function drawPlugins() { const el = $('#plugList'); if (!el) return; const ps = await api('/api/plugins').catch(() => []);
  el.innerHTML = `${ps.map(p => `<div class="plc" data-id="${esc(p.id)}"><div class="plr"><span class="plt"><b>${esc(p.name)}</b><small title="${esc(p.desc)}">${esc(p.desc)}</small></span>
      ${p.on ? `<button type="button" class="btn sm" data-pset aria-expanded="false">设置${lu('chevron-down', 14)}</button>` : ''}
      <button type="button" class="btn sm danger" data-pm>移除</button>
      <button type="button" class="plsw" role="switch" aria-checked="${p.on}" data-pl aria-label="${p.on ? '关闭' : '打开'} ${esc(p.name)}"><i></i></button></div><div class="plpanel" hidden></div></div>`).join('') || '<p class="note">还没有插件，点下面的“安装插件”装一个。</p>'}`;
  const pOf = b => ps.find(x => x.id === b.closest('.plc').dataset.id);
  el.querySelectorAll('[data-pl]').forEach(c => c.onclick = async () => { const on = c.getAttribute('aria-checked') !== 'true', id = pOf(c).id;
    c.setAttribute('aria-checked', on);  // 开关先动，不等请求
    try { await api('/api/plugins', { id, on }); } catch (e) { c.setAttribute('aria-checked', !on); return toast(e.message); }
    if (on) await loadPlugin(id); else unloadPlugin(id);
    drawPlugins(); });
  // 设置：在卡片下面展开 / 收起，插件自己画里面的内容
  el.querySelectorAll('[data-pset]').forEach(b => b.onclick = () => { const box = b.closest('.plc').querySelector('.plpanel'), open = box.hidden;
    box.hidden = !open; b.setAttribute('aria-expanded', open); b.closest('.plc').classList.toggle('open', open); if (!open) return (box.innerHTML = '');
    const pl = window.TwinPlugins?.[pOf(b).id]; if (pl?.panel) pl.panel(box); else box.innerHTML = '<p class="note">这个插件没有设置项。</p>'; });
  // 移除：这一行就地变成确认，不另开弹窗
  el.querySelectorAll('[data-pm]').forEach(b => b.onclick = () => { const p = pOf(b), row = b.closest('.plr');
    row.classList.add('ask'); row.innerHTML = `<span class="plt"><b>移除“${esc(p.name)}”？</b><small>移到 _export/已移除插件/，升级也不会装回来；它在知识库里的资料不删。</small></span>
      <button type="button" class="btn sm" data-no>取消</button><button type="button" class="btn sm danger" data-yes>移除</button>`;
    row.querySelector('[data-no]').onclick = drawPlugins;
    row.querySelector('[data-yes]').onclick = async () => { try { await api('/api/plugins/remove', { id: p.id }); unloadPlugin(p.id); drawPlugins(); toast(`已移除“${p.name}”`); } catch (e) { toast(e.message, 6000); } }; });
}

// ---------------- 检查更新：每天最多问一次发布页，只在设置里升级 ----------------
let upInfo = {};
const checkUp = force => api('/api/update' + (force ? '?force=1' : '')).then(r => upInfo = r).catch(e => upInfo = { ...upInfo, error: e.message });
function drawUp() { const el = $('#upInfo'); if (!el) return; const u = upInfo;
  el.textContent = `现在是 ${u.current || ''}。` + (u.enabled === false ? '这一份没有配置更新来源。' : u.error ? u.error : u.newer ? `有新版本 ${u.latest}。资料、对话、密码不会动，升级前会先备份程序。` : u.latest ? '已经是最新版。' : '');
  el.title = u.newer && u.notes ? u.notes : u.detail || ''; $('#upGo').hidden = !u.newer; }

// ---------------- 自动锁定：一直没有操作（点、打字、滚动、移动鼠标）才锁；在用就不锁 ----------------
// 到点前 1 分钟顶上居中一条倒计时（标签页标题也跟着倒数），动一下就取消。服务器那边每 20 秒最多续一次，后台自己发的请求不算操作
const lockNow = () => api('/api/logout', {}).catch(() => {}).then(() => location.reload());
function lockTimer(j) { clearTimeout(lockTimer.w); clearTimeout(lockTimer.t); clearInterval(lockTimer.i); lockTimer.min = j.min;
  if (document.getElementById('lockWarn')) { document.getElementById('lockWarn').remove(); document.title = $('#topTitle').textContent === 'TWIN' ? 'TWIN' : $('#topTitle').textContent + ' · TWIN'; }
  if (!j.min) return; const ms = j.left * 1000, end = Date.now() + ms;
  lockTimer.w = setTimeout(() => { const el = document.createElement('div'); el.id = 'lockWarn'; el.setAttribute('role', 'alert'); el.innerHTML = `${lu('lock', 16)}<span></span>`; document.body.append(el);
    const tick = () => { const s = Math.max(0, Math.ceil((end - Date.now()) / 1000)); el.querySelector('span').textContent = `一直没有操作，${s} 秒后自动锁定（动一下就不锁）`; document.title = `${s} 秒后锁定 · TWIN`; };
    tick(); lockTimer.i = setInterval(tick, 1000); }, Math.max(0, ms - 60000));
  lockTimer.t = setTimeout(lockNow, ms); }
const lockAct = () => { const m = lockTimer.min; if (!m) return; const now = Date.now();
  if (now - (lockAct.t || 0) < 3000 && !document.getElementById('lockWarn')) return; lockAct.t = now;
  lockTimer({ min: m, left: m * 60 });
  if (now - (lockAct.s || 0) > 20000) { lockAct.s = now; api('/api/lock/touch', {}).catch(() => {}); } };
['pointerdown', 'pointermove', 'keydown', 'wheel', 'touchstart'].forEach(t => addEventListener(t, lockAct, { passive: true, capture: true }));
// 切回这个标签页：服务器那边已经过期就锁上，没过期就算一次操作
const lockSync = () => api('/api/lock').then(j => { lockTimer.min = j.min; if (j.left <= 0) return lockNow(); lockAct.s = 0; lockAct.t = 0; lockAct(); }).catch(() => {});
// ---------------- 启动 ----------------
function inboxBadge(n) { inboxBadge.n = n; window.TwinUI?.bus.dispatchEvent(new CustomEvent('inbox', { detail: n })); }
(async () => { try { files = await api('/api/tree'); } catch (e) {} loadHist(); route();
  // 画像没填完时自动弹向导，但 7 天里最多自动弹一次（点“以后再说”、✕、Esc 都算）；设置里随时能手动打开
  api('/api/profile').then(p => { setPref('name', p.name);
    if (!p.done && Date.now() - (+pref('wizShown', 0) || 0) > 7 * 864e5) { setPref('wizShown', Date.now()); setupWizard(p); } }).catch(() => {}); api('/api/inbox').then(d => { viewInbox.d = viewInbox.d || d; inboxBadge(d.items.length); }).catch(() => {});
  // 本机记着有小组件、但已经关掉或删掉的插件：拿掉首页给它占的位置
  api('/api/plugins').then(ps => { Object.keys(plugWs()).filter(k => !ps.some(p => p.on && p.id === k)).forEach(unloadPlugin); ps.filter(p => p.on).forEach(p => loadPlugin(p.id)); }).catch(() => {});
  lockSync(); document.addEventListener('visibilitychange', () => { if (!document.hidden) lockSync(); });
  checkUp().then(u => { drawUp(); if (u.newer && pref('upSeen') !== u.latest) { setPref('upSeen', u.latest); toast(`有新版本 ${u.latest}，在“设置 → 版本”里升级`, 8000); } }); })();
