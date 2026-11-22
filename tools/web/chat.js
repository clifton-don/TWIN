'use strict';
// 对话页：对话、关联项目、确认卡片、改动预览、接单评估卡
// 普通 <script>，和 app.js 共用全局变量和函数；index.html 里按 app → chat → day → home → todo → pages 的顺序加载

// ---------------- 对话历史 ----------------
// 最近对话由新侧栏（ui.js）画，这里只通知它刷新
function loadHist() { window.TwinUI?.bus.dispatchEvent(new Event('chats')); }

// ---------------- 对话 ----------------
// stick：贴着底部就跟着新内容往下走；自己往上翻了就不拽回来，翻回底部又接着跟
let stick = true, stickTop = 0;
function toBottom() { const sc = $('#msgs'); if (sc && stick) { sc.scrollTop = sc.scrollHeight; stickTop = sc.scrollTop; } }
let chat = { id: '', title: '', messages: [] }, editIdx = -1, sending = false, pendingAsk = '', pendingSend = false, pendingProj = '', atts = [];
const ACTION_LABEL = { add_todo: '加入待办', complete_todo: '把待办打钩', add_event: '记一件事', add_idea: '记进 TWIN 建议池', idea_remove: '从建议池拿掉', add_decision: '加入待决策',
  update_goal: '更新目标进度', task_done: '项目任务打钩', task_add: '给项目加任务', task_due: '改项目任务截止', project_priority: '改项目优先级', task_priority: '改任务优先级', task_rename: '改任务名', task_delete: '删掉项目任务', task_merge: '合并任务', subtask_add: '拆成几步', subtask_done: '做完一步',
  task_reopen: '任务改回没做完', project_due: '改项目最终截止', project_status: '改项目状态', project_create: '新建项目', project_link: '存项目链接', project_profile: '补充项目画像',
  reopen_todo: '待办取消打钩', todo_rename: '改待办', todo_due: '改待办截止', todo_priority: '改待办优先级', todo_delete: '删掉待办', decision_close: '结掉待决策', asset_update: '改资产卡片 · 私密，只存本地', add_income: '记一笔收入 · 私密，只存本地', job_eval: '接单评估',
  file_move: '整理文件', note_create: '新建笔记', note_append: '补充到文档', add_asset: '新建资产卡片 · 私密，只存本地' };
const PSTATUS = { active: '进行中', paused: '暂停', done: '已完成', dropped: '放弃', archived: '归档' };
const ASTATUS = { in_use: '在用', idle: '闲置', lent: '借出', broken: '坏了', sold: '已卖' };
const ACAT = [['device', '数码设备'], ['digital', '账号与订阅'], ['tool', '工具仪器'], ['parts', '开发板与模块'], ['physical', '其他实物'], ['lease', '房屋与租约']];
const TEXT_ACTIONS = new Set(['add_todo', 'add_event', 'add_idea', 'add_decision']);
const CHIPS = [
  ['今天先做什么？', '按截止、目标和优先级排一下'],
  ['帮我评估一个单', '把客户需求发过来就行'],
  ['记账 ', '比如“记账 800 南瓜”，只存本地，不发给 AI'],
  ['推荐几款最近好玩的单机游戏', '随便聊什么都可以'],
];

// 输入框里没发出去的话：切到别的页面、刷新都留着（只存在这台设备的浏览器里），每个对话各存各的
const drafts = (() => { try { return JSON.parse(pref('drafts', '{}')) || {}; } catch (e) { return {}; } })();
function saveDraft(v) {
  const k = chat.id || 'new'; if ((drafts[k] || '') === v) return;
  if (v.trim()) { delete drafts[k]; drafts[k] = v; } else delete drafts[k];
  const ks = Object.keys(drafts); if (ks.length > 30) delete drafts[ks[0]];
  setPref('drafts', JSON.stringify(drafts));
}
async function viewChat(id) {
  setTitle('TWIN'); const ok = fresh(); editIdx = -1;
  if (id && id !== chat.id) { let c; try { c = await api('/api/chat?id=' + encodeURIComponent(id)); } catch (e) { if (ok()) { toast(e.message); location.hash = 'c'; } return; } if (!ok()) return; chat = c; }
  if (!id) { chat = { id: '', title: '', messages: [], project: pendingProj, auto: '' }; pendingProj = ''; }
  projList = null;
  if (!aiCfg.presets.length) await loadAi().catch(() => {});
  if (!ok()) return;
  $('#view').innerHTML = `<div class="chatwrap"><div class="chatview"><div class="msgs" id="msgs"><div class="wrap" id="mlist"></div></div>
    <div class="composer"><div class="cbox"><div class="atts" id="atts"></div><textarea id="inp" rows="1" placeholder="问点什么，或者直接说发生了什么事"></textarea>
      <div class="cbar"><button class="clip" type="button" id="clipBtn" title="加附件：存进暂存箱，AI 帮你决定放哪" aria-label="加附件"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5l-8.6 8.6a5 5 0 01-7.1-7.1l8.6-8.6a3.3 3.3 0 014.7 4.7l-8.6 8.6a1.7 1.7 0 01-2.4-2.4l8-8"/></svg></button><input type="file" id="clipIn" multiple hidden>${provSelect('prov')}<select id="cpPick" class="cppick" aria-label="关联项目" data-icon="${esc(FOLDER)}"><option value="" data-short="自动">自动匹配项目</option></select><button type="button" class="cproj" id="cproj" aria-label="关联项目"></button><button class="btn" type="button" id="expBtn" title="把知识库摘要和这句话一起复制，粘到任何 AI 网页" style="padding:4px 10px;font-size:12.5px"><span class="wide">复制给其他 AI</span><span class="narrow">复制</span></button>${tip(`文件可以拖进来或粘贴截图，先存进暂存箱。<br>AI 看得到摘要、项目任务和相关文档，私密内容和敏感值不发；要改文件都会先给你确认。${coarse ? '' : '<br>Enter 发送，Shift+Enter 换行。'}`)}
      <span class="sp"></span><button class="send" id="sendBtn" aria-label="发送" disabled><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 19V5M5 12l7-7 7 7"/></svg></button></div></div>
</div></div><aside class="cside" id="cside" aria-label="关联项目"></aside></div>`;
  const sc = $('#msgs'); stick = true; stickTop = 0;
  sc.onscroll = () => { stick = sc.scrollHeight - sc.scrollTop - sc.clientHeight < 80 || (stick && sc.scrollTop >= stickTop); stickTop = sc.scrollTop; };
  const inp = $('#inp');
  const grow = () => { inp.style.height = 'auto'; inp.style.height = Math.min(inp.scrollHeight, 220) + 'px'; $('#sendBtn').disabled = (!inp.value.trim() && !atts.length) || sending; };
  inp.oninput = () => { grow(); saveDraft(inp.value); };
  // 附件：点回形针、拖进来、粘贴截图都行。先放在这里，发送时才存进暂存箱
  const addFiles = fl => { for (const f of fl) { if (f.size > 25 * 1024 * 1024) { toast(`${f.name} 超过 25 MB，请直接复制到 _INBOX 文件夹`, 6000); continue; } atts.push(f); } drawAtts(); grow(); };
  $('#clipBtn').onclick = () => $('#clipIn').click();
  $('#clipIn').onchange = e => { addFiles(e.target.files); e.target.value = ''; };
  inp.onpaste = e => { const fl = [...(e.clipboardData || {}).files || []]; if (fl.length) { e.preventDefault(); addFiles(fl.map((f, k) => f.name === 'image.png' ? new File([f], `截图_${Date.now()}_${k}.png`, { type: f.type }) : f)); } };
  const cv = $('.chatview');
  cv.ondragover = e => { if ([...e.dataTransfer.types].includes('Files')) { e.preventDefault(); cv.classList.add('drop'); } };
  cv.ondragleave = e => { if (!cv.contains(e.relatedTarget)) cv.classList.remove('drop'); };
  cv.ondrop = e => { e.preventDefault(); cv.classList.remove('drop'); addFiles(e.dataTransfer.files); };
  drawAtts();
  inp.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && !coarse) { e.preventDefault(); send(); } };
  $('#sendBtn').onclick = send;
  $('#expBtn').onclick = async () => { try { const j = await api('/api/export', { question: inp.value });
    if (await copyText(j.text)) toast(`已复制（约 ${j.text.length} 字），粘到任何 AI 网页即可`, 4500); } catch (e) { toast(e.message, 6000); } };
  // 从一个对话点到另一个对话：只淡入消息区（输入框不动）。在路由里整页重播会先把旧对话闪一下，再淡入新对话
  drawMsgs(); drawProj(); fancy($('#prov')); if (viewChat.last != null && viewChat.last !== chat.id && !$('#view').classList.contains('enter')) replay($('#mlist'), 'fade'); viewChat.last = chat.id;
  $('#cproj').onclick = () => { const m = modal('<div class="cside insheet"></div><div class="row"><button class="btn" id="mx">关闭</button></div>'); m.querySelector('#mx').onclick = closeModal; drawProj(); };
  // pendingSend：带过来的话直接发出去（比如雅思“让 AI 批改”），不用再点发送
  if (!pendingAsk && drafts[chat.id || 'new']) { inp.value = drafts[chat.id || 'new']; grow(); }
  if (pendingAsk) { inp.value = pendingAsk; pendingAsk = ''; inp.dispatchEvent(new Event('input')); if (pendingSend) { pendingSend = false; send(); } }
  if (!coarse) inp.focus();
}

