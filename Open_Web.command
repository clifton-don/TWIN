#!/bin/bash
# macOS 上双击打开 TWIN（相当于 Windows 的 Open_Web.bat）。
# 第一次双击如果提示“无法验证开发者”：右键这个文件 → 打开 → 再点“打开”，以后就能直接双击。
cd "$(dirname "$0")" || exit 1

# Python：TWIN 只用标准库，3.9 以上就行。新 Mac 第一次用 python3 会弹出“安装命令行开发者工具”，点安装即可。
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
  echo
  echo " 没找到可用的 Python 3。"
  echo " 如果刚才弹出了“安装命令行开发者工具”，点“安装”，装好后重新双击这个文件。"
  echo " 也可以从 https://www.python.org/downloads/ 下载安装（点最上面黄色的 Download Python）。"
  echo
  open "https://www.python.org/downloads/"
  read -r -p " 按回车关闭……" _
  exit 1
fi

# KeePassXC：没装就提示一次（Mac 上需要自己装，装一次就行）
if [ ! -d "/Applications/KeePassXC.app" ] && [ ! -d "$HOME/Applications/KeePassXC.app" ] && [ ! -f "tools/runtime/.no-keepassxc-mac" ]; then
  echo
  echo " 没找到 KeePassXC（本地加密的密码库，首页点网站时自动填密码用）。"
  echo " 下载地址：https://keepassxc.org/download/#macos （装好后把 KeePassXC 拖进“应用程序”）"
  read -r -p " 现在打开下载页吗？[y/N] " ans
  if [ "$ans" = "y" ] || [ "$ans" = "Y" ]; then
    open "https://keepassxc.org/download/#macos"
  else
    mkdir -p tools/runtime && touch tools/runtime/.no-keepassxc-mac
  fi
fi
if [ -d "/Applications/KeePassXC.app" ] && ! pgrep -x KeePassXC >/dev/null; then
  open -a KeePassXC
fi

python3 tools/twin_web.py "$@"
