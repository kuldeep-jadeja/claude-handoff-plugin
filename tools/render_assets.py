#!/usr/bin/env python3
"""Render the README artwork in assets/src/ to PNG with headless Chrome.

  python3 tools/render_assets.py

Writes assets/banner-light.png, assets/banner-dark.png, assets/how-it-works-light.png,
assets/how-it-works-dark.png (at 2x), and the 1024px icons used by the plugin
manifests (.claude-plugin/icon.png, assets/icon.png) from assets/logo.svg.
Needs google-chrome or chromium on PATH and the Ubuntu Sans fonts.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "src")
PAGES = [("banner", 1280, 400), ("how-it-works", 1280, 560)]


def chrome():
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    sys.exit("Chrome or Chromium is needed on PATH.")


def shoot(url, width, height, out, scale=2, transparent=False):
    args = [
        chrome(), "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--allow-file-access-from-files", f"--force-device-scale-factor={scale}",
        f"--window-size={width},{height}", f"--screenshot={out}",
    ]
    if transparent:
        args.append("--default-background-color=00000000")
    subprocess.run(args + [url], check=True, capture_output=True)
    print("wrote", os.path.relpath(out, ROOT))


def main():
    for page, width, height in PAGES:
        url = "file://" + os.path.join(SRC, page + ".html")
        for theme in ("light", "dark"):
            out = os.path.join(ROOT, "assets", f"{page}-{theme}.png")
            shoot(url + ("#dark" if theme == "dark" else ""), width, height, out)
    icon = os.path.join(ROOT, "assets", "icon.png")
    shoot("file://" + os.path.join(SRC, "icon.html"), 1024, 1024, icon, scale=1, transparent=True)
    shutil.copy(icon, os.path.join(ROOT, ".claude-plugin", "icon.png"))
    print("wrote .claude-plugin/icon.png")


if __name__ == "__main__":
    main()