function drawAtts() {
  const box = $('#atts'); if (!box) return;
  box.innerHTML = atts.map((f, k) => `<span class="att">${esc(f.name)}<small>${f.size < 1024 * 1024 ? Math.ceil(f.size / 1024) + ' KB' : (f.size / 1048576).toFixed(1) + ' MB'}</small><button type="button" data-k="${k}" aria-label="去掉">×</button></span>`).join('');
  box.querySelectorAll('[data-k]').forEach(b => b.onclick = () => { atts.splice(+b.dataset.k, 1); drawAtts(); $('#inp').dispatchEvent(new Event('input')); });
}
// ----- 对话关联的项目：右侧栏（手机上是输入框上面的一行，点开是弹窗）-----
// chat.project：'' = 自动匹配，'none' = 不关联，其余是项目板块路径；chat.auto = 自动匹配到的路径
let projList = null;
const curProj = () => chat.project === 'none' ? '' : chat.project || chat.auto || '';
async function drawProj() {
  const ok = fresh(), boxes = [...document.querySelectorAll('.cside')]; if (!boxes.length) return;
  if (!projList) { try { projList = (await api('/api/home')).boards.map(b => ({ path: b.path, name: shortName(b.name) })); } catch (e) { projList = []; } }
  const path = curProj(); let b = null;
  if (path) { try { b = await api('/api/board?path=' + encodeURIComponent(path)); } catch (e) { b = null; } }
  if (!ok()) return;
  const DONE = '✓ 已完成';
  const sel = `<select id="cpSel" aria-label="关联项目"><option value="">自动${!chat.project && chat.auto ? '（' + esc((projList.find(x => x.path === chat.auto) || { name: '' }).name) + '）' : ''}</option>
    ${projList.map(x => `<option value="${esc(x.path)}" ${chat.project === x.path ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}<option value="none" ${chat.project === 'none' ? 'selected' : ''}>不关联项目</option></select>`;
  let body;
  if (!b) body = `<p class="note">${chat.project === 'none' ? '这段对话不关联项目。' : '还没关联项目。'} ${tip('说到某个项目时会自动关联，也可以在上面直接选。关联后 AI 会按你说的进展提议打勾或加任务，你确认了才写入。')}</p>`;
  else {
    const open = b.tasks.filter(t => t.status !== DONE), todo = open;
    // 右侧栏窄：一件事一行，长的省略（鼠标停上去看全文）；截止只写几个字
    const dueS = t => t.days == null ? '' : `<em class="cdue ${t.days <= 1 ? 'hot' : t.days <= 7 ? 'warm' : ''}" title="${esc(t.due)} 截止">${t.days < 0 ? `过期${-t.days}天` : t.days === 0 ? '今天' : t.days === 1 ? '明天' : `${t.days}天`}</em>`;
    const row = t => `<li class="row crow">${chk(false, `data-k data-i="${t.i}"`)}<span class="tx" data-full="${esc(t.task)}">${esc(t.task)}${subCount(t)}</span>${dueS(t)}</li>`;
    body = `<a class="cpname" href="${bLink(b.path)}">${esc(shortName(b.name))}<span>${!chat.project ? '自动' : ''}</span></a>
      <p class="note">${b.done}/${b.total} 完成 · 项目截止 ${dueTag({ due: b.due, days: b.days }) || '未定'}</p>
      <div class="track thin"><div class="fill" style="width:${b.total ? Math.round(b.done / b.total * 100) : 0}%"></div></div>
      ${(b.links || []).length ? `<div class="plinks">${b.links.map(l => `<span class="plink"><a href="${esc(l.url)}" target="_blank" rel="noopener" title="${esc(l.url)}">${esc(l.name)}</a></span>`).join('')}</div>` : ''}
      ${todo.length ? `<div class="gl">待做</div><ul class="list">${todo.slice(0, 5).map(row).join('')}</ul>${todo.length > 5 ? `<ul class="list" data-rest hidden>${todo.slice(5).map(row).join('')}</ul><button type="button" class="linkbtn cmore" data-cmore>还有 ${todo.length - 5} 件</button>` : ''}` : ''}
      ${!open.length ? '<p class="note">任务都做完了。</p>' : ''}`;
  }
  const chip = $('#cproj'); if (chip) chip.innerHTML = `<b>${b ? esc(shortName(b.name)) : chat.project === 'none' ? '不关联项目' : '项目：自动'}</b>${b && !chat.project ? '<small>自动</small>' : ''}<i>▾</i>`;
  // 新对话：在输入框里直接选项目（右侧栏要等有了对话才出现）。输入框里先放好“自动”一项，项目列表取回来再补全，不然“自动”会晚一下才闪出来
  const pick = $('#cpPick'); if (pick) { pick.innerHTML = `<option value="" data-short="自动">自动匹配项目</option>${projList.map(x => `<option value="${esc(x.path)}" ${chat.project === x.path ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}<option value="none" data-short="不关联">不关联项目</option>`;
    pick.onchange = () => { chat.project = pick.value; drawProj(); }; fancy(pick); }
  boxes.forEach(box => {
    box.innerHTML = `<div class="cphead"><span>关联项目</span>${sel}</div>${body}`;
    box.querySelector('#cpSel').onchange = async e => { chat.project = e.target.value; if (chat.id) await saveChat().catch(() => {}); drawProj(); };
    fancy(box.querySelector('#cpSel'));
    if (!b) return;
    // “还有几件”就地展开 / 收起；要去项目页点上面的项目名。显示不全的任务，鼠标停上去用提示框看全文
    const more = box.querySelector('[data-cmore]'); if (more) more.onclick = () => { const r = box.querySelector('[data-rest]'); r.hidden = !r.hidden; more.textContent = r.hidden ? `还有 ${r.children.length} 件` : '收起'; };
    box.onpointerover = e => { const x = e.target.closest('.crow .tx[data-full]'); if (x) { if (x.scrollWidth > x.clientWidth) x.dataset.tip = x.dataset.full; else delete x.dataset.tip; } };
    const act = async a => { try { await api('/api/action', { action: { ...a, path: b.path } }); } catch (e) { toast(e.message, 6000); } drawProj(); };
    bindChecks(box, el => act({ type: 'set_task', i: +el.dataset.i, status: DONE }));
  });
}

const userHtml = t => esc(t).replace(/\[附件：([^\]\n]+)\]/g, '<span class="att in">📎 $1</span>');

