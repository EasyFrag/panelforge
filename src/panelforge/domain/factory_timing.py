"""Comparable, versioned duration observations; no infrastructure dependencies."""
from collections import Counter
from datetime import datetime
from statistics import median
from math import isfinite
from .video_factory import fingerprint

VERSION = 1
LANES = ("local_gpu", "remote_gpu")


def epoch(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.timestamp() if parsed.tzinfo else None
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


def duration_profile(item, stage, lane, recipe=None):
    config = item.get("launch_snapshot") or item["config"]
    render = config["render"]
    settings = render["settings"]
    common = dict(version=VERSION, stage=stage, lane=lane)
    if stage in {"video", "dlss"}:
        common.update(settings={k: v for k, v in settings.items() if k != "seed"},
                      input_mode=config["mode"], roles=sorted(ref["role"] for ref in config["references"]),
                      initial_megapixels=render.get("initial_megapixels"),
                      force_upscale=render.get("force_upscale", False))
        if stage == "video":
            common.update(recipe=recipe or render["recipe"], bunny=render.get("bunny"),
                          checkpoint=render.get("checkpoint"), loras=render.get("video_loras"),
                          music=render.get("music_enabled"), spectrum=render.get("spectrum_enabled"),
                          batch=True)
        else:
            # Version this contract if the factory's fixed DLSS settings change.
            common.update(dlss_contract="factory-natural-interpolate-h264-v1", options=config["dlss"])
    elif stage == "export":
        common.update(dlss=config["dlss"]["enabled"], social=config["social"]["enabled"])
    else:
        common.update(model=config["social"]["model_id"] if stage == "social" else
                      config["plan_model_id" if stage == "plan" else "writer_model_id"],
                      profile=config["profile"], cookbook=config["cookbook"],
                      duration=settings["duration_seconds"], shots=config.get("shot_count"),
                      references=len(config["references"]),
                      preset=config.get("preset_origin") or config.get("preset"))
        if stage == "social":
            common.update(language=config["social"]["language"], variants=config["social"]["variant_count"])
    return common


def observation(item, stage, profile, *, legacy=False):
    step = item.get("delivery", {}) if stage == "export" else item["steps"][stage]
    start, end = epoch(step.get("started_at")), epoch(step.get("finished_at"))
    if step.get("status") != "succeeded" or start is None or end is None or end <= start:
        return None
    timing = step.get("timing") or {}
    if timing.get("quality") in {"recovered", "reused"}:
        return None
    if legacy:
        # Old journals lack attempt start times: reject ambiguous resumed video
        # polling and implausibly short GPU observations rather than learn them.
        if stage in {"video", "dlss"} and end - start < 10:
            return None
        if stage == "video" and str(step.get("message") or "").startswith("Rendu vidéo"):
            return None
        if stage == "plan" and item.get("runtime", {}).get("saved_plan"):
            return None
    return dict(id=timing.get("id") or fingerprint([item["id"], stage, step["started_at"], step["finished_at"]]),
                profile=profile, seconds=end - start, finished_at=step["finished_at"],
                quality="legacy" if legacy else "complete", item_id=item["id"],
                child_id=item.get("runtime", {}).get("attempt_id" if stage == "video" else "dlss_job_id")
                if stage in {"video", "dlss"} else None)


def _quantile(values, p):
    position = (len(values) - 1) * p
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


class DurationModel:
    def __init__(self, records=()):
        self.groups = {}
        for record in sorted(records, key=lambda r: r.get("finished_at", "")):
            seconds = record.get("seconds")
            if isinstance(seconds, (int, float)) and isfinite(seconds) and seconds > 0:
                key = fingerprint(record["profile"])
                self.groups.setdefault(key, []).append(record)
        for key in self.groups:
            self.groups[key] = self.groups[key][-40:]

    def _nearby_gpu_records(self, profile):
        stage = profile["stage"]
        if stage not in {"video", "dlss"} or stage == "video" and profile.get("input_mode") != "ref2v":
            return []
        # Keep every compute setting and the versioned workflow/contract.
        # DLSS processes the rendered video, independent of source references.
        core = {k: v for k, v in profile.items() if k != "roles"}
        roles = Counter(profile.get("roles", ()))
        records = []
        for group in self.groups.values():
            candidate = group[0]["profile"]
            if {k: v for k, v in candidate.items() if k != "roles"} != core:
                continue
            if stage == "video":
                other = Counter(candidate.get("roles", ()))
                # Only one additional/missing reference, with the same role kinds:
                # do not extrapolate across unrelated inputs or distant sizes.
                if set(roles) != set(other) or sum(abs(roles[k] - other[k]) for k in roles) != 1:
                    continue
            records.extend(group)
        return sorted(records, key=lambda r: r.get("finished_at", ""))[-40:]

    def estimate(self, profile, elapsed=0):
        records = self.groups.get(fingerprint(profile), [])
        source = "comparable"
        if not records and profile["stage"] in {"plan", "prompt", "social"}:
            # Keep model, lane, stage, recipe/profile and language semantics;
            # only relax content-size parameters, with a visibly wider interval.
            ignored = {"preset", "shots", "references", "duration"}
            core = {k: v for k, v in profile.items() if k not in ignored}
            records = [r for group in self.groups.values() for r in group
                       if {k: v for k, v in r["profile"].items() if k not in ignored} == core]
            records = sorted(records, key=lambda r: r["finished_at"])[-40:]
            source = "similar"
        if not records and profile["stage"] in {"video", "dlss"}:
            records = self._nearby_gpu_records(profile)
            source = "similar"
        if not records:
            if profile["stage"] == "export":
                overdue = elapsed >= 15
                return dict(seconds=15 if overdue else max(1, 15 - elapsed), low=0,
                            high=max(30, 60 - elapsed), samples=0, confidence="low",
                            source="allowance", indicative=overdue,
                            reason="Export plus long que prévu · marge indicative" if overdue else
                                   "Provision export, en attente de mesures")
            return dict(seconds=None, low=None, high=None, samples=0, confidence="unknown",
                        source="missing", reason="Historique comparable insuffisant")
        values = sorted(r["seconds"] for r in records)
        centre = median(values)
        # Trim only gross outliers; keep normal variability and warm/cold runs.
        values = [v for v in values if centre / 4 <= v <= centre * 4]
        remaining = [v - elapsed for v in values if v > elapsed]
        if not remaining:
            # Beyond the observed tail, retain a provisional residual budget rather
            # than erasing this stage and every delivery depending on it.
            margin = max(5, median(values) * .2)
            return dict(seconds=margin, low=0, high=max(margin * 2, elapsed - centre + margin),
                        samples=len(values), confidence="low", source=source, indicative=True,
                        reason="Durée habituelle dépassée · marge indicative, fin incertaine")
        confidence = "medium" if len(values) >= 5 and len(remaining) >= 3 and source == "comparable" else "low"
        margin = .15 if confidence == "medium" else .4
        result = dict(seconds=median(remaining), low=max(0, _quantile(remaining, .1) * (1 - margin)),
                      high=_quantile(remaining, .9) * (1 + margin), samples=len(values),
                      confidence=confidence, source=source,
                      reason="Médiane des durées comparables" if source == "comparable" else "Configuration voisine")
        if source == "similar" and profile["stage"] in {"video", "dlss"}:
            result.update(indicative=True, reason="Références voisines · durée indicative"
                          if profile["stage"] == "video" else "Format vidéo comparable · DLSS indicatif")
        return result
