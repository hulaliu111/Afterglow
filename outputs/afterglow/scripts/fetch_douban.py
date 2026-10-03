#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
采集豆瓣 Top 250，存成 JSON。

失败回退策略：
  - 先写临时文件，全部抓取成功后再原子替换正式文件；
  - 中途出错则直接退出，不覆盖上一次成功的数据。

用法：
  python3 scripts/fetch_douban.py              # 抓全部 10 页
  python3 scripts/fetch_douban.py --limit 1    # 只抓第 1 页（测试用）
"""
import argparse
import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

BASE = "https://movie.douban.com/top250"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
OUT_FILE = os.path.join(DATA_DIR, "douban_top250.json")


def clean(s):
    """把空白字符压成一个空格，去掉首尾空格。"""
    return re.sub(r"\s+", " ", s or "").strip()


def fetch_page(start):
    url = f"{BASE}?start={start}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_movie(item):
    # 片名：第一个 .title 是中文名
    title_spans = item.select(".hd .title")
    title = clean(title_spans[0].text) if title_spans else ""

    # 英文名/原片名：第二个 .title（取最后一个 / 后面的部分，避开港译台译）
    title_en = ""
    if len(title_spans) >= 2:
        title_en = clean(title_spans[1].text).split("/")[-1].strip()
    if not title_en:
        other = item.select_one(".hd .other")
        if other:
            title_en = clean(other.text).split("/")[-1].strip()

    # 排名
    rank_el = item.select_one(".pic em")
    rank = clean(rank_el.text) if rank_el else ""

    # 评分
    rating_el = item.select_one(".rating_num")
    douban_rating = clean(rating_el.text) if rating_el else ""

    # 评价人数：评分所在容器里最后一个 span
    douban_votes = ""
    if rating_el:
        parent = rating_el.find_parent("div")
        if parent:
            spans = parent.find_all("span")
            if spans:
                douban_votes = clean(spans[-1].text)

    # 一句短评引言（可作推荐理由候选）
    inq = item.select_one(".quote span")
    quote = clean(inq.text) if inq else ""

    # 海报、详情链接
    img = item.select_one(".pic img")
    poster = img["src"] if img else ""
    a = item.select_one(".hd a")
    url = a["href"] if a else ""

    # 导演 / 主演 / 年份 / 国家 / 类型 的原始文字
    p = item.select_one(".bd p")
    info = clean(p.text) if p else ""

    return {
        "rank": rank,
        "title": title,
        "title_en": title_en,
        "douban_rating": douban_rating,
        "douban_votes": douban_votes,
        "quote": quote,
        "poster": poster,
        "url": url,
        "info": info,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10,
                        help="抓取前几页（每页 25 部），默认 10 页")
    args = parser.parse_args()

    movies = []
    for page in range(args.limit):
        start = page * 25
        html = fetch_page(start)
        soup = BeautifulSoup(html, "lxml")
        items = soup.select(".grid_view li")
        if not items:
            print(f"[警告] 第 {page + 1} 页没解析到任何电影，可能被反爬拦截，停止。")
            break
        for item in items:
            movies.append(parse_movie(item))
        print(f"第 {page + 1} 页完成，共 {len(movies)} 部")
        time.sleep(2)  # 礼貌间隔，降低被封风险

    expected = args.limit * 25
    if len(movies) < expected:
        print(f"[失败] 只抓到 {len(movies)}/{expected} 部，数据不完整，保留旧数据不变。")
        sys.exit(1)  # 非零退出码，让 CI 任务失败，不提交残缺数据

    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = OUT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT_FILE)  # 原子替换，成功才覆盖旧文件
    print(f"[完成] 共 {len(movies)} 部电影，已写入 {OUT_FILE}")


if __name__ == "__main__":
    main()
