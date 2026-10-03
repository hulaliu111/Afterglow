#!/usr/bin/env python3
"""使用 TVmaze 的无凭据公共 API 更新精选剧集，不读取任何本地密钥。

离线生成：python3 scripts/fetch_tvmaze_series.py
公开资料刷新：python3 scripts/fetch_tvmaze_series.py --refresh

公共接口文档：https://www.tvmaze.com/api
数据许可：https://creativecommons.org/licenses/by-sa/4.0/
评分来自整部剧集，集数/时长针对指定季，并排除花絮与特别集。
时长沿用 TVmaze 记录，可能包含播出时段，并非统一核验的净片长。
网络所属地区记录为来源地区；它不等同于完整制作国清单。
TVmaze 没有季演员/导演接口，未另行核验时这两个字段保持空列表。
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import json
import statistics
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'data' / 'series_catalog.json'
API = 'https://api.tvmaze.com'
GENRES = {'Action': '动作', 'Adult': '成人', 'Adventure': '冒险', 'Anime': '动画',
          'Children': '儿童', 'Comedy': '喜剧', 'Crime': '犯罪', 'DIY': '生活',
          'Drama': '剧情', 'Espionage': '谍战', 'Family': '家庭', 'Fantasy': '奇幻',
          'Food': '美食', 'History': '历史', 'Horror': '恐怖', 'Legal': '法律',
          'Medical': '医疗', 'Music': '音乐', 'Mystery': '悬疑', 'Nature': '自然',
          'Romance': '爱情', 'Science-Fiction': '科幻', 'Sports': '运动',
          'Supernatural': '超自然', 'Thriller': '惊悚', 'Travel': '旅行',
          'War': '战争', 'Western': '西部'}
_request_lock = threading.Lock()
_last_request_at = 0.0


class FetchError(Exception):
    """公开资料获取或核验失败。"""


def request_bytes(url: str, *, label: str = 'TVmaze') -> bytes:
    """低频率请求公开 API/图片，限流时退避；不使用认证信息。"""
    global _last_request_at
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'api.tvmaze.com', 'static.tvmaze.com', 'images.tvmaze.com'}:
        raise FetchError(f'{label} 来源不是允许的 TVmaze 公共域名。')
    for attempt in range(4):
        with _request_lock:
            delay = max(0.0, 0.6 - (time.monotonic() - _last_request_at))
            if delay:
                time.sleep(delay)
            _last_request_at = time.monotonic()
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Afterglow-Catalog/1.0'})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise FetchError(f'{label} 的公开记录不存在。') from None
            if attempt == 3 or error.code not in {408, 425, 429, 500, 502, 503, 504}:
                raise FetchError(f'{label} 请求失败（HTTP {error.code}）。') from None
            time.sleep(4 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 3:
                raise FetchError(f'{label} 请求失败，请检查网络。') from None
            time.sleep(2 * (attempt + 1))
    raise FetchError(f'{label} 请求失败。')


@lru_cache(maxsize=1024)
def get_json(path: str):
    raw = request_bytes(API + path, label=f'TVmaze {path.split("?")[0]}')
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        raise FetchError('TVmaze 返回了无效 JSON。') from None


def search(query: str) -> list[dict]:
    """TVmaze 搜索返回完整匹配列表，无分页参数。调用者按名称和年份选 ID。"""
    result = get_json('/search/shows?' + urllib.parse.urlencode({'q': query}))
    if not isinstance(result, list):
        raise FetchError('TVmaze 搜索结果格式不正确。')
    return [row['show'] for row in result if isinstance(row, dict) and isinstance(row.get('show'), dict)]


def network_countries(season: dict, show: dict) -> list[str]:
    """优先采用所选季的首播网络/平台地区，避免后续换平台造成误判。"""
    for entry in (season, show):
        codes = []
        for key in ('network', 'webChannel'):
            source = entry.get(key) or {}
            code = (source.get('country') or {}).get('code')
            if isinstance(code, str) and len(code) == 2 and code not in codes:
                codes.append(code)
        if codes:
            return codes
    return []


def refresh_entry(item: dict, checked_at: str, staging: Path) -> dict:
    """核验一部剧的一个季并将海报写到 staging，返回统一片库记录。

    必填：tvmaze_id、title、reason、overview。season_number 默认为 1。
    title_en 会更新为官方英文名称。来源地区为空时保留有 region_source
    支持的 editorial_region；不会仅凭剧名或语言推断国家。
    """
    tv_id = int(item['tvmaze_id'])
    season_number = int(item.get('season_number', 1))
    show = get_json(f'/shows/{tv_id}')
    if not isinstance(show, dict) or show.get('id') != tv_id:
        raise FetchError(f'{item["title"]} 的 TVmaze ID 不一致。')
    expected = item.get('expected_year')
    if expected and not (show.get('premiered') or '').startswith(str(expected)):
        raise FetchError(f'{item["title"]} 的首播年份不符。')
    # 下列两个接口在官方文档中均返回完整列表，不需要遍历分页。
    seasons = get_json(f'/shows/{tv_id}/seasons')
    if not isinstance(seasons, list):
        raise FetchError(f'{item["title"]} 缺少季资料。')
    season = next((value for value in seasons if isinstance(value, dict) and value.get('number') == season_number), None)
    if not season:
        raise FetchError(f'{item["title"]} 未找到第 {season_number} 季。')
    episode_data = get_json(f'/seasons/{season["id"]}/episodes')
    if not isinstance(episode_data, list):
        raise FetchError(f'{item["title"]} 缺少分集资料。')
    # /seasons/:id/episodes 会包含特别集；仅统计正式编号的正片。
    regular = [episode for episode in episode_data if isinstance(episode, dict)
                and episode.get('type') == 'regular'
                and isinstance(episode.get('number'), int)
                and episode['number'] > 0]
    if not regular or len({episode['number'] for episode in regular}) != len(regular):
        raise FetchError(f'{item["title"]} 的正式分集记录不完整。')
    episodes = [episode for episode in regular if episode.get('airdate') and episode['airdate'] <= checked_at]
    if not episodes:
        raise FetchError(f'{item["title"]} 尚无已播正片。')
    episode_order = season.get('episodeOrder')
    runtimes = [episode['runtime'] for episode in episodes
                if isinstance(episode.get('runtime'), (int, float)) and episode['runtime'] > 0]
    end_date = season.get('endDate')
    # episodeOrder 是平台计划数，双集连播时可能不等于正片编号数。
    completed = bool(end_date and end_date <= checked_at and len(episodes) == len(regular))
    countries = network_countries(season, show)
    if not countries and item.get('editorial_region') and not item.get('region_source'):
        raise FetchError(f'{item["title"]} 的编辑地区缺少公开出处。')
    image = season.get('image') or show.get('image') or {}
    image_url = image.get('original') or image.get('medium')
    if not image_url:
        raise FetchError(f'{item["title"]} 缺少公开海报。')
    poster_data = request_bytes(image_url, label=f'{item["title"]} 海报')
    if len(poster_data) < 1024 or not poster_data.startswith(b'\xff\xd8'):
        raise FetchError(f'{item["title"]} 的海报不是有效 JPEG。')
    poster_name = f'tvmaze-series-{tv_id}-s{season_number}.jpg'
    staging.mkdir(parents=True, exist_ok=True)
    (staging / poster_name).write_bytes(poster_data)
    vote = (show.get('rating') or {}).get('average')
    premiere = min(episode['airdate'] for episode in episodes)
    title_en = show.get('name') or item.get('title_en') or ''
    source_url = season.get('url') or show.get('url')
    if not source_url or urllib.parse.urlparse(source_url).hostname != 'www.tvmaze.com':
        raise FetchError(f'{item["title"]} 缺少有效来源链接。')
    result = {
        **item,
        'id': f'tvmaze-tv-{tv_id}-s{season_number}',
        'media_type': 'tv',
        'title_en': title_en,
        'year': int(premiere[:4]) if len(premiere) >= 4 and premiere[:4].isdigit() else None,
        'genres': [GENRES.get(genre, genre) for genre in show.get('genres') or []],
        'origin_country': countries,
        'region_basis': '所选季首播网络/平台地区' if countries else '编辑分类（见地区来源）',
        'directors': item.get('directors') or [],
        'actors': item.get('actors') or [],
        'tvmaze_rating': float(vote) if isinstance(vote, (int, float)) and 0 < vote <= 10 else None,
        'tmdb_rating': None,
        'douban_rating': None,
        'douban_votes': '',
        'douban_url': '',
        'tmdb_id': None,
        'tmdb_url': '',
        'rating_scope': '剧集整体',
        'poster': f'posters/{poster_name}',
        'poster_source': image_url,
        'poster_scope': '所选季' if season.get('image') else '剧集通用海报',
        'source_provider': 'tvmaze',
        'source_url': source_url,
        'tvmaze_url': source_url,
        'tvmaze_id': tv_id,
        'episode_count': len(episodes),
        'episode_order': episode_order,
        'episode_runtime': round(statistics.median(runtimes)) if runtimes else None,
        'runtime_note': 'TVmaze 记录的本季单集时长中位数，可能包含播出时段' if runtimes else '暂无可靠时长',
        'season_label': f'第{season_number}季',
        'season_number': season_number,
        'completion': '本季已完结' if completed else '本季更新中',
        'source_note': 'TVmaze · 精选剧集',
        'data_license': 'CC BY-SA 4.0',
        'data_license_url': 'https://creativecommons.org/licenses/by-sa/4.0/',
        'metadata_checked_at': checked_at,
    }
    if countries:
        result.setdefault('region_source', source_url)
    return result


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(text, encoding='utf-8')
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='只刷新 source_provider 为 tvmaze 的记录，失败保留旧片库')
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    parser.add_argument('--output', type=Path, default=ROOT / 'series.js')
    args = parser.parse_args()
    try:
        items = json.loads(args.catalog.read_text(encoding='utf-8'))
        if not isinstance(items, list) or not items:
            raise FetchError('片库必须是非空列表。')
        if args.refresh:
            checked_at = datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
            updated = []
            with tempfile.TemporaryDirectory(prefix='.tvmaze-refresh-', dir=ROOT) as temp:
                staging = Path(temp)
                for item in items:
                    result = refresh_entry(item, checked_at, staging) if item.get('source_provider') == 'tvmaze' else item
                    updated.append(result)
                    print(result['title'], flush=True)
                (ROOT / 'posters').mkdir(exist_ok=True)
                for poster in staging.iterdir():
                    poster.replace(ROOT / 'posters' / poster.name)
                atomic_write(args.catalog, json.dumps(updated, ensure_ascii=False, indent=2) + '\n')
                items = updated
        js = '// Afterglow 精选剧集；来源、评分平台与许可见每条记录。\nconst SERIES = ' + json.dumps(items, ensure_ascii=False, indent=2) + ';\n'
        atomic_write(args.output, js)
        print(f'已生成 {len(items)} 条剧集记录。')
        return 0
    except FetchError as error:
        print(f'更新未完成：{error} 已保留上次片库。')
        return 1
    except (OSError, ValueError, TypeError, KeyError):
        print('更新未完成：目录或资料格式无效，已保留上次片库。')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
