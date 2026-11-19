'use strict';
// 界面语言：中文（默认）或英文。选英文时，按 en.js 里的词典把页面上的中文换成英文：
// 代码里的字不改；一段字只有能整段翻完（翻完不剩汉字）才换，翻不完的保持原样，所以你自己写的任务名、笔记不会被改得半中半英。
// 只改显示，不改文件；输入框、对话内容、文档正文不碰。语言也写进 cookie，后台据此让 AI 用英文回答。
const LANG = (() => { try { return localStorage.getItem('twin.lang') === 'en' ? 'en' : 'zh'; } catch (e) { return 'zh'; } })();
document.cookie = `twin_lang=${LANG}; path=/; SameSite=Strict; max-age=31536000`;
if (LANG === 'en') document.write('<script src="/static/en.js"><\/script>');
const HAN = /[㐀-鿿]/;
let trFrag = null;
function tr(s) {
  if (LANG !== 'en' || !s || !HAN.test(s)) return s;
  if (s.includes('\n')) return s.split('\n').map(tr).join('\n');  // 多行的逐行翻
  const D = window.I18N_EN || {}, t = s.trim();
  if (D[t] != null && !HAN.test(D[t])) return s.replace(t, D[t]);
  let r = t;
  for (const [re, to] of window.I18N_RX || []) r = r.replace(re, to);
  if (HAN.test(r)) {  // 再按词组拼：长的先换，单字最后
    trFrag ||= new RegExp(Object.keys(D).sort((a, b) => b.length - a.length).map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'g');
    r = r.replace(trFrag, m => ` ${D[m]} `);
  }
  if (HAN.test(r)) return s;  // 翻不完就不动
  r = r.replace(/[“”]/g, '"').replace(/[‘’]/g, "'").replace(/，/g, ', ').replace(/。/g, '. ').replace(/：/g, ': ').replace(/；/g, '; ')
    .replace(/（/g, ' (').replace(/）/g, ') ').replace(/？/g, '? ').replace(/！/g, '! ').replace(/、/g, ', ').replace(/…/g, '...')
    .replace(/\s+([,.:;)?!])/g, '$1').replace(/\(\s+/g, '(').replace(/\s{2,}/g, ' ').trim();
  return s.replace(t, r);
}
if (LANG === 'en') {
  document.documentElement.lang = 'en';
  const SKIP = 'textarea,input,pre,code,.md,.m-user,[contenteditable],[translate=no],script,style';
  const ATTRS = ['title', 'placeholder', 'aria-label', 'data-tip', 'alt'];
  const doText = n => { const p = n.parentElement; if (!p || p.closest(SKIP)) return; const v = tr(n.nodeValue); if (v !== n.nodeValue) n.nodeValue = v; };
  const doEl = el => { if (el.closest(SKIP + ',svg') && !el.matches('input,textarea')) return;
    for (const a of ATTRS) { const v = el.getAttribute(a); if (v && HAN.test(v)) { const t = tr(v); if (t !== v) el.setAttribute(a, t); } } };
  const walk = root => {
    if (root.nodeType === 3) return doText(root);
    if (root.nodeType !== 1) return;
    doEl(root);
    const w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) n.nodeType === 3 ? doText(n) : doEl(n);
  };
  new MutationObserver(ms => { for (const m of ms) {
    if (m.type === 'childList') m.addedNodes.forEach(walk);
    else if (m.type === 'characterData') doText(m.target);
    else if (m.type === 'attributes') doEl(m.target);
  } }).observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  // 标签页标题
  const td = Object.getOwnPropertyDescriptor(Document.prototype, 'title');
  Object.defineProperty(document, 'title', { get() { return td.get.call(this); }, set(v) { td.set.call(this, tr(String(v))); } });
  // 确认框和弹窗文字
  const c0 = window.confirm.bind(window), a0 = window.alert.bind(window), p0 = window.prompt.bind(window);
  window.confirm = m => c0(tr(String(m))); window.alert = m => a0(tr(String(m))); window.prompt = (m, d) => p0(tr(String(m)), d);
}
