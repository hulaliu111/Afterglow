/* Afterglow product showreel: a deterministic, seekable clock, isolated from app state. */
(() => {
  const dialog = $("showreel-dialog");
  const stage = $("showreel-stage");
  const viewport = $("showreel-viewport");
  const progress = $("showreel-progress");
  const playButton = $("showreel-play");
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const motionToggle = $("showreel-motion");
  motionToggle.checked = reduceMotion.matches;
  const reduced = () => motionToggle.checked;
  const DURATION = 30;
  const target = byId.get("tvmaze-tv-335-s1") || CATALOG.find(m => m.media_type === "tv" && regionsOf(m).includes("GB") && m.genres.includes("悬疑"));
  if (!target) { $("showreel-open").hidden = true; return; }
  const sampleDate = "2026-10-03";
  const daily = pickMovie(sampleDate, "movie") || target;
  const filterStates = [
    { media: "all", region: "all", genre: "全部", decade: "全部", sort: "rating", query: "" },
    { media: "tv", region: "all", genre: "全部", decade: "全部", sort: "rating", query: "" },
    { media: "tv", region: "GB", genre: "全部", decade: "全部", sort: "rating", query: "" },
    { media: "tv", region: "GB", genre: "悬疑", decade: "全部", sort: "rating", query: "" },
  ];
  const lists = filterStates.map(state => state.media === "tv" ? uniqueSeries(filterCatalog(state)) : filterCatalog(state));
  const phaseTimes = [3.1, 4.5, 6, 8];
  const chapters = [
    { time: 0, label: "每日一幕", text: "每天，遇见一个值得留下的故事。" },
    { time: 3.1, label: "探索片库", text: "电影、美剧、英剧、韩剧，按你的偏好寻找。" },
    { time: 6, label: "找到偏爱", text: "想看一部英剧？再选悬疑，缩小选择范围。" },
    { time: 12.2, label: "看见故事", text: "点开封面，感受完整海报的光影与景深。" },
    { time: 16.7, label: "值得开始", text: "推荐理由、季数和时长，让你知道从哪里开始。" },
    { time: 21.7, label: "留住余韵", text: "把想看的作品，留下为一张分享卡。" },
    { time: 27.2, label: "Afterglow", text: "好故事，自有余韵。现在，开始你的选择。" },
  ];
  let time = 0, playing = false, frame = 0, lastTick = 0, opener = null;
  let portrait = false, initialized = false, loadVersion = 0, resumeOnSeek = false;
  let lastChapter = -1, lastPhase = -1, shareReady = false;
  let nodes, cards;
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const smooth = p => p * p * (3 - 2 * p);
  const ease = p => 1 - Math.pow(1 - p, 3);
  const between = (t, a, b) => reduced() ? +(t >= b) : smooth(clamp((t - a) / (b - a)));
  const mix = (a, b, p) => a + (b - a) * p;
  const rectMix = (a, b, p) => Object.fromEntries(Object.keys(a).map(k => [k, mix(a[k], b[k], p)]));
  function place(node, r) {
    node.style.left = `${r.x}px`; node.style.top = `${r.y}px`;
    if (r.w != null) node.style.width = `${r.w}px`;
    if (r.h != null) node.style.height = `${r.h}px`;
  }
  function reveal(node, opacity) { node.style.opacity = clamp(opacity); node.style.visibility = opacity > .001 ? "visible" : "hidden"; }
  function facts(m) { return workFacts(m).map(f => `<span>${esc(f)}</span>`).join(""); }
  function rating(m) {
    const source = m.douban_rating != null ? "豆瓣" : m.tmdb_rating != null ? "TMDB" : "TVmaze";
    return `${source}<b>${fmtScore(scoreOf(m))}</b> <small>/ 10${m.media_type === "tv" ? " · 剧集整体" : ""}</small>`;
  }
  function info(m, detail = false) {
    return `<div class="sh-meta">${esc([MEDIA_LABELS[m.media_type], m.year, countryText(m), ...(m.genres || []).slice(0, 2)].filter(Boolean).join(" · "))}</div><h3>${esc(m.title)}</h3><p class="sh-en">${esc(m.title_en || "")}</p><div class="sh-reason"><small>${m.media_type === "tv" ? "这次，走进一个好故事" : "留在今天的一句话"}</small>${esc(m.reason || m.overview || "让故事，陪你度过这一刻。")}</div><div class="sh-facts">${facts(m)}</div><div class="sh-rating">${rating(m)}</div>${detail ? '<span class="sh-save">保存分享卡 ↗</span><p class="sh-source">资料：TVmaze · CC BY-SA 4.0</p>' : ""}`;
  }
  function build() {
    stage.innerHTML = `<div class="sh-box" data-motion-object="container"></div>
      <div class="sh-layer sh-daily" data-motion-object="daily"><div class="sh-brand">Afterglow<span>.</span></div><div class="sh-daily-label">今日一幕<span style="color:#e6b87b">・</span></div><span class="sh-browse">探索片库 ↗</span><img class="sh-daily-poster" src="${esc(daily.poster)}" alt=""><div class="sh-info">${info(daily)}</div></div>
      <div class="sh-layer sh-library" data-motion-object="library"><h3 class="sh-library-title">探索片库</h3><p class="sh-search">搜索片名、导演或演员…</p><div class="sh-filter-row" data-row="media"><span class="sh-filter-label">作品</span>${["全部", "电影", "剧集"].map(x => `<span class="sh-tag" data-tag="${x}">${x}</span>`).join("")}</div><div class="sh-filter-row" data-row="region"><span class="sh-filter-label">地区</span>${["全部地区", "美剧", "英剧", "韩剧"].map(x => `<span class="sh-tag" data-tag="${x}">${x}</span>`).join("")}</div><div class="sh-filter-row" data-row="genre"><span class="sh-filter-label">类型</span>${["全部", "剧情", "悬疑", "犯罪"].map(x => `<span class="sh-tag" data-tag="${x}">${x}</span>`).join("")}</div><p class="sh-count"></p><div class="sh-grid" data-motion-object="results"></div></div>
      <div class="sh-layer sh-cover" data-motion-object="cover"><div class="sh-cover-text"><span class="sh-eyebrow">AFTERGLOW · COVER GALLERY</span><h3>${esc(target.title)}</h3><span class="sh-save">查看作品介绍 ↗</span></div></div>
      <div class="sh-layer sh-detail" data-motion-object="detail"><div class="sh-info">${info(target, true)}</div></div>
      <div class="sh-layer sh-share" data-motion-object="share"><canvas class="sh-share-canvas" width="900" height="1420" aria-label="${esc(target.title)}分享卡"></canvas><div class="sh-share-text"><h3>Afterglow<span>.</span></h3><p>好故事，<br>自有余韵。</p><small>把想看的这一幕，留下来。</small><button class="sh-end-cta" type="button" tabindex="-1" aria-hidden="true">开始选片 ↗</button></div></div>
      <div class="sh-poster" data-motion-object="poster"><div class="sh-poster-face"><span class="sh-poster-fallback">${esc(target.title)}</span><img src="${esc(target.poster)}" alt="${esc(target.title)}海报"><span class="sh-glare"></span></div></div>
      <div class="sh-cursor" data-motion-object="cursor"><span class="sh-click"></span><svg viewBox="0 0 27 35" fill="none"><path d="M3 2L23 22L14 23L19 32L14 34L9 25L3 30Z" fill="#f7eee1" stroke="#231a11" stroke-width="2"/></svg></div>`;
    nodes = Object.fromEntries(["container", "daily", "library", "cover", "detail", "share", "poster", "cursor"].map(key => [key, stage.querySelector(`[data-motion-object="${key}"]`)]));
    const union = new Map(lists.flatMap(list => list.slice(0, 6)).map(m => [m.id, m]));
    cards = [...union.values()].map(m => {
      const node = document.createElement("div");
      node.className = "sh-grid-card";
      node.dataset.work = m.id;
      node.innerHTML = `${m.id === target.id ? '<div class="sh-empty-cover"></div>' : `<img src="${esc(m.poster)}" alt="">`}<h3>${esc(m.title)}</h3><p>${esc(scoreText(m).replace("（剧集整体）", ""))}</p>`;
      stage.querySelector(".sh-grid").append(node);
      return { m, node };
    });
    stage.querySelectorAll("img").forEach(img => img.addEventListener("error", () => { img.style.visibility = "hidden"; }));
    initialized = true;
  }
  function layout() {
    const w = viewport.clientWidth;
    portrait = w <= 650;
    const W = portrait ? 720 : 1280, H = portrait ? 1000 : 720;
    stage.style.width = `${W}px`; stage.style.height = `${H}px`;
    stage.dataset.portrait = String(portrait);
    const scale = Math.min(w / W, viewport.clientHeight / H);
    stage.style.transform = `translate(-50%, -50%) scale(${scale})`;
    if (initialized) render();
  }
  function gridRect(index, phase = 0) {
    if (phase === 3) return portrait ? { x: 80 + index * 320, y: 420, w: 240, h: 360 } : { x: 490 + index * 245, y: 310, w: 170, h: 255 };
    if (portrait) return { x: 65 + index % 3 * 200, y: 420 + Math.floor(index / 3) * 340, w: 185, h: 277.5 };
    return { x: 136 + index * 174, y: 310, w: 150, h: 225 };
  }
  function phaseAt(t) {
    let phase = 0;
    phaseTimes.forEach((v, i) => { if (t >= v) phase = i; });
    return phase;
  }
  function gridState(m, phase) {
    const i = lists[phase].slice(0, 6).findIndex(x => x.id === m.id);
    return { r: gridRect(Math.max(0, i), phase), opacity: i < 0 ? 0 : 1 };
  }
  function gridPose(m, t, phase) {
    const current = gridState(m, phase), previous = gridState(m, Math.max(0, phase - 1));
    const p = phase ? between(t, phaseTimes[phase], phaseTimes[phase] + .6) : 1;
    if (!previous.opacity) previous.r = { ...current.r, y: current.r.y + 65 };
    if (!current.opacity) current.r = { ...previous.r, y: previous.r.y - 50 };
    return { r: rectMix(previous.r, current.r, p), opacity: mix(previous.opacity, current.opacity, p) };
  }
  function render() {
    if (!initialized) return;
    const t = time;
    const phase = phaseAt(t);
    const dailyRect = portrait ? { x: 40, y: 145, w: 640, h: 790 } : { x: 100, y: 116, w: 1080, h: 548 };
    const libraryRect = portrait ? { x: 35, y: 30, w: 650, h: 940 } : { x: 100, y: 42, w: 1080, h: 620 };
    const detailRect = portrait ? { x: 40, y: 60, w: 640, h: 930 } : { x: 130, y: 92, w: 1020, h: 600 };
    let containerRect = rectMix(dailyRect, libraryRect, between(t, 2.75, 3.6));
    if (t >= 16.7) containerRect = detailRect;
    place(nodes.container, containerRect);
    reveal(nodes.container, (1 - between(t, 12.2, 13)) + between(t, 16.7, 17.5) - between(t, 21.7, 22.7));
    reveal(nodes.daily, 1 - between(t, 2.75, 3.35));
    nodes.daily.style.transform = `translateY(${-35 * between(t, 2.75, 3.35)}px)`;
    place(nodes.daily.querySelector(".sh-brand"), portrait ? { x: 65, y: 45 } : { x: 105, y: 38 });
    place(nodes.daily.querySelector(".sh-daily-label"), portrait ? { x: 65, y: 100 } : { x: 105, y: 86 });
    place(nodes.daily.querySelector(".sh-browse"), portrait ? { x: 445, y: 82 } : { x: 940, y: 60 });
    place(nodes.daily.querySelector(".sh-daily-poster"), portrait ? { x: 75, y: 190, w: 200, h: 300 } : { x: 136, y: 151, w: 300, h: 450 });
    const dailyInfo = nodes.daily.querySelector(".sh-info");
    place(dailyInfo, portrait ? { x: 310, y: 198, w: 330 } : { x: 485, y: 157, w: 635 });
    if (portrait) {
      place(dailyInfo.querySelector(".sh-reason"), { x: -235, y: 322, w: 550 });
      place(dailyInfo.querySelector(".sh-facts"), { x: -235, y: 525, w: 550 });
      place(dailyInfo.querySelector(".sh-rating"), { x: -235, y: 625, w: 550 });
      [".sh-reason", ".sh-facts", ".sh-rating"].forEach(s => dailyInfo.querySelector(s).style.position = "absolute");
    } else [".sh-reason", ".sh-facts", ".sh-rating"].forEach(s => dailyInfo.querySelector(s).style.position = "static");
    const libraryOpacity = between(t, 3.05, 3.65) * (1 - between(t, 12.2, 13));
    reveal(nodes.library, libraryOpacity);
    place(nodes.library.querySelector(".sh-library-title"), portrait ? { x: 65, y: 65 } : { x: 136, y: 70 });
    place(nodes.library.querySelector(".sh-search"), portrait ? { x: 65, y: 116, w: 590 } : { x: 410, y: 60, w: 730 });
    ["media", "region", "genre"].forEach((row, i) => {
      const node = nodes.library.querySelector(`[data-row="${row}"]`);
      place(node, portrait ? { x: 65, y: 188 + i * 59 } : { x: 136, y: 132 + i * 51 });
      reveal(node, row === "region" && phase < 1 ? 0 : 1);
    });
    if (phase !== lastPhase) {
      nodes.library.querySelectorAll(".sh-tag").forEach(n => n.classList.remove("active"));
      [["media", phase < 1 ? "全部" : "剧集"], ["region", phase < 2 ? "全部地区" : "英剧"], ["genre", phase < 3 ? "全部" : "悬疑"]].forEach(([r, tag]) => nodes.library.querySelector(`[data-row="${r}"] [data-tag="${tag}"]`).classList.add("active"));
      nodes.library.querySelector(".sh-count").textContent = phase === 0 ? `${catalogFor("movie").length} 部电影 · ${uniqueSeries(catalogFor("tv")).length} 部剧集` : `找到 ${lists[phase].length} 部剧集 · ${phase < 2 ? "按评分排序" : phase < 3 ? "英剧" : "英剧 / 悬疑"}`;
      lastPhase = phase;
    }
    place(nodes.library.querySelector(".sh-count"), portrait ? { x: 65, y: 371 } : { x: 136, y: 277 });
    cards.forEach(({ m, node }) => {
      const pose = gridPose(m, t, phase);
      const p = pose.r;
      place(node, { x: p.x, y: p.y, w: p.w });
      const image = node.querySelector("img, .sh-empty-cover"); image.style.height = `${p.h}px`;
      reveal(node, pose.opacity);
    });
    const coverPose = portrait ? { x: 173, y: 78, w: 374, h: 561 } : { x: 480, y: 24, w: 320, h: 480 };
    const detailPose = portrait ? { x: 78, y: 107, w: 210, h: 315 } : { x: 167, y: 130, w: 290, h: 435 };
    const shareLayout = portrait ? { x: 179, y: 288, s: .4 } : { x: 218, y: 65, s: .405 };
    const sharePose = { x: shareLayout.x + 270 * shareLayout.s, y: shareLayout.y + 180 * shareLayout.s, w: 360 * shareLayout.s, h: 540 * shareLayout.s };
    const posterGrid = gridPose(target, t, phase);
    let posterRect = posterGrid.r;
    if (t >= 12.2) posterRect = rectMix(posterRect, coverPose, between(t, 12.2, 13.25));
    if (t >= 16.7) posterRect = rectMix(coverPose, detailPose, between(t, 16.7, 17.6));
    if (t >= 21.7) posterRect = rectMix(detailPose, sharePose, between(t, 21.7, 22.9));
    place(nodes.poster, posterRect);
    const posterOpacity = (t >= 12.2 ? 1 : posterGrid.opacity * libraryOpacity) * (1 - between(t, 23, 23.35));
    reveal(nodes.poster, posterOpacity);
    const coverTilt = reduced() || t < 13.25 || t > 16.7 ? 0 : Math.sin(clamp((t - 13.25) / 3.45) * Math.PI * 2);
    const face = nodes.poster.querySelector(".sh-poster-face");
    face.style.transform = `rotateX(${-coverTilt * 4}deg) rotateY(${coverTilt * 7}deg)`;
    face.style.setProperty("--sh-light-x", `${45 + coverTilt * 25}%`);
    face.style.setProperty("--sh-light-y", `${35 - coverTilt * 15}%`);
    reveal(face.querySelector(".sh-glare"), between(t, 12.7, 13.5) * (1 - between(t, 16, 16.7)));
    reveal(nodes.cover, between(t, 12.4, 13.3) * (1 - between(t, 16.7, 17.3)));
    place(nodes.cover.querySelector(".sh-cover-text"), portrait ? { x: 65, y: 698, w: 590 } : { x: 270, y: 531, w: 740 });
    reveal(nodes.detail, between(t, 16.85, 17.6) * (1 - between(t, 21.7, 22.5)));
    const detailInfo = nodes.detail.querySelector(".sh-info");
    place(detailInfo, portrait ? { x: 327, y: 120, w: 320 } : { x: 510, y: 132, w: 585 });
    if (portrait) {
      [[".sh-reason", 365], [".sh-facts", 560], [".sh-rating", 715], [".sh-save", 755], [".sh-source", 830]].forEach(([s, y]) => {
        const n = detailInfo.querySelector(s); n.style.position = "absolute"; place(n, { x: -249, y, w: 555 });
      });
    } else [".sh-reason", ".sh-facts", ".sh-rating", ".sh-save", ".sh-source"].forEach(s => detailInfo.querySelector(s).style.position = "static");
    const shareOpacity = between(t, 21.85, 22.9);
    reveal(nodes.share, shareOpacity);
    const canvas = nodes.share.querySelector("canvas");
    place(canvas, { x: shareLayout.x, y: shareLayout.y });
    canvas.style.transform = `scale(${shareLayout.s})`;
    // Clip upwards to reveal the genuine card layout around the one travelling poster.
    const revealCard = between(t, 21.85, 23.3);
    canvas.style.clipPath = `inset(${(1 - revealCard) * 100}% 0 0 0)`;
    const shareText = nodes.share.querySelector(".sh-share-text");
    place(shareText, portrait ? { x: 70, y: 64, w: 580 } : { x: 705, y: 185, w: 440 });
    if (portrait) {
      shareText.querySelector("h3").style.fontSize = "60px";
      shareText.querySelector("p").innerHTML = "好故事，自有余韵。";
      shareText.querySelector("p").style.fontSize = "35px";
      place(shareText.querySelector(".sh-end-cta"), { x: 164, y: 845 });
      shareText.querySelector(".sh-end-cta").style.position = "absolute";
      shareText.querySelector(".sh-end-cta").style.marginTop = "0";
    } else {
      shareText.querySelector("h3").style.fontSize = "72px";
      shareText.querySelector("p").innerHTML = "好故事，<br>自有余韵。";
      shareText.querySelector("p").style.fontSize = "35px";
      shareText.querySelector(".sh-end-cta").style.position = "static";
      shareText.querySelector(".sh-end-cta").style.marginTop = "31px";
    }
    reveal(shareText, between(t, 23, 24.15));
    reveal(shareText.querySelector(".sh-end-cta"), between(t, 27.2, 28));
    shareText.querySelector(".sh-end-cta").style.pointerEvents = t >= 28 ? "auto" : "none";
    renderCursor(t, portrait, detailInfo);
    progress.value = String(time);
    progress.setAttribute("aria-valuetext", `${time.toFixed(1)} 秒，共 30 秒`);
    $("showreel-time").textContent = `00:${String(Math.floor(time)).padStart(2, "0")} / 00:30`;
    let chapter = 0; chapters.forEach((c, i) => { if (t >= c.time) chapter = i; });
    if (chapter !== lastChapter) {
      $("showreel-step").textContent = chapters[chapter].label;
      $("showreel-description").textContent = chapters[chapter].text;
      stage.setAttribute("aria-label", `${chapters[chapter].label}。${chapters[chapter].text}`);
      lastChapter = chapter;
    }
  }
  function renderCursor(t, phone, detailInfo) {
    const positions = phone ? [
      [0, 630, 915], [2.3, 585, 105], [3.1, 585, 105], [4.3, 410, 207], [5.8, 416, 266], [7.7, 415, 325], [10.8, 160, 505], [12.3, 190, 540], [14.5, 500, 340], [16.5, 434, 848], [18.1, 560, 903], [21.6, 240, 903], [22.5, 375, 899], [24, 620, 934]
    ] : [
      [0, 1130, 615], [2.3, 1040, 84], [3.1, 1040, 84], [4.3, 408, 153], [5.8, 452, 204], [7.7, 408, 254], [10.8, 210, 389], [12.3, 220, 412], [14.5, 740, 280], [16.5, 698, 689], [18.1, 1070, 590], [21.6, 584, 568], [22.5, 675, 587], [24, 1130, 615]
    ];
    const selected = gridRect(0, 3);
    [10.8, 12.3].forEach(mark => {
      const step = positions.find(p => p[0] === mark);
      step[1] = selected.x + selected.w * .52;
      step[2] = selected.y + selected.h * .4;
    });
    const save = detailInfo.querySelector(".sh-save");
    const saveStep = positions.find(p => p[0] === 21.6);
    saveStep[1] = detailInfo.offsetLeft + save.offsetLeft + Math.min(130, save.offsetWidth / 2);
    saveStep[2] = detailInfo.offsetTop + save.offsetTop + save.offsetHeight / 2;
    let i = 0;
    while (i < positions.length - 2 && t > positions[i + 1][0]) i++;
    const a = positions[i], b = positions[i + 1];
    const p = reduced() ? 1 : ease(clamp((t - a[0]) / (b[0] - a[0])));
    const x = mix(a[1], b[1], p), y = mix(a[2], b[2], p);
    nodes.cursor.style.transform = `translate(${x}px, ${y}px)`;
    reveal(nodes.cursor, reduced() ? 0 : (t > 1.7 && t < 23.6 ? 1 : 0));
    const taps = [3.1, 4.3, 5.8, 7.7, 12.2, 16.5, 21.6];
    const elapsed = Math.min(...taps.filter(v => v <= t).map(v => t - v));
    const pulse = clamp(elapsed / .42);
    const click = nodes.cursor.querySelector(".sh-click");
    click.style.transform = `scale(${.6 + pulse * 1.4})`;
    reveal(click, elapsed < .42 ? 1 - pulse : 0);
  }
  function setPlaying(value) {
    playing = value;
    playButton.textContent = playing ? "暂停" : time >= DURATION ? "播放" : "播放";
    playButton.setAttribute("aria-label", playing ? "暂停演示" : "播放演示");
    cancelAnimationFrame(frame); frame = 0;
    if (playing) { lastTick = performance.now(); frame = requestAnimationFrame(tick); }
  }
  function tick(now) {
    if (!playing || !dialog.open) return;
    time = Math.min(DURATION, time + Math.min(.1, (now - lastTick) / 1000));
    lastTick = now; render();
    if (time >= DURATION) {
      setPlaying(false); $("showreel-status").textContent = "演示结束。可以开始选片，或重播演示。";
    } else frame = requestAnimationFrame(tick);
  }
  async function open() {
    opener = document.activeElement;
    if (!initialized) build();
    time = 0; lastPhase = -1; lastChapter = -1;
    dialog.showModal(); document.body.classList.add("no-scroll");
    layout(); render();
    playButton.disabled = true;
    $("showreel-status").textContent = "正在准备演示海报。";
    const version = ++loadVersion;
    const imageLoads = [...stage.querySelectorAll("img")].map(img => img.decode().catch(() => {}));
    const card = shareReady ? Promise.resolve() : createShareCardCanvas(target, sampleDate).then(source => {
      nodes.share.querySelector("canvas").getContext("2d").drawImage(source, 0, 0);
      shareReady = true;
    }).catch(() => { $("showreel-status").textContent = "分享卡预览加载失败，可以重播重试。"; });
    await Promise.allSettled([...imageLoads, card]);
    if (version !== loadVersion || !dialog.open) return;
    playButton.disabled = false;
    $("showreel-status").textContent = reduced() ? "已启用减少动态模式，点击播放观看步骤。" : "演示已开始。";
    render(); setPlaying(!reduced());
  }
  function close() { dialog.close(); }
  $("showreel-open").addEventListener("click", open);
  $("showreel-close").addEventListener("click", close);
  viewport.addEventListener("click", e => { if (e.target.closest(".sh-end-cta") && time >= 28) $("showreel-start").click(); });
  $("showreel-start").addEventListener("click", () => {
    close(); $("library-btn").click();
  });
  playButton.addEventListener("click", () => {
    if (time >= DURATION) time = 0;
    setPlaying(!playing); render();
  });
  $("showreel-replay").addEventListener("click", () => { time = 0; lastPhase = -1; lastChapter = -1; render(); setPlaying(!reduced()); });
  progress.addEventListener("keydown", e => {
    if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown"].includes(e.key)) setPlaying(false);
  });
  progress.addEventListener("pointerdown", () => { resumeOnSeek = playing; setPlaying(false); });
  progress.addEventListener("input", () => { time = Number(progress.value); render(); });
  progress.addEventListener("change", () => { if (resumeOnSeek && time < DURATION) setPlaying(true); resumeOnSeek = false; });
  dialog.addEventListener("close", () => {
    loadVersion++; setPlaying(false);
    if ($("library-overlay").hidden && !$("poster-viewer").open) document.body.classList.remove("no-scroll");
    if (opener?.isConnected) opener.focus({ preventScroll: true });
  });
  dialog.addEventListener("click", e => { if (e.target === dialog) {
    const r = dialog.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) close();
  } });
  dialog.addEventListener("keydown", e => {
    if (e.code === "Space" && e.target === dialog) { e.preventDefault(); playButton.click(); }
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden && playing) setPlaying(false); });
  motionToggle.addEventListener("change", () => { setPlaying(false); render(); });
  reduceMotion.addEventListener("change", () => { motionToggle.checked = reduceMotion.matches; if (dialog.open) { setPlaying(false); render(); } });
  new ResizeObserver(layout).observe(viewport);
})();
