# -*- coding: utf-8 -*-
"""把所有原始碼合併成一個 txt 檔：原始碼.txt（每次更新後執行一次）"""
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "原始碼.txt")
FILES = [
    "crrank_clicker.py",
    "make_source_txt.py",
    "README.md",
    "docs/index.html",
    ".gitignore",
    "android/build.ps1",
    "android/AndroidManifest.xml",
    "android/res/values/strings.xml",
    "android/res/xml/accessibility_config.xml",
    "android/res/drawable/ic_launcher.xml",
    "android/assets/harvest.js",
    "android/assets/phone.html",
]
SRC_DIR = "android/src/com/crrank/autoharvest"


def main():
    files = list(FILES)
    for name in sorted(os.listdir(os.path.join(HERE, SRC_DIR))):
        if name.endswith(".java"):
            files.append(f"{SRC_DIR}/{name}")
    parts = [
        "CR Rank 自動收成器 — 全部原始碼",
        f"產生時間：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "檔案清單：",
        *[f"  {i + 1}. {f}" for i, f in enumerate(files)],
        "",
    ]
    for i, f in enumerate(files):
        with open(os.path.join(HERE, f), "r", encoding="utf-8-sig") as fh:
            body = fh.read().rstrip("\n")
        bar = "=" * 80
        parts += [bar, f"檔案 {i + 1}/{len(files)}：{f}", bar, body, ""]
    with open(OUT, "w", encoding="utf-8-sig", newline="\r\n") as fh:
        fh.write("\n".join(parts))
    print(f"已產生 {OUT}（{len(files)} 個檔案）")


if __name__ == "__main__":
    main()
