#!/usr/bin/env python3
"""维护 Afterglow 的独立精选剧集片库（不修改电影数据）。

离线生成浏览器文件：python3 scripts/fetch_series.py
核验资料并更新海报：TMDB_API_KEY=... python3 scripts/fetch_series.py --refresh
也可通过 --config /path/to/config.local.json 读取本地 tmdb_api_key。

来源：TMDB Search TV、TV Details、TV Season Details。评分为整部剧集的
TMDB 用户评分；集数、单集时长与完结状态针对所选季。时长取本季已知
单集时长的中位数。推荐理由和简介为人工编辑，刷新时保留。
只刷新 TMDB 条目，保留 TVmaze 条目。刷新中任一作品失败时保留上次数据。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'data' / 'series_catalog.json'
JS_FILE = ROOT / 'series.js'
API = 'https://api.themoviedb.org/3'
GENRES = {10759: '动作冒险', 16: '动画', 35: '喜剧', 80: '犯罪',
          99: '纪录片', 18: '剧情', 10751: '家庭', 10762: '儿童',
          9648: '悬疑', 10763: '新闻', 10764: '真人秀', 10765: '科幻奇幻',
          10766: '肥皂剧', 10767: '脱口秀', 10768: '战争政治', 37: '西部'}


class FetchError(Exception):
    """错误信息不包含认证信息或完整请求 URL。"""


def request_bytes(url: str, *, label: str) -> bytes:
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Afterglow-Catalog/1.0'})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 2:
                raise FetchError(f'{label} 请求失败，请检查网络与 TMDB 配置。') from None
            time.sleep(attempt + 1)
    raise FetchError(f'{label} 请求失败。')


def api_get(path: str, key: str, **params) -> dict:
    # key 只发送给 TMDB 官方 API；不记录包含 key 的 URL。
    query = urllib.parse.urlencode({'api_key': key, 'language': 'zh-CN', **params})
    raw = request_bytes(f'{API}{path}?{query}', label=f'TMDB {path}')
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        raise FetchError(f'TMDB {path} 返回了无效数据。') from None
    if result.get('success') is False:
        raise FetchError(f'TMDB {path} 返回失败状态。')
    return result


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def refresh_entry(item: dict, key: str, checked_at: str, staging: Path) -> dict:
    tv_id = int(item['tmdb_id'])
    season_number = int(item.get('season_number', 1))
    query = item.get('search_query') or item['title_en']
    search = api_get('/search/tv', key, query=query)
    if not any(result.get('id') == tv_id for result in search.get('results', [])):
        raise FetchError(f'{item["title"]} 未通过 TMDB 搜索 ID 核验。')
    detail = api_get(f'/tv/{tv_id}', key)
    english = api_get(f'/tv/{tv_id}', key, language='en-US')
    season = api_get(f'/tv/{tv_id}/season/{season_number}', key, append_to_response='credits')
    episodes = season.get('episodes') or []
    if not episodes or season.get('season_number') != season_number:
        raise FetchError(f'{item["title"]} 的季资料不完整。')
    season_summary = next((s for s in detail.get('seasons', [])
                           if s.get('season_number') == season_number), None)
    if not season_summary or season_summary.get('episode_count') != len(episodes):
        raise FetchError(f'{item["title"]} 的季集数不一致。')
    runtimes = [e['runtime'] for e in episodes if isinstance(e.get('runtime'), (int, float)) and e['runtime'] > 0]
    # 完结针对所选季：全部已知集数均有已过去的播出日期，且剧集已结束，
    # 或这季早于当前最后播出季，或最后播出集为本季最后一集且暂无下一集。
    all_aired = all(e.get('air_date') and e['air_date'] <= checked_at for e in episodes)
    last_aired = detail.get('last_episode_to_air') or {}
    last_season = int(last_aired.get('season_number') or 0)
    season_closed = (detail.get('status') in ('Ended', 'Canceled')
                     or last_season > season_number
                     or (last_season == season_number
                         and last_aired.get('episode_number') == len(episodes)
                         and not detail.get('next_episode_to_air')))
    credits = season.get('credits') or {}
    directors = unique([person.get('name', '') for episode in episodes
                        for person in episode.get('crew', []) if person.get('job') == 'Director']
                       + [person.get('name', '') for person in credits.get('crew', []) if person.get('job') == 'Director'])
    poster_path = season.get('poster_path') or detail.get('poster_path')
    if not poster_path or not re.fullmatch(r'/[A-Za-z0-9._-]+', poster_path):
        raise FetchError(f'{item["title"]} 缺少可用海报。')
    poster_name = f'series-{tv_id}-s{season_number}.jpg'
    image = request_bytes(f'https://image.tmdb.org/t/p/w500{poster_path}', label=f'{item["title"]} 海报')
    if len(image) < 1024 or not image.startswith(b'\xff\xd8'):
        raise FetchError(f'{item["title"]} 的海报文件无效。')
    (staging / poster_name).write_bytes(image)
    vote = detail.get('vote_average')
    return {
        **item,
        'id': f'tmdb-tv-{tv_id}-s{season_number}',
        'media_type': 'tv',
        'source_provider': 'tmdb',
        'title_en': english.get('name') or detail.get('original_name') or item['title_en'],
        'year': int((season.get('air_date') or detail['first_air_date'])[:4]),
        'genres': [GENRES.get(g['id'], g['name']) for g in detail.get('genres', [])],
        'origin_country': detail.get('origin_country') or [],
        'directors': directors,
        'actors': unique([person.get('name', '') for person in credits.get('cast', [])])[:6],
        'tmdb_rating': round(vote, 1) if isinstance(vote, (int, float)) and vote > 0 else None,
        'tmdb_vote_count': detail.get('vote_count'),
        'rating_scope': '剧集整体',
        'douban_rating': None,
        'douban_votes': '',
        'douban_url': '',
        'poster': f'posters/{poster_name}',
        'tmdb_url': f'https://www.themoviedb.org/tv/{tv_id}/season/{season_number}',
        'episode_count': len(episodes),
        'episode_runtime': round(statistics.median(runtimes)) if runtimes else None,
        'runtime_note': '本季单集时长中位数' if runtimes else '暂无可靠时长',
        'season_label': f'第{season_number}季',
        'completion': '本季已完结' if all_aired and season_closed else '播出状态待确认',
        'source_note': 'TMDB · 精选剧集',
        'metadata_checked_at': checked_at,
        'season_number': season_number,
        'tmdb_id': tv_id,
    }


def atomic_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(value, encoding='utf-8')
    temporary.replace(path)


def js_text(items: list[dict]) -> str:
    return '// Afterglow 精选剧集，由 scripts/fetch_series.py 生成。\n// 来源、评分平台与许可见每条记录；集数与时长针对所选季。\nconst SERIES = ' + json.dumps(items, ensure_ascii=False, indent=2) + ';\n'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='从 TMDB 核验资料并更新海报，失败保留旧数据')
    parser.add_argument('--config', type=Path, default=ROOT / 'config.local.json', help='本地配置文件，仅刷新时读取')
    args = parser.parse_args()
    try:
        items = json.loads(CATALOG.read_text(encoding='utf-8'))
        if not items or not isinstance(items, list):
            raise FetchError('剧集目录必须是非空列表。')
        if args.refresh:
            key = os.environ.get('TMDB_API_KEY')
            if not key and args.config.exists():
                key = json.loads(args.config.read_text(encoding='utf-8')).get('tmdb_api_key')
            if not key:
                raise FetchError('请设置 TMDB_API_KEY 或使用 --config 指定本地配置。')
            checked_at = datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
            refreshed = []
            with tempfile.TemporaryDirectory(prefix='.series-refresh-', dir=ROOT) as temp:
                staging = Path(temp)
                for index, item in enumerate(items, 1):
                    result = (item if item.get('source_provider') == 'tvmaze'
                              else refresh_entry(item, key, checked_at, staging))
                    refreshed.append(result)
                    print(f'[{index}/{len(items)}] {result["title"]}：{result["episode_count"]} 集，{result["completion"]}')
                (ROOT / 'posters').mkdir(exist_ok=True)
                # 所有 API 请求与海报验证成功后才发布新版本。
                for poster in staging.iterdir():
                    poster.replace(ROOT / 'posters' / poster.name)
                atomic_write(CATALOG, json.dumps(refreshed, ensure_ascii=False, indent=2) + '\n')
                items = refreshed
        atomic_write(JS_FILE, js_text(items))
        print(f'已生成 series.js，共 {len(items)} 部精选剧集。')
        return 0
    except FetchError as error:
        print(f'更新未完成：{error} 已保留上次剧集数据。', file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        print('更新未完成：目录或配置格式无效，已保留上次剧集数据。', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
