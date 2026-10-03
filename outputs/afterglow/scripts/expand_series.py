#!/usr/bin/env python3
"""补充现有剧集的已播后续季；使用 TVmaze 公共 API，不需要密钥。

python3 scripts/expand_series.py --cache /path/to/cache --refresh
不带 --refresh 时从已保存的公开资料重建。原有固定作品 ID 保持不变。
"""
from __future__ import annotations
import argparse
import concurrent.futures
import json
import re
import shutil
import statistics
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from fetch_tvmaze_series import GENRES, ROOT, CATALOG, FetchError, get_json, request_bytes, network_countries, atomic_write


def root_title(item):
    return re.sub(r'\s*第\s*\d+\s*季\s*$', '', item['title']).strip()


def resolve_id(item, cache, refresh):
    if item.get('tvmaze_id'):
        return int(item['tvmaze_id'])
    match = re.search(r'tvmaze\.com/shows/(\d+)', item.get('region_source', ''))
    if match:
        return int(match[1])
    query = item.get('search_query') or item.get('title_en') or item['title']
    path = cache / ('search-' + str(item.get('tmdb_id')) + '.json')
    if refresh and not path.exists():
        from urllib.parse import urlencode
        atomic_write(path, json.dumps(get_json('/search/shows?' + urlencode({'q': query})), ensure_ascii=False))
    if not path.exists():
        raise FetchError(f'{item["title"]} 缺少公开匹配资料')
    values = json.loads(path.read_text())
    names = {str(item.get('title_en', '')).casefold(), str(query).casefold()}
    choices = [row['show'] for row in values if row.get('show') and (row['show'].get('name', '').casefold() in names or any(name and row['show'].get('name', '').casefold().startswith(name + ':') for name in names))]
    choices = [show for show in choices if str(show.get('premiered', '')).startswith(str(item.get('year')))]
    if len(choices) != 1:
        raise FetchError(f'{item["title"]} 的名称和首播年份不能唯一匹配')
    return choices[0]['id']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    originals = json.loads(CATALOG.read_text())
    roots = {}
    for item in originals:
        key = item.get('series_key') or (f'tvmaze:{item["tvmaze_id"]}' if item.get('tvmaze_id') else f'tmdb:{item["tmdb_id"]}')
        if key not in roots or item['season_number'] < roots[key]['season_number']:
            roots[key] = item
    checked = datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    pending_images = {}
    for path in args.cache.glob('show-*.json'):
        show = json.loads(path.read_text())
        aired_seasons = {e['season'] for e in show.get('_embedded', {}).get('episodes', []) if e.get('type') == 'regular' and e.get('airdate') and e['airdate'] <= checked}
        for season in show.get('_embedded', {}).get('seasons', []):
            number = season.get('number')
            name = f'tvmaze-series-{show["id"]}-s{number}.jpg'
            image = season.get('image') or show.get('image') or {}
            url = image.get('original') or image.get('medium')
            if number and number > 1 and number in aired_seasons and url and not (ROOT / 'posters' / name).exists():
                pending_images[name] = url
    def preload(pair):
        name, url = pair
        raw = request_bytes(url, label=name)
        if len(raw) < 1024 or not raw.startswith(b'\xff\xd8'):
            raise FetchError('海报不是有效 JPEG')
        (ROOT / 'posters' / name).write_bytes(raw)
    if args.refresh and pending_images:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            jobs = [pool.submit(preload, pair) for pair in pending_images.items()]
            done = 0
            for job in concurrent.futures.as_completed(jobs):
                try:
                    job.result(); done += 1
                    if done % 10 == 0: print(f'已缓存 {done}/{len(pending_images)} 张后续季海报', flush=True)
                except FetchError as error:
                    print(f'海报稍后重试：{error}', flush=True)
    updated = {item['id']: dict(item) for item in originals}
    skipped, added = [], []
    with tempfile.TemporaryDirectory(prefix='.season-expansion-', dir=ROOT) as temp:
        staging = Path(temp)
        image_cache = {}
        for base in roots.values():
            try:
                tv_id = resolve_id(base, args.cache, args.refresh)
                path = args.cache / f'show-{tv_id}.json'
                if args.refresh and not path.exists():
                    atomic_write(path, json.dumps(get_json(f'/shows/{tv_id}?embed[]=seasons&embed[]=episodes'), ensure_ascii=False))
                show = json.loads(path.read_text())
                if show.get('id') != tv_id:
                    raise FetchError('公开剧集 ID 不一致')
                seasons = show['_embedded']['seasons']
                episodes = show['_embedded']['episodes']
                key = f'tvmaze:{tv_id}'
                title = root_title(base)
                related = [m for m in updated.values() if m['id'] == base['id'] or m.get('series_key') == key]
                for old in related:
                    old.update(series_key=key, series_title=title, tvmaze_id=tv_id)
                    if old.get('source_provider') == 'tvmaze':
                        old_season = next((s for s in seasons if s.get('number') == old['season_number']), None)
                        regular = [e for e in episodes if e.get('season') == old['season_number'] and e.get('type') == 'regular' and isinstance(e.get('number'), int) and e['number'] > 0]
                        aired = [e for e in regular if e.get('airdate') and e['airdate'] <= checked]
                        if old_season and aired:
                            completed = bool(old_season.get('endDate') and old_season['endDate'] <= checked and len(aired) == len(regular))
                            old.update(episode_count=len(aired), episode_order=old_season.get('episodeOrder'), completion='本季已完结' if completed else '本季更新中', year=int(min(e['airdate'] for e in aired)[:4]))
                known = {m['season_number'] for m in related}
                for season in seasons:
                    number = season.get('number')
                    if not isinstance(number, int) or number < 1 or number in known:
                        continue
                    regular = [e for e in episodes if e.get('season') == number and e.get('type') == 'regular' and isinstance(e.get('number'), int) and e['number'] > 0]
                    aired = [e for e in regular if e.get('airdate') and e['airdate'] <= checked]
                    if not aired:
                        continue
                    if len({e['number'] for e in aired}) != len(aired):
                        raise FetchError(f'{title} 第{number}季分集编号重复')
                    expected = season.get('episodeOrder')
                    complete = bool(season.get('endDate') and season['endDate'] <= checked and len(aired) == len(regular))
                    countries = network_countries(season, show)
                    runtimes = [e['runtime'] for e in aired if isinstance(e.get('runtime'), (int, float)) and e['runtime'] > 0]
                    image = season.get('image') or show.get('image') or {}
                    image_url = image.get('original') or image.get('medium')
                    poster = base['poster']
                    if image_url:
                        poster_name = f'tvmaze-series-{tv_id}-s{number}.jpg'
                        existing = ROOT / 'posters' / poster_name
                        if existing.exists():
                            image_cache[image_url] = existing.read_bytes()
                        if image_url not in image_cache:
                            raw = request_bytes(image_url, label=f'{title} 第{number}季海报')
                            if len(raw) < 1024 or not raw.startswith(b'\xff\xd8'):
                                raise FetchError('海报不是有效 JPEG')
                            image_cache[image_url] = raw
                        (staging / poster_name).write_bytes(image_cache[image_url])
                        poster = f'posters/{poster_name}'
                    source = season.get('url') or show['url']
                    vote = (show.get('rating') or {}).get('average')
                    item = {
                        'id': f'tvmaze-tv-{tv_id}-s{number}', 'media_type': 'tv',
                        'tvmaze_id': tv_id, 'search_query': show['name'],
                        'title': f'{title} 第{number}季', 'title_en': show['name'],
                        'series_key': key, 'series_title': title,
                        'season_number': number, 'season_label': f'第{number}季',
                        'year': int(min(e['airdate'] for e in aired)[:4]),
                        'genres': [GENRES.get(g, g) for g in show.get('genres') or []],
                        'origin_country': countries or base.get('origin_country', []),
                        'region_basis': '所选季首播网络/平台地区' if countries else base.get('region_basis', '编辑分类（见地区来源）'),
                        'region_source': source if countries else base.get('region_source', source),
                        'directors': [], 'actors': [], 'douban_rating': None, 'tmdb_rating': None,
                        'tvmaze_rating': vote, 'rating_scope': '剧集整体',
                        'reason': f'走进《{title}》第{number}季。可以在下方切换已收录的各季，按自己的节奏继续看。',
                        'overview': base.get('overview', ''),
                        'episode_count': len(aired), 'episode_order': expected,
                        'episode_runtime': round(statistics.median(runtimes)) if runtimes else None,
                        'runtime_note': 'TVmaze 记录的本季已播正片单集时长中位数，可能包含播出时段',
                        'completion': '本季已完结' if complete else '本季更新中',
                        'poster': poster, 'poster_source': image_url,
                        'poster_scope': '所选季' if season.get('image') else '剧集通用海报',
                        'source_provider': 'tvmaze', 'source_url': source, 'tvmaze_url': source,
                        'source_note': 'TVmaze · 剧集后续季', 'data_license': 'CC BY-SA 4.0',
                        'data_license_url': 'https://creativecommons.org/licenses/by-sa/4.0/',
                        'metadata_checked_at': checked,
                    }
                    if base.get('editorial_region') and not countries:
                        item['editorial_region'] = base['editorial_region']
                    updated[item['id']] = item
                    added.append(item['id'])
                print(f'{title}: 已收录 {len([m for m in updated.values() if m.get("series_key") == key])} 季', flush=True)
            except (FetchError, OSError, ValueError, KeyError) as error:
                skipped.append({'title': base['title'], 'error': str(error)})
                print(f'保留原记录：{base["title"]} — {error}', flush=True)
        for poster in staging.iterdir():
            shutil.copyfile(poster, ROOT / 'posters' / poster.name)
    items = list(updated.values())
    atomic_write(CATALOG, json.dumps(items, ensure_ascii=False, indent=2) + '\n')
    atomic_write(ROOT / 'series.js', '// Afterglow 剧集；逐季资料和来源见每条记录。\nconst SERIES = ' + json.dumps(items, ensure_ascii=False, indent=2) + ';\n')
    atomic_write(args.cache / 'expansion-report.json', json.dumps({'added': len(added), 'total_seasons': len(items), 'skipped': skipped}, ensure_ascii=False, indent=2))
    print(f'新增 {len(added)} 季，共 {len(items)} 季；{len(skipped)} 部待补核。', flush=True)
    return bool(skipped)


if __name__ == '__main__':
    raise SystemExit(main())
