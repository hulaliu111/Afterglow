#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只重新匹配 OVERRIDES 里手动修正的 3 部电影，并写回 tmdb_matched.json。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_tmdb as ft


def main():
    key = ft.load_key()
    douban = json.load(open(ft.IN_FILE, encoding="utf-8"))
    tmdb = json.load(open(ft.OUT_FILE, encoding="utf-8"))

    targets = set(ft.OVERRIDES.keys())
    new_list = []
    for t in tmdb:
        d = next((dd for dd in douban if dd["url"] == t["douban_url"]), None)
        if d and d["title"] in targets:
            r = ft.process(key, d)
            new_list.append(r)
            print(f'{d["title"]} -> {r.get("matched_title")} (id {r.get("tmdb_id")}, '
                  f'year {r.get("matched_year")})')
            time.sleep(0.5)
        else:
            new_list.append(t)

    tmp = ft.OUT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(new_list, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ft.OUT_FILE)
    print(f"[完成] 已写回 {ft.OUT_FILE}")


if __name__ == "__main__":
    main()
