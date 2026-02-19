#!/usr/bin/env python3
"""
Combine chunk outputs from a dataset-specific prediction folder.

Default behavior:
- Reads all chunk folders matching test_chuck_<n>
- Sorts chunks by numeric <n>
- Validates chunk summary and line counts
- Writes combined predictions and debug outputs in the same dataset folder
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_BASE = PROJECT_ROOT / "evaluation" / "predict_results"

CHUNK_DIR_PATTERN = re.compile(r"^test_chuck_(\d+)$")


def _prompt_text(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default


def _prompt_dataset_kind() -> str:
    print("What kind of dataset you use:")
    print("1) Train set")
    print("2) Dev set")
    print("3) Test set")
    while True:
        choice = input("Select (1/2/3): ").strip()
        if choice == "1":
            return "train"
        if choice == "2":
            return "dev"
        if choice == "3":
            return "test"
        print("Please select 1, 2, or 3.")


def _read_lines(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f]


def _load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _find_chunk_dirs(chunks_root: Path) -> List[Tuple[int, Path]]:
    if not chunks_root.exists():
        return []

    chunk_dirs: List[Tuple[int, Path]] = []
    for child in chunks_root.iterdir():
        if not child.is_dir():
            continue
        match = CHUNK_DIR_PATTERN.match(child.name)
        if not match:
            continue
        chunk_no = int(match.group(1))
        chunk_dirs.append((chunk_no, child))

    return sorted(chunk_dirs, key=lambda item: item[0])


def main() -> int:
    parser = argparse.ArgumentParser(description="Combine Spider chunk predictions")
    parser.add_argument("--output-base", type=Path, default=DEFAULT_OUTPUT_BASE, help="Base folder for predict_results")
    parser.add_argument("--dataset-kind", type=str, choices=["train", "dev", "test"], help="Dataset type")
    parser.add_argument("--chunks-root", type=Path, help="Folder that contains test_chuck_*")
    parser.add_argument("--output", type=Path, help="Combined predictions output file")
    parser.add_argument(
        "--debug-output",
        type=Path,
        help="Combined debug JSONL output file",
    )
    parser.add_argument("--report", type=Path, help="Merge report JSON file")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if a chunk is incomplete, missing files, or has integrity issues",
    )
    args = parser.parse_args()

    dataset_kind = args.dataset_kind or _prompt_dataset_kind()
    output_root = args.output_base / f"{dataset_kind.capitalize()}_predict_results"
    chunks_root = args.chunks_root or output_root
    output_path = args.output or (output_root / "predictions_combined.txt")
    debug_output_path = args.debug_output or (output_root / "predictions_debug_combined.jsonl")
    report_path = args.report or (output_root / "combine_report.json")

    chunk_dirs = _find_chunk_dirs(chunks_root)
    if not chunk_dirs:
        print(f"ERROR: No chunk folders found in: {chunks_root}")
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    debug_output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    merged_prediction_lines: List[str] = []
    merged_debug_lines: List[str] = []

    report: Dict[str, object] = {
        "chunks_root": str(chunks_root),
        "dataset_kind": dataset_kind,
        "chunk_count": len(chunk_dirs),
        "chunks": [],
        "total_prediction_lines": 0,
        "total_debug_lines": 0,
        "strict_mode": bool(args.strict),
        "warnings": [],
    }

    for chunk_no, chunk_dir in chunk_dirs:
        predictions_path = chunk_dir / "predictions.txt"
        debug_path = chunk_dir / "predictions_debug.jsonl"
        summary_path = chunk_dir / "summary.json"

        chunk_report = {
            "chunk_no": chunk_no,
            "chunk_dir": str(chunk_dir),
            "has_predictions": predictions_path.exists(),
            "has_debug": debug_path.exists(),
            "has_summary": summary_path.exists(),
            "integrity_ok": None,
            "expected_questions": None,
            "successful_predictions": None,
            "prediction_lines": 0,
            "debug_lines": 0,
            "used": False,
            "warning": None,
        }

        missing = []
        if not predictions_path.exists():
            missing.append("predictions.txt")
        if not debug_path.exists():
            missing.append("predictions_debug.jsonl")
        if missing:
            warning = f"Chunk {chunk_no}: missing file(s): {', '.join(missing)}"
            chunk_report["warning"] = warning
            report["warnings"].append(warning)
            report["chunks"].append(chunk_report)
            if args.strict:
                print(f"ERROR: {warning}")
                return 2
            continue

        prediction_lines = _read_lines(predictions_path)
        debug_lines = _read_lines(debug_path)

        chunk_report["prediction_lines"] = len(prediction_lines)
        chunk_report["debug_lines"] = len(debug_lines)

        if summary_path.exists():
            summary = _load_json(summary_path)
            expected_questions = int(summary.get("expected_questions", -1))
            successful_predictions = int(summary.get("successful_predictions", -1))
            integrity_ok = bool(summary.get("integrity_ok", False))

            chunk_report["integrity_ok"] = integrity_ok
            chunk_report["expected_questions"] = expected_questions
            chunk_report["successful_predictions"] = successful_predictions

            mismatch = successful_predictions >= 0 and successful_predictions != len(prediction_lines)
            if mismatch:
                warning = (
                    f"Chunk {chunk_no}: summary successful_predictions={successful_predictions} "
                    f"but predictions.txt has {len(prediction_lines)} lines"
                )
                chunk_report["warning"] = warning
                report["warnings"].append(warning)
                if args.strict:
                    print(f"ERROR: {warning}")
                    return 2

            if not integrity_ok:
                warning = f"Chunk {chunk_no}: summary integrity_ok=false"
                if chunk_report["warning"] is None:
                    chunk_report["warning"] = warning
                report["warnings"].append(warning)
                if args.strict:
                    print(f"ERROR: {warning}")
                    return 2
        else:
            warning = f"Chunk {chunk_no}: summary.json is missing"
            chunk_report["warning"] = warning
            report["warnings"].append(warning)
            if args.strict:
                print(f"ERROR: {warning}")
                return 2

        merged_prediction_lines.extend(prediction_lines)
        merged_debug_lines.extend(debug_lines)
        chunk_report["used"] = True
        report["chunks"].append(chunk_report)

    with output_path.open("w", encoding="utf-8") as f:
        for line in merged_prediction_lines:
            f.write(line + "\n")

    with debug_output_path.open("w", encoding="utf-8") as f:
        for line in merged_debug_lines:
            f.write(line + "\n")

    report["total_prediction_lines"] = len(merged_prediction_lines)
    report["total_debug_lines"] = len(merged_debug_lines)
    report["output"] = str(output_path)
    report["debug_output"] = str(debug_output_path)

    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("Combine complete.")
    print(f"Chunks root           : {chunks_root}")
    print(f"Combined predictions  : {output_path}")
    print(f"Combined debug        : {debug_output_path}")
    print(f"Report                : {report_path}")
    print(f"Total prediction lines: {len(merged_prediction_lines)}")
    print(f"Warnings              : {len(report['warnings'])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
