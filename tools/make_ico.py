"""把 tools/web/logo-{尺寸}.png 拼成 tools/web/logo.ico（开发用，只用标准库）。

先跑 tools/make_logo.ps1 生成各尺寸 PNG，再跑：python tools/make_ico.py
ICO 里直接放 PNG 数据（Vista 以后都认），托盘、快捷方式按需要取合适的尺寸。
"""
import struct
from pathlib import Path

WEB = Path(__file__).resolve().parent / "web"
SIZES = [16, 20, 24, 32, 40, 48, 64, 256]


def main():
    images = [(s, (WEB / f"logo-{s}.png").read_bytes()) for s in SIZES]
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = len(head) + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        b = 0 if size >= 256 else size  # 256 在目录里写 0
        entries += struct.pack("<BBBBHHII", b, b, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    (WEB / "logo.ico").write_bytes(head + entries + blobs)
    print(f"已生成 {WEB / 'logo.ico'}（{len(images)} 个尺寸）")


if __name__ == "__main__":
    main()
