'use strict';
// 雅思小练习：右下角一张小卡片。只在没打字、没开弹窗、页面在前台时出，两次之间隔几分钟（设置里调）。
// 点空白处不收起（免得错过），只有点 ✕ 才收起；⤢ 放大到屏幕中间，方便读文章。
(() => {
  const P = '/api/p/ielts/', KIND = { wr: '单词 · 认', ww: '单词 · 拼', s: '同义替换', p: '写作句型', r: '阅读' };
  const css = document.createElement('style'); css.dataset.ielts = ''; document.head.append(css); css.textContent = `
.iec{position:fixed;right:20px;bottom:20px;z-index:35;width:min(380px,calc(100vw - 32px));max-height:min(78vh,640px);overflow:auto;background:var(--paper);color:var(--ink);border:1px solid var(--rule);border-radius:14px;box-shadow:var(--shadow);padding:14px 16px;display:grid;gap:10px;font-size:14px}
.iec .ih{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--ink-3)}.iec .ih b{font-weight:600;color:var(--ink-2)}.iec .ih .sp{flex:1}
.iec .ih button{border:1px solid var(--rule);background:none;color:var(--ink-2);cursor:pointer;font:inherit;font-size:12px;height:26px;padding:0 8px;border-radius:7px;display:inline-grid;place-items:center}.iec .ih button:hover{background:var(--hover);color:var(--ink);border-color:var(--ink-3)}.iec .ih button.ic{width:26px;padding:0}
.iec .iw{font-size:22px;font-weight:600}.iec .iph{color:var(--ink-3);font-size:12.5px;margin-left:6px}
.iec .io{display:grid;gap:6px}.iec .io button{text-align:left;padding:8px 10px;border:1px solid var(--rule);border-radius:9px;background:var(--ground);color:var(--ink);cursor:pointer;font:inherit}
.iec .io button:hover{background:var(--hover)}.iec .io button.y{border-color:var(--ok);background:var(--ok-soft)}.iec .io button.n{border-color:var(--p0);background:var(--p0-soft)}
.iec input,.iec textarea{width:100%;box-sizing:border-box;padding:8px 10px;border:1px solid var(--rule);border-radius:9px;background:var(--ground);color:var(--ink);font:inherit}
.iec .ipass{max-height:170px;overflow:auto;padding:8px 10px;border-radius:9px;background:var(--hover);font-size:13px;line-height:1.55;white-space:pre-wrap}
.iec .ires{padding:8px 10px;border-radius:9px;line-height:1.55;white-space:pre-wrap}.iec .ires.y{background:var(--ok-soft)}.iec .ires.n{background:var(--p0-soft)}
.iec .ift{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.iec .note{margin:0}
.iec.big{right:50%;bottom:50%;transform:translate(50%,50%);width:min(760px,calc(100vw - 32px));max-height:88vh;font-size:15.5px;padding:20px 24px;gap:12px}
.iec.big .ipass{max-height:52vh;font-size:15px;line-height:1.7}.iec .ity{font-size:12px;color:var(--ink-3)}
@media(max-width:700px){.iec{right:16px;bottom:76px}.iec.big{right:50%;bottom:50%}}
.iep{display:grid;gap:14px}.iep .ist{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.iep .ist div{border:1px solid var(--rule);border-radius:10px;padding:8px 10px;display:grid;gap:2px}.iep .ist b{font-size:20px;font-weight:600}.iep .ist span{font-size:12px;color:var(--ink-3)}
.iep .iac{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.iep .iac .sp{flex:1}.iep details summary{cursor:pointer;font-size:13px;color:var(--ink-2)}.iep details p{margin:6px 0 0;line-height:1.9}
@media(max-width:700px){.iep .ist{grid-template-columns:repeat(2,1fr)}}`;
  let box = null, lastKey = 0;
  const skipped = () => { try { const s = JSON.parse(pref('ieltsSkip', '{}')); return s.d === today() ? s.ids : []; } catch (e) { return []; } };
  const onKey = () => { lastKey = Date.now(); };
  addEventListener('keydown', onKey, true);
  const typing = el => el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable);
  const busy = () => document.hidden || box || $('#modalHost .modal') || typing(document.activeElement) || Date.now() - lastKey < 8000;
  const later = min => setPref('ieltsNext', String(Date.now() + min * 60000));
  const maybe = () => { if (!busy() && Date.now() > +pref('ieltsNext', '0')) show(false); };
  const onHash = () => setTimeout(maybe, 2500);
  addEventListener('hashchange', onHash);
  const tick = setInterval(maybe, 60000);
  const close = () => { if (box) window.viewHome?.refreshW?.('ielts'); box?.remove(); box = null; };
  const norm = s => String(s).toLowerCase().replace(/[^\w\s'-]/g, '').replace(/\s+/g, ' ').trim();
  const LINKS = [['mini-ielts 阅读', 'https://mini-ielts.com/reading'], ['IELTS-up 阅读', 'https://ielts-up.com/reading/ielts-reading-practice.html'],
    ['IELTS Liz 技巧', 'https://ieltsliz.com'], ['IELTS Buddy', 'https://www.ieltsbuddy.com'], ['Writing9 作文批改', 'https://writing9.com'], ['IELTS Online Tests 模考', 'https://ieltsonlinetests.com']];
  const lead = s => norm(s).split(' ')[0];  // 选项开头的字母或罗马数字：A、B、ii、iv
  // 问 AI 都进同一个“雅思答疑”对话，不关联项目；第一次问时先建好这个对话（标题固定），记住它的 id
  const ask = async t => { let id = pref('ieltsChat', ''), d = id && await api('/api/chat?id=' + encodeURIComponent(id)).catch(() => null);
    try { if (!d || d.project !== 'none' || d.title !== '雅思答疑' || !d.fixed) id = (await api('/api/chat/save', { ...(d || {}), id: d ? id : '', title: '雅思答疑', fixed: true, project: 'none', auto: '', messages: d?.messages || [] })).id; }
    catch (e) { return toast(e.message); }
    setPref('ieltsChat', id); if (chat.id === id) chat.id = '';  // 让对话页重新读一次，拿到改过的标题和项目
    pendingAsk = t; pendingSend = true; close(); if (location.hash === '#c/' + id) route(); else location.hash = 'c/' + id; };
  const TYPE = { tfng: '判断：和原文一致选 TRUE，矛盾选 FALSE，原文没说选 NOT GIVEN', ynng: '判断作者观点：YES / NO / NOT GIVEN', fill: '填空：用原文里的词，不超过两个', mc: '选择' };

  async function show(force) {
    let c; try { c = await api(P + 'next?skip=' + encodeURIComponent(skipped().join(','))); } catch (e) { return force && toast(e.message); }
    later(+pref('ieltsFreq', '15'));
    if (c.empty) return force && toast(c.bank || !c.hasAi ? '今天的练习都做完了，明天再来' : '今天的单词和句型做完了。去“设置 → 插件 → 雅思 → 设置”里点“备 5 篇阅读”，让 AI 出几道阅读题');
    if (!force && busy()) return;
    draw(c);
  }

  function draw(c) {
    close(); box = document.createElement('div'); box.className = 'iec' + (pref('ieltsBig', '') ? ' big' : ''); box.setAttribute('role', 'dialog'); box.setAttribute('aria-label', '雅思小练习');
    const head = `<div class="ih"><b>雅思 · ${KIND[c.kind]}${c.kind === 'r' ? ` ${c.n}/${c.of}` : ''}</b>${c.new ? '<span>新</span>' : ''}<span class="sp"></span><button data-off title="今天不再弹出，明天再来">今天不出了</button><button class="ic" data-big></button><button class="ic" data-x title="收起（没答的题今天先不出）" aria-label="收起">${lu('x', 14)}</button></div>`;
    let body = '';
    if (c.kind === 'wr') body = `<div><span class="iw">${esc(c.word)}</span><span class="iph">/${esc(c.phonetic)}/</span></div><div class="io">${c.options.map((o, i) => `<button data-i="${i}">${esc(o)}</button>`).join('')}</div>`;
    if (c.kind === 'ww') body = `<div>${esc(c.meaning)}<span class="iph">/${esc(c.phonetic)}/</span></div><p class="note">拼出这个词：${esc(c.hint)}</p><input data-in autocomplete="off" spellcheck="false"><div class="ift"><button class="btn primary sm" data-go>确定</button></div>`;
    if (c.kind === 's') body = `<p class="note">题目里写的是</p><div class="iw">${esc(c.word)}</div><p class="note">原文里最可能换成哪个说法？</p><div class="io">${c.options.map((o, i) => `<button data-i="${i}">${esc(o)}</button>`).join('')}</div>`;
    if (c.kind === 'p') body = `<div class="iw" style="font-size:17px">${esc(c.pat)}</div><p class="note">${esc(c.zh)}</p><p>用这个句型翻译：${esc(c.ex_zh)}</p><textarea data-in rows="2" placeholder="写一句英文，写不出来也可以直接看参考"></textarea><div class="ift"><button class="btn primary sm" data-go>看参考</button></div>`;
    if (c.kind === 'r') body = `<details${c.n === 1 ? ' open' : ''}><summary>${esc(c.title)}</summary><div class="ipass">${esc(c.text)}</div></details><p class="ity">${esc(/heading/i.test(c.q) ? '标题配对：选最能概括这一段的标题' : /which paragraph/i.test(c.q) ? '信息配对：这个信息在哪一段' : TYPE[c.type] || '')}</p><p>${esc(c.q)}</p>`
      + (c.options ? `<div class="io">${c.options.map((o, i) => `<button data-i="${i}">${esc(o)}</button>`).join('')}</div>` : `<input data-in autocomplete="off" placeholder="填原文里的词（不超过两个）"><div class="ift"><button class="btn primary sm" data-go>确定</button></div>`);
    box.innerHTML = head + body; document.body.append(box);
    // 没答就点 ✕：今天先不出这一题（不然下一题又是它），明天再来
    box.querySelector('[data-x]').onclick = () => { if (!box.querySelector('[data-more]')) setPref('ieltsSkip', JSON.stringify({ d: today(), ids: [...skipped(), c.id] })); close(); };
    // 放大 / 还原：图标和提示跟着现在的样子变
    const bb = box.querySelector('[data-big]'), bigUi = () => { const big = box.classList.contains('big'); bb.innerHTML = lu(big ? 'minimize-2' : 'maximize-2', 14); bb.title = bb.ariaLabel = big ? '缩回右下角' : '放大到屏幕中间'; };
    bigUi(); bb.onclick = () => { setPref('ieltsBig', box.classList.toggle('big') ? '1' : ''); bigUi(); };
    box.querySelector('[data-off]').onclick = () => { const d = new Date(); d.setHours(24, 0, 0, 0); setPref('ieltsNext', String(+d)); close(); toast('今天不出了，明天见'); };
    const inp = box.querySelector('[data-in]');
    if (inp) { inp.focus(); inp.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); box.querySelector('[data-go]').click(); } }; }
    const right = c.kind === 'r' && c.options ? (c.type === 'tfng' || c.type === 'ynng' ? c.options.findIndex(o => norm(o) === norm(c.answer)) : c.options.findIndex(o => lead(o) === lead(c.answer))) : c.answer;
    box.querySelectorAll('[data-i]').forEach(b => b.onclick = () => {
      box.querySelectorAll('[data-i]').forEach(x => { x.disabled = true; x.classList.toggle('y', +x.dataset.i === right); });
      const ok = +b.dataset.i === right; if (!ok) b.classList.add('n'); done(c, ok, b.textContent); });
    const go = box.querySelector('[data-go]'); if (go) go.onclick = () => {
      const v = inp.value.trim(); inp.disabled = true; go.remove();
      if (c.kind === 'p') return selfRate(c, v);
      done(c, c.kind === 'ww' ? norm(v) === norm(c.answer) : String(c.answer).split('/').some(a => norm(a) === norm(v)), v); };
  }

  // 句型没法自动判分：给参考句，自己判断写对没有，也可以让 AI 批改
  function selfRate(c, v) {
    box.insertAdjacentHTML('beforeend', `<div class="ires">参考：${esc(c.ex)}</div><div class="ift">${v ? '<button class="btn sm" data-ai>让 AI 批改</button>' : ''}<button class="btn sm" data-r="0">没写好</button><button class="btn primary sm" data-r="1">写对了</button></div>`);
    box.querySelectorAll('[data-r]').forEach(b => b.onclick = () => { box.querySelector('.ift:last-child').remove(); done(c, b.dataset.r === '1', v, true); });
    const ai = box.querySelector('[data-ai]'); // 让 AI 批改也算答过（记作写了一遍，按遗忘曲线排到以后）；以前不记，这个句型一直是“新”的，每次都先出它
    if (ai) ai.onclick = () => api(P + 'answer', { id: c.id, ok: true }).catch(() => {}).then(() => ask(`帮我批改这句雅思作文句子，句型是“${c.pat}”，要表达的意思是“${c.ex_zh}”。我写的是：${v}\n指出语法和用词问题，给一个更好的写法，用中文讲。`));
  }

  async function done(c, ok, given, quiet) {
    let s; try { s = await api(P + 'answer', { id: c.id, ok }); } catch (e) { return toast(e.message); }
    const ans = c.kind === 'wr' || c.kind === 's' ? c.options[c.answer] : c.kind === 'r' && c.options ? c.options[c.options.findIndex(o => lead(o) === lead(c.answer))] || c.answer : c.answer;
    const res = quiet ? '' : `<div class="ires ${ok ? 'y' : 'n'}">${ok ? '对了' : `正确答案：${esc(c.kind === 'ww' ? c.answer : ans)}`}${c.kind === 's' ? `\n\n${esc(c.word)} ≈ ${esc(c.options[c.answer])}（${esc(c.zh)}）。真题的题干和原文几乎从不用同一个词，先在原文里找它的同义说法。` : ''}${c.explain ? '\n\n' + esc(c.explain) : ''}${c.kind === 'r' && c.vocab?.length && c.n === c.of ? '\n\n这篇的词：' + c.vocab.map(v => `${esc(v[0])} ${esc(v[1])}`).join('，') : ''}</div>`;
    box.insertAdjacentHTML('beforeend', `${res}<p class="note">今天做了 ${s.today} 题${s.due ? `，还有 ${s.due} 张该复习` : ''}。${ok ? '' : '答错的今天会再出一次。'}${s.left < 12 ? `阅读题只剩 ${s.left} 道了，去“设置 → 插件 → 雅思 → 设置”里点“备 5 篇阅读”。` : ''}</p>
      <div class="ift">${!ok && !quiet ? '<button class="btn sm" data-ask>问 AI</button>' : ''}<button class="btn sm" data-x2>收起</button><button class="btn primary sm" data-more>再来一题</button></div>`);
    box.querySelector('[data-x2]').onclick = close;
    box.querySelector('[data-more]').onclick = () => show(true);
    const a = box.querySelector('[data-ask]'); if (a) a.onclick = () => ask(c.kind === 'r'
      ? `雅思阅读题，文章《${c.title}》：\n${c.text}\n\n题目：${c.q}${c.options ? '\n选项：' + c.options.join('；') : ''}\n我选的是：${given}，正确答案：${c.answer}\n给的解析：${c.explain || '无'}\n我还是不太懂，请用中文再讲清楚，并教我这种题型以后怎么做。`
      : c.kind === 's' ? `雅思阅读同义替换：${c.word} 和 ${ans}（${c.zh}）。我没认出来。请用中文讲讲这两个词的区别和用法，再列 3 个雅思阅读里常和它们互换的说法，各给一个例句。`
      : `雅思单词 ${c.word || c.answer}（${c.kind === 'wr' ? ans : c.meaning}）：我答错了。请用中文讲讲它的常见用法、搭配，给两个雅思写作里能用的例句，再教我一个好记的方法。`);
    box.scrollTop = box.scrollHeight;
  }

  // 设置里的弹窗：几个数字、频率、三个按钮；练习网站收起来
  (window.TwinPlugins ||= {}).ielts = {
    // 首页小组件：今天做了几题、几张待复习，点一下马上练一题
    widget: { name: '雅思', desc: '今天做了几题、待复习几张，点一下练一题', icon: 'graduation-cap',
      load: put => api(P + 'stats').then(put),
      draw: (box, s) => { box.innerHTML = `<span class="hwt">雅思<em>今天</em></span><span class="hwbig">${s.today}<small>题</small></span><span class="hwn">${s.due ? `${s.due} 张待复习` : '没有要复习的'}</span>`;
        box.dataset.tip = `最近 7 天答了 ${s.week} 题${s.rate != null ? `，正确率 ${s.rate}%` : ''}\n阅读题还有 ${s.left} 道没做\n点一下马上练一题`; box.onclick = () => show(true); } },
    stop() { clearInterval(tick); removeEventListener('keydown', onKey, true); removeEventListener('hashchange', onHash); close(); css.remove(); },
    async panel(el) {
    const s = await api(P + 'stats').catch(() => null); if (!s) return;
    const n = (v, l) => `<div><b>${v}</b><span>${l}</span></div>`;
    el.innerHTML = `<div class="iep"><div class="ist">${n(s.today, '今天做了')}${n(s.due, '待复习')}${n(s.left, '阅读题没做')}${n(s.rate != null ? s.rate + '%' : '-', '7 天正确率')}</div>
      <p class="note" style="margin:0">学过 ${s.words} 个单词、${s.syns} 组同义替换、${s.patterns} 个句型，做过 ${s.reading} 道阅读题。</p>
      <div class="iac"><span class="note">最多每</span><select id="ieF">${[10, 15, 30, 60].map(m => `<option ${pref('ieltsFreq', '15') == m ? 'selected' : ''}>${m}</option>`).join('')}</select><span class="note">分钟出一题</span><span class="sp"></span>
        <button class="btn" id="iePrep" title="请 AI 写 5 篇原创阅读、30 道题，一篇调用一次">备 5 篇阅读</button><button class="btn" id="ieImp" title="把手上的真题粘贴进来，AI 整理成卡片、补解析">导入阅读题</button><button class="btn primary" id="ieOne">现在练一题</button></div>
      <details><summary>免费练习网站</summary><p>${LINKS.map(([t, u]) => `<a href="${u}" target="_blank" rel="noopener">${t}</a>`).join(' · ')}</p></details></div>`;
    el.querySelector('#ieF').onchange = e => setPref('ieltsFreq', e.target.value);
    el.querySelector('#ieOne').onclick = () => { closeModal(); show(true); };
    el.querySelector('#ieImp').onclick = () => { const m = dlg('导入阅读题', '一次一篇：文章、题目、答案（有就带上）一起粘贴，格式乱也没关系。AI 整理成卡片并补中文解析，会用一次 token。只存在你自己的知识库里。',
      '<textarea id="ieT" rows="12" style="width:100%;box-sizing:border-box" placeholder="粘贴文章和题目…"></textarea>', '<span style="flex:1"></span><button class="btn" data-x>取消</button><button class="btn primary" id="ieGo">导入</button>', 'hdwide');
      m.querySelector('.hdf [data-x]').onclick = closeModal; const go = m.querySelector('#ieGo');
      go.onclick = async () => { go.disabled = true; go.textContent = 'AI 正在整理…';
        try { const r = await api(P + 'import', { text: m.querySelector('#ieT').value }); closeModal(); toast(`导入了 ${r.added} 道题`); } catch (e) { toast(e.message, 8000); go.disabled = false; go.textContent = '导入'; } }; };
    const pb = el.querySelector('#iePrep'); pb.onclick = async () => { pb.disabled = true; let k = 0;
      try { for (; k < 5; k++) { pb.textContent = `AI 正在出第 ${k + 1}/5 篇…`; await api(P + 'prepare', {}); } } catch (e) { toast(e.message, 8000); }
      if (k) toast(`备好了 ${k} 篇阅读，${k * 6} 道题`); if (el.isConnected) this.panel(el); };
  } };
})();
