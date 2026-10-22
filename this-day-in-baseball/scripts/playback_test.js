// Real-browser playback test. Paste into the browser console (or run through the Chrome tool) on a page served from
// http://localhost:8765 (any page of this site). It plays nothing visibly; it only asks the player whether it can start.
//
//   await playbackTest({ youtube: ["VIDEOID", ...], files: { "ia:some-item": "https://archive.org/download/..mp4" } })
//
// YouTube: loads YouTube's iframe player script and counts a video as playable only if it reports "ready" and no error
// 101, 150 or 153 follows within 6 seconds (the embeddable flag in YouTube's data is NOT trustworthy: 73 of 74 saved videos
// said yes and failed with error 150). Files: an HTML5 <video> must load its metadata and report a picture (width above 0),
// which also catches formats a browser cannot decode (Ogg Theora from Commons failed this way).
// Results are returned as { id: { ok, why, duration } }; copy them into .cache/open_video/playback.json or data/video_playable.json.
async function playbackTest({ youtube = [], files = {} }) {
  const out = {};
  const holder = document.createElement("div");
  holder.style.cssText = "position:fixed;left:-9999px;top:0";
  document.body.append(holder);
  if (youtube.length) {
    await new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = "https://www.youtube.com/iframe_api";
      s.onerror = rej;
      window.onYouTubeIframeAPIReady = res;
      document.head.append(s);
      setTimeout(() => rej(new Error("YouTube player script did not load")), 15000);
    });
    const ytTest = (id) => new Promise((done) => {
      const d = document.createElement("div");
      holder.append(d);
      let ready = false, err = null, fin = false;
      const finish = () => {
        if (fin) return;
        fin = true;
        let dur = null;
        try { dur = Math.round(p.getDuration()); } catch (e) { /* not ready */ }
        try { p.destroy(); } catch (e) { /* already gone */ }
        done({ ok: ready && !err, why: err ? "error " + err : ready ? "ready" : "timeout", duration: dur });
      };
      const p = new YT.Player(d, { videoId: id, host: "https://www.youtube-nocookie.com", width: 320, height: 180,
        events: { onReady: () => { ready = true; setTimeout(finish, 6000); }, onError: (e) => { err = e.data; finish(); } } });
      setTimeout(finish, 16000);
    });
    for (let i = 0; i < youtube.length; i += 4) {   // a few at a time; many at once gives false timeouts
      const chunk = youtube.slice(i, i + 4);
      const res = await Promise.all(chunk.map(ytTest));
      chunk.forEach((id, k) => { out["youtube:" + id] = res[k]; });
    }
  }
  const fileTest = (url) => new Promise((done) => {
    const v = document.createElement("video");
    v.preload = "metadata"; v.muted = true;
    v.style.cssText = "position:fixed;left:-9999px;width:200px";
    let fin = false;
    const finish = (ok, why) => {
      if (fin) return;
      fin = true;
      const r = { ok, why, duration: isFinite(v.duration) ? Math.round(v.duration) : null, width: v.videoWidth };
      v.removeAttribute("src"); v.load(); v.remove();
      done(r);
    };
    v.onloadedmetadata = () => setTimeout(() => finish(v.readyState >= 1 && v.duration > 0 && v.videoWidth > 0, "metadata"), 1500);
    v.onerror = () => finish(false, "error " + (v.error && v.error.code));
    setTimeout(() => finish(false, "timeout"), 25000);
    v.src = url;
    document.body.append(v);
  });
  for (const [name, url] of Object.entries(files)) out[name] = await fileTest(url);
  holder.remove();
  return out;
}
