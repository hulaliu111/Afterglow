#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把所有电影海报下载到 posters/ 目录，作为站点本地静态资源。

为什么需要：海报原图来自 image.tmdb.org（国内常被墙）/ doubanio.com（防盗链返回 418），
部署到公网后手机（无代理）加载不出来。下载到本地后，海报就是网站自带的资源，永远稳定。

- 文件名用电影 id（douban-{subject_id}.jpg），和 data.js 里的 id 一一对应；
- 幂等：已存在且非空的海报直接跳过，可重复运行 / 增量更新；
- 单张失败不中断（有前端文字占位兜底），最后打印失败清单。

用法：python3 scripts/download_posters.py
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(SCRIPT_DIR, "..")
DATA_DIR = os.path.join(ROOT, "data")
DOUBAN_FILE = os.path.join(DATA_DIR, "douban_top250.json")
TMDB_FILE = os.path.join(DATA_DIR, "tmdb_matched.json")
POSTER_DIR = os.path.join(ROOT, "posters")

POSTER_BASE = "https://image.tmdb.org/t/p/w500"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def subject_id(url):
    m = re.search(r"/subject/(\d+)", url or "")
    return m.group(1) if m else ""


def download(item):
    """item = (movie_id, poster_url)，返回 (movie_id, 状态)。"""
    mid, url = item
    path = os.path.join(POSTER_DIR, f"{mid}.jpg")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return mid, "skip"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(resp.content)
        os.replace(tmp, path)  # 原子替换，避免半截文件
        return mid, "ok"
    except Exception as e:  # noqa: BLE001
        return mid, f"失败: {e}"


def main():
    with open(DOUBAN_FILE, encoding="utf-8") as f:
        douban = json.load(f)
    tmdb_map = {}
    with open(TMDB_FILE, encoding="utf-8") as f:
        for t in json.load(f):
            tmdb_map[t.get("douban_url")] = t

    items = []
    for d in douban:
        mid = "douban-" + subject_id(d.get("url"))
        t = tmdb_map.get(d.get("url"), {})
        if t.get("poster_path"):
            items.append((mid, POSTER_BASE + t["poster_path"]))

    os.makedirs(POSTER_DIR, exist_ok=True)
    ok = skip = 0
    fails = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(download, it) for it in items]
        for i, fut in enumerate(as_completed(futures), 1):
            mid, status = fut.result()
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            else:
                fails.append((mid, status))
            if i % 50 == 0 or i == len(items):
                print(f"进度 {i}/{len(items)}")

    print(f"[完成] 共 {len(items)} 张：新下载 {ok}，已存在跳过 {skip}，失败 {len(fails)}")
    for mid, status in fails:
        print(f"  {mid}: {status}")
    # 单张失败不返回非零（前端有占位兜底，下次运行会自动重试缺失的图）
    if fails:
        print("[提示] 有海报下载失败，可稍后重跑本脚本补齐。")


if __name__ == "__main__":
    main()
