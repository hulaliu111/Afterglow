#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合并「豆瓣 Top 250」和「TMDB 匹配」两份数据，生成前端 data.js（const MOVIES = [...]）。

- 海报、完整演员表、第二评分（TMDB 评分）来自 TMDB；
- 烂番茄接口不可用，rt_tomatometer / rt_audience 置 None（页面降级展示 TMDB 评分）。

用法：python3 scripts/build_data.py
"""
import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
DOUBAN_FILE = os.path.join(DATA_DIR, "douban_top250.json")
TMDB_FILE = os.path.join(DATA_DIR, "tmdb_matched.json")
CHART_FILE = os.path.join(DATA_DIR, "douban_chart.json")
OUT_FILE = os.path.join(SCRIPT_DIR, "..", "data.js")

# 海报改为下载到本地 posters/ 目录（scripts/download_posters.py 负责），
# 避免依赖 image.tmdb.org（国内被墙）/ doubanio.com（防盗链）


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_info(info):
    """从豆瓣列表页的 info 字符串提取 year / directors / actors / genres。"""
    year = ""
    m = re.search(r"(\d{4})", info)
    if m:
        year = m.group(1)

    directors, actors, genres = [], [], []

    dm = re.search(r"导演:\s*(.*?)\s*主演:", info)
    if dm:
        d = clean(re.sub(r"[A-Za-z][A-Za-z\s.\-]*", " ", dm.group(1)))
        if d:
            directors = [d]

    am = re.search(r"主演:\s*(.*?)\s*\d{4}", info)
    if am:
        for p in am.group(1).split("/"):
            p = clean(re.sub(r"[A-Za-z][A-Za-z\s.\-]*", " ", p))
            if p and p != "...":
                actors.append(p)

    parts = [clean(x) for x in info.split("/")]
    if parts:
        genres = [g for g in parts[-1].split() if g]

    return year, directors, actors, genres


def subject_id(url):
    m = re.search(r"/subject/(\d+)", url or "")
    return m.group(1) if m else ""


def build():
    with open(DOUBAN_FILE, encoding="utf-8") as f:
        douban = json.load(f)

    tmdb_map = {}
    if os.path.exists(TMDB_FILE):
        with open(TMDB_FILE, encoding="utf-8") as f:
            for t in json.load(f):
                tmdb_map[t.get("douban_url")] = t

    movies = []
    for d in douban:
        year, directors, actors, genres = parse_info(d.get("info", ""))
        t = tmdb_map.get(d.get("url"), {})

        # 演员：优先用 TMDB 完整演员表，否则用豆瓣解析的
        final_actors = t.get("actors") or actors
        # 导演：优先豆瓣中文名，否则用 TMDB
        final_directors = directors or ([t["director"]] if t.get("director") else [])

        mid = "douban-" + subject_id(d.get("url"))
        poster = f"posters/{mid}.jpg" if t.get("poster_path") else ""

        reason = d.get("quote", "").strip()
        if not reason:
            reason = f"豆瓣 Top 250 第 {d.get('rank', '')} 名，评分 {d.get('douban_rating', '')}。"

        movies.append({
            "id": mid,
            "title": d.get("title", ""),
            "title_en": d.get("title_en", ""),
            "year": year,
            "directors": final_directors,
            "actors": final_actors[:6],
            "genres": genres,
            "douban_rating": to_float(d.get("douban_rating")),
            "douban_votes": d.get("douban_votes", ""),
            "tmdb_rating": t.get("vote_average"),
            "rt_tomatometer": None,   # 烂番茄接口不可用，暂空
            "rt_audience": None,
            "reason": reason,
            "poster": poster,
            "overview": t.get("overview", ""),
            "douban_url": d.get("url", ""),
            "tmdb_id": t.get("tmdb_id"),
        })

    # 一周口碑榜（近期热门电影），字段由 fetch_chart.py 生成，直接透传
    chart = []
    if os.path.exists(CHART_FILE):
        with open(CHART_FILE, encoding="utf-8") as f:
            chart = json.load(f)

    js = "// 本文件由 scripts/build_data.py 自动生成，请勿手动编辑\n"
    js += "const MOVIES = " + json.dumps(movies, ensure_ascii=False, indent=2) + ";\n"
    js += "const CHART = " + json.dumps(chart, ensure_ascii=False, indent=2) + ";\n"
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"[完成] 已生成 {OUT_FILE}，共 {len(movies)} 部主片 + {len(chart)} 部口碑榜")


if __name__ == "__main__":
    build()
