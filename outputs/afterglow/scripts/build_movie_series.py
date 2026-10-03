#!/usr/bin/env python3
"""从独立电影系列目录离线重建浏览器数据，不改豆瓣 Top250。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    data = json.loads((ROOT / 'data/movie_continuations.json').read_text())
    families, movies = data['families'], data['movies']
    if len({m['id'] for m in movies}) != len(movies):
        raise ValueError('补充电影 ID 重复')
    text = '// Afterglow 电影系列；由 scripts/build_movie_series.py 离线生成。\n'
    text += 'const MOVIE_FAMILIES = ' + json.dumps(families, ensure_ascii=False, indent=2) + ';\n'
    text += 'const MOVIE_EXTRAS = ' + json.dumps(movies, ensure_ascii=False, indent=2) + ';\n'
    path = ROOT / 'movie-series.js'
    temporary = path.with_suffix('.js.tmp')
    temporary.write_text(text)
    temporary.replace(path)
    print(f'已生成 {len(families)} 个系列、{len(movies)} 部补充电影。')


if __name__ == '__main__':
    build()
