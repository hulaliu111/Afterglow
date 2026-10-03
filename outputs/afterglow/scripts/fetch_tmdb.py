#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 TMDB 匹配豆瓣 Top 250，补齐：海报、TMDB 评分、完整演员表、导演、简介。

用法：
  python3 scripts/fetch_tmdb.py              # 处理全部
  python3 scripts/fetch_tmdb.py --limit 10   # 只处理前 10 部（测试用）

输出 data/tmdb_matched.json，用 douban_url 关联回豆瓣数据。
"""
import argparse
import json
import os
import re
import time

import requests

BASE = "https://api.themoviedb.org/3"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(SCRIPT_DIR, "..")
CONFIG_FILE = os.path.join(ROOT, "config.local.json")
IN_FILE = os.path.join(ROOT, "data", "douban_top250.json")
OUT_FILE = os.path.join(ROOT, "data", "tmdb_matched.json")

# 已知匹配错误的电影：豆瓣片名 -> 正确 TMDB id（手动修正，避免以后重跑再错）
OVERRIDES = {
    "哈利·波特与死亡圣器(下)": 12445,
    "情书": 47002,
    "告白": 54186,
}


def load_key():
    # CI 环境优先从环境变量读（GitHub Actions 用 secret 注入）
    env_key = os.environ.get("TMDB_API_KEY")
    if env_key:
        return env_key
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)["tmdb_api_key"]


def extract_year(info):
    m = re.search(r"(\d{4})", info or "")
    return m.group(1) if m else ""


def get_with_retry(url, params, retries=3):
    """带重试的 GET，应对偶发的 SSL / 网络错误。"""
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=20)
            resp.raise_for_status()
            return resp
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def search(key, query, year):
    params = {"api_key": key, "query": query, "language": "zh-CN"}
    if year:
        params["year"] = year
    resp = get_with_retry(f"{BASE}/search/movie", params)
    return resp.json().get("results", [])


def credits(key, movie_id):
    params = {"api_key": key, "language": "zh-CN"}
    resp = get_with_retry(f"{BASE}/movie/{movie_id}/credits", params)
    return resp.json()


def movie_detail(key, movie_id):
    params = {"api_key": key, "language": "zh-CN"}
    resp = get_with_retry(f"{BASE}/movie/{movie_id}", params)
    return resp.json()


def match_result(key, d):
    """先按英文名+年份匹配，再退回中文名。年份差 ≤1 才算命中。"""
    title_en = (d.get("title_en") or "").strip()
    title = (d.get("title") or "").strip()
    year = extract_year(d.get("info"))

    for q in (title_en, title):
        if not q:
            continue
        results = search(key, q, year)
        for res in results:
            ry = (res.get("release_date") or "")[:4]
            if year and ry and abs(int(year) - int(ry)) <= 1:
                return res
        if results:
            return results[0]
    return None


def process(key, d):
    res = None
    tmdb_id = OVERRIDES.get(d.get("title"))
    if tmdb_id:
        try:
            res = movie_detail(key, tmdb_id)  # 手动修正，直接取正确电影
        except Exception:
            res = match_result(key, d)
    if res is None:
        res = match_result(key, d)

    if not res:
        return {"douban_url": d.get("url"), "matched": False}

    out = {
        "douban_url": d.get("url"),
        "matched": True,
        "tmdb_id": res.get("id"),
        "matched_title": res.get("title") or res.get("original_title"),
        "matched_year": (res.get("release_date") or "")[:4],
        "poster_path": res.get("poster_path"),
        "vote_average": res.get("vote_average"),
        "vote_count": res.get("vote_count"),
        "overview": res.get("overview"),
        "director": "",
        "actors": [],
    }
    try:
        cr = credits(key, res.get("id"))
        out["actors"] = [c.get("name") for c in cr.get("cast", [])[:6]]
        for c in cr.get("crew", []):
            if c.get("job") == "Director":
                out["director"] = c.get("name")
                break
    except Exception:
        pass
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 部，0 表示全部")
    args = parser.parse_args()

    key = load_key()
    with open(IN_FILE, encoding="utf-8") as f:
        douban = json.load(f)

    items = douban[: args.limit] if args.limit else douban
    results = []
    matched = 0
    for i, d in enumerate(items, 1):
        r = process(key, d)
        results.append(r)
        if r.get("matched"):
            matched += 1
        print(f"[{i}/{len(items)}] {d.get('title')} -> "
              f"{r.get('matched_title', '未匹配')}")
        time.sleep(0.5)  # 控制速率，降低触发限流/断连的概率

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    tmp = OUT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT_FILE)
    print(f"[完成] 共 {len(results)} 部，匹配成功 {matched} 部，写入 {OUT_FILE}")


if __name__ == "__main__":
    main()
