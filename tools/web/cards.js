// 卡片页：资产、人脉……一张卡就是一个 md 文件，字段写在 Frontmatter 里。
// 每种卡片的字段、分组由后端 twin_cards.py 的 KINDS 定义，这里按定义画，不写死某一种。
// 依赖 app.js 里的 $、esc、api、toast、modal、closeModal、setTitle、render、libLink、today。

const cardState = {}; // kind -> { group, status, q }
const AVATAR = { device: '💻', digital: '🔑', tool: '🛠', parts: '🔌', physical: '📦' };

async function viewCards(kind) {
  let d; try { d = await api('/api/cards?kind=' + kind); } catch (e) { return toast(e.message); }
  const S = d.schema, st = cardState[kind] || (cardState[kind] = { group: '', status: '', q: '' });
  setTitle(S.title);
  const F = Object.fromEntries(S.fields.map(f => [f.key, f]));
  const optName = (key, v) => ((F[key].options || []).find(o => o[0] === v) || [v, v])[1];
  const shown = () => d.items.filter(c => (!st.group || c[S.group] === st.group) && (!st.status || c[S.badge] === st.status)
    && (!st.q || JSON.stringify([c.name, ...S.sub.map(k => c[k]), c.body]).toLowerCase().includes(st.q.toLowerCase())));
  const count = g => d.items.filter(c => c[S.group] === g).length;
  const val = (c, k) => Array.isArray(c[k]) ? c[k].map(x => String(x).replace(/^\[\[(?:.*\|)?([^\]]*)\]\]$/, '$1')).join('、') : c[k];
  const card = (c, i) => {
    const badge = c[S.badge], sub = S.sub.map(k => val(c, k)).filter(Boolean).join(' · ') || c.summary;
    const meta = S.meta.map(k => val(c, k) ? `<span><i>${esc(F[k].label)}</i>${esc(val(c, k))}</span>` : '').join('');
    return `<button type="button" class="ccard" data-i="${i}">
      <div class="ctop"><span class="cav" aria-hidden="true">${kind === 'people' ? esc((c.name || '?').slice(0, 1)) : AVATAR[c.category] || '📦'}</span>
        <span class="cname">${esc(c.name)}${sub ? `<small>${esc(sub)}</small>` : ''}</span>
        ${badge ? `<span class="cbadge b-${esc(badge)}">${esc(optName(S.badge, badge))}</span>` : ''}</div>
      ${meta ? `<div class="cmeta">${meta}</div>` : ''}
      ${c.log.length ? `<div class="clog">${esc(c.log.at(-1))}</div>` : ''}</button>`;
  };
  const draw = () => {
    const xs = shown();
    $('#cgrid').innerHTML = xs.map(c => card(c, d.items.indexOf(c))).join('') ||
      `<p class="note">${d.items.length ? '没有符合条件的卡片。' : `还没有${S.noun}卡片。点右上角“新建”。`}</p>`;
    $('#cgrid').querySelectorAll('.ccard').forEach(b => b.onclick = () => openCard(kind, S, d.items[+b.dataset.i]));
    document.querySelectorAll('#cgroups button').forEach(b => b.classList.toggle('on', b.dataset.g === st.group));
    document.querySelectorAll('#cstatus button').forEach(b => b.classList.toggle('on', b.dataset.s === st.status));
  };
  const statusOpts = S.badge !== S.group ? F[S.badge].options : null;
  $('#view').innerHTML = `<div class="wrap page wide"><div class="dayhead"><h1>${esc(S.title)}</h1><span class="sub">${d.items.length} 张 · 私密，只在本机显示，不发给 AI</span>
      <span class="sp"></span><button class="btn primary" id="cnew">新建</button></div>
    <div class="cbar2"><input id="cq" type="search" placeholder="${kind === 'people' ? '搜名字、城市、擅长、记录' : '搜名字、型号、备注'}" value="${esc(st.q)}">
      <div class="segs" id="cgroups"><button type="button" data-g="">全部</button>${S.groups.map(g => count(g[0]) ? `<button type="button" data-g="${esc(g[0])}">${esc(g[1])}<small>${count(g[0])}</small></button>` : '').join('')}</div>
      ${statusOpts ? `<div class="segs" id="cstatus"><button type="button" data-s="">全部状态</button>${statusOpts.map(o => `<button type="button" data-s="${esc(o[0])}">${esc(o[1])}</button>`).join('')}</div>` : ''}</div>
    <div class="cgrid" id="cgrid"></div>
    <p class="foot">每张卡是 <code>${esc(kind === 'assets' ? '06_Assets' : '05_Network')}</code> 下的一个 md 文件，在 Obsidian 里改也行。改动都能在<a href="#history">改动历史</a>里撤销。
      ${kind === 'assets' ? '<button class="linkbtn" id="cimp">从旧的资产总清单导入</button>' : ''}</p></div>`;
  $('#cq').oninput = e => { st.q = e.target.value; draw(); };
  document.querySelectorAll('#cgroups button').forEach(b => b.onclick = () => { st.group = b.dataset.g; draw(); });
  document.querySelectorAll('#cstatus button').forEach(b => b.onclick = () => { st.status = b.dataset.s; draw(); });
  $('#cnew').onclick = () => openCard(kind, S, null);
  const imp = $('#cimp'); if (imp) imp.onclick = async () => {
    const m = modal(`<h3>从资产总清单导入</h3><p class="note">把 <code>Asset_List.md</code> 里已经填了内容的行变成一张张卡片，再从表里拿掉这些行。只有名字、其他格子都空着的行留在表里。传感器那节是清点用的，不导入。可以在改动历史里一键撤销。</p>
      <div class="row"><button class="btn" id="mx">取消</button><button class="btn primary" id="mok">导入</button></div>`);
    m.querySelector('#mx').onclick = closeModal;
    m.querySelector('#mok').onclick = async () => { try { const r = await api('/api/cards/import', {}); closeModal(); toast(r.message); viewCards(kind); } catch (e) { toast(e.message, 6000); } };
  };
  draw();
}

