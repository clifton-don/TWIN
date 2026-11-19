# 怎么写一个插件

一个插件就是 `tools/plugins/` 里的一个文件夹，文件夹名就是插件 id（小写字母、数字、下划线）。最少两个文件：

```
tools/plugins/hello/
  plugin.py   后端：名字、说明、处理 /api/p/hello/... 的请求
  plugin.js   网页：小组件、设置面板、要做的事
```

拷进来以后重启 TWIN，在侧栏左下角抽屉里的“插件”打开开关就能用。也可以把文件夹打成 zip，用“安装插件”上传。

## plugin.py

```python
"""hello：一句话说明这个插件做什么。"""
from twin import ROOT          # 知识库根目录；插件自己的资料放进知识库，移除插件也不会丢

NAME = "打个招呼"               # 插件列表里显示的名字
DESC = "首页显示今天打了几次招呼。"  # 一句说明
DATA = ROOT / "02_Life" / "hello.json"


def get(path, qs):             # GET /api/p/hello/<path>
    if path == "count":
        return {"n": int(DATA.read_text()) if DATA.exists() else 0}
    raise RuntimeError("没有这个功能。")   # 报错的文字会直接显示给用户


def post(path, body):          # POST /api/p/hello/<path>，body 是网页发来的 json
    if path == "hi":
        n = get("count", {})["n"] + 1
        DATA.parent.mkdir(parents=True, exist_ok=True)
        DATA.write_text(str(n))
        return {"n": n}
    raise RuntimeError("没有这个功能。")
```

- 插件关着的时候，`plugin.py` 不会运行，`NAME`、`DESC` 是直接从文件里读出来的，所以这两个要写成普通字符串。
- 要用 AI 就 `import twin_ai`：先 `twin_ai.check_outgoing(text)` 挡住敏感信息，再 `twin_ai.call_model(系统提示, 消息, twin_ai.active_provider(), 最多字数)`。只在用户点按钮时调用，别自动调。

## plugin.js

```js
'use strict';
(() => {
  const P = '/api/p/hello/';
  (window.TwinPlugins ||= {}).hello = {
    // 首页小组件（可以不写）。第一次打开插件时自动放到首页
    widget: { name: '招呼', desc: '今天打了几次招呼', icon: 'lightbulb',
      load: put => api(P + 'count').then(put),
      draw: (box, d) => { box.innerHTML = `<span class="hwt">招呼</span><span class="hwbig">${d.n}<small>次</small></span>`;
        box.onclick = async () => { await api(P + 'hi', {}); window.viewHome?.refreshW?.('hello'); }; } },
    // 插件弹窗里点“设置”时画的内容（可以不写）
    panel(el) { el.innerHTML = '<p class="note">这个插件没有要设置的。</p>'; },
    // 关掉插件时调用：把加过的东西（定时器、事件、元素、样式）都拿掉，这样关掉马上就和没装一样
    stop() {},
  };
})();
```

- 网页里能直接用 TWIN 的几个函数：`api(url, body)`（不带 body 是 GET）、`toast(文字)`、`dlg(...)`、`pref(k, 默认)` / `setPref(k, v)`（存在这台设备上）、`esc(文字)`。
- 小组件的 `icon` 用 Lucide 图标名，要是 TWIN 里还没有这个图标，会显示成默认图标。
- 样式写在插件自己的 `<style>` 里，类名加上插件名做前缀，免得和别的冲突；颜色用 `var(--ink)`、`var(--paper)`、`var(--rule)` 这些，白天黑夜就都好看。

完整的例子可以看 `ielts/`（雅思小练习）。
