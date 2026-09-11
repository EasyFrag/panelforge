(() => {
  "use strict";
  window.PanelForgeAnalysisSpeech = {
    create({ el, context, onChange, setBusy, message }) {
      let transcript = null, spec = null, controller = null, timer = null;
      const enabled = () => context().sourceKind === "video" && el("speech-enabled").checked;
      function matches() {
        const clip = context().clip;
        return transcript && clip && transcript.clip_start_seconds === clip.start && transcript.clip_end_seconds === clip.end && transcript.language === el("speech-language").value;
      }
      function validation() {
        if (!enabled()) return "";
        if (!matches()) return "Transcrivez l’extrait actuel, ou désactivez les paroles pour analyser les images seules.";
        return "";
      }
      function metadata() {
        return enabled() && transcript ? { ...transcript, text: el("speech-text").value, keep_dialogue: el("speech-keep").checked } : null;
      }
      function update(busy) {
        const { sourceKind, video, clip } = context();
        el("speech-panel").hidden = sourceKind !== "video";
        el("speech-options").hidden = !enabled();
        el("speech-availability").textContent = spec?.message || "Transcription locale facultative.";
        el("speech-enabled").disabled = busy || (!spec?.available && !transcript);
        const validClip = clip && clip.end - clip.start >= .1 && clip.end - clip.start <= 60;
        el("speech-transcribe").disabled = busy || !enabled() || !video || !validClip || !spec?.available;
        el("speech-transcribe").textContent = transcript ? "Retranscrire l’extrait" : "Transcrire l’extrait";
        el("speech-result").hidden = !transcript;
        el("speech-stale").hidden = !enabled() || !transcript || Boolean(matches());
        el("speech-restore").disabled = busy || !transcript || el("speech-text").value === transcript.original_text;
        el("speech-file-note").hidden = Boolean(video);
        if (controller) el("cancel").textContent = "Annuler la transcription";
        else el("cancel").textContent = "Annuler l’analyse";
      }
      function reset() {
        transcript = null;
        el("speech-enabled").checked = false;
        el("speech-keep").checked = false;
        el("speech-language").value = "en";
        el("speech-device").value = "cpu";
        el("speech-text").value = "";
        el("speech-status").textContent = "";
      }
      function restore(value) {
        reset();
        if (!value) return;
        transcript = structuredClone(value);
        el("speech-enabled").checked = true;
        el("speech-language").value = value.language;
        el("speech-device").value = value.device;
        el("speech-keep").checked = value.keep_dialogue;
        el("speech-text").value = value.text;
        el("speech-status").textContent = "Transcription enregistrée restaurée. Les corrections restent possibles.";
      }
      async function transcribe() {
        if (controller || el("speech-transcribe").disabled) return;
        const { video, clip } = context();
        if (!video || !clip) return;
        if (video.size > (spec?.video_bytes || 1024 ** 3)) return message("La vidéo dépasse 1 Gio. Importez un extrait plus court pour transcrire son audio.", true);
        const request = { clip_start_seconds: clip.start, clip_end_seconds: clip.end,
          language: el("speech-language").value, device: el("speech-device").value };
        controller = new AbortController();
        const signal = controller.signal, started = Date.now();
        let phase = "Envoi temporaire de la vidéo au Lab…";
        const status = () => { el("speech-status").textContent = `${phase} · ${Math.floor((Date.now()-started)/1000)} s`; };
        timer = setInterval(status, 1000); status();
        setBusy(true, phase);
        try {
          const form = new FormData(); form.append("metadata", JSON.stringify(request)); form.append("file", video, video.name);
          let result = null;
          await window.PanelForgeLabCore.streamRequest("/api/media-analysis/transcriptions/stream", { method: "POST", body: form, signal }, event => {
            if (event.kind === "status") { phase = event.text || "Transcription en cours…"; status(); message(phase); }
            if (event.kind === "completed") result = event.transcript;
          });
          if (!result) throw new Error("Transcription interrompue. Vous pouvez réessayer ; votre brouillon est conservé.");
          transcript = result;
          el("speech-text").value = result.text;
          el("speech-status").textContent = result.text ? "Paroles transcrites. Corrigez le texte avant d’analyser." : "Aucune parole détectée dans l’extrait. Vous pouvez poursuivre l’analyse.";
          message("Transcription terminée. Relisez les paroles, puis lancez l’analyse des médias.");
        } catch (error) {
          const text = error.name === "AbortError" ? "Transcription annulée. Le brouillon est conservé." : error.message;
          el("speech-status").textContent = text; message(text, true);
        } finally {
          clearInterval(timer); timer = null; controller.abort(); controller = null;
          setBusy(false); onChange();
        }
      }
      for (const id of ["speech-enabled", "speech-language", "speech-keep"]) el(id).addEventListener("change", onChange);
      el("speech-text").addEventListener("input", onChange);
      el("speech-transcribe").addEventListener("click", transcribe);
      el("speech-restore").addEventListener("click", () => { if (transcript) { el("speech-text").value = transcript.original_text; onChange(); } });
      return { metadata, validation, update, reset, restore,
        setSpec(value) { spec = value; },
        signature() { return enabled() ? { enabled: true, language: el("speech-language").value } : null; },
        cancel() { if (!controller) return false; controller.abort(); return true; }
      };
    }
  };
})();