// 异步拿到数据后填进去：原来是空的就淡入，免得内容“啪”一下弹出来；原来有内容（刷新）就直接换
function fillIn(el, html) { if (!el) return; const was = el.childElementCount; el.innerHTML = html; if (!was) replay(el, 'fade'); }
async function drawHello() {
  const box = $('#mlist'); const hr = new Date().getHours();
  const hi = hr < 6 ? '夜深了' : hr < 11 ? '早上好' : hr < 14 ? '中午好' : hr < 18 ? '下午好' : '晚上好';
  box.innerHTML = `<div class="hello"><h1>${hi}${pref('name') ? '，' + esc(pref('name')) : ''}</h1><p class="sub">问什么都行，也可以直接告诉我发生了什么，我帮你记下来。</p>
    <div id="strip" class="${drawHello.strip ? 'on' : ''}"><div class="stripin">${drawHello.strip || ''}</div></div><div class="chips">${CHIPS.map(([t, s]) => `<button type="button" data-t="${esc(t)}">${esc(t)}<small>${esc(s)}</small></button>`).join('')}</div>
    ${aiCfg.providers.length ? '' : `<div class="panel" style="margin-top:18px"><b>还没接 AI。</b><p class="note" style="margin:4px 0 10px">到设置里选一家、填 API key 就能对话。没有 key 也可以用“复制给其他 AI”。</p><a class="btn primary" href="#settings">去设置</a></div>`}</div>`;
  box.querySelectorAll('.chips button').forEach(b => b.onclick = () => { const inp = $('#inp'); inp.value = tr(b.dataset.t); inp.dispatchEvent(new Event('input'));
    if (/[：:\s]$/.test(inp.value)) inp.focus(); else send(); });
  try { const h = await api('/api/home');
    const steps = (h.boards || []).filter(b => b.next.length).slice(0, 4).map(b => `<li>${pri(b.loose ? b.next[0].priority : b.priority)}<a class="tx" href="${bLink(b.path)}"><b>${esc(shortName(b.name))}</b> · ${esc(b.next[0].task)}</a>${dueTag({ due: b.next[0].due, days: b.next[0].days })}</li>`);
    const items = [...steps, ...h.reviews.slice(0, 1).map(r => `<li><span class="pri P2">回看</span><a class="tx" href="${libLink(r.path)}">${esc(r.title)}</a></li>`)];
    // 第一次：内容先放进去，再把高度从 0 展开，下面的按钮是被慢慢推下去的，不是一下跳下去
    const s = $('#strip'); if (s) { const first = !s.classList.contains('on'); s.firstElementChild.innerHTML = drawHello.strip = `<div class="todaystrip"><div class="k"><span>接下来</span><a href="#today">全部待办</a></div><ul>${items.join('') || '<li class="note">没有待办。</li>'}</ul></div>`;
      if (first) requestAnimationFrame(() => s.classList.add('on')); }
  } catch (e) { /* 首页摘要拿不到不影响对话 */ }
}

// 回答下面列出这次的依据：关联项目，加上按相关度挑中、真的发给 AI 的资料；点一下打开原文，核对它说的有没有根据
function srcName(p) { const parts = p.replace(/\.md$/, '').split('/'), last = parts.at(-1);
  return last === 'board' || last === 'index' ? `${parts.at(-2)} · ${last === 'board' ? '任务' : '说明'}` : last; }
function srcHtml(list) { if (!list || !list.length) return '';
  return `<div class="srcs"><span class="lbl">依据</span>${list.map(p => `<a href="${p.endsWith('/board.md') ? bLink(p) : libLink(p)}" title="${esc(p)}">${esc(srcName(p))}</a>`).join('')}</div>`; }
// 思考过程：在回答上面，灰色、可折叠。正在想的时候展开，开始回答后收起，点一下能再展开
function thinkHtml(m) { if (!m.think) return ''; const now = m.streaming && !m.content;
  return `<details class="think"${now ? ' open' : ''}><summary>${now ? '正在思考…' : '思考过程'}</summary><div class="tk" translate="no">${esc(m.think)}</div></details>`; }
// 消息下面的小图标按钮：鼠标停上去有说明
const ib = (attrs, icon, tip) => `<button type="button" class="ib" ${attrs} data-tip="${tip}" aria-label="${tip}">${lu(icon, 15)}</button>`;
function userMsg(m, i) {
  if (i === editIdx) { const later = chat.messages.length - 1 > i + 1;
    return `<div class="m-uedit"><textarea id="uedit" rows="3">${esc(m.content)}</textarea>
      <div class="row">${later ? '<span class="note">发送后，这句后面的对话会换成新的回答</span>' : ''}<span style="flex:1"></span><button type="button" class="btn sm" id="ueX">取消</button><button type="button" class="btn sm primary" id="ueGo">发送</button></div></div>`; }
  return `<div class="m-uwrap"><div class="m-user">${userHtml(m.content)}</div><div class="uacts">${ib(`data-copy="${i}"`, 'copy', '复制')}${m.local ? '' : ib(`data-edit="${i}"`, 'pencil', '编辑')}</div></div>`;
}
function drawMsgs() {
  const box = $('#mlist'); if (!box) return; hideTip();  // 按钮重画了，停在旧按钮上的说明框也收掉
  const cw = $('.chatwrap'); if (cw) cw.classList.toggle('has-msgs', chat.messages.length > 0);
  if (!chat.messages.length) return drawHello();
  const sm = chat.summary && chat.summary.upto > 0 && chat.summary.upto < chat.messages.length ? chat.summary : null;
  box.innerHTML = chat.messages.map((m, i) => (sm && i === sm.upto ? `<details class="csum"><summary>上面的对话已自动总结，AI 按总结记得前面聊过什么 · 看总结</summary><div class="tk" translate="no">${esc(sm.text)}</div></details>` : '') + (m.role === 'user' ? userMsg(m, i) : `
    <div class="m-ai ${m.streaming ? 'live' : ''}"><div class="body"><div class="who">${esc(m.who || 'AI')}</div>
      ${m.pending ? `<div class="thinking"><i></i><i></i><i></i>${m.note ? `<span class="note">${esc(m.note)}</span>` : ''}</div>` : m.streaming ? `${thinkHtml(m)}<div class="md">${m.content || !m.think ? render(m.content, true) + '<span class="caretblink"></span>' : ''}</div>` : `${thinkHtml(m)}<div class="md">${render(m.content, true)}</div>
      ${srcHtml(m.sources)}
      ${(m.actions || []).length ? `<div class="cards">${previewHtml(m, i)}${m.actions.map((a, j) => FORM_ACTIONS.has(a.type) ? actionCard(a, i, j) : '').join('')}</div>` : ''}
      <div class="acts">${ib(`data-copy="${i}"`, 'copy', '复制')}
        ${i === chat.messages.length - 1 && m.who !== '本地' ? ib('id="retry"', 'rotate-ccw', '重新回答') : ''}
        ${m.rated ? `<span class="done">已记录：${esc(m.rated)}</span>` : `${ib(`data-rate="1" data-i="${i}"`, 'thumbs-up', '有用')}${ib(`data-rate="0" data-i="${i}"`, 'thumbs-down', '没用')}`}</div>`}</div></div>`)).join('');
  box.querySelectorAll('[data-copy]').forEach(b => b.onclick = async () => { if (!await copyText(chat.messages[+b.dataset.copy].content)) return;
    b.innerHTML = lu('check', 15); b.classList.add('ok'); setTimeout(() => { b.innerHTML = lu('copy', 15); b.classList.remove('ok'); }, 1500); });
  box.querySelectorAll('[data-edit]').forEach(b => b.onclick = () => { if (sending) return; editIdx = +b.dataset.edit; drawMsgs(); });
  const ue = $('#uedit');
  if (ue) { ue.focus(); ue.setSelectionRange(ue.value.length, ue.value.length); ue.style.height = Math.min(ue.scrollHeight + 2, 300) + 'px';
    const cancel = () => { editIdx = -1; drawMsgs(); };
    ue.oninput = () => { ue.style.height = 'auto'; ue.style.height = Math.min(ue.scrollHeight + 2, 300) + 'px'; };
    ue.onkeydown = e => { if (e.key === 'Escape') cancel(); else if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); resend(editIdx, ue.value); } };
    $('#ueX').onclick = cancel; $('#ueGo').onclick = () => resend(editIdx, ue.value); }
  box.querySelectorAll('[data-rate]').forEach(b => b.onclick = () => rate(+b.dataset.i, b.dataset.rate === '1'));
  const rt = $('#retry'); if (rt) rt.onclick = retry;
  bindCards(box); bindPreview(box);
  if (!ue) toBottom();
}

