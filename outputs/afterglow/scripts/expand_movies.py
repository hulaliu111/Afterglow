#!/usr/bin/env python3
"""从现有电影的 TMDB 公开系列页面补齐已发行影片，不需要 API 密钥。

python3 scripts/expand_movies.py --cache /path/to/cache --refresh
需 requirements.txt 中的 beautifulsoup4。HTML 缓存可用于离线核验。
只将已公开发行的同系列影片纳入片库，不把重拍版自行归为续集。
"""
from __future__ import annotations
import argparse
import concurrent.futures
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
HOST = 'https://www.themoviedb.org'
GENRES = {12:'冒险',14:'奇幻',16:'动画',18:'剧情',27:'恐怖',28:'动作',35:'喜剧',36:'历史',37:'西部',53:'惊悚',80:'犯罪',99:'纪录片',878:'科幻',9648:'悬疑',10402:'音乐',10749:'爱情',10751:'家庭',10752:'战争'}
# 系列起点均已存在于原片库；系列成员随后由公开页面核实。
SEEDS = [
    (671,'哈利·波特','harry-potter-and-the-philosopher-s-stone'),
    (238,'教父','the-godfather'), (120,'指环王','the-lord-of-the-rings-the-fellowship-of-the-ring'),
    (155,'蝙蝠侠：黑暗骑士三部曲','the-dark-knight'), (603,'黑客帝国','the-matrix'),
    (19995,'阿凡达','avatar'), (22,'加勒比海盗','pirates-of-the-caribbean-the-curse-of-the-black-pearl'),
    (2501,'谍影重重','the-bourne-identity'), (10193,'玩具总动员','toy-story-3'),
    (10191,'驯龙高手','how-to-train-your-dragon'), (20352,'神偷奶爸','despicable-me'),
    (109445,'冰雪奇缘','frozen'), (150540,'头脑特工队','inside-out'),
    (269149,'疯狂动物城','zootopia'), (585,'怪兽','monsters-inc'),
    (8587,'狮子王','the-lion-king'), (82690,'无敌破坏王','wreck-it-ralph'),
    (425,'冰川时代','ice-age'), (49519,'疯狂原始人','the-croods'),
    (280,'终结者','terminator-2-judgment-day'), (76341,'疯狂的麦克斯','mad-max-fury-road'),
    (176,'电锯惊魂','saw'), (1954,'蝴蝶效应','the-butterfly-effect'),
    (539,'惊魂记','psycho'), (10775,'无间道','infernal-affairs'),
    (11471,'英雄本色','a-better-tomorrow'), (30421,'倩女幽魂','a-chinese-ghost-story'),
    (274,'汉尼拔','the-silence-of-the-lambs'), (396535,'釜山行','train-to-busan'),
    (62,'太空漫游','2001-a-space-odyssey'), (9323,'攻壳机动队','ghost-in-the-shell'),
    (324857,'蜘蛛侠：蜘蛛宇宙','spider-man-into-the-spider-verse'),
    (475557,'小丑','joker'), (76,'爱在三部曲','before-sunrise'),
    (21835,'大话西游','a-chinese-odyssey-part-two-cinderella'),
    (89825,'你看起来好像很好吃','you-are-umasou'),
    (294682,'小森林','little-forest-summer-autumn'),
    (37703,'唐伯虎点秋香','flirting-scholar'),
    (406997,'奇迹男孩','wonder'),
]
TITLES = {58: '加勒比海盗2：聚魂棺',
 214: '电锯惊魂3',
 215: '电锯惊魂2',
 218: '终结者',
 272: '蝙蝠侠：侠影之谜',
 285: '加勒比海盗3：世界的尽头',
 296: '终结者3',
 534: '终结者2018',
 663: '电锯惊魂4',
 767: '哈利·波特与混血王子',
 862: '玩具总动员',
 863: '玩具总动员2',
 950: '冰川时代2',
 1865: '加勒比海盗4：惊涛怪浪',
 4437: '2010：威震太阳神',
 8355: '冰川时代3',
 8810: '疯狂的麦克斯2',
 9048: '倩女幽魂3：道道道',
 9050: '倩女幽魂2：人间道',
 9355: '疯狂的麦克斯3',
 9533: '红龙',
 9659: '疯狂的麦克斯',
 9732: '狮子王2：辛巴的荣耀',
 9740: '汉尼拔',
 10576: '惊魂记2',
 11430: '狮子王3',
 11917: '电锯惊魂5',
 12140: '攻壳机动队2：无罪',
 12662: '惊魂记3',
 14310: '无间道3：终极无间',
 14620: '蝴蝶效应2',
 16258: '蝴蝶效应3：启示',
 18305: '英雄本色2',
 22804: '电锯惊魂6',
 40377: '惊魂记4',
 41244: '英雄本色3：夕阳之歌',
 41439: '电锯惊魂7',
 49040: '谍影重重4',
 54324: '唐伯虎点秋香2之四大才子',
 57800: '冰川时代4',
 62211: '怪兽大学',
 76600: '阿凡达：水之道',
 82702: '驯龙高手2',
 83533: '阿凡达：火与烬',
 87101: '终结者：创世纪',
 93456: '神偷奶爸2',
 166426: '加勒比海盗5：死无对证',
 166428: '驯龙高手3',
 278154: '冰川时代5：星际碰撞',
 290859: '终结者：黑暗命运',
 298250: '电锯惊魂8：竖锯',
 301528: '玩具总动员4',
 324668: '谍影重重5',
 324852: '神偷奶爸3',
 330457: '冰雪奇缘2',
 377091: '你看起来好像很好吃2：永远永远爱你',
 389201: '大话西游3',
 404368: '无敌破坏王2：大闹互联网',
 519182: '神偷奶爸4',
 529203: '疯狂原始人2',
 569094: '蜘蛛侠：纵横宇宙',
 581392: '釜山行2：半岛',
 602734: '电锯惊魂9：漩涡',
 624860: '黑客帝国：矩阵重启',
 774825: '冰川时代：巴克·怀尔德的冒险之旅',
 779816: '白鸟：奇迹男孩故事',
 786892: '疯狂的麦克斯：狂暴女神',
 889737: '小丑2：双重妄想',
 951491: '电锯惊魂10',
 1022789: '头脑特工队2',
 1084242: '疯狂动物城2',
 1084244: '玩具总动员5'}
