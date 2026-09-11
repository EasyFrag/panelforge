(() => {
  "use strict";
  function timelineError(frames, duration, videoLength = null) {
    if (!frames.length || frames.length > 16) return "Choisissez entre 1 et 16 images.";
    if (!Number.isFinite(duration) || duration < 5 || duration > 15) return "La durée cible H3/REF2V doit être comprise entre 5 et 15 secondes.";
    let previous = -1;
    for (const frame of frames) {
      const time = frame.time;
      if (time == null) {
        if (videoLength != null) return "Une capture vidéo doit avoir un temps.";
        continue;
      }
      if (!Number.isFinite(time) || time < 0 || time <= previous) return "Les temps doivent augmenter dans l’ordre des images. Corrigez ou effacez un repère.";
      if (time > (videoLength ?? duration) + .001) return videoLength == null ? "La durée cible doit inclure le dernier repère." : "Une capture est hors de l’extrait sélectionné.";
      previous = time;
    }
    return "";
  }
  function sampleTimes(start, end, count, sourceDuration) {
    if (![start, end, sourceDuration].every(Number.isFinite) || start < 0 || end > sourceDuration || end - start < .1 || end - start > 60 || !Number.isInteger(count) || count < 2 || count > 16) throw new Error("Choisissez un extrait de 0,1 à 60 secondes et 2 à 16 captures.");
    const last = Math.min(end, Math.max(start, sourceDuration - .001));
    return Array.from({ length: count }, (_, i) => start + (last - start) * i / (count - 1));
  }
  function wait(target, event, signal) {
    return new Promise((resolve, reject) => {
      const cleanup = () => { clearTimeout(timer); target.removeEventListener(event, done); target.removeEventListener("error", fail); signal?.removeEventListener("abort", abort); };
      const done = () => { cleanup(); resolve(); };
      const fail = () => { cleanup(); reject(new Error("Ce média ne peut pas être décodé par le navigateur.")); };
      const abort = () => { cleanup(); reject(new DOMException("Annulé", "AbortError")); };
      const timer = setTimeout(fail, 30000);
      target.addEventListener(event, done, { once: true }); target.addEventListener("error", fail, { once: true });
      signal?.addEventListener("abort", abort, { once: true });
      if (signal?.aborted) abort();
    });
  }
  const blob = canvas => new Promise((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error("Capture impossible.")), "image/jpeg", .95));
  async function capture(file, times, onProgress, signal) {
    const video = document.createElement("video"), url = URL.createObjectURL(file);
    video.preload = "auto"; video.muted = true; video.playsInline = true;
    try {
      const ready = wait(video, "loadedmetadata", signal); video.src = url; video.load(); await ready;
      if (!video.videoWidth || !video.videoHeight) throw new Error("Dimensions vidéo indisponibles.");
      const canvas = document.createElement("canvas"); canvas.width = video.videoWidth; canvas.height = video.videoHeight;
      const context = canvas.getContext("2d", { alpha: false });
      if (!context) throw new Error("Extraction Canvas indisponible.");
      const result = [];
      for (const [i, time] of times.entries()) {
        if (signal?.aborted) throw new DOMException("Annulé", "AbortError");
        const target = Math.min(time, Math.max(0, video.duration - .001));
        if (Math.abs(video.currentTime - target) > .0001) {
          const seeking = wait(video, "seeked", signal); video.currentTime = target; await seeking;
        }
        if (video.readyState < 2) await wait(video, "loadeddata", signal);
        context.drawImage(video, 0, 0); result.push(await blob(canvas)); onProgress?.(i + 1, times.length);
      }
      return result;
    } finally { video.removeAttribute("src"); video.load(); URL.revokeObjectURL(url); }
  }
  window.PanelForgeAnalysisMedia = Object.freeze({ timelineError, sampleTimes, wait, capture });
})();