function openCard(kind, S, c) {
  const isNew = !c; c = c || { name: '', body: '', log: [] };
  const input = f => {
    const v = c[f.key] ?? (f.type === 'list' ? [] : '');
    if (f.type === 'readonly') return `<div class="field"><label>${esc(f.label)}</label><div class="ro">${esc(v || '—')}${f.hint ? `<small>${esc(f.hint)}</small>` : ''}</div></div>`;
    if (f.type === 'select') return `<div class="field"><label>${esc(f.label)}</label><select data-k="${f.key}"><option value="">—</option>${f.options.map(o => `<option value="${esc(o[0])}" ${o[0] === v ? 'selected' : ''}>${esc(o[1])}</option>`).join('')}</select></div>`;
    const shown = f.type === 'list' ? v.join('，') : v;
    return `<div class="field ${f.key === 'name' ? 'wide' : ''}"><label>${esc(f.label)}</label><input data-k="${f.key}" value="${esc(shown)}" ${f.hint ? `placeholder="${esc(f.hint)}"` : ''}></div>`;
  };
  const m = modal(`<div class="csheet"><h3>${isNew ? `新建${esc(S.noun)}` : esc(c.name)}</h3>
    <div class="cform">${S.fields.filter(f => !(isNew && f.type === 'readonly')).map(input).join('')}</div>
    ${isNew ? '' : `<div class="lbl">记录</div><ul class="clogs">${c.log.map(l => `<li>${esc(l)}</li>`).join('') || '<li class="note">还没有记录。</li>'}</ul>
      <div class="addlog"><input id="clog" placeholder="${kind === 'people' ? '比如：电话聊了南瓜的眼睛图案，她 10-28 前定稿' : '比如：借给小王了 / 换了新电池'}"><button class="btn" id="clogb">记一笔</button></div>
      <details class="cbody"><summary class="note">正文（备注、用途，md 格式）</summary><textarea id="cbody" rows="10">${esc(c.body)}</textarea></details>`}
    <div class="row">${isNew ? '' : `<a class="btn" href="${libLink(c.path)}">打开文件</a><button class="btn danger" id="cdel">删除</button>`}<span class="sp"></span>
      <button class="btn" id="mx">取消</button><button class="btn primary" id="cok">保存</button></div></div>`);
  m.classList.add('wide');
  m.querySelector('#mx').onclick = closeModal;
  const fields = () => Object.fromEntries([...m.querySelectorAll('[data-k]')].map(x => [x.dataset.k, x.value]));
  const done = async (p, msg) => { closeModal(); if (msg) toast(msg); viewCards(kind); };
  m.querySelector('#cok').onclick = async () => {
    const f = fields(); if (!f.name.trim()) return toast('先写名字');
    const body = !isNew && m.querySelector('#cbody').value !== c.body ? m.querySelector('#cbody').value : undefined;
    try { const r = await api('/api/cards/save', { kind, path: isNew ? '' : c.path, fields: f, body }); done(r.path); } catch (e) { toast(e.message, 6000); } };
  if (isNew) { m.querySelector('[data-k=name]').focus(); return; }
  const lb = m.querySelector('#clogb'), li = m.querySelector('#clog');
  lb.onclick = async () => { if (!li.value.trim()) return li.focus();
    try { await api('/api/cards/log', { kind, path: c.path, text: li.value }); done(); } catch (e) { toast(e.message, 6000); } };
  li.onkeydown = e => { if (e.key === 'Enter' && !e.isComposing) lb.click(); };
  m.querySelector('#cdel').onclick = async () => { if (!confirm(`删掉“${c.name}”这张卡片？可以在改动历史里撤销。`)) return;
    try { const r = await api('/api/cards/delete', { kind, path: c.path }); done(null, r.message); } catch (e) { toast(e.message, 6000); } };
}
