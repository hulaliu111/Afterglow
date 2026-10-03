/* Afterglow — 电影与剧集，每日一幕。保持纯静态，可直接部署到 GitHub Pages。 */
const MEDIA_LABELS = { all: "全部", movie: "电影", tv: "剧集" };
const movieFamilyById = new Map((typeof MOVIE_FAMILIES !== "undefined" ? MOVIE_FAMILIES : []).flatMap(family => family.tmdb_ids.map(id => [id, family])));
const CATALOG = [
  ...(typeof MOVIES !== "undefined" ? MOVIES : []).map(m => ({ ...m, media_type: "movie", collection_key: movieFamilyById.get(m.tmdb_id)?.key, collection_name: movieFamilyById.get(m.tmdb_id)?.name })),
  ...(typeof MOVIE_EXTRAS !== "undefined" ? MOVIE_EXTRAS : []).filter(m => !(typeof MOVIES !== "undefined" ? MOVIES : []).some(original => original.tmdb_id === m.tmdb_id)).map(m => ({ ...m, media_type: "movie" })),
  ...(typeof SERIES !== "undefined" ? SERIES : []).map(m => ({ ...m, media_type: "tv", genres: normalizeGenres(m.genres) })),
];
const byId = new Map(CATALOG.map(m => [m.id, m]));
const $ = id => document.getElementById(id);
const REGION_LABELS = { US: "美剧", GB: "英剧", KR: "韩剧", CN: "国产剧", JP: "日剧", FR: "法国剧集" };
const COUNTRY_NAMES = { US: "美国", GB: "英国", KR: "韩国", CN: "中国大陆", JP: "日本", FR: "法国" };
function regionsOf(m) { return m.editorial_region ? [m.editorial_region] : (m.origin_country || []); }
function countryText(m) { return regionsOf(m).map(c => COUNTRY_NAMES[c] || c).join(" / "); }
function seriesRegionOptions() {
  const countries = new Set(catalogFor("tv").flatMap(m => regionsOf(m)));
  return [{ value: "all", label: "全部地区" }, ...Object.entries(REGION_LABELS).filter(([code]) => countries.has(code)).map(([value, label]) => ({ value, label }))];
}
const BRAND_COLORS = { glow: "#453323", accent: "#e6b87b", background: "#161512" };