# 原版上下篇的合辑，并非新增故事，不重复收录。
EXCLUDED_EDITIONS = {890406}
# 少数已核实的续作没有被 TMDB 建成集合；显式保留关系出处。
EXPLICIT_FAMILIES = {
    37703: {'key':'editorial:flirting-scholar','members':[(37703,'flirting-scholar'),(54324,'flirting-scholar-2')],
        'source_url':'https://www.1905.com/mdb/film/354446/info/',
        'source_urls':['https://www.themoviedb.org/movie/54324-2','https://www.disneyplus.com/en-hk/browse/entity-6a482dca-1e4a-41e9-8c33-b2c046f23835']},
    406997: {'key':'editorial:wonder','members':[(406997,'wonder'),(779816,'white-bird')],
        'source_url':'https://tv.apple.com/gb/movie/white-bird-a-wonder-story/umc.cmc.1fytklzqfndctoczere1gfwnl',
        'source_urls':['https://www.themoviedb.org/movie/779816-white-bird']},
    89825: {'key':'editorial:umasou','members':[(89825,'you-are-umasou'),(377091,'the-adventures-of-tyrano-boy')],
        'source_url':'https://www.jfkl.org.my/wp-content/uploads/2022/06/Teman-Baru-83.pdf',
        'source_urls':['https://www.themoviedb.org/movie/377091','https://www.gscmovies.com.my/the-adventures-of-tyrano-boy/']},
}
lock = threading.Lock()
last_request = 0.0


