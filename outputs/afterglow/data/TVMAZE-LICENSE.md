# TVmaze 资料署名与许可

本项目使用 [TVmaze 公共 API](https://www.tvmaze.com/api) 提供的剧集事实资料，包括季、集数、时长、类型、整体用户评分、播出平台地区及海报来源链接。

`series_catalog.json` 与生成的 `series.js` 中标有 `source_provider: "tvmaze"` 的记录，其来源资料及本项目对这些资料的整理、类型中文翻译和字段转换，按 [Creative Commons Attribution-ShareAlike 4.0 International（CC BY-SA 4.0）](https://creativecommons.org/licenses/by-sa/4.0/) 提供。每条记录的 `source_url` 链接到具体 TVmaze 来源，`metadata_checked_at` 记录核验日期。推荐理由和简短介绍由 Afterglow 原创整理，并随这些记录使用相同许可。

部分已有 TMDB 记录的地区字段也由 TVmaze 补充，具体条目带 `region_source` 与 `region_data_license`。这些新增地区字段同样按 CC BY-SA 4.0 提供，不代表本项目为原有 TMDB 或豆瓣资料重新授权。

本项目作了以下整理：选择各季、只收录已有已播正片的季、排除特别集、以已播正片时长中位数显示约每集时长、把题材翻译为中文，以及归纳推荐文案。地区分类优先参考所选季首播电视网/平台地区；少数全球流媒体作品使用另有官方出处的编辑分类，见 `editorial_region` 与 `region_source`。该分类并非完整制作国清单。

海报按 TVmaze API 文档建议在本地缓存，具体来源见 `poster_source`；图像本身的底层版权归各自权利人，以上资料许可不声称赋予海报额外权利。未复制 TVmaze 的剧情梗概。
