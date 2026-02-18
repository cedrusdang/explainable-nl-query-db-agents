#!/usr/bin/env python3
"""
Generate Spider predictions in chunk folders with detailed timing logs.

Main behavior:
- Read run settings from evaluation/prediction_parameters.json
- Process 10 questions per chunk by default
- Save each chunk to evaluation/test_chunks/test_chuck_<n>
- Retry failures; stop the run if a question still fails after retries
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PARAMS_PATH = PROJECT_ROOT / "evaluation" / "prediction_parameters.json"


def _load_examples(input_path: Path) -> List[Dict[str, Any]]:
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected list JSON in {input_path}, got {type(data).__name__}")
    return data


def _load_params(params_path: Path) -> Dict[str, Any]:
    with params_path.open("r", encoding="utf-8") as f:
        params = json.load(f)
    if not isinstance(params, dict):
        raise ValueError(f"Expected object JSON in {params_path}, got {type(params).__name__}")
    return params


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _log(log_file: Path, message: str) -> None:
    line = f"[{_timestamp()}] {message}"
    print(line)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _duration_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _normalize_sql(sql: str) -> str:
    return " ".join(sql.replace("\n", " ").split())


def _pick_question(record: Dict[str, Any]) -> str:
    question = record.get("question") or record.get("Question")
    if not question:
        raise ValueError("Missing question field")
    return str(question)


def _pick_gold_db(record: Dict[str, Any]) -> str | None:
    db_id = record.get("db_id") or record.get("database") or record.get("db_name")
    return str(db_id) if db_id else None


def _run_one_question(
    row: Dict[str, Any],
    index: int,
    params: Dict[str, Any],
    agent_a_mod: Any,
    agent_b_mod: Any,
    agent_c_mod: Any,
    log_file: Path,
) -> Dict[str, Any]:
    question_start = time.perf_counter()
    question = _pick_question(row)
    gold_db = _pick_gold_db(row)
    use_gold_db = bool(params.get("use_gold_db", False))
    top_k = int(params.get("top_k", 5))

    predicted_db = None
    tables: List[str] = []
    sql = ""
    step_times: Dict[str, int] = {}

    _log(log_file, f"Q{index} START")

    if use_gold_db:
        if not gold_db:
            raise ValueError("use_gold_db=true but current row has no db_id")
        predicted_db = gold_db
        step_times["agent_a_ms"] = 0
        _log(log_file, f"Q{index} AgentA skipped (use_gold_db=true), db={predicted_db}")
    else:
        step_start = time.perf_counter()
        predicted_db = agent_a_mod.apply_database_selector(
            question,
            mode="light",
            top_k=top_k,
        )
        step_times["agent_a_ms"] = _duration_ms(step_start)
        if not predicted_db:
            raise ValueError("Agent A returned empty db_name")
        _log(log_file, f"Q{index} AgentA done in {step_times['agent_a_ms']}ms, db={predicted_db}")

    step_start = time.perf_counter()
    b_result = agent_b_mod.agent_b(question, predicted_db, mode="light")
    step_times["agent_b_ms"] = _duration_ms(step_start)
    if isinstance(b_result, dict) and b_result.get("error"):
        raise ValueError(f"Agent B error: {b_result['error']}")
    if isinstance(b_result, dict):
        tables = b_result.get("Tables", []) or []
    _log(log_file, f"Q{index} AgentB done in {step_times['agent_b_ms']}ms, tables={len(tables)}")

    step_start = time.perf_counter()
    c_result = agent_c_mod.agent_c(question, predicted_db, tables, mode="light")
    step_times["agent_c_ms"] = _duration_ms(step_start)
    if isinstance(c_result, dict) and c_result.get("error"):
        raise ValueError(f"Agent C error: {c_result['error']}")
    if not isinstance(c_result, str) or not c_result.strip():
        raise ValueError("Agent C returned empty SQL")
    sql = _normalize_sql(c_result)
    _log(log_file, f"Q{index} AgentC done in {step_times['agent_c_ms']}ms")

    total_ms = _duration_ms(question_start)
    _log(log_file, f"Q{index} DONE total={total_ms}ms")

    return {
        "index": index,
        "question": question,
        "gold_db": gold_db,
        "predicted_db": predicted_db,
        "tables": tables,
        "prediction_sql": sql,
        "step_times_ms": step_times,
        "total_time_ms": total_ms,
        "error": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Spider predictions with scripts agents")
    parser.add_argument(
        "--params",
        type=Path,
        default=DEFAULT_PARAMS_PATH,
        help="Path to parameter JSON file",
    )
    args = parser.parse_args()

    if "OPENAI_API_KEY" not in os.environ:
        print("ERROR: OPENAI_API_KEY is not set in environment.")
        print("Tip: create project .env or export env var before running.")
        return 1

    if not args.params.exists():
        print(f"ERROR: Parameter file not found: {args.params}")
        return 1

    params = _load_params(args.params)

    input_path = Path(params.get("input", PROJECT_ROOT / "data" / "test" / "spider_query_answers.json"))
    output_root = Path(params.get("output_root", PROJECT_ROOT / "evaluation" / "test_chunks"))
    start_index = max(0, int(params.get("start", 0)))
    end_cfg = int(params.get("end", -1))
    chunk_size = int(params.get("chunk_size", 10))
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    max_retries = int(params.get("max_retries", 2))

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        return 1

    sys.path.append(str(PROJECT_ROOT))

    try:
        import scripts.agents.agent_a as agent_a_mod
        import scripts.agents.agent_b as agent_b_mod
        import scripts.agents.agent_c as agent_c_mod
    except Exception as import_error:
        print(f"ERROR: Failed to import scripts agents: {import_error}")
        return 1

    agent_a_mod.QUIET_MODE = True
    agent_b_mod.QUIET_MODE = True
    agent_c_mod.QUIET_MODE = True

    examples = _load_examples(input_path)
    total_examples = len(examples)
    end_index = total_examples if end_cfg < 0 else min(end_cfg, total_examples)

    if start_index >= end_index:
        print(f"Nothing to run: start={start_index}, end={end_index}, total={total_examples}")
        return 0

    output_root.mkdir(parents=True, exist_ok=True)
    chunk_no = 1
    current = start_index

    while current < end_index:
        chunk_start = current
        chunk_end = min(current + chunk_size, end_index)
        chunk_folder = output_root / f"test_chuck_{chunk_no}"
        chunk_folder.mkdir(parents=True, exist_ok=True)

        predictions_path = chunk_folder / "predictions.txt"
        debug_path = chunk_folder / "predictions_debug.jsonl"
        summary_path = chunk_folder / "summary.json"
        log_path = chunk_folder / "run.log"
        params_copy_path = chunk_folder / "parameters.json"
        shutil.copy2(args.params, params_copy_path)

        chunk_timer = time.perf_counter()
        _log(log_path, f"CHUNK {chunk_no} START range=[{chunk_start}, {chunk_end})")
        _log(log_path, f"Parameters copied to: {params_copy_path}")

        chunk_debug_rows: List[Dict[str, Any]] = []
        chunk_ok = 0
        stop_all = False

        with predictions_path.open("w", encoding="utf-8") as pred_f, debug_path.open("w", encoding="utf-8") as dbg_f:
            for idx in range(chunk_start, chunk_end):
                row = examples[idx]
                attempt = 0
                success = False
                last_error = ""

                while attempt <= max_retries and not success:
                    attempt += 1
                    _log(log_path, f"Q{idx} attempt {attempt}/{max_retries + 1}")
                    try:
                        result = _run_one_question(
                            row=row,
                            index=idx,
                            params=params,
                            agent_a_mod=agent_a_mod,
                            agent_b_mod=agent_b_mod,
                            agent_c_mod=agent_c_mod,
                            log_file=log_path,
                        )
                        pred_f.write(result["prediction_sql"] + "\n")
                        dbg_f.write(json.dumps(result, ensure_ascii=False) + "\n")
                        chunk_debug_rows.append(result)
                        chunk_ok += 1
                        success = True
                    except Exception as err:
                        last_error = str(err)
                        _log(log_path, f"Q{idx} attempt {attempt} FAILED: {last_error}")

                if not success:
                    fail_row = {
                        "index": idx,
                        "question": row.get("question") or row.get("Question"),
                        "error": f"FAILED after {max_retries + 1} attempts: {last_error}",
                        "prediction_sql": None,
                    }
                    chunk_debug_rows.append(fail_row)
                    dbg_f.write(json.dumps(fail_row, ensure_ascii=False) + "\n")
                    _log(log_path, f"Q{idx} hard-fail => STOP RUN")
                    stop_all = True
                    break

        expected_count = chunk_end - chunk_start
        predicted_count = chunk_ok
        integrity_ok = predicted_count == expected_count
        if not integrity_ok and not stop_all:
            _log(
                log_path,
                f"CHUNK {chunk_no} integrity mismatch expected={expected_count} got={predicted_count} => STOP RUN",
            )
            stop_all = True

        chunk_total_ms = _duration_ms(chunk_timer)
        summary = {
            "chunk_no": chunk_no,
            "chunk_folder": str(chunk_folder),
            "range_start": chunk_start,
            "range_end_exclusive": chunk_end,
            "expected_questions": expected_count,
            "successful_predictions": predicted_count,
            "integrity_ok": integrity_ok,
            "stopped_due_to_error": stop_all,
            "max_retries": max_retries,
            "chunk_total_time_ms": chunk_total_ms,
            "next_start_suggestion": chunk_start + predicted_count,
        }
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        _log(log_path, f"CHUNK {chunk_no} END total={chunk_total_ms}ms ok={predicted_count}/{expected_count}")
        _log(log_path, f"Summary saved: {summary_path}")

        if stop_all:
            print(f"Stopped at chunk {chunk_no}. Check logs in: {chunk_folder}")
            return 2

        current = chunk_end
        chunk_no += 1

    print("Done all chunks successfully.")
    print(f"Output root: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