async function saveChat() {
  if (!chat.title) { const f = chat.messages.find(m => m.role === 'user'); chat.title = f ? (f.content.replace(/\[附件：([^\]\n]+)\]/g, ' $1').trim()).slice(0, 24) : '新对话'; }
  // 资产价格只在确认写入时用一次，不存进对话记录
  const clean = chat.messages.filter(m => !m.pending).map(m => m.actions ? { ...m, actions: m.actions.map(({ price, value_range, ...a }) => a) } : m);
  const j = await api('/api/chat/save', { id: chat.id, title: chat.title, project: chat.project || '', auto: chat.auto || '', titled: chat.titled || '', messages: clean, ...(chat.summary ? { summary: chat.summary } : {}) });
  const isNew = !chat.id; chat.id = j.id;
  if (isNew) { history.replaceState(null, '', '#c/' + chat.id); }
  loadHist();
}

// 标题：第一轮回答后让 AI 按内容起一个，第三轮再按聊开的内容改一次。旧对话继续聊时也补上
async function send() {
  const inp = $('#inp'); let q = inp.value.trim(); if ((!q && !atts.length) || sending) return;
  const acc = !atts.length && q.match(/^(?:记账|income\b)\s*([0-9]+(?:\.[0-9]+)?)\s*元?\s*(.*)$/);
  if (acc) { // 金额只在本地记，不发给 AI
    inp.value = ''; inp.dispatchEvent(new Event('input'));
    chat.messages.push({ role: 'user', content: q, local: true }, { role: 'assistant', who: '本地', content: '这条只在本地处理，没有发给 AI。确认后写进私密的收入记录。',
      actions: [{ type: 'add_income', amount: acc[1], source: acc[2] || '', date: today() }] });
    await saveChat(); return drawMsgs();
  }
  if (!aiCfg.providers.length) return toast('先到设置里接一家 AI，或者点“复制给其他 AI”');
  const sel = $('#prov'), who = sel ? sel.options[sel.selectedIndex].text : 'AI';
  sending = true;
  if (atts.length) { // 附件先存进暂存箱（只在本机），AI 只看到文件名和去掉敏感值的文本内容
    $('#sendBtn').disabled = true; const names = [];
    for (const f of atts) { const data = await new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = no; r.readAsDataURL(f); });
      try { names.push((await api('/api/inbox/upload', { name: f.name, data })).name); } catch (e) { toast(e.message, 6000); sending = false; inp.dispatchEvent(new Event('input')); return; } }
    atts = []; drawAtts(); api('/api/inbox').then(d => inboxBadge(d.items.length)).catch(() => {});
    q = (q || '帮我整理一下这些附件') + '\n' + names.map(n => `[附件：${n}]`).join('\n');
  }
  inp.value = ''; inp.dispatchEvent(new Event('input'));
  chat.messages.push({ role: 'user', content: q }, { role: 'assistant', pending: true, who });
  stick = true; drawMsgs(); await ask(sel && sel.value, who, q);
}
// 每张确认卡的结果也告诉 AI，免得它重复提已经写过的
function cardResults(m) {
  const xs = (m.actions || []).map(a => { const what = `${ACTION_LABEL[a.type] || a.type}（${a.text || a.name || a.match || a.project || a.from || a.title || ''}）`;
    return a.state === 'done' ? `已写入：${what}${a.result ? ' → ' + a.result : ''}` : a.state === 'skip' ? `他没要：${what}` : a.state === 'fail' || a.err ? `失败：${what}，原因：${a.err}` : `还没处理：${what}`; });
  return xs.length ? `[上一条回答的确认卡结果（系统记录）：${xs.join('；')}]` : '';
}
// 发给 AI 的消息：本地记账那类不发；确认卡结果放进他下一句话的开头，不接在 AI 回答后面（接在后面 AI 会学着自己编一段“已写入”）
// from / to 是 chat.messages 的下标；from 前一条 AI 回答的确认卡结果也带上
function sendable(from, to) {
  const ok = m => !m.pending && !m.local && m.who !== '本地';
  const prev = chat.messages[from - 1]; let carry = prev && prev.role === 'assistant' && ok(prev) ? cardResults(prev) : '';
  return chat.messages.slice(from, to).filter(ok).map(m => { if (m.role === 'assistant') { carry = cardResults(m); return { role: m.role, content: m.content.split(/\n*\[(?:上一条回答的)?确认卡结果/)[0] }; }
    const c = carry ? carry.trim() + '\n\n' + m.content : m.content; carry = ''; return { role: m.role, content: c }; });
}
// 聊长了自动压缩：没总结过的消息超过 COMPACT_AT 条，就把除了最近 KEEP 条以外的让 AI 总结（和旧总结合并），之后只发总结 + 最近几轮
const COMPACT_AT = 24, KEEP = 10;
async function compact(pid, last) {
  const from = chat.summary ? chat.summary.upto : 0, idx = [];
  chat.messages.slice(from, last).forEach((m, k) => { if (!m.pending && !m.local && m.who !== '本地') idx.push(from + k); });
  if (idx.length <= COMPACT_AT) return;
  let cut = idx[idx.length - KEEP]; if (chat.messages[cut].role === 'assistant') cut = idx[idx.length - KEEP - 1];  // 从他的一句话开始留
  const m = chat.messages[last]; m.note = '聊得有点长，先把前面的对话总结一下…'; drawMsgs();
  try { const j = await api('/api/chat/compact', { summary: chat.summary ? chat.summary.text : '', messages: sendable(from, cut), provider_id: pid });
    chat.summary = { upto: cut, text: j.summary };
  } catch (e) { /* 没总结成：这次照旧发最近 30 条，下次再试 */ }
  delete m.note; drawMsgs();
}
async function ask(pid, who, restore) {
  pvBoards = {}; let ok = false;
  const last = chat.messages.length - 1;
  try {
    await compact(pid, last);
    const from = chat.summary ? chat.summary.upto : 0, msgs = sendable(from, last);
    const r = await fetch('/api/ask/stream', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Twin': '1' }, body: JSON.stringify({ messages: msgs, provider_id: pid, project: chat.project || '', summary: from ? chat.summary.text : '' }) });
    if (r.status === 401) { location.reload(); return; }
    if (!r.ok || !r.body) throw new Error((await r.json().catch(() => ({}))).error || '出错了');
    const reader = r.body.getReader(), dec = new TextDecoder(); let buf = '', text = '', think = '', fin = null, t = 0;
    // 第一次画整条消息，之后只换正在写的那一段，不重画整个列表（整列表重画会闪，滚动也会一顿一顿）
    // 想→答换阶段时整条重画一次（收起思考框），同一阶段里只换字
    const paint = () => { const m = chat.messages[last], was = m.content; m.content = text.split('```twin-actions')[0]; m.who = who; if (think) m.think = think;
      const live = !m.pending && $('#mlist > .m-ai.live:last-child'), md = live && live.querySelector('.md'), tk = live && live.querySelector('.think .tk');
      if (md && (!think || tk) && !!was === !!m.content) {
        if (m.content) md.innerHTML = render(m.content, true) + '<span class="caretblink"></span>';
        if (tk && !m.content) { tk.textContent = think; tk.scrollTop = tk.scrollHeight; }
        toBottom();
      } else { m.pending = false; m.streaming = true; drawMsgs(); } };
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      let k; while ((k = buf.indexOf('\n\n')) >= 0) {
        const line = buf.slice(0, k); buf = buf.slice(k + 2); if (!line.startsWith('data: ')) continue;
        const ev = JSON.parse(line.slice(6));
        if (ev.error) throw new Error(ev.error);
        if ('project' in ev && !ev.delta && !ev.done) { if (!chat.project && ev.project !== (chat.auto || '')) { chat.auto = ev.project; drawProj(); } }
        if (ev.delta) { text += ev.delta; if (Date.now() - t > 80) { t = Date.now(); paint(); } }
        if (ev.think) { think += ev.think; if (Date.now() - t > 80) { t = Date.now(); paint(); } }
        if (ev.done) fin = ev;
      }
    }
    if (!fin) throw new Error('AI 的回答中断了，点“重新回答”再试一次');
    chat.messages[last] = { role: 'assistant', content: fin.answer, actions: fin.actions || [], who, ...(think ? { think } : {}), ...(fin.sources && fin.sources.length ? { sources: fin.sources } : {}) };
    await saveChat(); ok = true;
  } catch (e) {
    chat.messages.splice(-2, 2); toast(e.message, 8000);
    const inp = $('#inp'); if (inp && restore) { inp.value = restore; inp.dispatchEvent(new Event('input')); }
  }
  sending = false; drawMsgs(); const inp = $('#inp'); if (inp) inp.dispatchEvent(new Event('input'));
  return ok;
}
// 改了自己说的话再发：这句后面的对话换成新的回答；没发成就恢复原样
async function resend(i, text) {
  text = (text || '').trim(); if (!text || sending) return;
  const sel = $('#prov'), who = sel ? sel.options[sel.selectedIndex].text : 'AI', before = chat.messages;
  const sumBefore = chat.summary; if (chat.summary && i < chat.summary.upto) delete chat.summary;  // 改了已经总结过的话：总结作废，需要时重新总结
  editIdx = -1; chat.messages = [...before.slice(0, i), { role: 'user', content: text }, { role: 'assistant', pending: true, who }];
  sending = true; stick = true; drawMsgs();
  if (!await ask(sel && sel.value, who)) { chat.messages = before; if (sumBefore) chat.summary = sumBefore; drawMsgs(); }
}
async function retry() {
  if (sending) return; const sel = $('#prov'), who = sel ? sel.options[sel.selectedIndex].text : 'AI', before = chat.messages;
  chat.messages = [...before.slice(0, -1), { role: 'assistant', pending: true, who }]; sending = true; stick = true; drawMsgs();
  if (!await ask(sel && sel.value, who)) { chat.messages = before; drawMsgs(); }  // 没答成：原来的回答留着
}
function rate(i, useful) {
  const q = (chat.messages.slice(0, i).reverse().find(m => m.role === 'user') || {}).content || '';
  const done = async note => { await api('/api/feedback', { useful, question: q, note }); chat.messages[i].rated = useful ? '有用' : '没用'; await saveChat(); drawMsgs(); };
  if (useful) return done('');
  const m = modal(`<h3>哪里没用？</h3><p class="note">一句话就行，比如“没考虑我在准备申博”。每周复盘升级时会用到。</p><input id="fbn" placeholder="可以不写"><div class="row"><button class="btn" id="mx">取消</button><button class="btn primary" id="mok">提交</button></div>`);
  m.querySelector('#mx').onclick = closeModal; m.querySelector('#mok').onclick = async () => { const v = m.querySelector('#fbn').value; closeModal(); done(v); };
  m.querySelector('#fbn').focus();
}

// ----- 确认卡片 -----
function describe(a) {
  if (a.type === 'complete_todo') return `把含“${esc(a.match)}”的待办打钩`;
  if (a.type === 'project_priority') return `${esc(a.project)}：改成 ${esc(a.priority)}`;
  if (a.type === 'task_priority') return `${esc(a.project)}：含“${esc(a.match)}”的任务改成 ${esc(a.priority)}`;
  if (a.type === 'task_reopen') return `${esc(a.project)}：含“${esc(a.match)}”的已完成任务改回没做完`;
  if (a.type === 'project_link') return `${esc(a.project)}：存链接“${esc(a.name || '链接')}”<small>${esc(a.url)}</small>`;
  if (a.type === 'project_profile') return `${esc(shortName(a.project || ''))} · ${esc(a.section || '现状')}<small>${(Array.isArray(a.items) ? a.items : [a.text || '']).map(x => '· ' + esc(x)).join(' ')}</small>`;
  if (a.type === 'project_due') return `${esc(a.project)}：最终截止改成 ${esc(a.due || '无')}`;
  if (a.type === 'project_status') return `${esc(a.project)}：改成“${esc(PSTATUS[a.status] || a.status)}”${a.status !== 'active' ? '，不再出现在今天页' : ''}`;
  if (a.type === 'project_create') return `${esc(a.name)} · ${esc(a.priority || 'P2')}${a.due ? ' · 截止 ' + esc(a.due) : ''}<div class="pv">放在 ${esc(a.parent)}/${esc(a.folder || a.name)}${a.goal ? '\n目标：' + esc(a.goal) : ''}${(a.tasks || []).map(t => '\n· ' + esc(t.text)).join('')}</div>`;
  if (a.type === 'reopen_todo') return `把含“${esc(a.match)}”的待办取消打钩`;
  if (a.type === 'todo_rename') return `含“${esc(a.match)}”的待办改成“${esc(a.text)}”`;
  if (a.type === 'todo_priority') return `含“${esc(a.match)}”的待办改成 ${esc(a.priority)}`;
  if (a.type === 'todo_due') return `含“${esc(a.match)}”的待办截止改成 ${esc(a.due || '无')}`;
  if (a.type === 'idea_remove') return `从建议池拿掉含“${esc(a.match)}”的一条`;
  if (a.type === 'todo_delete') return `删掉含“${esc(a.match)}”的待办`;
  if (a.type === 'asset_update') return `${esc(a.match)}：${[a.status && ASTATUS[a.status] || a.status, a.qty && '数量 ' + a.qty, a.location && '放在 ' + a.location, a.expires && '到期 ' + a.expires, a.party && '对方 ' + a.party, a.note].filter(Boolean).map(esc).join('，')}`;
  if (a.type === 'task_rename') return `${esc(shortName(a.project || ''))}：“${esc(a.match)}” → “${esc(a.text)}”${a.note ? `<small>备注：${esc(a.note)}</small>` : ''}`;
  if (a.type === 'task_merge') return `${esc(shortName(a.project || ''))}：合成“${esc(a.text)}”<small>${(a.matches || []).map(m => '· ' + esc(m)).join(' ')}</small>`;
  if (a.type === 'subtask_add') return `${esc(shortName(a.project || ''))}：“${esc(a.match)}”<small>${(a.items || []).map(m => '○ ' + esc(m)).join('　')}</small>`;
  if (a.type === 'subtask_done') return `${esc(shortName(a.project || ''))}：“${esc(a.match)}” 的 ● ${esc(a.sub)}`;
  if (a.type === 'task_delete') return `${esc(a.project)}：删掉含“${esc(a.match)}”的任务`;
  if (a.type === 'task_add') return `${esc(shortName(a.project || ''))}：${esc(a.text)}${a.note ? `<small>${esc(a.note)}</small>` : ''}`;
  if (a.type === 'task_due') return `${esc(a.project)}：含“${esc(a.match)}”的任务截止改成 ${esc(a.due || '无')}`;
  if (a.type === 'task_done') return `${esc(a.project)}：含“${esc(a.match)}”的任务打钩`;
  if (a.type === 'update_goal') return `${esc(a.match)}：当前改成 ${esc(a.current)}`;
  if (a.type === 'file_move') return `${esc(a.from)} → ${esc(a.to_dir)}/${esc(a.name || '')}`;
  if (a.type === 'note_append') return `${esc(a.path)}${a.heading ? ' · ' + esc(a.heading) : ''}<div class="pv">${esc(a.text)}</div>`;
  if (a.type === 'add_income') return `${esc(a.amount)} 元 · ${esc(a.source || '')}${a.date ? ' · ' + esc(a.date) : ''}`;
  return '';
}
function actionCard(a, i, j) {
  if (a.type === 'job_eval') return jobCard(a, i, j);
  const label = ACTION_LABEL[a.type] || a.type;
  if (a.state === 'done') return `<div class="card ok slim"><span class="tag">✓ ${esc(label)}</span><div class="what">${esc(a.result || '')}</div></div>`;
  if (a.state === 'skip') return `<div class="card no slim"><span class="tag">已忽略 · ${esc(label)}</span><div class="what">${describe(a).replace(/<small>.*?<\/small>|<div class="pv">[\s\S]*?<\/div>/g, '')}</div></div>`;
  const editable = TEXT_ACTIONS.has(a.type);
  if (a.type === 'note_create') return `<div class="card" data-i="${i}" data-j="${j}"><div class="k">${esc(label)} · ${esc(a.dir)}</div>
    <div class="field"><input data-f="title" value="${esc(a.title)}" aria-label="标题"></div><div class="pv">${esc(a.text)}</div>
    <div class="row"><button class="btn primary" data-ok>确认写入</button><button class="btn" data-skip>不用</button></div></div>`;
  if (a.type === 'add_asset') return `<div class="card" data-i="${i}" data-j="${j}"><div class="k">${esc(label)}</div>
    <div class="grid3 aset"><div class="field"><label>分类</label><select data-f="category">${ACAT.map(([k, l]) => `<option value="${k}" ${k === (a.category || 'physical') ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
      ${[['name', '名称'], ['model', '型号 / 配置'], ['acquired', '购入 / 起租'], ['expires', '到期'], ['party', '对方'], ['qty', '数量'], ['location', '放在哪'], ['note', '用途 / 备注']].map(([k, l]) =>
      `<div class="field"><label>${l}</label><input data-f="${k}" value="${esc(a[k] || '')}"></div>`).join('')}
      <div class="field"><label>状态</label><select data-f="status">${Object.entries(ASTATUS).map(([k, l]) => `<option value="${k}" ${k === (a.status || 'in_use') ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
      <div class="field"><label>价格 / 租金区间（只在本地，不发给 AI）</label><input data-f="value_range" placeholder="比如 3k-5k" value="${esc(a.value_range || '')}"></div></div>
    <div class="row"><button class="btn primary" data-ok>确认写入</button><button class="btn" data-skip>不用</button></div></div>`;
  return `<div class="card slim" data-i="${i}" data-j="${j}"><span class="tag">${esc(label)}${a.priority ? ' · ' + esc(a.priority) : ''}${a.due ? ' · ' + esc(a.due.slice(5)) : ''}</span>
    ${editable ? `<div class="field"><input data-edit value="${esc(a.text)}" aria-label="内容，可以改"></div>` : `<div class="what">${describe(a)}</div>`}
    <div class="cacts"><button class="btn primary sm" data-ok title="确认写入">确认</button><button class="btn sm" data-skip title="不用" aria-label="不用">不用</button></div>${a.err ? `<div class="cerr">上次失败：${esc(a.err)}</div>` : ''}</div>`;
}
async function applyCard(a) {
  try { const r = await api('/api/action', { action: a, via: 'ai' }); a.state = 'done'; a.result = r.message; delete a.err;
    if (a.type === 'file_move') api('/api/inbox').then(d => inboxBadge(d.items.length)).catch(() => {});
    return true; }
  catch (e) { a.err = e.message; return false; }
}
function bindCards(box) {
  box.querySelectorAll('.card[data-i]').forEach(c => {
    const a = chat.messages[+c.dataset.i].actions[+c.dataset.j];
    if (a.type === 'job_eval') return bindJob(c, a);
    const ed = c.querySelector('[data-edit]'); if (ed) ed.oninput = () => { a.text = ed.value; };
    c.querySelectorAll('[data-f]').forEach(x => { if (x.tagName === 'SELECT') a[x.dataset.f] = x.value; x.oninput = x.onchange = () => { a[x.dataset.f] = x.value; }; });
    c.querySelector('[data-ok]').onclick = async () => { c.classList.add('busy');
      const ok = await applyCard(a); await saveChat();
      if (ok) { drawMsgs(); if (/^task_|^project_/.test(a.type)) drawProj(); } else { c.classList.remove('busy'); toast(a.err, 6000); } };
    c.querySelector('[data-skip]').onclick = async () => { a.state = 'skip'; await saveChat(); drawMsgs(); };
  });
}

// ----- 改动预览：AI 提的改动先画成“改完后的样子”，一键应用；哪一处不要就点 ✕ -----
// 要填表的（接单评估、新笔记、新资产、新项目）还是单独的卡片
const FORM_ACTIONS = new Set(['job_eval', 'note_create', 'add_asset', 'project_create']);
const BOARD_ACT = a => a.project && /^(task_|subtask_)/.test(a.type);
const DONE_ST = '✓ 已完成';
let pvBoards = {};  // 项目名 → 板块，预览时按需取
const pvBoard = name => pvBoards[name] || (pvBoards[name] = api('/api/board/find', { project: name }).catch(e => ({ error: e.message })));
const pvItems = m => (m.actions || []).map((a, j) => ({ a, j })).filter(x => !FORM_ACTIONS.has(x.a.type));
function subStatus(r) {  // 子任务带动任务状态，和后台一样
  const k = r.subs.filter(x => x.done).length;
  if (r.subs.length && k === r.subs.length) r.status = DONE_ST; else if (k) r.status = '进行中'; else if (r.status === DONE_ST) r.status = '未开始';
}
// 在本地把改动套到任务表的副本上，只用来画预览；真正写入还是后台按同样的规则做
function simulate(b, items) {
  const rows = b.tasks.map(t => ({ task: t.task, was: t.task, status: t.status, priority: t.priority, due: t.due, note: t.note,
    subs: (t.subs || []).map(x => ({ ...x })), kind: '', marks: [], js: [] }));
  const find = (key, done) => { key = String(key || '').trim(); const xs = rows.filter(r => r.kind !== 'del' && r.kind !== 'gone' && (r.status === DONE_ST) === done);
    const hit = xs.filter(r => r.task === key), h = hit.length ? hit : xs.filter(r => key && r.task.includes(key)); return h.length === 1 ? h[0] : null; };
  const touch = (r, j, mark) => { if (!r.kind) r.kind = 'mod'; if (!r.js.includes(j)) r.js.push(j); if (mark && !r.marks.includes(mark)) r.marks.push(mark); };
  const miss = [];
  for (const { a, j } of items) {
    const t = a.type;
    if (t === 'task_add') { rows.push({ task: a.text, status: '未开始', priority: a.priority || '', due: a.due || '', note: a.note || '', subs: [], kind: 'add', marks: [], js: [j] }); continue; }
    if (t === 'task_merge') {
      const rs = (a.matches || []).map(k => find(k, false));
      if (rs.length < 2 || rs.some(r => !r)) { miss.push({ j, text: `合并：有的任务找不到（${(a.matches || []).join('、')}）` }); continue; }
      const head = a.text || rs[0].task;
      const subs = rs.flatMap(r => r.subs.length ? r.subs : [{ text: r.task, done: r.status === DONE_ST }]).map(x => {
        const k = x.text.indexOf('：'), pre = x.text.slice(0, k); return { ...x, add: true, text: k > 0 && (head.includes(pre) || pre.includes(head)) ? x.text.slice(k + 1).trim() : x.text }; });
      rs.slice(1).forEach(r => { r.kind = 'del'; r.into = head; r.js.push(j); });
      rs[0].task = head; rs[0].was = head; rs[0].subs = subs; touch(rs[0], j, `${rs.length} 条合成一条`); subStatus(rs[0]); continue;
    }
    const r = find(a.match, t === 'task_reopen');
    if (!r) { miss.push({ j, text: `找不到含“${a.match}”的任务` }); continue; }
    if (t === 'task_delete') { r.kind = r.kind === 'add' ? 'gone' : 'del'; r.js.push(j); }
    else if (t === 'task_rename') { r.task = a.text; if ('note' in a) r.note = a.note; touch(r, j, '改名'); }
    else if (t === 'task_done') { r.status = DONE_ST; r.subs.forEach(x => { x.done = true; }); touch(r, j, '做完'); }
    else if (t === 'task_reopen') { r.status = '未开始'; touch(r, j, '改回没做完'); }
    else if (t === 'task_due') { r.due = a.due || ''; touch(r, j, a.due ? '截止 ' + a.due.slice(5) : '去掉截止'); }
    else if (t === 'task_priority') { r.priority = a.priority; touch(r, j, '改成 ' + a.priority); }
    else if (t === 'subtask_add') { for (const x of a.items || []) if (!r.subs.some(y => y.text === x)) r.subs.push({ text: x, done: false, add: true }); touch(r, j, '拆成几步'); subStatus(r); }
    else if (t === 'subtask_done') {
      const s = r.subs.filter(x => x.text === a.sub), s2 = s.length ? s : r.subs.filter(x => a.sub && x.text.includes(a.sub));
      if (s2.length !== 1) { miss.push({ j, text: `找不到子任务“${a.sub}”` }); continue; }
      s2[0].done = true; s2[0].tick = true; touch(r, j, '做完一步'); subStatus(r);
    }
  }
  // 并入别的任务的那几条不单独列：合并后的任务下面的圆点就是它们
  return { rows: rows.filter(r => r.kind && r.kind !== 'gone' && !r.into), same: rows.filter(r => !r.kind).length, miss };
}
function pvRow(r, m) {
  const off = r.js.every(j => m.actions[j].off), st = r.status === DONE_ST ? 'done' : '';
  const tag = r.kind === 'add' ? '新增' : r.kind === 'del' ? (r.into ? `并入“${r.into}”` : '删掉') : r.marks.join(' · ');
  return `<li class="pvr ${r.kind} ${off ? 'off' : ''}"><span class="pvs ${st}" title="${esc(r.status)}"></span>
    <div class="pvt"><div class="pvn">${r.kind === 'mod' && r.was !== r.task ? `<s>${esc(r.was)}</s>` : ''}<span>${esc(r.task)}</span>${r.priority ? `<em>${esc(r.priority)}</em>` : ''}${r.due ? `<em>${esc(r.due.slice(5))}</em>` : ''}<i class="pvtag">${esc(tag)}</i></div>
      ${r.kind !== 'del' && r.subs.length ? `<ul class="subs mini">${r.subs.map(x => `<li class="${x.done ? 'on' : ''} ${x.add || x.tick ? 'new' : ''}"><span class="dot"></span><span>${esc(x.text)}</span></li>`).join('')}</ul>` : ''}
      ${r.kind === 'add' && r.note ? `<small>${esc(r.note)}</small>` : ''}</div>
    <button type="button" class="pvx" data-pvx="${r.js.join(',')}" title="${off ? '恢复这处' : '不要这处'}" aria-label="${off ? '恢复这处' : '不要这处'}">${off ? '恢复' : '✕'}</button></li>`;
}
function previewHtml(m, i) {
  const xs = pvItems(m); if (!xs.length) return '';
  if (xs.every(x => x.a.state)) {
    const done = xs.filter(x => x.a.state === 'done'), bad = xs.filter(x => x.a.state === 'fail'), skip = xs.filter(x => x.a.state === 'skip');
    const head = m.undone ? '已撤销这些改动' : done.length ? `✓ 已应用 ${done.length} 处改动${skip.length ? `，去掉 ${skip.length} 处` : ''}` : bad.length ? '没写成' : '这些改动没要';
    return `<div class="pvw sum"><div class="pvsum"><span>${head}</span>${done.length ? `<button type="button" class="linkbtn" data-pvmore>明细</button>` : ''}${m.undo && !m.undone && done.length ? `<button type="button" class="btn sm" data-pvundo="${i}">撤销</button>` : ''}</div>
      <ul class="pvlist" hidden>${done.map(x => `<li>${esc(x.a.result || '')}</li>`).join('')}</ul>${bad.map(x => `<p class="pvwarn">没写成：${esc(x.a.err || '')}</p>`).join('')}</div>`;
  }
  return `<div class="pvw" data-pv="${i}"><p class="note">正在生成预览…</p></div>`;
}
async function fillPreview(el, i) {
  const m = chat.messages[i], xs = pvItems(m).filter(x => !x.a.state), ok = fresh();
  const byProj = {}, other = [];
  xs.forEach(x => BOARD_ACT(x.a) ? (byProj[x.a.project] = byProj[x.a.project] || []).push(x) : other.push(x));
  const parts = [], miss = [];
  for (const [name, items] of Object.entries(byProj)) {
    const b = await pvBoard(name);
    if (b.error) { items.forEach(x => miss.push({ j: x.j, text: b.error })); continue; }
    const s = simulate(b, items); miss.push(...s.miss);
    parts.push(`<div class="pvh"><b>${esc(shortName(b.name))}</b><span>改完后的样子</span></div><ul class="pvrows">${s.rows.map(r => pvRow(r, m)).join('')}</ul>${s.same ? `<p class="pvsame">其余 ${s.same} 条不变</p>` : ''}`);
  }
  if (other.length) parts.push(`${parts.length ? '<div class="pvh"><b>其它</b></div>' : ''}<ul class="pvrows">${other.map(x => `<li class="pvr mod ${x.a.off ? 'off' : ''}"><span class="pvs"></span><div class="pvt"><div class="pvn"><span>${describe(x.a) || esc(ACTION_LABEL[x.a.type] || x.a.type)}</span><i class="pvtag">${esc(ACTION_LABEL[x.a.type] || '')}</i></div></div>
    <button type="button" class="pvx" data-pvx="${x.j}" title="${x.a.off ? '恢复这处' : '不要这处'}">${x.a.off ? '恢复' : '✕'}</button></li>`).join('')}</ul>`);
  miss.forEach(x => { m.actions[x.j].off = true; });  // 预览里就对不上的，先不写
  if (!ok() || !el.isConnected) return;
  const n = xs.filter(x => !x.a.off).length;
  el.innerHTML = `${parts.join('')}${miss.map(x => `<p class="pvwarn">${esc(x.text)}，这处先跳过</p>`).join('')}
    <div class="pvf"><button type="button" class="btn primary sm" data-pvok ${n ? '' : 'disabled'}>应用 ${n} 处改动</button><button type="button" class="btn sm" data-pvno>都不要</button>
      <span class="sp"></span>${tip('点 ✕ 去掉某一处，再点“恢复”加回来。<br>应用后可以点“撤销”一次全部改回，也可以在“改动历史”里撤销。', '说明')}</div>`;
  el.querySelectorAll('[data-pvx]').forEach(x => x.onclick = async () => { const js = x.dataset.pvx.split(',').map(Number), on = js.every(j => m.actions[j].off);
    js.forEach(j => { m.actions[j].off = !on; }); await saveChat(); fillPreview(el, i); });
  el.querySelector('[data-pvno]').onclick = async () => { xs.forEach(x => { x.a.state = 'skip'; }); await saveChat(); drawMsgs(); };
  el.querySelector('[data-pvok]').onclick = async e => {
    const go = xs.filter(x => !x.a.off); e.target.disabled = true; e.target.textContent = '写入中…';
    let r; try { r = await api('/api/actions', { actions: go.map(({ a }) => { const { off, state, err, result, ...rest } = a; return rest; }), via: 'ai' }); }
    catch (er) { e.target.disabled = false; e.target.textContent = `应用 ${go.length} 处改动`; return toast(er.message, 7000); }
    r.results.forEach((res, k) => { const a = go[k].a; if (res.ok) { a.state = 'done'; a.result = res.message; delete a.err; } else { a.state = 'fail'; a.err = res.error; } });
    xs.forEach(x => { if (!x.a.state) x.a.state = 'skip'; });
    m.undo = r.undo_id || ''; pvBoards = {};
    await saveChat(); drawMsgs(); drawProj();
    if (go.some(x => x.a.type === 'file_move')) api('/api/inbox').then(d => inboxBadge(d.items.length)).catch(() => {});
    const bad = r.results.filter(x => !x.ok).length; if (bad) toast(`${bad} 处没写成，原因在预览下面`, 7000);
  };
}
function bindPreview(box) {
  box.querySelectorAll('[data-pv]').forEach(el => fillPreview(el, +el.dataset.pv));
  box.querySelectorAll('[data-pvmore]').forEach(b => b.onclick = () => { const l = b.closest('.pvw').querySelector('.pvlist'); l.hidden = !l.hidden; b.textContent = l.hidden ? '明细' : '收起'; });
  box.querySelectorAll('[data-pvundo]').forEach(b => b.onclick = async () => { const m = chat.messages[+b.dataset.pvundo];
    try { const j = await api('/api/history/undo', { id: m.undo }); m.undone = true; await saveChat(); toast(j.message); pvBoards = {}; drawMsgs(); drawProj(); } catch (e) { toast(e.message, 7000); } });
}

// ----- 接单评估卡 -----
const SC = { pay: '报酬', learning: '学习价值', alignment: '方向对齐', clarity: '需求清晰', load: '当前负荷' };
const vClass = v => v === '接' ? 'yes' : v === '不接' ? 'no' : 'mid';
function seg(a, k, label) {
  return `<div class="field"><span class="lbl">${label}</span><div class="seg" data-k="${k}">${[1, 2, 3, 4, 5].map(n => `<button type="button" class="${(a[k] || 3) == n ? 'on' : ''}" data-n="${n}">${n}</button>`).join('')}</div></div>`;
}
function jobCard(a, i, j) {
  const L = a.local, o = a.opinion;
  return `<div class="card job" data-i="${i}" data-j="${j}">
    <div class="k">接单评估 · 先按你的规则在本地打分，AI 只给第二意见</div>
    <div class="field"><label>标题</label><input data-f="title" value="${esc(a.title)}"></div>
    <div class="field"><label>需求（会发给 AI，别贴联系方式）</label><textarea data-f="desc">${esc(a.desc)}</textarea></div>
    <div class="grid3"><div class="field"><label>报价（元，只在本地用）</label><input data-f="price" type="number" inputmode="decimal" value="${esc(a.price ?? '')}"></div>
      <div class="field"><label>你估的工时（小时）</label><input data-f="hours" type="number" inputmode="decimal" value="${esc(a.hours ?? '')}"></div>
      <div class="field"><label>截止</label><input data-f="deadline" type="date" value="${esc(a.deadline || '')}"></div></div>
    <div class="checks"><label><input type="checkbox" data-c="deposit" ${a.deposit ? 'checked' : ''}>有定金</label><label><input type="checkbox" data-c="contract" ${a.contract ? 'checked' : ''}>有书面约定</label></div>
    <div class="grid3">${seg(a, 'learning', '学习价值')}${seg(a, 'alignment', '方向对齐')}${seg(a, 'clarity', '需求清晰度')}</div>
    <div data-local>${L ? localHtml(L) : ''}</div>
    ${o ? aiHtml(o) : ''}
    <div class="row">${a.saved ? `<a class="btn" href="${libLink(a.saved)}">打开决策记录</a>` : `<button class="btn" data-ai>${o ? '重新问 AI' : '请 AI 给第二意见'}</button><button class="btn primary" data-save>存为决策记录</button>`}</div></div>`;
}
function localHtml(l) {
  return `<div class="score"><span class="big">${l.total}</span><span class="note">/ 100 · 本地规则</span><span class="v ${vClass(l.verdict)}">${l.verdict}</span></div>
    <div class="bars" style="margin-top:8px">${Object.entries(l.scores).map(([k, v]) => `<span>${SC[k]}</span><div class="track"><div class="fill" style="width:${v}%"></div></div><span class="n">${v}</span>`).join('')}</div>
    ${l.flags.map(f => `<div class="flag">⚠ ${esc(f)}</div>`).join('')}`;
}
function aiHtml(o) {
  const a = o.ai, L = (t, xs) => xs && xs.length ? `<div class="lbl">${t}</div><ul>${xs.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '';
  return `<div class="ailist"><div class="score"><span class="note">AI 第二意见</span><span class="v ${vClass(a.verdict)}">${esc(a.verdict || '?')}</span><span class="note">置信度 ${esc(a.confidence || '-')}</span></div>
    ${o.diffs.map(d => `<div class="diff" style="margin-top:8px">分歧：${esc(d)}</div>`).join('')}
    <p>${esc(a.summary || '')}</p><p class="note">AI 估工时 ${esc(a.hours_estimate ?? '-')} 小时（${esc(a.hours_reason || '')}）；建议报价调整 ${a.quote_adjust_pct > 0 ? '+' : ''}${esc(a.quote_adjust_pct ?? 0)}%</p>
    ${L('做过的类似项目', a.similar_projects)}${L('风险', a.risks)}${L('要问清客户的', a.missing_info)}${L('AI 的假设', a.assumptions)}</div>`;
}
function bindJob(c, a) {
  let t; const rescore = () => { clearTimeout(t); t = setTimeout(async () => { try { a.local = await api('/api/job/score', { job: a }); c.querySelector('[data-local]').innerHTML = localHtml(a.local); } catch (e) {} }, 300); };
  c.querySelectorAll('[data-f]').forEach(el => el.oninput = () => { a[el.dataset.f] = el.value; a.opinion = null; rescore(); });
  c.querySelectorAll('[data-c]').forEach(el => el.onchange = () => { a[el.dataset.c] = el.checked; rescore(); });
  c.querySelectorAll('.seg').forEach(s => s.querySelectorAll('button').forEach(b => b.onclick = () => { a[s.dataset.k] = +b.dataset.n;
    s.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); rescore(); }));
  if (!a.local) rescore();
  const ab = c.querySelector('[data-ai]'); if (ab) ab.onclick = async () => { c.classList.add('busy'); ab.textContent = 'AI 正在看…';
    try { const sel = $('#prov'); const j = await api('/api/job/ai', { job: a, provider_id: sel && sel.value }); a.local = j.local; a.opinion = { ai: j.ai, diffs: j.diffs }; await saveChat(); }
    catch (e) { toast(e.message, 7000); } drawMsgs(); };
  const sb = c.querySelector('[data-save]'); if (sb) sb.onclick = async () => { try { const j = await api('/api/job/save', { job: a, opinion: a.opinion }); a.saved = j.path; await saveChat(); drawMsgs(); toast('已存为决策记录，到期会提醒你回看'); } catch (e) { toast(e.message, 6000); } };
}
