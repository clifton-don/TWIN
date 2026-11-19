"""twin_ai 拆出来的功能模块。

各部分顶部会 import twin_ai 核心；先导入 twin_ai，保证不管从哪个模块开始导入，都按 twin_ai -> jobs -> boards -> ... 的顺序加载。
"""
import twin_ai  # noqa: F401