function normalizeGenres(genres = []) {
  const aliases = { "动作冒险": ["动作", "冒险"], "科幻奇幻": ["科幻", "奇幻"], "战争政治": ["战争", "政治"] };
  return [...new Set(genres.flatMap(g => aliases[g] || [g]))];
}
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function fmtScore(value) { return value == null ? "" : Number(value).toFixed(1); }
function scoreOf(m) { return m.douban_rating ?? m.tmdb_rating ?? m.tvmaze_rating ?? -1; }
function scoreText(m) {
  const values = [];
  if (m.douban_rating != null) values.push("豆瓣 " + fmtScore(m.douban_rating));
  if (m.tmdb_rating != null) values.push("TMDB " + fmtScore(m.tmdb_rating) + (m.media_type === "tv" ? "（剧集整体）" : ""));
  if (m.tvmaze_rating != null) values.push("TVmaze " + fmtScore(m.tvmaze_rating) + "（剧集整体）");
  return values.join(" · ") || "暂无评分";
}
function workUrl(m) {
  return m.douban_url || m.tvmaze_url || m.tmdb_url || m.source_url || (m.tmdb_id ? "https://www.themoviedb.org/" + (m.media_type === "tv" ? "tv/" : "movie/") + m.tmdb_id : "");
}
function sourceNote(m) {
  return m.source_note || (m.media_type === "tv" ? "TMDB · 精选剧集" : "豆瓣 Top 250 · TMDB");
}
function seriesKey(m) { return m.series_key || (m.tvmaze_id ? `tvmaze:${m.tvmaze_id}` : `tmdb:${m.tmdb_id}`); }
function uniqueSeries(list) {
  const first = new Map();
  for (const m of list) { const key = seriesKey(m); if (!first.has(key) || m.season_number < first.get(key).season_number) first.set(key, m); }
  return [...first.values()];
}
function relatedWorks(m) {
  if (m.media_type === "tv") return CATALOG.filter(work => work.media_type === "tv" && seriesKey(work) === seriesKey(m)).sort((a, b) => a.season_number - b.season_number);
  return m.collection_key ? CATALOG.filter(work => work.media_type === "movie" && work.collection_key === m.collection_key).sort((a, b) => Number(a.year) - Number(b.year)) : [];
}
function relatedWorksHtml(m) {
  const related = relatedWorks(m);
  if (related.length < 2) return "";
  const isSeries = m.media_type === "tv";
  return `<nav class="related-works" aria-label="${isSeries ? "切换剧集季数" : "同系列电影"}"><div class="related-heading"><span>${isSeries ? "继续这个故事" : esc(m.collection_name)}</span><small>${isSeries ? `已收录 ${related.length} 季` : `已收录 ${related.length} 部 · 按上映年份`}</small></div><div class="related-links">${related.map(work => `<button class="related-work${work.id === m.id ? " active" : ""}" data-open-work="${esc(work.id)}" type="button" aria-current="${work.id === m.id ? "true" : "false"}">${isSeries ? esc(work.season_label || `第${work.season_number}季`) : esc(work.title)}</button>`).join("")}</div></nav>`;
}
function localDateStr(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function todayStr() { return localDateStr(new Date()); }
function validDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return false;
  const [y, m, d] = value.split("-").map(Number);
  if (y < 1900 || y > 9999) return false;
  return localDateStr(new Date(y, m - 1, d, 12)) === value;
}
function dateFromUrl() {
  const value = new URLSearchParams(location.search).get("date");
  return validDate(value) ? value : todayStr();
}
function mediaFromUrl() {
  const media = new URLSearchParams(location.search).get("type");
  return ["movie", "tv"].includes(media) ? media : "all";
}
function workFromUrl() {
  const id = new URLSearchParams(location.search).get("work");
  return byId.has(id) ? id : null;
}
function shiftDate(dateStr, delta) {
  const [y, m, d] = dateStr.split("-").map(Number);
  const date = new Date(y, m - 1, d, 12);
  date.setDate(date.getDate() + delta);
  const result = localDateStr(date);
  return validDate(result) ? result : dateStr;
}
function hashStr(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
  return h;
}
let currentDate = dateFromUrl();
let currentMedia = mediaFromUrl();
let selectedWorkId = workFromUrl();
let recentRandomId = null;
function catalogFor(media = currentMedia) {
  return media === "all" ? CATALOG : CATALOG.filter(m => m.media_type === media);
}
function pickMovie(dateStr, media = currentMedia) {
  // 电影模式保留原有日期算法。全部模式每三天选一部剧集，避免剧集被大电影库淹没。
  let kind = media;
  if (kind === "all") kind = hashStr(dateStr) % 3 === 0 && catalogFor("tv").length ? "tv" : "movie";
  // 推荐从各剧的第一季进入；后续季可由作品卡直接切换。
  const list = kind === "tv" ? uniqueSeries(catalogFor(kind)) : (typeof MOVIES !== "undefined" ? CATALOG.filter(m => MOVIES.some(original => original.id === m.id)) : catalogFor(kind));
  // 对剧集单独混合种子，避免「每三天」条件与片库数量存在公约数时只选中部分作品。
  let seed = hashStr(dateStr);
  if (kind === "tv") {
    seed = Math.imul(seed ^ (seed >>> 16), 0x45d9f3b);
    seed = Math.imul(seed ^ (seed >>> 16), 0x45d9f3b);
    seed = (seed ^ (seed >>> 16)) >>> 0;
  }
  return list.length ? list[seed % list.length] : null;
}
function currentWork() { return byId.get(selectedWorkId) || pickMovie(currentDate); }
function syncUrl() {
  const url = new URL(location.href);
  currentDate === todayStr() ? url.searchParams.delete("date") : url.searchParams.set("date", currentDate);
  currentMedia === "all" ? url.searchParams.delete("type") : url.searchParams.set("type", currentMedia);
  selectedWorkId ? url.searchParams.set("work", selectedWorkId) : url.searchParams.delete("work");
  if (url.href !== location.href) history.pushState({}, "", url);
}
function shareUrl(m) {
  const url = new URL(location.href);
  url.search = "";
  url.hash = "";
  url.searchParams.set("work", m.id);
  url.searchParams.set("type", m.media_type);
  url.searchParams.set("date", currentDate);
  return url.href;
}
function personLinks(names = []) {
  return names.map(n => `<button class="person-link" data-person="${esc(n)}" type="button">${esc(n)}</button>`).join("、");
}
function fallbackPoster(img) {
  const box = img.closest(".poster, .lib-poster-wrap");
  if (box) {
    box.classList.add("poster-missing");
    img.remove();
  } else {
    img.hidden = true;
  }
}
function posterHtml(m, miniature = false) {
  const cls = miniature ? "lib-poster" : "poster-img";
  return `<span class="poster-title">${esc(m.title)}</span>${m.poster ? `<img class="${cls}" src="${esc(m.poster)}" alt="${esc(m.title)}海报" ${miniature ? 'loading="lazy"' : 'fetchpriority="high"'} decoding="async" onerror="fallbackPoster(this)">` : ""}`;
}
function workFacts(m) {
  const facts = [];
  if (m.media_type === "tv") {
    if (m.season_label) facts.push(m.season_label);
    if (m.episode_count) facts.push(m.completion === "本季更新中" ? `已播 ${m.episode_count}${m.episode_order ? ` / ${m.episode_order}` : ""} 集` : `共 ${m.episode_count} 集`);
    if (m.episode_runtime) facts.push(`约 ${m.episode_runtime} 分钟 / 集`);
    if (m.completion) facts.push(m.completion);
  } else if (m.duration || m.runtime) {
    facts.push(m.duration || `${m.runtime} 分钟`);
  }
  return facts;
}
function scoreHtml(m) {
  let html = "";
  if (m.douban_rating != null) html += `<span class="score douban"><span class="score-label">豆瓣</span><b>${fmtScore(m.douban_rating)}</b><small>/ 10</small></span>`;
  if (m.tmdb_rating != null) html += `<span class="score tmdb"><span class="score-label">TMDB</span><b>${fmtScore(m.tmdb_rating)}</b><small>/ 10${m.media_type === "tv" ? " · 剧集整体" : ""}</small></span>`;
  if (m.tvmaze_rating != null) html += `<span class="score tvmaze"><span class="score-label">TVmaze</span><b>${fmtScore(m.tvmaze_rating)}</b><small>/ 10 · 剧集整体</small></span>`;
  if (m.rt_tomatometer != null) html += `<span class="score rt"><span class="score-label">烂番茄</span><b>${esc(m.rt_tomatometer)}%</b></span>`;
  return html || '<span class="source-note">暂无评分</span>';
}
function movieCardHtml(m, withShare = true) {
  const link = workUrl(m);
  const trailer = "https://search.bilibili.com/all?keyword=" + encodeURIComponent(m.title + " 预告片");
  const facts = workFacts(m);
  const genres = (m.genres || []).slice(0, 4).join(" / ");
  const directors = (m.directors || []).slice(0, 3);
  const actors = (m.actors || []).slice(0, 4);
  return `
    <button class="poster" data-view-poster="${esc(m.id)}" type="button" aria-label="查看《${esc(m.title)}》封面大图">${posterHtml(m)}<span class="poster-stamp">AFTERGLOW SELECTION <span aria-hidden="true">↗</span></span></button>
    <div class="info">
      <div class="work-kicker"><span class="media-badge">${MEDIA_LABELS[m.media_type]}</span><span class="work-year">${esc([m.year, countryText(m), genres].filter(Boolean).join(" · "))}</span></div>
      <h2 class="movie-title">${esc(m.title)}</h2>
      ${m.title_en ? `<p class="movie-title-en">${esc(m.title_en)}</p>` : ""}
      <div class="reason-block"><p class="reason-label">${m.media_type === "tv" ? "这次，走进一个好故事" : "留在今天的一句话"}</p><p class="reason">${esc(m.reason || m.overview || "让故事，陪你度过这一刻。")}</p></div>
      ${facts.length ? `<div class="work-facts">${facts.map(f => `<span class="fact"${f.includes("分钟") && m.runtime_note ? ` title="${esc(m.runtime_note)}"` : ""}>${esc(f)}</span>`).join("")}</div>` : ""}
      ${relatedWorksHtml(m)}
      <div class="work-details">
        ${directors.length ? `<p class="meta"><span>导演</span>${personLinks(directors)}</p>` : ""}
        ${actors.length ? `<p class="meta"><span>主演</span>${personLinks(actors)}${(m.actors || []).length > 4 ? " 等" : ""}</p>` : ""}
      </div>
      <div class="scores">${scoreHtml(m)}</div>
      <div class="actions"><a class="action-btn primary" href="${esc(trailer)}" target="_blank" rel="noopener">看预告片 <span aria-hidden="true">↗</span></a>${link ? `<a class="action-btn" href="${esc(link)}" target="_blank" rel="noopener">${m.douban_url ? "豆瓣详情" : m.source_provider === "tvmaze" ? "TVmaze 详情" : "TMDB 详情"} ↗</a>` : ""}<a class="action-btn subtle" href="https://quanpan.xyz/?q=${encodeURIComponent(m.title)}" target="_blank" rel="noopener">资源搜索 ↗</a></div>
      ${withShare ? `<div class="share-actions"><button class="text-btn" data-copy="${esc(m.id)}" type="button">复制推荐</button><span aria-hidden="true">·</span><button class="text-btn" data-share="${esc(m.id)}" type="button">保存分享卡</button></div>` : ""}
      <p class="source-note">资料来自 ${m.source_provider === "tvmaze" ? `<a href="${esc(workUrl(m))}" target="_blank" rel="noopener">TVmaze</a> · <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener">CC BY-SA</a>` : esc(sourceNote(m))}${m.media_type === "tv" && m.metadata_checked_at ? " · 核对于 " + esc(m.metadata_checked_at) : ""}</p>
    </div>`;
}
function render() {
  const m = currentWork();
  $("date").textContent = currentDate.replaceAll("-", " / ");
  $("date").dateTime = currentDate;
  $("today-btn").hidden = currentDate === todayStr() && !selectedWorkId;
  $("back-daily").hidden = !selectedWorkId;
  $("daily-title").innerHTML = (selectedWorkId ? "片库选映" : "今日一幕") + '<span class="heading-dot">・</span>';
  $("daily-context").textContent = selectedWorkId ? "值得留下的故事，慢慢看。" : "一日一选 · 慢慢看，好好感受";
  document.querySelectorAll("[data-media]").forEach(btn => btn.setAttribute("aria-pressed", String(btn.dataset.media === currentMedia)));
  $("selection-note").textContent = currentMedia === "tv" ? "从第一集开始，让好故事多陪你一会儿。" : currentMedia === "movie" ? "把一段时间，交给一部好电影。" : "每天，留一点时间给好故事。";
  document.querySelector('[data-kind="cold"]').hidden = currentMedia === "tv";
  $("card").innerHTML = m ? movieCardHtml(m) : '<div class="empty-state">这个分类暂时没有作品，试试其他分类。</div>';
  $("card").classList.remove("animate");
  requestAnimationFrame(() => $("card").classList.add("animate"));
  $("collection").hidden = true;
  document.title = m ? `${m.title} · Afterglow` : "Afterglow · 好故事，自有余韵。";
}
function gotoDate(date) {
  currentDate = date;
  selectedWorkId = null;
  syncUrl();
  render();
}
function chooseMedia(media) {
  currentMedia = media;
  selectedWorkId = null;
  recentRandomId = null;
  $("random-result").hidden = true;
  syncUrl();
  render();
}
function openWork(id) {
  if (!byId.has(id)) return;
  if (!$("library-overlay").hidden) closeLibrary();
  selectedWorkId = id;
  currentMedia = byId.get(id).media_type;
  $("random-result").hidden = true;
  syncUrl();
  render();
  $("main").focus({ preventScroll: true });
  $("main").scrollIntoView({ behavior: scrollBehavior(), block: "start" });
}
function scrollBehavior() { return matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"; }
function parseVotes(value) {
  if (!value) return 0;
  const n = Number.parseFloat(String(value).replace(/,/g, ""));
  return Number.isFinite(n) ? n * (String(value).includes("万") ? 10000 : 1) : 0;
}
function randomPick(list) {
  const candidates = list.filter(m => m.id !== recentRandomId && m.id !== currentWork()?.id);
  const pool = candidates.length ? candidates : list;
  return pool[Math.floor(Math.random() * pool.length)] || null;
}
function randomAny() { return randomPick(catalogFor()); }
function randomCold() {
  return randomPick(catalogFor().filter(m => m.douban_rating >= 8.8 && parseVotes(m.douban_votes) > 0 && parseVotes(m.douban_votes) < 600000));
}
function randomByType(type) { return randomPick(catalogFor().filter(m => (m.genres || []).includes(type))); }
function randomByDecade(decade) {
  return randomPick(catalogFor().filter(m => {
    const y = Number.parseInt(m.year, 10);
    return y && (decade === "old" ? y < 1990 : y >= Number(decade) && y < Number(decade) + 10);
  }));
}
function showRandom(m) {
  const box = $("random-result");
  box.hidden = false;
  if (m) {
    recentRandomId = m.id;
    box.innerHTML = '<p class="random-result-label">另一幕，也许正合心意。</p><section class="card">' + movieCardHtml(m) + "</section>";
  } else {
    box.innerHTML = '<p class="empty-state">当前片库中还没有符合条件的作品，换个类型或年代试试。</p>';
  }
  box.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
}
function personMovies(name) { return CATALOG.filter(m => (m.directors || []).includes(name) || (m.actors || []).includes(name)); }
function showCollection(name) {
  const works = personMovies(name);
  $("collection").innerHTML = `<div class="collection-head"><h3 class="collection-name">${esc(name)}的作品 <span class="collection-count">${works.length} 部</span></h3><button class="collection-close" type="button" aria-label="关闭人物作品合集">×</button></div><div class="collection-list">${works.map(m => `<button class="collection-item" data-open-work="${esc(m.id)}" type="button">${m.poster ? `<img class="collection-poster" src="${esc(m.poster)}" alt="" loading="lazy" onerror="this.hidden=true">` : ""}<span class="collection-info"><span class="collection-title">${esc(m.title)}</span><span class="collection-meta">${MEDIA_LABELS[m.media_type]} · ${esc(m.year)} · ${esc(scoreText(m))}</span></span></button>`).join("")}</div>`;
  $("collection").hidden = false;
  $("collection").scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
}
function smallCard(m) {
  return `<div class="lib-card"><button class="lib-poster-wrap" data-view-poster="${esc(m.id)}" type="button" aria-label="查看《${esc(m.title)}》封面大图">${posterHtml(m, true)}<span class="lib-type">${MEDIA_LABELS[m.media_type]}</span></button><button class="lib-work-link" data-open-work="${esc(m.id)}" type="button"><span class="lib-name">${esc(m.title)}</span><span class="lib-meta">${esc(m.year)} · ${esc(scoreText(m))}</span></button></div>`;
}
function renderSeries() {
  const seasons = catalogFor("tv");
  const series = uniqueSeries(seasons);
  if (!series.length) return;
  // 不同地区各留一个位置，更多剧集可从地区入口继续浏览。
  const picks = [];
  ["US", "GB", "KR", null].forEach(region => {
    const pool = series.filter(m => (!region || regionsOf(m).includes(region)) && !picks.some(p => p.id === m.id));
    if (pool.length) picks.push(pool[hashStr(todayStr() + (region || "all")) % pool.length]);
  });
  const shortcuts = seriesRegionOptions().filter(option => ["US", "GB", "KR"].includes(option.value));
  $("series-section").innerHTML = `<div class="shelf-heading"><div><span class="eyebrow">STORIES TO STAY WITH</span><h2 id="series-title">好故事，不止一集。</h2></div><button class="text-btn" id="all-series" type="button">${series.length} 部剧集 · ${seasons.length} 季 ↗</button></div><div class="series-shortcuts" aria-label="按地区探索剧集">${shortcuts.map(({ value, label }) => `<button class="random-tag" type="button" data-series-region="${value}">${label}<span>${series.filter(m => regionsOf(m).includes(value)).length}</span></button>`).join("")}</div><div class="series-grid">${picks.map(smallCard).join("")}</div>`;
  $("series-section").hidden = false;
  $("all-series").addEventListener("click", () => openLibrary("tv"));
}
function renderChart() {
  if (typeof CHART === "undefined" || !CHART.length) return;
  $("chart").innerHTML = `<div class="shelf-heading"><div><span class="eyebrow">ON THE RADAR</span><h2 class="chart-title">电影口碑榜</h2></div><span class="chart-sub">豆瓣口碑榜收录</span></div><ol class="chart-list">${CHART.map((m, i) => `<li class="chart-item"><a href="${esc(m.douban_url)}" target="_blank" rel="noopener"><span class="chart-rank">${String(i + 1).padStart(2, "0")}</span>${m.poster ? `<img class="chart-poster" src="${esc(m.poster)}" alt="" loading="lazy" onerror="this.hidden=true">` : ""}<span class="chart-info"><span class="chart-name">${esc(m.title)}</span><span class="chart-meta">${esc([m.year, ...(m.genres || []).slice(0, 2)].filter(Boolean).join(" · "))}</span></span><span class="chart-score">${m.douban_rating != null ? `<span class="cs-douban">${fmtScore(m.douban_rating)}<small> 豆瓣</small></span>` : ""}</span></a></li>`).join("")}</ol>`;
  $("chart").hidden = false;
}

// 片库：分类、搜索、筛选和键盘操作。
const libraryState = { media: "all", region: "all", genre: "全部", decade: "全部", sort: "rating", query: "" };
const LIBRARY_SORTS = [{ label: "评分优先", value: "rating" }, { label: "最新年份", value: "year" }, { label: "片名", value: "title" }];
const LIBRARY_DECADES = ["全部", "20年代", "10年代", "00年代", "90年代", "更早"];
function collectGenres() {
  const count = {};
  catalogFor(libraryState.media).forEach(m => (m.genres || []).forEach(g => { count[g] = (count[g] || 0) + 1; }));
  return Object.keys(count).sort((a, b) => count[b] - count[a]);
}
function decadeOf(year) {
  const y = parseInt(year, 10);
  return !y ? "" : y < 1990 ? "更早" : y < 2000 ? "90年代" : y < 2010 ? "00年代" : y < 2020 ? "10年代" : "20年代";
}
function filterCatalog(state) {
  const query = state.query.trim().toLowerCase();
  return catalogFor(state.media).filter(m => {
    const text = [m.title, m.title_en, ...(m.directors || []), ...(m.actors || [])].join(" ").toLowerCase();
    return (state.region === "all" || regionsOf(m).includes(state.region)) && (!query || text.includes(query)) && (state.genre === "全部" || (m.genres || []).includes(state.genre)) && (state.decade === "全部" || decadeOf(m.year) === state.decade);
  }).sort((a, b) => {
    if (state.sort === "year") return (parseInt(b.year, 10) || 0) - (parseInt(a.year, 10) || 0);
    if (state.sort === "title") return a.title.localeCompare(b.title, "zh");
    return scoreOf(b) - scoreOf(a);
  });
}
function filteredMovies() { return filterCatalog(libraryState); }
function renderTagRow(id, options, active) {
  $(id).innerHTML = options.map(opt => {
    const value = typeof opt === "string" ? opt : opt.value;
    const label = typeof opt === "string" ? opt : opt.label;
    return `<button class="library-tag${value === active ? " active" : ""}" aria-pressed="${value === active}" data-value="${esc(value)}" type="button">${esc(label)}</button>`;
  }).join("");
}
function renderFilters() {
  renderTagRow("library-media", Object.entries(MEDIA_LABELS).map(([value, label]) => ({ value, label })), libraryState.media);
  $("library-region-row").hidden = libraryState.media !== "tv";
  renderTagRow("library-region", seriesRegionOptions(), libraryState.region);
  renderTagRow("library-genres", ["全部", ...collectGenres()], libraryState.genre);
  renderTagRow("library-decades", LIBRARY_DECADES, libraryState.decade);
  renderTagRow("library-sort", LIBRARY_SORTS, libraryState.sort);
}
function renderLibrary() {
  const list = filteredMovies();
  $("library-count").textContent = (libraryState.media === "tv" ? `找到 ${uniqueSeries(list).length} 部剧集 · ${list.length} 季` : `找到 ${list.length} 部作品`) + (libraryState.sort === "rating" ? " · 评分来自豆瓣、TMDB 或 TVmaze，分数供参考" : "");
  $("library-grid").innerHTML = list.length ? list.map(smallCard).join("") : '<p class="empty-state">还没找到这部作品，试试其他关键词或放宽筛选。</p>';
}
let libraryOpener = null;
function openLibrary(media, region = "all") {
  libraryOpener = document.activeElement;
  libraryState.media = typeof media === "string" ? media : currentMedia;
  libraryState.region = libraryState.media === "tv" ? region : "all";
  libraryState.genre = "全部";
  libraryState.decade = "全部";
  libraryState.query = "";
  $("library-search").value = "";
  $("library-overlay").hidden = false;
  document.body.classList.add("no-scroll");
  document.querySelector(".page").inert = true;
  renderFilters();
  renderLibrary();
  $("library-overlay").scrollTop = 0;
  $("library-search").focus();
}
function closeLibrary() {
  $("library-overlay").hidden = true;
  document.body.classList.remove("no-scroll");
  document.querySelector(".page").inert = false;
  if (libraryOpener?.isConnected) libraryOpener.focus({ preventScroll: true });
}

// 第一版完整海报 3D 弹窗：透视倾斜、光泽及后景阴影。
let posterOpener = null;
let viewedPosterId = null;
let posterFrame = 0;
let posterPointer = null;
const posterSurface = $("poster-depth");
const posterMotion = matchMedia("(prefers-reduced-motion: no-preference)");
function resetPosterDepth() {
  cancelAnimationFrame(posterFrame);
  $("poster-depth").style.setProperty("--tilt-x", "0deg");
  $("poster-depth").style.setProperty("--tilt-y", "0deg");
  $("poster-depth").style.setProperty("--light-x", "50%");
  $("poster-depth").style.setProperty("--light-y", "35%");
}
function openPoster(id, opener) {
  const m = byId.get(id);
  if (!m) return;
  posterOpener = opener;
  viewedPosterId = id;
  resetPosterDepth();
  if (posterMotion.matches) {
    $("poster-depth").style.setProperty("--tilt-x", "-4deg");
    $("poster-depth").style.setProperty("--tilt-y", "6deg");
  }
  $("poster-depth").style.setProperty("--poster-ratio", "0.6667");
  $("poster-viewer-title").textContent = m.title;
  $("poster-depth-placeholder").textContent = m.title;
  $("poster-depth-image").alt = m.title + "完整封面";
  ["poster-depth-image", "poster-depth-shadow", "poster-ambient"].forEach(key => {
    $(key).hidden = !m.poster;
    if (m.poster) $(key).src = m.poster;
    else $(key).removeAttribute("src");
  });
  $("poster-viewer").showModal();
  document.body.classList.add("no-scroll");
}
function closePoster() { $("poster-viewer").close(); }
$("poster-depth-image").addEventListener("load", e => {
  const img = e.target;
  if (img.naturalHeight) $("poster-depth").style.setProperty("--poster-ratio", String(img.naturalWidth / img.naturalHeight));
});
$("poster-depth-image").addEventListener("error", () => {
  ["poster-depth-image", "poster-depth-shadow", "poster-ambient"].forEach(key => { $(key).hidden = true; });
});
function updatePosterDepth(e) {
  if (!posterMotion.matches) return;
  if (posterPointer && e.pointerId !== posterPointer.id) return;
  if (e.pointerType === "touch" && !posterPointer) return;
  // 拖动期间使用按下时的边界，避免倾斜改变尺寸后产生反馈抖动。
  const box = posterPointer?.box || posterSurface.getBoundingClientRect();
  const x = Math.max(-1, Math.min(1, (e.clientX - box.left) / box.width * 2 - 1));
  const y = Math.max(-1, Math.min(1, (e.clientY - box.top) / box.height * 2 - 1));
  cancelAnimationFrame(posterFrame);
  posterFrame = requestAnimationFrame(() => {
    $("poster-depth").style.setProperty("--tilt-x", `${-y * 7}deg`);
    $("poster-depth").style.setProperty("--tilt-y", `${x * 9}deg`);
    $("poster-depth").style.setProperty("--light-x", `${(x + 1) * 50}%`);
    $("poster-depth").style.setProperty("--light-y", `${(y + 1) * 50}%`);
  });
}
function endPosterDrag(e) {
  if (!posterPointer || (e && e.pointerId !== posterPointer.id)) return;
  const id = posterPointer.id;
  posterPointer = null;
  posterSurface.classList.remove("is-dragging");
  if (posterSurface.hasPointerCapture(id)) posterSurface.releasePointerCapture(id);
  resetPosterDepth();
}
posterSurface.addEventListener("pointerdown", e => {
  if (!posterMotion.matches || e.isPrimary === false || posterPointer) return;
  if (e.pointerType === "mouse" && e.button !== 0) return;
  posterPointer = { id: e.pointerId, box: posterSurface.getBoundingClientRect() };
  posterSurface.classList.add("is-dragging");
  posterSurface.setPointerCapture(e.pointerId);
  updatePosterDepth(e);
});
posterSurface.addEventListener("pointerup", endPosterDrag);
posterSurface.addEventListener("pointercancel", endPosterDrag);
posterSurface.addEventListener("lostpointercapture", endPosterDrag);
posterSurface.addEventListener("dragstart", e => e.preventDefault());
$("poster-scene").addEventListener("pointermove", updatePosterDepth);
$("poster-scene").addEventListener("pointerleave", () => {
  if (!posterPointer) resetPosterDepth();
});
posterMotion.addEventListener("change", () => {
  endPosterDrag();
  resetPosterDepth();
});
$("poster-viewer-close").addEventListener("click", closePoster);
$("poster-viewer").addEventListener("click", e => {
  if (e.target === $("poster-viewer") || e.target === $("poster-scene")) closePoster();
});
$("poster-viewer").addEventListener("close", () => {
  endPosterDrag();
  resetPosterDepth();
  if ($("library-overlay").hidden) document.body.classList.remove("no-scroll");
  if (posterOpener?.isConnected) posterOpener.focus({ preventScroll: true });
  viewedPosterId = null;
});
$("poster-viewer-work").addEventListener("click", () => {
  const id = viewedPosterId;
  closePoster();
  openWork(id);
});

// 分享卡与复制推荐共用作品 ID，链接不会随之后的片库更新改变作品。
let toastTimer;
function toast(message) {
  clearTimeout(toastTimer);
  $("toast").textContent = message;
  $("toast").hidden = false;
  toastTimer = setTimeout(() => { $("toast").hidden = true; }, 3200);
}
async function copyRecommend(m) {
  const text = `Afterglow · 今日一幕\n《${m.title}》 · ${MEDIA_LABELS[m.media_type]} · ${m.year || ""}\n${scoreText(m)}\n${workFacts(m).join(" · ")}\n${m.reason || ""}\n${shareUrl(m)}\n好故事，自有余韵。`;
  try {
    await navigator.clipboard.writeText(text);
    toast("已复制推荐，分享这一幕。");
  } catch (_) {
    window.prompt("请复制这段推荐：", text);
  }
}
function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    const timer = setTimeout(() => reject(new Error("海报加载超时")), 5000);
    img.onload = () => { clearTimeout(timer); resolve(img); };
    img.onerror = () => { clearTimeout(timer); reject(new Error("海报加载失败")); };
    img.src = url;
  });
}
function wrapText(ctx, text, maxWidth) {
  let line = "";
  const lines = [];
  for (const char of String(text || "")) {
    if (line && ctx.measureText(line + char).width > maxWidth) { lines.push(line); line = char; }
    else line += char;
  }
  if (line) lines.push(line);
  return lines;
}
function limitedLines(ctx, text, width, count) {
  const lines = wrapText(ctx, text, width);
  const result = lines.slice(0, count);
  if (lines.length > count) {
    let last = result[count - 1];
    while (last && ctx.measureText(last + "…").width > width) last = last.slice(0, -1);
    result[count - 1] = last + "…";
  }
  return result;
}
async function createShareCardCanvas(m, date = currentDate) {
    const canvas = document.createElement("canvas");
    canvas.width = 900;
    canvas.height = 1420;
    const ctx = canvas.getContext("2d");
    const font = "'PingFang SC', 'Microsoft YaHei', sans-serif";
    ctx.fillStyle = BRAND_COLORS.background;
    ctx.fillRect(0, 0, 900, 1420);
    const glow = ctx.createRadialGradient(450, 300, 30, 450, 300, 670);
    glow.addColorStop(0, "#483723"); glow.addColorStop(1, "#161512");
    ctx.fillStyle = glow; ctx.fillRect(0, 0, 900, 1420);
    ctx.textAlign = "center";
    ctx.fillStyle = BRAND_COLORS.accent;
    ctx.font = "52px Georgia, serif";
    ctx.fillText("Afterglow.", 450, 90);
    ctx.font = `20px ${font}`;
    ctx.fillStyle = "#b4a797";
    ctx.fillText(`今日一幕  /  ${date}`, 450, 135);
    const px = 270, py = 180, pw = 360, ph = 540;
    ctx.fillStyle = "#2b261f"; ctx.fillRect(px, py, pw, ph);
    let image = null;
    if (m.poster) { try { image = await loadImage(m.poster); } catch (_) {} }
    if (image) {
      const scale = Math.max(pw / image.width, ph / image.height);
      const sw = pw / scale, sh = ph / scale;
      ctx.drawImage(image, (image.width - sw) / 2, (image.height - sh) / 2, sw, sh, px, py, pw, ph);
    } else {
      ctx.fillStyle = BRAND_COLORS.accent; ctx.font = `36px ${font}`;
      limitedLines(ctx, m.title, 290, 4).forEach((line, i) => ctx.fillText(line, 450, py + 220 + i * 52));
    }
    let y = 790;
    ctx.fillStyle = BRAND_COLORS.accent; ctx.font = `20px ${font}`;
    ctx.fillText([MEDIA_LABELS[m.media_type], m.year, (m.genres || []).slice(0, 2).join(" / ")].filter(Boolean).join(" · "), 450, y);
    y += 66;
    ctx.fillStyle = "#f7eee1"; ctx.font = `bold 46px ${font}`;
    limitedLines(ctx, m.title, 770, 2).forEach(line => { ctx.fillText(line, 450, y); y += 61; });
    ctx.font = `22px ${font}`; ctx.fillStyle = "#b4a797";
    limitedLines(ctx, workFacts(m).join(" · "), 750, 2).forEach(line => { ctx.fillText(line, 450, y); y += 34; });
    y += 24;
    ctx.font = `30px ${font}`; ctx.fillStyle = BRAND_COLORS.accent;
    ctx.fillText(scoreText(m), 450, y);
    y += 60;
    ctx.font = `28px ${font}`; ctx.fillStyle = "#e9ded0";
    limitedLines(ctx, m.reason, 720, 3).forEach(line => { ctx.fillText(line, 450, y); y += 44; });
    ctx.strokeStyle = "#63503a"; ctx.beginPath(); ctx.moveTo(385, 1290); ctx.lineTo(515, 1290); ctx.stroke();
    ctx.fillStyle = BRAND_COLORS.accent; ctx.font = `24px ${font}`; ctx.fillText("好故事，自有余韵。", 450, 1340);
    ctx.fillStyle = "#b4a797"; ctx.font = `16px ${font}`; ctx.fillText(m.source_provider === "tvmaze" ? "资料：TVmaze · CC BY-SA 4.0 · tvmaze.com" : `资料与海报：${sourceNote(m)}`, 450, 1380);
    return canvas;
}

async function generateShareCard(m, button) {
  if (button?.disabled) return;
  if (button) { button.disabled = true; button.textContent = "正在生成…"; }
  try {
    const canvas = await createShareCardCanvas(m);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("无法生成分享卡");
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `afterglow-${m.id}-${currentDate}.png`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
    toast("分享卡已生成。");
  } catch (_) { toast("分享卡暂时无法生成，可以先复制推荐。"); }
  finally { if (button) { button.disabled = false; button.textContent = "保存分享卡"; } }
}

function applyTheme(theme) {
  if (theme === "light") document.documentElement.dataset.theme = "light";
  else delete document.documentElement.dataset.theme;
  $("theme-btn").textContent = theme === "light" ? "夜间模式" : "日间模式";
  $("theme-btn").setAttribute("aria-label", theme === "light" ? "切换到夜间模式" : "切换到日间模式");
  document.querySelector('meta[name="theme-color"]').content = theme === "light" ? "#f7f2e9" : "#161512";
  try { localStorage.setItem("theme", theme); } catch (_) {}
}
$("theme-btn").addEventListener("click", () => applyTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light"));
$("prev-day").addEventListener("click", () => gotoDate(shiftDate(currentDate, -1)));
$("next-day").addEventListener("click", () => gotoDate(shiftDate(currentDate, 1)));
$("today-btn").addEventListener("click", () => gotoDate(todayStr()));
$("back-daily").addEventListener("click", () => { selectedWorkId = null; syncUrl(); render(); });
$("media-tabs").addEventListener("click", e => { const button = e.target.closest("[data-media]"); if (button) chooseMedia(button.dataset.media); });
$("library-btn").addEventListener("click", () => openLibrary());
$("library-close").addEventListener("click", closeLibrary);
$("library-overlay").addEventListener("click", e => { if (e.target === $("library-overlay")) closeLibrary(); });
$("library-search").addEventListener("input", e => { libraryState.query = e.target.value; renderLibrary(); });
["media", "region", "genres", "decades", "sort"].forEach(key => {
  $("library-" + key).addEventListener("click", e => {
    const button = e.target.closest("[data-value]");
    if (!button) return;
    const property = { genres: "genre", decades: "decade" }[key] || key;
    libraryState[property] = button.dataset.value;
    if (key === "media") { libraryState.genre = "全部"; libraryState.region = "all"; }
    renderFilters(); renderLibrary();
    // 标签重绘后恢复键盘焦点。
    Array.from($("library-" + key).querySelectorAll("button")).find(b => b.dataset.value === button.dataset.value)?.focus();
  });
});
document.addEventListener("keydown", e => {
  if ($("poster-viewer").open) return;
  if ($("library-overlay").hidden) return;
  if (e.key === "Escape") { closeLibrary(); return; }
  if (e.key !== "Tab") return;
  const focusable = Array.from($("library-overlay").querySelectorAll('button, input, a[href]')).filter(el => !el.disabled && el.getClientRects().length);
  const first = focusable[0], last = focusable.at(-1);
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
});
document.addEventListener("click", e => {
  const target = e.target.closest("button");
  if (!target) return;
  if (target.dataset.viewPoster) openPoster(target.dataset.viewPoster, target);
  else if (target.dataset.seriesRegion) openLibrary("tv", target.dataset.seriesRegion);
  else if (target.dataset.openWork) openWork(target.dataset.openWork);
  else if (target.dataset.person) showCollection(target.dataset.person);
  else if (target.classList.contains("collection-close")) $("collection").hidden = true;
  else if (target.dataset.kind) showRandom(target.dataset.kind === "cold" ? randomCold() : randomAny());
  else if (target.dataset.type) showRandom(randomByType(target.dataset.type));
  else if (target.dataset.decade) showRandom(randomByDecade(target.dataset.decade));
  else if (target.dataset.copy && byId.has(target.dataset.copy)) copyRecommend(byId.get(target.dataset.copy));
  else if (target.dataset.share && byId.has(target.dataset.share)) generateShareCard(byId.get(target.dataset.share), target);
});
window.addEventListener("popstate", () => {
  currentDate = dateFromUrl(); currentMedia = mediaFromUrl(); selectedWorkId = workFromUrl();
  $("random-result").hidden = true; render();
});
$("library-total").textContent = CATALOG.length;
applyTheme(document.documentElement.dataset.theme === "light" ? "light" : "dark");
render(); renderSeries(); renderChart();
