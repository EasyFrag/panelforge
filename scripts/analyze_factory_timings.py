"""Offline chronological audit of duration estimates; never submits a job.

Usage: python scripts/analyze_factory_timings.py --workspace D:/Code/panelforge/workspace
Run after the updated Lab has imported the timing journal.
"""
import argparse
import json
from pathlib import Path
from statistics import median
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from panelforge.domain.factory_timing import DurationModel


def analyze(records, minimum=5):
    previous, stages = [], {}
    for record in sorted(records, key=lambda r: r["finished_at"]):
        estimate = DurationModel(previous).estimate(record["profile"])
        actual = record["seconds"]
        if (actual > 0 and estimate["seconds"] is not None and estimate["samples"] >= minimum
                and estimate["source"] == "comparable"):
            stage = stages.setdefault(record["profile"]["stage"], [])
            stage.append(dict(error_seconds=abs(estimate["seconds"] - actual),
                              error_percent=abs(estimate["seconds"] - actual) / actual * 100,
                              covered=estimate["low"] <= actual <= estimate["high"],
                              legacy=record.get("quality") == "legacy"))
        previous.append(record)
    result = {}
    for name, values in stages.items():
        errors = sorted(v["error_seconds"] for v in values)
        result[name] = dict(predictions=len(values), legacy_observations=sum(v["legacy"] for v in values),
                           median_absolute_error_seconds=round(median(errors), 2),
                           p90_absolute_error_seconds=round(errors[min(len(errors) - 1, int(len(errors) * .9))], 2),
                           median_absolute_percentage_error=round(median(v["error_percent"] for v in values), 2),
                           interval_coverage_percent=round(sum(v["covered"] for v in values) / len(values) * 100, 1))
    return dict(method="Chronological holdout: each prediction uses only earlier completed observations.",
                scope="Individual stages only; this does not validate whole-queue finish times.",
                observations=len(records), minimum_prior_samples=minimum, stages=result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    path = args.workspace / "video_factory" / "timings.json"
    if not path.is_file():
        parser.error("The updated Lab must first import its timing journal.")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1:
        parser.error("Unsupported timing journal version.")
    print(json.dumps(analyze(value["records"]), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
