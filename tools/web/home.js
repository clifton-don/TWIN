'use strict';
// 首页（时钟、搜索、小组件、图标网格）、要闻
// 普通 <script>，和 app.js 共用全局变量和函数；index.html 里按 app → chat → day → home → todo → pages 的顺序加载

// ---------------- 首页：时钟、搜索、常用网站、天气、时间进度、今天 ----------------
// 设成浏览器主页（地址后面加 #home）就能代替 iTab 这类插件；天气本机从 Open-Meteo 取，AI 只看到地点名、天气数字和作息
const ENG = [['twin', '知识库', ''], ['bing', '必应', 'https://www.bing.com/search?q='], ['baidu', '百度', 'https://www.baidu.com/s?wd='],
  ['google', 'Google', 'https://www.google.com/search?q='], ['github', 'GitHub', 'https://github.com/search?q='],
  ['bili', 'B 站', 'https://search.bilibili.com/all?keyword='], ['scholar', '学术', 'https://scholar.google.com/scholar?q=']];
// 天气详情：逐小时和注意事项，AI 提醒点了才生成
function wxDialog(w) { const h0 = new Date().getHours(); const nh = h0 < 3 ? h0 + 24 : h0, hrs = w.hours.filter(x => x.h >= nh).filter((x, i) => i % 2 === 0).slice(0, 7), hasAi = aiCfg.providers.length;
  const tl = t => (t || []).map(x => `<li>${esc(x)}</li>`).join('') || '<li>今天天气平稳，没什么要注意的。</li>';
  const m = modal(`<div class="wxh">${lu(wxIcon(w.now.icon, h0), 34)}<div><b>${Math.round(w.now.t)}°</b><span>${esc(w.now.text)} · 体感 ${Math.round(w.now.feel)}°</span><small>${esc(w.place)} · ${Math.round(w.today.min)}～${Math.round(w.today.max)}° · 降雨 ${w.today.rain}%${w.stale ? ' · 离线' : ''}</small></div></div>
    ${hrs.length ? `<div class="wxhr">${hrs.map(x => `<span title="${x.h % 24} 点，降雨概率 ${x.rain}%"><em>${x.h % 24}</em>${lu(wxIcon(x.icon, x.h), 16)}<b>${Math.round(x.t)}°</b><u style="--r:${x.rain}%"></u></span>`).join('')}</div>` : ''}
    <ul class="wxtips" id="mWxT">${tl(w.ai_tips || w.local_tips)}</ul>
    <div class="row">${hasAi && !w.ai_tips ? '<button class="btn" id="mWxAi">让 AI 结合作息看看</button>' : ''}<a class="btn" href="${libLink('_RULES/Weather_Rhythm.md')}" id="mWxSet">改地点和作息</a><button class="btn primary" id="mx">关闭</button></div>`);
  m.querySelector('#mx').onclick = closeModal; m.querySelector('#mWxSet').addEventListener('click', closeModal);
  const b = m.querySelector('#mWxAi'); if (b) b.onclick = async () => { b.textContent = 'AI 正在看…'; b.disabled = true;
    try { const nw = await api('/api/weather/tips', {}); w.ai_tips = nw.ai_tips; m.querySelector('#mWxT').innerHTML = tl(nw.ai_tips); b.remove(); } catch (e) { b.textContent = '让 AI 结合作息看看'; b.disabled = false; toast(e.message, 6000); } }; }
