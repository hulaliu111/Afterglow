#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
采集豆瓣「一周口碑榜」（近期热门电影），存成 JSON。

数据来源拆成两段（豆瓣详情页被 302 反爬拦截，改用轻量接口）：
  1. https://movie.douban.com/chart  列表页：拿到排名 + 片名 + subject_id；
  2. https://movie.douban.com/j/subject_abstract?subject_id=…  轻量接口：
     拿到豆瓣评分(rate)、导演、演员、类型、年份、一条热门短评（详情页拿不到，这个接口能通）。
  3. 海报：豆瓣接口不返回海报，用 TMDB 搜索按中文名+年份匹配补 poster_path，
     再下载到 posters/ 目录（和 Top250 同一套本地化方案）。

失败回退策略：
  - 列表页必须抓到完整 10 部才写文件，否则保留旧数据；
  - TMDB 单部匹配失败不致命（海报留空，前端有占位兜底），下次运行自动重试。

用法：python3 scripts/fetch_chart.py
"""
import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

CHART_URL = "https://movie.douban.com/chart"
ABSTRACT_URL = "https://movie.douban.com/j/subject_abstract"
TMDB_BASE = "https://api.themoviedb.org/3"
POSTER_BASE = "https://image.tmdb.org/t/p/w500"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(SCRIPT_DIR, "..")
DATA_DIR = os.path.join(ROOT, "data")
POSTER_DIR = os.path.join(ROOT, "posters")
CONFIG_FILE = os.path.join(ROOT, "config.local.json")
OUT_FILE = os.path.join(DATA_DIR, "douban_chart.json")


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def subject_id(url):
    m = re.search(r"/subject/(\d+)", url or "")
    return m.group(1) if m else ""


def fetch_chart_list():
    """抓 chart 列表页，解析「一周口碑榜」的 10 部片（排名 + 片名 + 链接）。"""
    resp = requests.get(CHART_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    ul = soup.select_one("#listCont2")
    if not ul:
        # 兜底：新片榜在 listCont3，找不到口碑榜就报错
        raise RuntimeError("没找到「一周口碑榜」列表（#listCont2），页面结构可能变了")

    items = []
    for li in ul.select("li"):
        no = li.select_one(".no")
        name_a = li.select_one(".name a")
        if not name_a:
            continue
        items.append({
            "rank": clean(no.text) if no else "",
            "title": clean(name_a.text),
            "douban_url": name_a.get("href", ""),
        })
    return items


def fetch_abstract(sid):
    """调 subject_abstract 轻量接口，拿豆瓣评分/导演/演员/类型/年份/短评。"""
    params = {"subject_id": sid}
    headers = dict(HEADERS)
    headers["Referer"] = f"https://movie.douban.com/subject/{sid}/"
    resp = requests.get(ABSTRACT_URL, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    subj = data.get("subject") or {}
    sc = subj.get("short_comment") or {}
    return {
        "douban_rating": to_float(subj.get("rate")),
        "directors": subj.get("directors") or [],
        "actors": subj.get("actors") or [],
        "genres": subj.get("types") or [],
        "year": str(subj.get("release_year") or ""),
        "region": subj.get("region") or "",
        "duration": subj.get("duration") or "",
        "short_comment": sc.get("content", ""),
    }


def load_tmdb_key():
    env_key = os.environ.get("TMDB_API_KEY")
    if env_key:
        return env_key
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)["tmdb_api_key"]
    except (OSError, KeyError):
        return None


def tmdb_search_poster(key, title, year):
    """用中文名+年份搜 TMDB，返回第一个有海报的结果的 (tmdb_id, poster_path, vote_average)。"""
    if not key:
        return None, None, None
    params = {"api_key": key, "query": title, "language": "zh-CN"}
    if year:
        params["year"] = year
    resp = requests.get(f"{TMDB_BASE}/search/movie", params=params, timeout=20)
    resp.raise_for_status()
    for res in resp.json().get("results", []):
        if res.get("poster_path"):
            va = res.get("vote_average")
            return res.get("id"), res.get("poster_path"), (va if va else None)
    return None, None, None


def download_poster(sid, poster_path):
    """下载海报到 posters/douban-{subject_id}.jpg，幂等。返回最终相对路径或空串。"""
    if not poster_path:
        return ""
    rel = f"posters/douban-{sid}.jpg"
    path = os.path.join(ROOT, rel)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return rel
    os.makedirs(POSTER_DIR, exist_ok=True)
    try:
        resp = requests.get(POSTER_BASE + poster_path, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(resp.content)
        os.replace(tmp, path)
        return rel
    except Exception as e:  # noqa: BLE001
        print(f"  [海报] {sid} 下载失败：{e}")
        return ""


def main():
    items = fetch_chart_list()
    if len(items) < 10:
        print(f"[失败] 口碑榜只抓到 {len(items)} 部，不足 10 部，保留旧数据不变。")
        sys.exit(1)

    key = load_tmdb_key()
    print(f"[1/2] 口碑榜抓到 {len(items)} 部，开始补详情…")

    chart = []
    for i, it in enumerate(items, 1):
        sid = subject_id(it["douban_url"])
        entry = dict(it)
        entry["subject_id"] = sid

        # 豆瓣详情（评分/导演/演员/类型/年份/短评）
        try:
            abs_data = fetch_abstract(sid)
            entry.update(abs_data)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i}] {it['title']} subject_abstract 失败：{e}")

        # TMDB 补海报 + 评分
        try:
            tmdb_id, poster_path, vote_average = tmdb_search_poster(key, it["title"], entry.get("year"))
            entry["tmdb_id"] = tmdb_id
            entry["tmdb_rating"] = vote_average
            entry["poster"] = download_poster(sid, poster_path)
        except Exception as e:  # noqa: BLE001
            entry["tmdb_id"] = None
            entry["tmdb_rating"] = None
            entry["poster"] = ""
            print(f"  [{i}] {it['title']} TMDB 匹配失败（海报/评分留空）：{e}")

        chart.append(entry)
        print(f"  [{i}/{len(items)}] {it['title']} 豆瓣 {entry.get('douban_rating')} 分"
              f"{'，海报 ok' if entry.get('poster') else ''}")
        time.sleep(1)  # 礼貌间隔

    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = OUT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(chart, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT_FILE)
    print(f"[完成] 口碑榜 {len(chart)} 部，已写入 {OUT_FILE}")


if __name__ == "__main__":
    main()
