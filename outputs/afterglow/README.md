# Afterglow

**好故事，自有余韵。** 电影与剧集，每日一幕。

Afterglow 是「每日一部好电影」的新版：纯 HTML / CSS / JavaScript 静态网站，继续兼容原有 GitHub Pages 地址与每周电影资料更新。

- 原站地址：https://hulaliu111.github.io/daily-movie/
- 电影片库：322 部：保留豆瓣 Top 250，独立补充 72 部系列影片，建立 39 个电影系列。
- 剧集片库：60 部精选剧集、216 季，资料与海报来自 TMDB / TVmaze；后续季可从作品卡直接切换。
- 外观：暖黑与琥珀色；可切换奶油色日间模式

## 功能

- **今日一幕**：全部 / 电影 / 剧集切换，按日期推荐，前后翻页。
- **继续观看**：剧集按季切换；电影按上映年份展示同系列各部。每季显示已播正片集数、约单集时长与播出状态；未上映电影和未播季不收录。
- **探索片库**：搜索片名、已收录导演和演员；新增美剧、英剧、韩剧等地区入口；筛选作品类别、题材、年代；按评分或年份排序；点击作品查看站内推荐卡。
- **随机选片**：遵循首页所选类别；支持题材、年代与电影冷门佳作，无结果时明确提示。
- **分享**：复制推荐与固定作品链接，保存 Afterglow 分享图片。
- **移动端与键盘操作**：适配窄屏；片库支持焦点管理、Tab 导航、Escape 关闭；尊重系统减少动画设置。

## 本地预览

在本目录运行：

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

打开 http://127.0.0.1:8765/ 。无需安装前端依赖，无需构建。

## 目录

- `index.html` / `style.css` / `app.js`：页面、样式和交互。
- `favicon.svg`：Afterglow 余晖标记。
- `data.js`：电影和电影口碑榜资料，由 `scripts/build_data.py` 生成。
- `series.js`：剧集资料，由 `scripts/fetch_series.py` 或 `scripts/fetch_tvmaze_series.py` 生成。
- `movie-series.js` / `data/movie_continuations.json`：独立电影系列资料，不参与 Top250 排名。
- `scripts/build_movie_series.py`：离线重建电影系列浏览器数据。
- `scripts/expand_movies.py` / `scripts/expand_series.py`：从公开来源补齐电影系列和已播后续季，无需密钥。
- `scripts/fetch_tvmaze_series.py`：不需要密钥的 TVmaze 公共资料更新器。
- `data/TVMAZE-LICENSE.md`：TVmaze 资料署名、许可与整理说明。
- `data/series_catalog.json`：剧集精选目录与编辑推荐文案。
- `posters/`：本地电影及剧集海报。
- `.github/workflows/update-data.yml`：每周一北京时间 11:00 更新资料。

## 电影资料更新

Python 3，依赖安装：`pip install -r requirements.txt`。TMDB API key 使用 `TMDB_API_KEY` 环境变量，或不入库的 `config.local.json`。

```bash
python3 scripts/fetch_douban.py
python3 scripts/fetch_tmdb.py
python3 scripts/fetch_chart.py
python3 scripts/build_data.py
python3 scripts/download_posters.py
```

电影抓取必须获得 250 部才覆盖旧资料。不要直接编辑自动生成的 `data.js`。补充电影单独保存在 `data/movie_continuations.json`，从 TMDB 公开电影集合核对关系；少数未建集合的续作另附核验出处，评分标注为 TMDB，不冒充豆瓣 Top250 作品。

```bash
# 离线重建补充电影
python3 scripts/build_movie_series.py
# 公开网页核对当前电影系列（HTML 缓存不提交到仓库）
python3 scripts/expand_movies.py --cache .catalog-cache/tmdb --refresh
# 核对现有剧集，并补充已有已播正片的后续季
python3 scripts/expand_series.py --cache .catalog-cache/tvmaze --refresh
```

## 剧集资料更新