// ---------------- 首页小组件 ----------------
// 一个小组件一段，key 对应 _RULES/Home_Links.md 里的 twin:key（表里有这一行才显示，首页“添加 → 小组件”能加回来）
// name：显示名；desc、icon：在“添加”里显示；href：点了去哪（不写就是按钮，在 draw 里设 box.onclick）
// load(put)：取数据，每取到一份调一次 put(data)，可以调多次（比如先显示“正在取”，取到再换）
// draw(box, data)：把数据画进小组件（细节写进 box.dataset.tip，鼠标停留时显示）；keep(data)：返回真时把这份数据存在本机，下次打开首页先画它（适合要上网取、会慢的）
const WIDGETS = {
  weather: { name: '天气', desc: '现在的天气，点开看逐小时', icon: 'cloud-sun', keep: d => d.weather,
    load: put => api('/api/weather').then(put),
    draw: (box, d) => { const w = d.weather, h0 = new Date().getHours();
      if (!w) { box.innerHTML = `<span class="hwt">天气</span><span class="hwn">取不到</span>`; box.dataset.tip = d.error || ''; return; }
      const tips = w.local_tips || [];
      box.innerHTML = `<span class="hwt">${esc(w.place.split('·')[0].trim())}<em>${esc(w.now.text)}</em></span><span class="hwbig">${Math.round(w.now.t)}°${lu(wxIcon(w.now.icon, h0), 30)}</span>
        <span class="hwn">${Math.round(w.today.min)}～${Math.round(w.today.max)}° · 降雨 ${w.today.rain}%</span><span class="hwn">${tips.length ? `有 ${tips.length} 条提醒` : '今天没什么要注意的'}</span>`;
      box.dataset.tip = [`${w.place} · ${w.now.text} ${Math.round(w.now.t)}°，体感 ${Math.round(w.now.feel)}°`, `最高 ${Math.round(w.today.max)}° 最低 ${Math.round(w.today.min)}° · 降雨 ${w.today.rain}%`, ...tips].join('\n');
      box.onclick = () => wxDialog(w); } },
  // 小组件只放几个字和一个大数字，放得下；细节在鼠标停留的提示里（data-tip）
  today: { name: '今天', desc: '要做几件、最近的截止', icon: 'list-checks', href: '#today',
    load: put => Promise.all([api('/api/home'), api('/api/rhythm').catch(() => ({}))]).then(([h, r]) => put({ h, r })),
    draw: (box, { h, r }) => { const all = (h.boards || []).flatMap(b => (h.next || {})[b.path] || []), nowN = all.filter(isNow).length;
      const dated = all.filter(x => x.days != null && x.days > 0).sort((a, b) => a.days - b.days), d1 = dated[0]?.days, n1 = dated.filter(x => x.days === d1).length;
      // 现在的作息时段
      const bl = r.blocks || [], t0 = bl.length ? mins(bl[0].start) : 0, norm = m => (m < t0 ? m + 1440 : m), d0 = new Date(), nowM = norm(d0.getHours() * 60 + d0.getMinutes());
      const cur = bl.find(b => { const a = norm(mins(b.start)); let e = norm(mins(b.end)); if (e <= a) e += 1440; return nowM >= a && nowM < e; });
      box.innerHTML = `<span class="hwt">今天<em>${cur ? esc(cur.name) : ''}</em></span><span class="hwbig">${nowN}<small>件要做</small></span>
        <span class="hwn">${d1 ? `${d1 === 1 ? '明天' : `${d1} 天后`}截止 ${n1} 件` : '近期没有截止'}</span>`;
      const due = x => x.days == null ? '' : x.days < 0 ? `（过期 ${-x.days} 天）` : x.days === 0 ? '（今天）' : x.days === 1 ? '（明天）' : `（${x.days} 天后）`;
      const list = all.filter(x => x.days != null).sort((a, b) => a.days - b.days).slice(0, 6);
      box.dataset.tip = [cur ? `现在：${cur.name} · ${cur.what}` : '', ...list.map(x => `· ${x.text}${due(x)}`)].filter(Boolean).join('\n'); } },
  sug: { name: '今日建议', desc: 'AI 给今天的几条建议，点开采纳', icon: 'lightbulb',
    load: async put => { await loadAi().catch(() => {}); const sg = (await api('/api/home')).suggest || null; put(sg);
      if (!sg && aiCfg.providers.length && sugAuto() && onceToday('sug')) { await api('/api/suggest', {}, { quiet: true }).catch(() => {}); put((await api('/api/home')).suggest || null); } },
    draw: (box, sg) => { const n = sugNew(sg);
      box.innerHTML = `<span class="hwt">今日建议</span>${n.length ? `<span class="hwbig">${n.length}<small>条待看</small></span><span class="hwn">点开采纳</span>`
        : `<span class="hwov">${sg ? '都看完了' : aiCfg.providers.length ? '还没生成' : '接入 AI 后才有'}</span><span class="hwn">${sg ? '明天再来' : aiCfg.providers.length ? '点开生成' : ''}</span>`}`;
      box.dataset.tip = n.map(x => `· ${x.title}`).join('\n');
      box.onclick = () => sugDlg(sg, box); } },
  // 要闻：今天的一句话总结，每天第一次打开首页时自动取一次
  news: { name: '要闻', desc: '今天的要闻总结', icon: 'newspaper', href: '#news',
    load: async put => { await loadAi().catch(() => {}); const nw = await api('/api/news'), has = nw && nw.items; put(has ? nw : {});
      if (!has && aiCfg.providers.length && onceToday('news')) { put({ msg: '正在取今天的要闻…' }); put(await api('/api/news', {}, { quiet: true }).catch(e => ({ msg: e.message }))); } },
    draw: (box, nw) => { const n = (nw.items || []).length;
      box.innerHTML = `<span class="hwt">要闻</span>${n ? `<span class="hwbig">${n}<small>条和你有关</small></span><span class="hwn">点开看总结</span>`
        : `<span class="hwov">${esc(nw.msg || (aiCfg.providers.length ? '今天还没取' : '接入 AI 后才有'))}</span>`}`;
      box.dataset.tip = n ? [nw.overview, ...nw.items.slice(0, 6).map(x => `· ${x.title}`)].filter(Boolean).join('\n') : ''; } },
};
// 插件的小组件：开着的插件写了 TwinPlugins[id].widget（格式同上），就和自带的一样能放到首页，key 是插件 id
// plugWs：开着的插件小组件 {id: 名字}，存在本机，首页先给它们占位
const plugWs = () => { try { return JSON.parse(pref('plugWs', '{}')); } catch (e) { return {}; } };
const allW = () => ({ ...Object.fromEntries(Object.entries(window.TwinPlugins || {}).filter(([, p]) => p.widget).map(([k, p]) => [k, p.widget])), ...WIDGETS });
async function viewHome() {
  setTitle('首页'); const ok = fresh(); loadAi().catch(() => {});
  let eng = pref('engine', 'bing'); if (!ENG.some(e => e[0] === eng)) eng = 'bing';
  const engName = () => ENG.find(e => e[0] === eng)[1];
  $('#view').innerHTML = `<div class="home">
    <div class="hcorner"><button type="button" class="ib modeBtn" aria-label="切换白天黑夜"></button></div>
    <div class="hhero"><b id="hClock"></b><span id="hDate"></span></div>
    <form class="hsearch" id="hSearch" role="search"><button type="button" class="hengb" id="hEng" aria-haspopup="listbox" title="换搜索引擎（输入框里按 Tab 也行）"><span id="hEngN"></span>${lu('chevron-down', 14)}</button>
      <input id="hQ" autocomplete="off" placeholder="输入搜索内容" aria-label="搜索"><button class="hgo" aria-label="搜索">${lu('search', 19)}</button>
      <div class="hengm" id="hEngM" role="listbox" hidden>${ENG.map(e => `<button type="button" role="option" data-eng="${e[0]}">${e[1]}</button>`).join('')}</div></form>
    <div class="hgrid" id="hGrid"></div><div hidden id="hPool"></div></div>`;
  // 小组件（WIDGETS）：先画上次的（存在本机的数据，或者上次离开首页时的样子），新数据到了再换，不会先空一下
  const wbox = {}, addW = (k, w) => { const c = document.createElement('div'), tag = w.href ? 'a' : 'button'; c.className = 'hwc';
    c.innerHTML = `<${tag} class="hw" ${w.href ? `href="${w.href}"` : 'type="button"'} aria-label="${w.name}"></${tag}><span class="hln">${w.name}</span>`;
    $('#hPool').append(c); const box = wbox[k] = c.firstChild, saved = w.keep && (() => { try { return JSON.parse(pref('w.' + k, 'null')); } catch (e) {} })();
    if (saved) w.draw(box, saved); else if (viewHome.c[k]) box.innerHTML = viewHome.c[k];
    w.load(d => { if (!ok()) return; w.draw(box, d); if (w.keep?.(d)) setPref('w.' + k, JSON.stringify(d)); snap(k, box); }).catch(() => {});
    // 右键：从首页移走（“添加 → 小组件”里能加回来）
    c.oncontextmenu = e => popMenu(e, [['从首页移走', async () => { const i = items.findIndex(x => x.url === 'twin:' + k);
      try { draw((await api('/api/home/links', { action: 'del', i })).links); toast(`移走了“${w.name}”，在“添加 → 小组件”里能加回来`); } catch (er) { toast(er.message, 6000); } }]]); };
  // 首次打开也不空着、不跳：上次的小组件样子和图标表都存在本机，先画出来，新数据到了再换。
  // 插件的小组件在插件脚本加载完之前先占好位置（ph 里是占位的），免得加载完插进来把后面的图标挤开
  viewHome.c ||= (() => { try { return JSON.parse(pref('homeSnap', '{}')); } catch (e) { return {}; } })();
  const snap = (k, b) => { viewHome.c[k] = b.innerHTML; clearTimeout(snap.t); snap.t = setTimeout(() => setPref('homeSnap', JSON.stringify(viewHome.c)), 500); }, ph = new Set();
  Object.entries(allW()).forEach(([k, w]) => addW(k, w));
  Object.entries(plugWs()).forEach(([k, name]) => { if (!wbox[k]) { addW(k, { name, load: async () => {}, draw() {} }); ph.add(k); } });
  viewHome.save = () => Object.entries(wbox).forEach(([k, b]) => { viewHome.c[k] = b.innerHTML; });
  // 时钟：时分秒 + 日期 + 农历（浏览器自带农历历法，不用联网）
  let lunar = ''; try { lunar = new Intl.DateTimeFormat('zh-CN-u-ca-chinese', { month: 'long', day: 'numeric' }).format(new Date()).replace(/^\d+年/, ''); } catch (e) {}
  const tick = () => { if (!ok() || !$('#hClock')) return clearInterval(tick.t); const d = new Date(), p2 = n => String(n).padStart(2, '0');
    $('#hClock').textContent = `${p2(d.getHours())}:${p2(d.getMinutes())}:${p2(d.getSeconds())}`;
    $('#hDate').textContent = `${d.getMonth() + 1}月${d.getDate()}日  星期${'日一二三四五六'[d.getDay()]}  ${lunar}`; };
  drawModeBtns(); tick(); tick.t = setInterval(tick, 1000);
  // 搜索：左边选引擎，Tab 也能换；“知识库”直接搜 TWIN
  const menu = $('#hEngM'), setEng = k => { eng = k; setPref('engine', k); $('#hEngN').textContent = engName(); menu.hidden = true; };
  setEng(eng);
  $('#hEng').onclick = () => { menu.hidden = !menu.hidden; };
  menu.querySelectorAll('[data-eng]').forEach(b => b.onclick = () => { setEng(b.dataset.eng); $('#hQ').focus(); });
  $('#hQ').onkeydown = e => { if (e.key === 'Tab' && !e.shiftKey) { e.preventDefault(); const i = ENG.findIndex(x => x[0] === eng); setEng(ENG[(i + 1) % ENG.length][0]); } };
  $('#hSearch').onsubmit = e => { e.preventDefault(); const q = $('#hQ').value.trim(); if (!q) return;
    const en = ENG.find(x => x[0] === eng); if (!en[2]) return window.TwinUI?.bus.dispatchEvent(new CustomEvent('palette', { detail: q }));
    window.open(en[2] + encodeURIComponent(q), '_blank', 'noopener'); $('#hQ').value = ''; };
  if (!coarse) $('#hQ').focus();
  // 图标网格：小组件（twin:名字）和常用网站排在一起，顺序和文件夹都存在 _RULES/Home_Links.md
  // 拖到另一个图标正中间 = 放进同一个文件夹；拖到两边 = 插到它前面或后面
  const wkey = u => u.startsWith('twin:') ? u.slice(5) : '';
  let items = [];
  // 取不到网站图标时显示首字，底色按名字算，同一个网站每次颜色一样
  const hue = t => [...t].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);
  const icon = x => { let host = ''; try { host = new URL(x.url).origin; } catch (e) {}
    if (x.icon && host) return `<span class="hli hsvg"><img src="/api/home/icon?h=${encodeURIComponent(new URL(host).hostname.replace(/^www\./, ''))}&v=${x.icon}" alt="" draggable="false"></span>`;
    return `<span class="hli lt" style="--lc:hsl(${hue(x.name)} 55% 52%)" data-c="${esc(x.name.slice(0, 1))}">${host ? `<img src="${esc(host)}/favicon.ico" alt="" loading="lazy" draggable="false" onload="this.parentNode.classList.remove('lt')" onerror="this.remove()">` : ''}</span>`; };
  const tilesOf = ls => { const out = [], seen = {};
    ls.forEach((x, i) => { if (wkey(x.url)) { if (wbox[wkey(x.url)]) out.push({ k: 'w', ix: [i] }); }
      else if (x.folder) { if (seen[x.folder]) seen[x.folder].ix.push(i); else out.push(seen[x.folder] = { k: 'f', name: x.folder, ix: [i] }); }
      else out.push({ k: 'l', ix: [i] }); });
    return out; };
  // 只剩一个网站的文件夹自动解散
  // 同一个文件夹的网站在表里挨在一起（放在文件夹第一次出现的位置），这样“插到文件夹后面”就是紧跟在文件夹后面
  const tidy = ls => { const n = {}; ls.forEach(x => { if (x.folder) n[x.folder] = (n[x.folder] || 0) + 1; });
    ls = ls.map(x => (x.folder && n[x.folder] < 2 ? { ...x, folder: '' } : x));
    return tilesOf(ls).flatMap(t => t.ix.map(k => ls[k])); };
  const save = async ls => { ls = tidy(ls); const old = items; draw(ls);
    try { draw((await api('/api/home/links', { action: 'layout', layout: ls })).links); } catch (er) { toast(er.message, 6000); draw(old); } };
  // 拖动：drag 记着正在拖的是哪几项（网格里的一个图标 / 整个文件夹 / 文件夹里的一个网站）
  let drag = null, fold = null;
  const zoneOf = (e, el, canIn) => { const ic = el.querySelector('.hli') || el, r = ic.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
    if (canIn && x > .18 && x < .82 && y > .05 && y < .95) return 'in';
    const b = el.getBoundingClientRect(); return e.clientX - b.left < b.width / 2 ? 'before' : 'after'; };
  const clearMarks = () => document.querySelectorAll('.home .drag,.home .in,.home .before,.home .after').forEach(x => x.classList.remove('drag', 'in', 'before', 'after'));
  const newFolderName = () => { const used = new Set(items.map(x => x.folder)); let n = 1; while (used.has(n === 1 ? '文件夹' : '文件夹' + n)) n++; return n === 1 ? '文件夹' : '文件夹' + n; };
  // 把 drag 里的项挪到 target（一组下标）的前面 / 后面 / 里面（文件夹）；target 为空就放到最后
  const moveTo = (target, z, tk, tname) => { if (!drag) return; const d = drag; drag = null; clearMarks();
    // 从文件夹里拖出来放回这个文件夹旁边时，目标里去掉正在拖的那一项
    if (target) { target = target.filter(k => !d.ix.includes(k)); if (!target.length) return; }
    const moving = d.ix.map(k => ({ ...items[k] })), rest = items.filter((x, k) => !d.ix.includes(k)), tgt = (target || []).map(k => items[k]);
    let at = tgt.length ? rest.indexOf(z === 'before' ? tgt[0] : tgt[tgt.length - 1]) + (z === 'before' ? 0 : 1) : rest.length;
    if (z === 'in') { const name = tk === 'f' ? tname : newFolderName(); moving.forEach(x => { x.folder = name; }); if (tk === 'l') rest[at - 1] = { ...rest[at - 1], folder: name }; }
    else if (z === 'fold' || tk === 'fi') moving.forEach(x => { x.folder = tname; });
    else if (d.k === 'l') moving.forEach(x => { x.folder = ''; });
    rest.splice(at, 0, ...moving); save(rest); };
  const draw = ls => { if (!ok() || !$('#hGrid')) return; items = viewHome.items = ls; const g = $('#hGrid'), pool = $('#hPool'), tiles = tilesOf(ls);
    [...g.children].forEach(c => { if (c.classList.contains('hwc')) pool.append(c); else c.remove(); });
    tiles.forEach(t => { let el;
      if (t.k === 'w') el = wbox[wkey(ls[t.ix[0]].url)].parentElement;
      else if (t.k === 'l') { const x = ls[t.ix[0]]; el = document.createElement('a'); el.className = 'hl'; el.href = x.url; el.target = '_blank'; el.rel = 'noopener'; el.title = x.url;
        el.innerHTML = `${icon(x)}<span class="hln">${esc(x.name)}</span>`; el.oncontextmenu = e => ctxMenu(e, t); }
      else { el = document.createElement('button'); el.type = 'button'; el.className = 'hl hfold'; el.title = `${t.name}（${t.ix.length} 个）`;
        el.innerHTML = `<span class="hli hfi">${t.ix.slice(0, 4).map(k => icon(ls[k])).join('')}</span><span class="hln">${esc(t.name)}</span>`;
        el.onclick = () => openFolder(t.name); el.oncontextmenu = e => ctxMenu(e, t); }
      el.draggable = !locked();
      el.ondragstart = e => { drag = { ix: t.ix, k: t.k }; e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', ''); setTimeout(() => el.classList.add('drag')); };
      el.ondragend = () => { drag = null; clearMarks(); if (fold && fold.away) closeFolder(); };
      el.ondragover = e => { if (!drag || t.ix.every(k => drag.ix.includes(k))) return; e.preventDefault(); e.stopPropagation(); const z = zoneOf(e, el, t.k !== 'w' && drag.k === 'l');
        if (!el.classList.contains(z)) { el.classList.remove('in', 'before', 'after'); el.classList.add(z); } };
      el.ondragleave = e => { if (!el.contains(e.relatedTarget)) el.classList.remove('in', 'before', 'after'); };
      el.ondrop = e => { e.preventDefault(); e.stopPropagation(); if (!drag) return; moveTo(t.ix, zoneOf(e, el, t.k !== 'w' && drag.k === 'l'), t.k, t.name); };
      g.append(el); });
    const add = document.createElement('button'); add.type = 'button'; add.className = 'hl hladd'; add.title = '加一个网站';
    add.innerHTML = `<span class="hli">${lu('plus', 22)}</span><span class="hln">添加</span>`; add.onclick = () => addSite(); g.append(add);
    if (fold) drawFolder(); };
  // 拖到网格空白处 = 放到最后
  const home = $('.home');
  home.ondragover = e => { if (drag) e.preventDefault(); };
  home.ondrop = e => { e.preventDefault(); if (drag) moveTo(null, 'after'); };
  // 文件夹：点开是一块毛玻璃面板，点外面或按 Esc 关上；里面的网站能拖动排序，拖出面板就回到首页网格
  const closeFolder = () => { if (fold) { fold.el.remove(); fold = null; } document.removeEventListener('keydown', escFold); };
  const escFold = e => { if (e.key === 'Escape') closeFolder(); };
  const openFolder = name => { closeFolder(); const el = document.createElement('div'); el.className = 'hfov';
    el.innerHTML = `<div class="hfbox"><input class="hfname" maxlength="12" aria-label="文件夹名称" title="点一下改名"><div class="hfpanel"><div class="hfgrid"></div></div></div>`;
    home.append(el); fold = { name, el, away: false };
    el.onclick = e => { if (e.target === el || e.target.classList.contains('hfbox')) closeFolder(); };
    document.addEventListener('keydown', escFold);
    const panel = el.querySelector('.hfpanel'), rn = el.querySelector('.hfname');
    // 面板很大、盖住了首页网格（包括这个文件夹自己）。拖着网站离开文件夹里那几个图标的范围，面板就淡出，下面的网格能直接放
    const away = () => { if (fold && !fold.away) { fold.away = true; el.classList.add('away'); } };
    el.ondragover = e => { if (!drag || !drag.from || fold.away) return; const its = [...el.querySelectorAll('.hfgrid > .hl')]; if (!its.length) return away();
      const r = its.reduce((a, x) => { const b = x.getBoundingClientRect(); return { l: Math.min(a.l, b.left), t: Math.min(a.t, b.top), r: Math.max(a.r, b.right), b: Math.max(a.b, b.bottom) }; }, { l: 1e9, t: 1e9, r: -1e9, b: -1e9 });
      if (e.clientX < r.l - 24 || e.clientX > r.r + 24 || e.clientY < r.t - 24 || e.clientY > r.b + 24) away(); };
    rn.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); rn.blur(); } };
    rn.onblur = () => { const nn = rn.value.trim().replace(/\|/g, '').slice(0, 12); if (!fold || !nn || nn === fold.name) { if (fold) rn.value = fold.name; return; }
      if (items.some(x => x.folder === nn)) { toast('已经有同名文件夹了'); rn.value = fold.name; return; }
      const old = fold.name; fold.name = nn; save(items.map(x => (x.folder === old ? { ...x, folder: nn } : x))); };
    drawFolder(); };
  const drawFolder = () => { const mem = items.map((x, k) => [x, k]).filter(([x]) => x.folder === fold.name);
    if (!mem.length) return closeFolder();
    const rn = fold.el.querySelector('.hfname'); if (document.activeElement !== rn) rn.value = fold.name;
    const fg = fold.el.querySelector('.hfgrid'); fg.innerHTML = '';
    mem.forEach(([x, k]) => { const a = document.createElement('a'); a.className = 'hl'; a.href = x.url; a.target = '_blank'; a.rel = 'noopener'; a.title = x.url; a.draggable = !locked();
      a.innerHTML = `${icon(x)}<span class="hln">${esc(x.name)}</span>`; a.oncontextmenu = e => ctxMenu(e, { k: 'l', ix: [k] });
      a.ondragstart = e => { drag = { ix: [k], k: 'l', from: fold.name }; e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', ''); setTimeout(() => a.classList.add('drag')); };
      a.ondragend = () => { drag = null; clearMarks(); if (fold && fold.away) closeFolder(); };
      a.ondragover = e => { if (!drag || drag.ix[0] === k) return; e.preventDefault(); e.stopPropagation(); const z = zoneOf(e, a, false); if (!a.classList.contains(z)) { a.classList.remove('before', 'after'); a.classList.add(z); } };
      a.ondragleave = e => { if (!a.contains(e.relatedTarget)) a.classList.remove('before', 'after'); };
      a.ondrop = e => { e.preventDefault(); e.stopPropagation(); if (!drag) return; moveTo([k], zoneOf(e, a, false), 'fi', fold.name); };
      fg.append(a); });
    // 文件夹里互相拖，落点仍在这个文件夹里
    fg.ondragover = e => { if (drag) { e.preventDefault(); e.stopPropagation(); } };
    fg.ondrop = e => { e.preventDefault(); e.stopPropagation(); if (drag) moveTo(mem.map(([, k]) => k), 'fold', 'f', fold.name); }; };
  // 右键菜单：网站可以编辑、删掉；文件夹可以打开、解散；空白处是添加、锁定布局、搜知识库、白天黑夜、侧栏、设置
  const locked = () => pref('homeLock', '0') === '1';
  const editSite = k => { const x = items[k];
    const md = dlg('编辑网站', '', `<div class="hafl"><label class="haf"><span>名称</span><span class="hain">${lu('type', 15)}<input id="lkN" value="${esc(x.name)}" maxlength="20"></span></label>
      <label class="haf"><span>网址</span><span class="hain">${lu('link', 15)}<input id="lkU" value="${esc(x.url)}"></span></label></div>`,
      `<button class="btn ghost" data-x2>取消</button><button class="btn primary" id="mok">保存</button>`, 'hdsmall');
    md.querySelector('[data-x2]').onclick = closeModal;
    md.querySelector('#mok').onclick = () => { let u = md.querySelector('#lkU').value.trim(); if (!/^https?:\/\//.test(u)) u = 'https://' + u;
      const n = md.querySelector('#lkN').value.trim(); if (!n) return toast('名称要填');
      closeModal(); save(items.map((y, j) => (j === k ? { ...y, name: n, url: u } : y))); }; };
  const ctxMenu = (e, t) => popMenu(e, t.k === 'f'
    ? [['打开', () => openFolder(t.name)], ['解散文件夹', () => save(items.map(x => (x.folder === t.name ? { ...x, folder: '' } : x)))]]
    : [['在新标签页打开', () => window.open(items[t.ix[0]].url, '_blank', 'noopener')], ['编辑', () => editSite(t.ix[0])], ['换图标', () => iconDlg(t.ix[0])],
       ['删掉', () => { const x = items[t.ix[0]]; if (confirm(`删掉“${x.name}”？`)) save(items.filter((y, k) => k !== t.ix[0])); }]]);
  home.oncontextmenu = e => { if (e.target.closest('input,.hfov,.hsearch')) return;
    popMenu(e, [['添加图标或小组件', () => addSite()], ['图标大小', () => sizeDlg()], [locked() ? '解锁布局（可以拖动）' : '锁定布局（防止误拖）', () => { setPref('homeLock', locked() ? '0' : '1'); draw(items); toast(locked() ? '布局已锁定，图标拖不动了' : '布局已解锁'); }],
      ['设置', () => { location.hash = 'settings'; }]]); };
  // 首页的几个小窗口共用一个样子：标题 + 说明小图标（悬停看）+ 右上角关闭；正文；底部按钮靠右
  const copyText = async t => { if (navigator.clipboard && isSecureContext) return navigator.clipboard.writeText(t);
    const ta = document.createElement('textarea'); ta.value = t; document.body.append(ta); ta.select(); document.execCommand('copy'); ta.remove(); };
  // 换图标：自动找现成的 SVG（网站自己的 → Simple Icons → Remix Icon → IconPark），找不到让 AI 画；也能直接让 AI 画或粘贴 SVG
  const iconDlg = k => { const x = items[k], hasAi = aiCfg.providers.length;
    const m = dlg(`换图标`, '先找现成的 SVG：网站自己的图标 → Simple Icons → 国内的 Remix Icon、字节 IconPark，找到就直接用、不花 token；找不到再让 AI 画（只发网站名称、网址和网站公开的标题简介）。也可以粘贴别处拿到的 SVG。存在 _RULES/Home_Icons/。',
      `<div class="hic"><div class="hicpv"><span id="icP">${icon(x)}</span><b>${esc(x.name)}</b><small id="icSrc">${x.icon ? '自己的图标' : '网站默认图标'}</small></div>
        <div class="hicops">
          <div class="hop"><span class="hrl">${lu('search', 16)}<b>自动配图标</b>${tip(hasAi ? '找不到现成的会接着让 AI 画。' : '接入 AI 后，找不到现成的还能让 AI 画。')}</span><button type="button" class="btn primary" id="icAuto">开始</button></div>
          ${hasAi ? `<div class="hop col"><span class="hrl">${lu('wand', 16)}<b>让 AI 画</b>${tip('不写也行，AI 会按它对这个网站品牌的了解来画。写一句能画得更合心意，比如“蓝色渐变、用‘淘’字”。')}</span>
            <span class="hain"><input id="icH" maxlength="200" placeholder="想要的样子（可不填）" autocomplete="off"><button type="button" id="icAi">画</button></span></div>` : ''}
          <div class="hop col"><span class="hrl">${lu('copy', 16)}<b>粘贴 SVG</b>${tip('从 iconfont、Simple Icons 或其他 AI 拿到的 SVG 代码。存之前会自动去掉脚本和外部链接。')}</span>
            <textarea id="icS" rows="3" placeholder="<svg viewBox=&quot;0 0 64 64&quot;>…</svg>"></textarea><button type="button" class="btn" id="icSave">用这段 SVG</button></div>
        </div></div>`,
      `<button class="btn ghost" id="icReset" ${x.icon ? '' : 'hidden'}>恢复网站默认图标</button><button class="btn" id="icCopy" ${x.icon ? '' : 'hidden'}>${lu('copy', 14)}复制 SVG</button><button class="btn primary" data-x2>完成</button>`, 'hdwide');
    m.querySelector('[data-x2]').onclick = closeModal;
    const done = (j, src) => { draw(j.links); const nx = j.links.find(y => y.url === x.url); if (!nx) return;
      m.querySelector('#icP').innerHTML = icon(nx); m.querySelector('#icCopy').hidden = m.querySelector('#icReset').hidden = !nx.icon; m.querySelector('#icSrc').textContent = src; };
    m.querySelector('#icCopy').onclick = async () => { try { const h = new URL(x.url).hostname.replace(/^www\./, '');
        const r = await fetch(`/api/home/icon?h=${encodeURIComponent(h)}&t=${Date.now()}`); if (!r.ok) throw new Error('还没有自己的图标');
        await copyText(await r.text()); toast('SVG 代码已复制'); } catch (er) { toast(er.message || '复制失败', 6000); } };
    const call = async (body, btn, busy) => { const t0 = btn.textContent; btn.disabled = true; btn.textContent = busy;
      try { const j = await api('/api/home/icon', { url: x.url, name: x.name, ...body }); done(j, j.source || (body.action === 'reset' ? '网站默认图标' : '粘贴的 SVG')); toast('图标换好了'); } catch (er) { toast(er.message, 6000); }
      btn.disabled = false; btn.textContent = t0; };
    const auto = m.querySelector('#icAuto'); auto.onclick = () => call({ action: 'auto', hint: m.querySelector('#icH')?.value || '' }, auto, '找…');
    const ai = m.querySelector('#icAi'); if (ai) ai.onclick = () => call({ action: 'draw', hint: m.querySelector('#icH').value }, ai, '画…');
    m.querySelector('#icSave').onclick = e => { const v = m.querySelector('#icS').value.trim(); if (!v) return toast('先粘贴 SVG 代码'); call({ action: 'paste', svg: v }, e.target, '保存…'); };
    m.querySelector('#icReset').onclick = e => call({ action: 'reset' }, e.target, '恢复…'); };
  // 图标大小：图标、格子、间距一起缩放，文字不缩；记在这台电脑的浏览器里
  // 图标调到 65% 以下标上 .hsm：小组件放不下两行小字，只留一行
  const applyScale = () => { const s = +pref('homeScale', '0.7') || 0.7; home.style.setProperty('--hs', s); home.classList.toggle('hsm', s < 0.65); };
  applyScale();
  const sizeDlg = () => { const m = dlg('图标大小', '图标、小组件和间距一起缩放，文字大小不变。拖动时首页马上变，只记在这台电脑上。',
      `<div class="hasz"><small>小</small><input type="range" id="szR" min="0.5" max="1.2" step="0.05" value="${pref('homeScale', '0.7')}" aria-label="图标大小"><small>大</small><b id="szV"></b></div>`,
      `<button class="btn ghost" id="szD">恢复默认</button><button class="btn primary" data-x2>好了</button>`, 'hdsmall');
    document.querySelector('#modalHost .modal').classList.add('clear');
    const r = m.querySelector('#szR'), show = () => { setPref('homeScale', r.value); applyScale(); m.querySelector('#szV').textContent = Math.round(r.value * 100) + '%'; };
    show(); r.oninput = show; m.querySelector('#szD').onclick = () => { r.value = '0.7'; show(); }; m.querySelector('[data-x2]').onclick = closeModal; };
  // 添加图标（照 iTab）：“自定义”填网址和名称，右边实时预览；“推荐网站”按分类列出常用网站，点“添加”就加
  const REC = [['常用', [['B 站', 'https://www.bilibili.com'], ['知乎', 'https://www.zhihu.com'], ['小红书', 'https://www.xiaohongshu.com'], ['飞书', 'https://www.feishu.cn'], ['腾讯文档', 'https://docs.qq.com'], ['QQ 邮箱', 'https://mail.qq.com'], ['百度网盘', 'https://pan.baidu.com'], ['闲鱼', 'https://www.goofish.com']]],
    ['AI', [['Claude', 'https://claude.ai'], ['DeepSeek', 'https://chat.deepseek.com'], ['Kimi', 'https://kimi.moonshot.cn'], ['豆包', 'https://www.doubao.com'], ['通义', 'https://tongyi.aliyun.com'], ['ChatGPT', 'https://chatgpt.com'], ['Gemini', 'https://gemini.google.com'], ['v0', 'https://v0.dev']]],
    ['硬件', [['嘉立创 EDA', 'https://lceda.cn'], ['立创商城', 'https://www.szlcsc.com'], ['嘉立创下单', 'https://www.jlc.com'], ['立创开源广场', 'https://oshwhub.com'], ['乐鑫文档', 'https://docs.espressif.com'], ['Arduino', 'https://www.arduino.cc'], ['淘宝', 'https://www.taobao.com'], ['1688', 'https://www.1688.com']]],
    ['设计', [['Fusion 360', 'https://www.autodesk.com/products/fusion-360'], ['MakerWorld', 'https://makerworld.com.cn'], ['Figma', 'https://www.figma.com'], ['ProcessOn', 'https://www.processon.com'], ['Canva 可画', 'https://www.canva.cn']]],
    ['开发', [['GitHub', 'https://github.com'], ['Gitee', 'https://gitee.com'], ['Stack Overflow', 'https://stackoverflow.com'], ['CSDN', 'https://www.csdn.net'], ['菜鸟教程', 'https://www.runoob.com'], ['Vercel', 'https://vercel.com']]],
    ['学习', [['Overleaf', 'https://www.overleaf.com'], ['Google Scholar', 'https://scholar.google.com'], ['IEEE Xplore', 'https://ieeexplore.ieee.org'], ['知网', 'https://www.cnki.net'], ['有道词典', 'https://www.youdao.com'], ['雅思报名', 'https://ielts.neea.cn'], ['电子科大研招网', 'https://yz.uestc.edu.cn']]]];
  const hostOf = u => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return ''; } };
  const addSite = () => { const m = dlg('添加到首页', '加到首页的图标网格最后，加完可以拖到别处或拖进文件夹。图标默认用网站自己的，之后右键“换图标”能换成 SVG。<br>小组件右键能从首页移走，移走的在“小组件”里能加回来。',
      `<div class="hatab" role="tablist"><button type="button" role="tab" data-t="c" aria-selected="true">自定义</button><button type="button" role="tab" data-t="r" aria-selected="false">推荐网站</button><button type="button" role="tab" data-t="w" aria-selected="false">小组件</button></div>
      <div class="hapane" data-p="c"><div class="hic"><div class="hafl">
          <label class="haf"><span>网址</span><span class="hain">${lu('link', 15)}<input id="lkU" placeholder="https://" autocomplete="off"><button type="button" id="lkG">获取图标</button></span></label>
          <label class="haf"><span>名称 ${tip('空着就用网址里的名字，比如 github.com 就叫 github。')}</span><span class="hain">${lu('type', 15)}<input id="lkN" placeholder="网站名称" maxlength="20" autocomplete="off"></span></label></div>
        <div class="hicpv"><span id="lkP"></span><b id="lkPN">网站名称</b><small>预览</small></div></div></div>
      <div class="hapane" data-p="r" hidden><div class="hacat">${REC.map((c, i) => `<button type="button" data-c="${i}" class="${i ? '' : 'on'}">${c[0]}</button>`).join('')}</div><div class="harec" id="lkR"></div></div>
      <div class="hapane" data-p="w" hidden><div class="harec" id="wgL"></div></div>`,
      `<span class="hdfp" data-p="c"><button class="btn ghost" id="mok2">保存并继续</button><button class="btn primary" id="mok">保存</button></span>`, 'hdwide');
    const U = m.querySelector('#lkU'), N = m.querySelector('#lkN'), norm = () => { let u = U.value.trim(); if (u && !/^https?:\/\//.test(u)) u = 'https://' + u; return u; };
    const host = () => hostOf(norm());
    const prev = () => { const h = host(), nm = N.value.trim() || (h ? h.split('.')[0] : '');
      m.querySelector('#lkP').innerHTML = h ? icon({ name: nm || h, url: norm() }) : `<span class="hli haempty">${lu('plus', 24)}</span>`;
      m.querySelector('#lkPN').textContent = nm || '网站名称'; };
    prev(); setTimeout(() => U.focus()); U.oninput = () => { clearTimeout(prev.t); prev.t = setTimeout(prev, 400); }; m.querySelector('#lkG').onclick = prev; N.oninput = prev;
    // 小组件：在首页的打勾，移走了的能点加号加回来
    const wtab = () => { const on = new Set(items.map(x => x.url));
      m.querySelector('#wgL').innerHTML = Object.entries(allW()).map(([k, w]) => `<div class="harc"><span class="hli hwi">${lu(w.icon, 22)}</span><span class="harn"><b>${esc(w.name)}</b><small>${esc(w.desc)}</small></span>
          ${on.has('twin:' + k) ? `<em>${lu('check', 14)}</em>` : `<button type="button" class="hadd1" data-k="${k}" aria-label="添加 ${esc(w.name)}">${lu('plus', 16)}</button>`}</div>`).join('');
      m.querySelectorAll('#wgL [data-k]').forEach(b => b.onclick = async () => { b.disabled = true; try { await add(allW()[b.dataset.k].name, 'twin:' + b.dataset.k); wtab(); } catch (er) { b.disabled = false; toast(er.message, 6000); } }); };
    wtab();
    const add = async (name, url) => draw((await api('/api/home/links', { action: 'add', name, url })).links);
    const go = async again => { const name = N.value.trim() || (host() ? host().split('.')[0] : '');
      try { await add(name, norm()); if (again) { U.value = ''; N.value = ''; prev(); U.focus(); toast(`加上了：${name}`); } else closeModal(); } catch (er) { toast(er.message, 6000); } };
    m.querySelector('#mok').onclick = () => go(false); m.querySelector('#mok2').onclick = () => go(true);
    [U, N].forEach(x => x.onkeydown = e => { if (e.key === 'Enter') go(false); });
    let cat = 0;
    const rec = () => { const have = new Set(items.map(x => hostOf(x.url)));
      m.querySelector('#lkR').innerHTML = REC[cat][1].map(([n, u]) => `<div class="harc">${icon({ name: n, url: u })}<span class="harn"><b>${esc(n)}</b><small>${esc(hostOf(u))}</small></span>
        ${have.has(hostOf(u)) ? `<em>${lu('check', 14)}</em>` : `<button type="button" class="hadd1" data-n="${esc(n)}" data-u="${esc(u)}" aria-label="添加 ${esc(n)}">${lu('plus', 16)}</button>`}</div>`).join('');
      m.querySelectorAll('#lkR [data-u]').forEach(b => b.onclick = async () => { b.disabled = true; try { await add(b.dataset.n, b.dataset.u); rec(); } catch (er) { b.disabled = false; toast(er.message, 6000); } }); };
    m.querySelectorAll('.hacat [data-c]').forEach(b => b.onclick = () => { cat = +b.dataset.c; m.querySelectorAll('.hacat button').forEach(x => x.classList.toggle('on', x === b)); rec(); });
    m.querySelectorAll('.hatab [data-t]').forEach(b => b.onclick = () => { m.querySelectorAll('.hatab [data-t]').forEach(x => x.setAttribute('aria-selected', x === b));
      m.querySelectorAll('.hapane').forEach(p => { p.hidden = p.dataset.p !== b.dataset.t; }); m.querySelector('.hdf').hidden = b.dataset.t !== 'c'; if (b.dataset.t === 'r') rec(); else U.focus(); }); };
  draw(viewHome.items || (() => { try { return JSON.parse(pref('homeLinks', '[]')); } catch (e) { return []; } })());
  // 插件开关时加上 / 拿掉它的小组件，不刷新首页；refreshW：插件里的数字变了，重新取一次
  viewHome.plugW = (k, w, ls) => { if (!ok() || !$('#hGrid')) return; if (w && ph.delete(k)) { wbox[k].parentElement.remove(); delete wbox[k]; }
    if (w && !wbox[k]) addW(k, w); else if (!w && wbox[k]) { wbox[k].parentElement.remove(); delete wbox[k]; } draw(ls || items); };
  viewHome.refreshW = k => { const w = allW()[k], b = wbox[k]; if (ok() && w && b) w.load(d => ok() && w.draw(b, d)).catch(() => {}); };
  // 新加的“今日建议”小组件：老首页表里没有，第一次自动放上去一次，移走后不再加
  const sugOnce = async ls => { if (ls.some(x => x.url === 'twin:sug') || pref('w.sugAdded', '')) return ls; setPref('w.sugAdded', '1');
    try { return (await api('/api/home/links', { action: 'add', name: '今日建议', url: 'twin:sug' })).links; } catch (e) { return ls; } };
  api('/api/home/links').then(j => sugOnce(j.links)).then(ls => { setPref('homeLinks', JSON.stringify(ls)); draw(ls); }).catch(() => { draw(Object.entries(WIDGETS).map(([k, w]) => ({ name: w.name, url: 'twin:' + k, folder: '' }))); });
}


// ----- 要闻：只推对他影响大的（能赚钱的风口、会改变收入和计划的事），领域不限；颜色跟着标签走，5 格是影响因子 -----
let newsTag = '';
async function viewNews() {
  setTitle('要闻'); const ok = fresh(); await loadAi().catch(() => {}); if (!ok()) return;
  const hasAi = aiCfg.providers.length;
  $('#view').innerHTML = `<div class="wrap page news"><div class="dayhead"><h1>要闻</h1><span class="sub" id="nwSub"></span><span class="sp"></span>${tip('只推对你影响大的：能帮你赚钱的风口，或者会改变你收入、计划、申请的事。<br>判断依据是 00_Crown/Profile.md 和 _RULES/News_Profile.md，两页都是公开层，会和新闻标题一起发给 AI；想看什么、不看什么直接改 News_Profile。')}${hasAi ? '<button class="btn sm" id="nwRe">刷新</button>' : ''}</div>
    <div class="nbar"><span class="seg nmode"><button type="button" data-nm="day" class="on">每日</button><button type="button" data-nm="star">收藏</button></span><select id="nwDay" aria-label="看哪一天"></select></div>
    <div id="nbody"><p class="note">读取中…</p></div></div>`;
  // 每天的要闻都存着：上面选日期看以前的；点卡片右上角的星收藏，“收藏”里集中看
  let d, mode = 'day', star = [];
  const load = async date => { try { d = await api('/api/news' + (date ? '?date=' + date : '')); } catch (e) { d = {}; } };
  await load(); if (!ok()) return;
  const dayName = x => x === today() ? `今天 ${x.slice(5)}` : x === (() => { const y = new Date(Date.now() - 864e5); return `${y.getFullYear()}-${String(y.getMonth() + 1).padStart(2, '0')}-${String(y.getDate()).padStart(2, '0')}`; })() ? `昨天 ${x.slice(5)}` : `${x.slice(5)} 星期${'日一二三四五六'[new Date(x + 'T12:00').getDay()]}`;
  const bar = () => { const days = d.days || [], sel = $('#nwDay'), t = today(); if (!days.includes(t)) days.unshift(t);
    sel.innerHTML = days.map(x => `<option value="${x}" ${x === d.date ? 'selected' : ''}>${dayName(x)}</option>`).join(''); sel.hidden = mode !== 'day';
    const rb = $('#nwRe'); if (rb) rb.hidden = mode !== 'day' || d.date !== t;
    document.querySelectorAll('[data-nm]').forEach(b => { b.classList.toggle('on', b.dataset.nm === mode); if (b.dataset.nm === 'star') b.textContent = `收藏${(d.starred || []).length ? ' ' + d.starred.length : ''}`; }); };
  $('#nwDay').onchange = async e => { await load(e.target.value); newsTag = ''; if (ok()) draw(); };
  document.querySelectorAll('[data-nm]').forEach(b => b.onclick = async () => { mode = b.dataset.nm; newsTag = '';
    if (mode === 'star') star = (await api('/api/news/starred').catch(() => ({ starred: [] }))).starred; if (ok()) draw(); });
  const gen = async () => { const b = $('#nwRe'); if (b) { b.textContent = '正在取…'; b.disabled = true; } $('#nbody').innerHTML = '<p class="note">正在从各家来源取最新标题，再让 AI 按你的情况挑，要几十秒…</p>';
    try { const p = $('#prov'); d = await api('/api/news', { provider_id: p && p.value }); newsTag = ''; if (ok()) draw(); } catch (e) { if (ok()) $('#nbody').innerHTML = `<p class="flag">${esc(e.message)}</p>`; }
    if (b) { b.textContent = '刷新'; b.disabled = false; } };
  const draw = () => { bar();
    if (mode === 'star' && !star.length) { $('#nbody').innerHTML = `<p class="note">还没收藏。看到想留着细看的，点卡片右上角的星。收藏也会写进 <a href="${libLink('00_Crown/Briefs/News/要闻收藏.md')}">要闻收藏.md</a>。</p>`; return; }
    if (mode === 'day' && (!d || !d.items)) { $('#nbody').innerHTML = `<p class="note">${d.date !== today() ? '这一天没有要闻。' : hasAi ? '今天还没取。' : '接入 AI 后才能生成要闻。'}</p>`; return; }
    const on = new Set(mode === 'star' ? star.map(x => x.link) : d.starred || []);
    const all = (mode === 'star' ? star : d.items).map(x => ({ ...x, tag: x.tag || x.cat || '要闻', score: x.score || x.weight || 3 }));
    const tags = [...new Set(all.map(x => x.tag))], col = t => 'c' + (tags.indexOf(t) % 6);
    $('#nwSub').textContent = mode === 'star' ? `收藏了 ${all.length} 条` : `${d.date} ${d.time || ''} · ${d.sources ? d.sources + ' 个来源、' : ''}${d.fetched} 条里挑了 ${all.length} 条`;
    const its = all.filter(x => !newsTag || x.tag === newsTag);
    const meter = n => `<span class="nw" title="对你的影响 ${n}/5" aria-label="对你的影响 ${n}/5">${[1, 2, 3, 4, 5].map(k => `<i class="${k <= n ? 'on' : ''}"></i>`).join('')}</span>`;
    $('#nbody').innerHTML = `${mode === 'day' && d.overview ? `<p class="nover">${esc(d.overview)}</p>` : ''}
      ${all.length ? `<div class="nmix" role="img" aria-label="${tags.map(t => `${t} ${all.filter(x => x.tag === t).length} 条`).join('，')}">${tags.map(t => `<i class="${col(t)}" style="flex:${all.filter(x => x.tag === t).reduce((n, x) => n + x.score, 0)}"></i>`).join('')}</div>
      <div class="nchips"><button type="button" class="${!newsTag ? 'on' : ''}" data-nt="">全部 ${all.length}</button>${tags.map(t => `<button type="button" class="${newsTag === t ? 'on' : ''}" data-nt="${esc(t)}"><i class="${col(t)}"></i>${esc(t)} ${all.filter(x => x.tag === t).length}</button>`).join('')}</div>` : '<p class="note">今天没有对你影响大的新闻。</p>'}
      <div class="ngrid">${its.map(x => { const k = all.indexOf(x);
        return `<article class="ncard ${col(x.tag)}"><div class="nh"><span class="ncat">${esc(x.tag)}${mode === 'star' ? ` · ${esc(x.date.slice(5))}` : ''}</span>${meter(x.score)}<button type="button" class="nstar${on.has(x.link) ? ' on' : ''}" data-star="${k}" title="${on.has(x.link) ? '取消收藏' : '收藏，留着细看'}" aria-label="收藏">${lu('star', 16)}</button></div>
        <h3>${esc(x.title)}</h3><p>${esc(x.summary)}</p>
        ${x.impact || x.why ? `<div class="nimp"><b>对你</b>${esc(x.impact || x.why)}</div>` : ''}
        ${x.action ? `<div class="nact"><span>${esc(x.action)}</span><button type="button" class="btn sm" data-nadd="${k}">加进待办</button></div>` : ''}
        <a class="nsrc" href="${esc(x.link)}" target="_blank" rel="noopener" title="${esc(x.orig)}">${esc(x.source)} · 原文</a></article>`; }).join('')}</div>
      ${mode === 'star' ? `<p class="foot">收藏也写在 <a href="${libLink('00_Crown/Briefs/News/要闻收藏.md')}">要闻收藏.md</a>，Obsidian 里也能看。</p>` : `<p class="foot">${(d.failed || []).length ? `没取到：${d.failed.map(f => esc(f.name)).join('、')}。` : ''}来源在 <a href="${libLink('_RULES/News_Sources.md')}">News_Sources</a>，挑选规则在 <a href="${libLink('_RULES/News_Profile.md')}">News_Profile</a>。</p>`}`;
    $('#nbody').querySelectorAll('[data-star]').forEach(b => b.onclick = async () => { const x = all[+b.dataset.star], to = !on.has(x.link);
      try { const r = await api('/api/news/star', { date: x.date || d.date, link: x.link, on: to }); d.starred = r.starred.map(y => y.link); if (mode === 'star') star = r.starred; draw(); toast(to ? '收藏了，在“收藏”里能找到' : '取消收藏了'); } catch (e) { toast(e.message, 6000); } });
    $('#nbody').querySelectorAll('[data-nt]').forEach(b => b.onclick = () => { newsTag = b.dataset.nt; draw(); });
    $('#nbody').querySelectorAll('[data-nadd]').forEach(b => b.onclick = async () => { const x = all[+b.dataset.nadd];
      try { await api('/api/action', { action: { type: 'add_todo', text: x.action, priority: 'P2' } }); b.outerHTML = '<span class="sdone">已加进待办</span>'; } catch (e) { toast(e.message, 6000); } });
  };
  const rb = $('#nwRe'); if (rb) rb.onclick = gen;
  bar(); if (!d || !d.items) { if (hasAi) return gen(); }
  draw();
}