def public_bytes(url):
    global last_request
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'www.themoviedb.org','media.themoviedb.org','image.tmdb.org'}:
        raise ValueError('来源不是允许的 TMDB 公开域名')
    for attempt in range(3):
        try:
            with lock:
                time.sleep(max(0, .7 - (time.monotonic() - last_request)))
                last_request = time.monotonic()
            request = urllib.request.Request(url, headers={'User-Agent':'Afterglow-Catalog/1.0','Accept-Language':'zh-CN,zh;q=0.9,en;q=0.8'})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except OSError:
            if attempt == 2: raise
            time.sleep(2 * (attempt + 1))


def read_page(path, url, refresh):
    if not path.exists():
        if not refresh: raise ValueError(f'缺少缓存 {path.name}')
        text = public_bytes(url).decode('utf-8')
        if len(text) < 1000 or '<meta' not in text:
            raise ValueError('公开页面不完整')
        path.write_text(text)
    return BeautifulSoup(path.read_text(), 'html.parser')


def movie_data(mid, href, args, fallback_title):
    soup = read_page(args.cache / f'movie-{mid}.html', HOST + href, args.refresh)
    canonical = soup.select_one('meta[property="og:url"]')
    if canonical is None or not re.search(rf'/movie/{mid}(?:-|$)', canonical['content']):
        raise ValueError(f'电影 {mid} 的来源 ID 不匹配')
    status = None
    heading = soup.select_one('.title h2 a')
    title_en = heading.get_text(' ', strip=True) if heading else fallback_title
    for p in soup.select('section.facts p'):
        label = p.find('strong')
        if label:
            label_text = label.get_text(' ',strip=True)
            value = p.get_text(' ',strip=True)[len(label_text):].strip()
            if label_text in {'Status','状态','狀態','状態'}: status = value
            if label_text in {'Original Title','原始标题','原名','原題','原标题'}: title_en = value
    if status not in {'Released','已上映','已发行','已發行','公開'}:
        return None
    year_node = soup.select_one('.header_poster_wrapper .release_date, .title .release_date')
    year_match = re.search(r'\d{4}', year_node.get_text() if year_node else '')
    if not year_match: raise ValueError(f'已发行电影 {mid} 缺少年份')
    year = int(year_match[0])
    if year > args.checked_year:
        return None
    genres = []
    for a in soup.select('.header_poster_wrapper .genres a'):
        match = re.search(r'/genre/(\d+)', a.get('href',''))
        if match and int(match[1]) in GENRES: genres.append(GENRES[int(match[1])])
    runtime_node = soup.select_one('.header_poster_wrapper .runtime')
    runtime_text = runtime_node.get_text(' ',strip=True) if runtime_node else ''
    hours = re.search(r'(\d+)h',runtime_text); minutes = re.search(r'(\d+)m',runtime_text)
    runtime = (int(hours[1])*60 if hours else 0)+(int(minutes[1]) if minutes else 0)
    score_node = soup.select_one('.header_poster_wrapper .user_score_chart[data-percent]')
    percent = float(score_node['data-percent']) if score_node else 0
    image = soup.select_one('meta[property="og:image"]')
    poster = ''
    if image:
        image_url = image['content']
        image_file = ROOT / 'posters' / f'tmdb-movie-{mid}.jpg'
        if not image_file.exists():
            raw = public_bytes(image_url)
            if len(raw)<1024 or not raw.startswith((b'\xff\xd8', b'\x89PNG')):
                raise ValueError(f'电影 {mid} 海报格式不正确')
            image_file.write_bytes(raw)
        poster = f'posters/{image_file.name}'
    return {'id':f'tmdb-movie-{mid}','tmdb_id':mid,'media_type':'movie','title':TITLES.get(mid,title_en or fallback_title), 'title_en':title_en,'year':year,'genres':genres,'directors':[],'actors':[], 'runtime':runtime or None,'tmdb_rating':round(percent/10,1) if percent>0 else None,'douban_rating':None,'douban_votes':'','poster':poster,'poster_source':image['content'] if image else None,'tmdb_url':canonical['content'],'source_url':canonical['content'],'source_provider':'tmdb-public','source_note':'TMDB · 公开电影资料','metadata_checked_at':args.checked}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args();args.cache.mkdir(parents=True,exist_ok=True)
    args.checked=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat();args.checked_year=int(args.checked[:4])
    original_ids={m['tmdb_id'] for m in json.loads((ROOT/'data/tmdb_matched.json').read_text()) if m.get('tmdb_id')}
    families=[];extras={};failures=[]
    def family(seed):
        root_id,name,slug=seed
        root=read_page(args.cache/f'movie-{root_id}.html',f'{HOST}/movie/{root_id}-{slug}',args.refresh)
        match=re.search(r"/collection/\{0\}/static_cache/movie_card.*?'(\d+)'",str(root),re.S)
        members={}
        if match:
            collection_id=int(match[1])
            page=read_page(args.cache/f'collection-{collection_id}.html',f'{HOST}/collection/{collection_id}',args.refresh)
            key=f'tmdb-collection:{collection_id}'
            sources={'source_url':f'{HOST}/collection/{collection_id}'}
            for link in page.select('a[href]'):
                href=link['href'];m=re.match(r'/movie/(\d+)(?:-|$)',href)
                if m: members.setdefault(int(m[1]), {'href':href,'title':link.get_text(' ',strip=True)})
        elif root_id in EXPLICIT_FAMILIES:
            explicit=EXPLICIT_FAMILIES[root_id]
            key=explicit['key']
            sources={field:explicit[field] for field in ('source_url','source_urls')}
            members={mid:{'href':f'/movie/{mid}-{slug}','title':TITLES.get(mid,'')} for mid,slug in explicit['members']}
        else:
            return None, []
        if root_id not in members: raise ValueError(f'{name} 系列未包含原作品')
        added=[];ids=[]
        for mid,member in members.items():
            if mid in EXCLUDED_EDITIONS: continue
            if mid in original_ids:
                ids.append(mid);continue
            item=movie_data(mid,member['href'],args,member['title'])
            if not item:continue
            item.update(collection_key=key,collection_name=name)
            item['reason']=f'继续《{name}》系列的故事。前后篇章已经连在一起，可以在下方选择下一部。'
            added.append(item);ids.append(mid)
        print(f'{name}: {len(ids)} 部，补充 {len(added)} 部',flush=True)
        return {'key':key,'name':name,'tmdb_ids':ids,**sources,'metadata_checked_at':args.checked},added
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(family,seed):seed for seed in SEEDS}
        for job in concurrent.futures.as_completed(jobs):
            try:
                group,items=job.result()
                if group:families.append(group)
                extras.update({m['id']:m for m in items})
            except Exception as error:
                failures.append({'series':jobs[job][1],'error':str(error)})
                print(f'{jobs[job][1]} 待重试：{error}',flush=True)
    report={'families':len(families),'added':len(extras),'failed':failures}
    (args.cache/'expansion-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if failures:
        print(f'{len(failures)} 个系列未核验完成，保留上次电影目录。',flush=True)
        return True
    families.sort(key=lambda group:group['key'])
    items=sorted(extras.values(),key=lambda item:(item['collection_key'],item['year'],item['tmdb_id']))
    data={'families':families,'movies':items}
    (ROOT/'data/movie_continuations.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    from build_movie_series import build
    build()
    print(f'已建立 {len(families)} 个电影系列，补充 {len(extras)} 部；{len(failures)} 个系列待补核。',flush=True)
    return bool(failures)


if __name__=='__main__':raise SystemExit(main())