剧集使用独立目录，电影数据重建不会覆盖精选剧集。新增或调整剧集，编辑 `data/series_catalog.json` 中的资料来源及对应 ID、所选季、中文标题和推荐文案。TVmaze 条目标注 `source_provider: "tvmaze"` 与 `tvmaze_id`，原有条目标注 `source_provider: "tmdb"` 与 `tmdb_id`。

```bash
# 离线：从目录生成浏览器数据
python3 scripts/fetch_series.py

# 无需密钥：只刷新 TVmaze 剧集，保留 TMDB 条目
python3 scripts/fetch_tvmaze_series.py --refresh

# 使用已配置密钥：只刷新 TMDB 剧集，保留 TVmaze 条目
python3 scripts/fetch_series.py --refresh
```

TMDB 刷新通过环境变量 `TMDB_API_KEY` 或 `--config /path/to/config.local.json` 读取认证信息。脚本不依赖第三方 Python 包。每个更新器都在自己负责的全部剧集及海报获取成功后才更新资料；失败时保留旧版本。GitHub Actions 分别运行两种资料更新，TMDB 使用现有的 `TMDB_API_KEY` 仓库 Secret，TVmaze 无需密钥；任一剧集刷新失败不会阻止其他资料更新。

**资料口径：**剧集评分按实际来源标注 TMDB 或 TVmaze，均为整部剧集用户评分，不冒充豆瓣评分。集数与完结状态针对所选季，并排除特别集；单集时长取所选季已知时长中位数。TVmaze 的时长可能包含播出时段，页面标为约时长并提供提示。页面有核验日期。未核实所选季演员和导演的条目留空。不同评分平台不直接等价，排序仅作粗略参考。

地区优先按所选季首播网络/平台地区筛选；全球流媒体缺少地区字段的少数作品，使用附有官方出处的编辑分类。该分类并非完整制作国清单，具体见条目的 `region_basis` / `region_source`。

## 推荐与链接

- 每日电影推荐沿用原 Top250 的日期算法；补充续作可从作品卡、搜索和随机选片进入。
- 每日剧集推荐从各剧最早收录的一季开始，不因新增后续季反复推荐同一剧的不同季。
- 全部模式约每三天推荐一部剧集。具体作品按日期确定，同一天在不同设备上结果一致（以各设备当地日期和同一版本片库为准）。
- `?type=movie` / `?type=tv`：指定作品类别。
- `?date=2026-10-03`：指定日期。
- `?work=作品ID`：固定作品，复制推荐使用此链接，避免片库更新后分享变成另一部作品。
- 日推仍可能重复；这版没有引入持久的每日排期表。

## 发布

修改提交到仓库当前 GitHub Pages 发布源后，由原有 Pages 配置发布。仓库名和 Pages URL 无需随品牌更名而改变。发布前先查看本地预览，再提交所需文件；不要提交 `config.local.json`、`.env` 或 API key。

## 版权与来源

本站仅供学习交流。作品资料、海报与文字介绍的版权归原作者及来源平台（豆瓣、TMDB、TVmaze）所有。剧集推荐文案由本项目整理。

TVmaze 来源资料及整理、翻译按 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 提供，详见 [资料署名与许可](data/TVMAZE-LICENSE.md)。网站每条作品附具体来源链接，未复制原站剧情梗概。


## 网站产品演示

今日推荐卡下方的「看看 Afterglow 如何选片」打开 30 秒的独立演示。它依次展示真实电影推荐、剧集 / 英剧 / 悬疑筛选、夏洛克封面、季信息和真正生成的分享卡；支持播放、暂停、拖动进度、重播、减少动态和开始选片。关闭会恢复入口焦点，演示不修改原页面作品、日期、URL 或筛选，不自动下载。

新增文件 `showreel.js`、`showreel.css` 无第三方运行依赖。筛选复用 `filterCatalog(state)`，分享卡复用 `createShareCardCanvas(work, date)`。所有动画从一个时间值计算，暂停会停止封面光泽、倾斜、指针和容器变化；切换到后台也会暂停。窄屏使用独立竖版构图。
