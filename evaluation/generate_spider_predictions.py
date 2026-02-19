#!/usr/bin/env python3
"""
Generate Spider predictions in chunk folders with detailed timing logs.

Main behavior:
- Read run settings from evaluation/prediction_parameters.json
- Prompt for dataset type and range on startup
- Process 10 questions per chunk by default
- Save each chunk to evaluation/predict_results/<Dataset>_predict_results/test_chuck_<n>
- Retry failures; stop the run if a question still fails after retries
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import IO, Any, Dict, List

from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.prompts import PromptTemplate


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PARAMS_PATH = PROJECT_ROOT / "evaluation" / "prediction_parameters.json"
DEFAULT_DATASET_ROOT = PROJECT_ROOT / "evaluation" / "spider_data"
DEFAULT_OUTPUT_BASE = PROJECT_ROOT / "evaluation" / "predict_results"


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


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def _extract_json_object(text: str) -> str:
    stripped = _strip_code_fences(text)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _parse_json(text: str) -> Dict[str, Any] | None:
    candidate = _extract_json_object(text)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_db_name(text: str) -> str | None:
    parsed = _parse_json(text)
    if parsed:
        db_name = parsed.get("db_name") or parsed.get("database")
        if db_name:
            return str(db_name)

    match = re.search(r'"db_name"\s*:\s*"([^"]+)"', text)
    if match:
        return match.group(1)
    match = re.search(r"db_name\s*[:=]\s*([A-Za-z0-9_]+)", text)
    if match:
        return match.group(1)
    return None


def _clean_sql(text: str) -> str:
    cleaned = _strip_code_fences(text)
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1].strip().strip("'").strip('"')
    return cleaned


def _detect_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _write_trace(trace_f: IO[str], payload: Dict[str, Any]) -> None:
    line = json.dumps(payload, ensure_ascii=False)
    print(line)
    trace_f.write(line + "\n")


def _pick_question(record: Dict[str, Any]) -> str:
    question = record.get("question") or record.get("Question")
    if not question:
        raise ValueError("Missing question field")
    return str(question)


def _pick_gold_db(record: Dict[str, Any]) -> str | None:
    db_id = record.get("db_id") or record.get("database") or record.get("db_name")
    return str(db_id) if db_id else None


def _prompt_text(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default


def _prompt_int(label: str, default: int | None = None) -> int:
    while True:
        raw = _prompt_text(label, str(default) if default is not None else None)
        try:
            return int(raw)
        except ValueError:
            print("Please enter a valid integer.")


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


def _prompt_llm_backend() -> str:
    print("LLM backend:")
    print("1) Using ChatGPT by API (Original)")
    print("2) Qwen/Qwen2.5-7B-Instruct (transformers)")
    while True:
        choice = input("Select (1/2): ").strip()
        if choice == "1":
            return "openai"
        if choice == "2":
            return "qwen"
        print("Please select 1 or 2.")


def _resolve_dataset_file(dataset_root: Path, dataset_kind: str) -> Path:
    candidates = {
        "train": [
            dataset_root / "train_spider.json",
            dataset_root / "train.json",
            dataset_root / "train_others.json",
        ],
        "dev": [dataset_root / "dev.json"],
        "test": [dataset_root / "test.json"],
    }
    for candidate in candidates.get(dataset_kind, []):
        if candidate.exists():
            return candidate
    fallback = _prompt_text(
        "Dataset file path (could not auto-detect)",
        str(dataset_root),
    )
    return Path(fallback)


def _compute_range(start_case: int, end_case: int, total_examples: int) -> tuple[int, int]:
    start_index = max(0, start_case)
    if end_case < 0:
        end_index = total_examples
    else:
        end_index = min(end_case + 1, total_examples)
    return start_index, end_index


def _load_tables_json(schema_path: Path) -> List[Dict[str, Any]]:
    with schema_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(
            f"Expected list JSON in {schema_path}, got {type(data).__name__}"
        )
    return data


def _extract_essential_schema(tables_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    essential_data: List[Dict[str, Any]] = []
    for entry in tables_data:
        essential_data.append(
            {
                "database_name": entry.get("db_id", "undefined"),
                "table_names": entry.get("table_names", []),
                "column_names": entry.get("column_names", []),
            }
        )
    return essential_data


def _reshape_with_headings(
    essential_schemas: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for db in essential_schemas:
        db_name = db.get("database_name", "unknown")
        table_names = list(db.get("table_names", []))
        col_specs = list(db.get("column_names", []))
        tables = []

        for idx, table_name in enumerate(table_names):
            cols: List[str] = []
            for pair in col_specs:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    continue
                t_idx, col = pair
                try:
                    t_idx = int(t_idx)
                except (ValueError, TypeError):
                    continue
                if t_idx != idx:
                    continue
                if col is None or str(col).strip() == "*" or t_idx < 0:
                    continue
                cols.append(str(col))

            tables.append({"table_name": table_name, "columns": cols})

        out[db_name] = {"database_name": db_name, "tables": tables}

    return out


def _format_schema_jsonish(
    reshaped_essential_schemas: Dict[str, Dict[str, Any]],
) -> List[str]:
    lines: List[str] = []
    for _, db in reshaped_essential_schemas.items():
        db_name = db.get("database_name", "unknown")
        for table in db.get("tables", []):
            obj = {
                "database": db_name,
                "table": table.get("table_name", "unknown"),
                "columns": table.get("columns", []),
            }
            lines.append(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    return lines


def _build_notebook_pipeline(
    schema_path: Path,
    llm_backend: str,
) -> Dict[str, Any]:
    tables_data = _load_tables_json(schema_path)
    essential_schemas = _extract_essential_schema(tables_data)
    reshaped_essential_schemas = _reshape_with_headings(essential_schemas)
    final_schema_result = _format_schema_jsonish(reshaped_essential_schemas)

    if llm_backend == "openai":
        embeddings = OpenAIEmbeddings()
    else:
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
        except ImportError as exc:
            raise ImportError(
                "Please install sentence-transformers to use Qwen embeddings."
            ) from exc
        device = _detect_device()
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": device},
        )

    vectorstore = FAISS.from_texts(final_schema_result, embeddings)

    prompt_db = PromptTemplate(
        input_variables=["query", "retrieved_schema"],
        template=(
            "Please selects the most relevant database and table in order to answer user's query.\n"
            "User query: {query}\n"
            "Schema info: {retrieved_schema}\n"
            "Which database and tables has the most relevant information for this query? "
            "Selecting 1 database only. Respond the database name, table and column "
            "infomation in JSON format: {{ \"db_name\": \"...\", \"tables\": [\"...\"], "
            "\"columns\":[\"...\"]}}\n"
        ),
    )

    list_tables_prompt = PromptTemplate(
        input_variables=["user_query", "db_schema_json"],
        template=(
            "Given the selected database schema, return ONLY valid JSON with exactly these keys"
            '  "relevant_tables": ["..."],\n'
            '  "reasons": "..." \n\n'
            "User query: {user_query}\n"
            "DB schema JSON: {db_schema_json}\n"
            "Do not wrap all_tables in an extra list. Do not include any text outside JSON."
        ),
    )

    if llm_backend == "openai":
        llm = ChatOpenAI(model="gpt-5-mini", temperature=0)
        return {
            "llm_backend": "openai",
            "vectorstore": vectorstore,
            "db_chain": prompt_db | llm,
            "table_chain": list_tables_prompt | llm,
            "reshaped_schemas": reshaped_essential_schemas,
            "db_prompt": prompt_db,
            "table_prompt": list_tables_prompt,
        }

    from qwen_model import QwenChatClient

    qwen_client = QwenChatClient()
    return {
        "llm_backend": "qwen",
        "vectorstore": vectorstore,
        "qwen_client": qwen_client,
        "db_prompt": prompt_db,
        "table_prompt": list_tables_prompt,
        "reshaped_schemas": reshaped_essential_schemas,
    }


def _notebook_db_select(
    user_query: str, notebook_pipeline: Dict[str, Any], top_k: int
) -> tuple[str | None, Dict[str, Any]]:
    vectorstore = notebook_pipeline["vectorstore"]
    if notebook_pipeline.get("llm_backend") == "openai":
        db_chain = notebook_pipeline["db_chain"]
    else:
        db_chain = None

    relevant_docs = vectorstore.similarity_search_with_score(user_query, k=top_k)
    selected_schema = ""
    for doc, score in relevant_docs:
        selected_schema += f"score: {score}, content: {doc.page_content}\n"

    prompt_db = notebook_pipeline["db_prompt"]
    prompt_text = prompt_db.format(query=user_query, retrieved_schema=selected_schema)

    if db_chain is not None:
        response = db_chain.invoke(
            {"query": user_query, "retrieved_schema": selected_schema}
        )
        llm_output = response.content if hasattr(response, "content") else str(response)
    else:
        qwen_client = notebook_pipeline["qwen_client"]
        llm_output = qwen_client.invoke(prompt_text)

    db_name = _parse_db_name(llm_output)
    trace = {
        "agent": "A",
        "prompt": prompt_text,
        "db_name": db_name,
    }
    return db_name, trace


def _notebook_table_select(
    user_query: str, db_name: str, notebook_pipeline: Dict[str, Any]
) -> tuple[List[str], Dict[str, Any]]:
    reshaped_schemas = notebook_pipeline["reshaped_schemas"]
    if notebook_pipeline.get("llm_backend") == "openai":
        table_chain = notebook_pipeline["table_chain"]
    else:
        table_chain = None

    if db_name not in reshaped_schemas:
        raise ValueError(f"No schema found for database: {db_name}")

    full_schema = reshaped_schemas[db_name]["tables"]
    prompt_table = notebook_pipeline["table_prompt"]
    prompt_text = prompt_table.format(user_query=user_query, db_schema_json=full_schema)

    if table_chain is not None:
        response = table_chain.invoke(
            {"user_query": user_query, "db_schema_json": full_schema}
        )
        llm_output = response.content if hasattr(response, "content") else str(response)
    else:
        qwen_client = notebook_pipeline["qwen_client"]
        llm_output = qwen_client.invoke(prompt_text)

    parsed = _parse_json(llm_output)
    if not parsed:
        raise ValueError("Agent B JSON parse error: invalid JSON output")

    tables = parsed.get("relevant_tables") or parsed.get("tables") or []
    trace = {
        "agent": "B",
        "prompt": prompt_text,
        "tables": tables,
    }
    return tables, trace


def _qwen_generate_sql(
    user_query: str,
    db_name: str,
    recommended_tables: List[str],
    notebook_pipeline: Dict[str, Any],
) -> tuple[str, Dict[str, Any]]:
    reshaped_schemas = notebook_pipeline["reshaped_schemas"]
    if db_name not in reshaped_schemas:
        raise ValueError(f"No schema found for database: {db_name}")

    schema_json = reshaped_schemas[db_name]["tables"]
    prompt = (
        "You are an SQL expert. Given the following database schema:\n\n"
        "DB schema JSON: {db_schema_json}\n\n"
        "Recommended tables: {recommended_tables}\n\n"
        "Write a SQL query that answers the following question:\n\n"
        "User query: {user_query}\n\n"
        "Only return the SQL query, nothing else."
    )
    prompt_text = prompt.format(
        db_schema_json=schema_json,
        recommended_tables=recommended_tables,
        user_query=user_query,
    )

    qwen_client = notebook_pipeline["qwen_client"]
    llm_output = qwen_client.invoke(prompt_text)
    sql = _clean_sql(llm_output)
    trace = {
        "agent": "C",
        "prompt": prompt_text,
        "sql": sql,
    }
    return sql, trace


def _run_one_question(
    row: Dict[str, Any],
    index: int,
    params: Dict[str, Any],
    notebook_pipeline: Dict[str, Any],
    agent_c_mod: Any,
    log_file: Path,
    trace_f: IO[str],
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
    trace: Dict[str, Any] = {"question_index": index, "question": question}

    _log(log_file, f"Q{index} START")
    _log(log_file, f"Q{index} Question: {question}")

    if use_gold_db:
        if not gold_db:
            raise ValueError("use_gold_db=true but current row has no db_id")
        predicted_db = gold_db
        step_times["agent_a_ms"] = 0
        trace["agent_a"] = {"db_name": predicted_db}
        _log(log_file, f"Q{index} AgentA skipped (use_gold_db=true), db={predicted_db}")
    else:
        step_start = time.perf_counter()
        predicted_db, _ = _notebook_db_select(question, notebook_pipeline, top_k)
        step_times["agent_a_ms"] = _duration_ms(step_start)
        if not predicted_db:
            raise ValueError("Agent A returned empty db_name")
        trace["agent_a"] = {"db_name": predicted_db}
        _log(log_file, f"Q{index} AgentA db_name={predicted_db}")
        _log(log_file, f"Q{index} AgentA done in {step_times['agent_a_ms']}ms, db={predicted_db}")

    step_start = time.perf_counter()
    tables, _ = _notebook_table_select(question, predicted_db, notebook_pipeline)
    step_times["agent_b_ms"] = _duration_ms(step_start)
    trace["agent_b"] = {"tables": tables}
    _log(log_file, f"Q{index} AgentB tables={tables}")
    _log(log_file, f"Q{index} AgentB done in {step_times['agent_b_ms']}ms, tables={len(tables)}")

    step_start = time.perf_counter()
    if notebook_pipeline.get("llm_backend") == "qwen":
        c_result, _ = _qwen_generate_sql(question, predicted_db, tables, notebook_pipeline)
    else:
        c_result = agent_c_mod.agent_c(question, predicted_db, tables, mode="light")
        
    step_times["agent_c_ms"] = _duration_ms(step_start)
    if isinstance(c_result, dict) and c_result.get("error"):
        raise ValueError(f"Agent C error: {c_result['error']}")
    if not isinstance(c_result, str) or not c_result.strip():
        raise ValueError("Agent C returned empty SQL")
    sql = _normalize_sql(c_result)
    trace["agent_c"] = {"sql": sql}
    _log(log_file, f"Q{index} AgentC sql={sql}")
    _log(log_file, f"Q{index} AgentC done in {step_times['agent_c_ms']}ms")

    total_ms = _duration_ms(question_start)
    _log(log_file, f"Q{index} DONE total={total_ms}ms")

    _write_trace(trace_f, trace)

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

    if not args.params.exists():
        print(f"ERROR: Parameter file not found: {args.params}")
        return 1

    params = _load_params(args.params)

    llm_backend = params.get("llm_backend") or _prompt_llm_backend()
    qwen_mode = None
    if llm_backend == "qwen":
        qwen_mode = "pipeline"
    else:
        if "OPENAI_API_KEY" not in os.environ:
            print("ERROR: OPENAI_API_KEY is not set in environment.")
            print("Tip: create project .env or export env var before running.")
            return 1

    print("Path to the main dataset (Include train, dev, and test sets)")
    dataset_root = Path(
        _prompt_text(
            "Dataset root",
            str(params.get("dataset_root", DEFAULT_DATASET_ROOT)),
        )
    )
    dataset_kind = _prompt_dataset_kind()
    input_path = _resolve_dataset_file(dataset_root, dataset_kind)

    from_case = _prompt_int("From case", int(params.get("start", 0)))
    to_case = _prompt_int("To case", int(params.get("end", -1)))

    output_base = Path(params.get("output_base", DEFAULT_OUTPUT_BASE))
    output_root = output_base / f"{dataset_kind.capitalize()}_predict_results"

    chunk_size = int(params.get("chunk_size", 10))
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    max_retries = int(params.get("max_retries", 2))

    output_root.mkdir(parents=True, exist_ok=True)
    session_log = output_root / "session.log"
    _log(session_log, f"LLM backend: {llm_backend}")
    if qwen_mode:
        _log(session_log, f"Qwen mode: {qwen_mode}")
    _log(session_log, f"Dataset root: {dataset_root}")
    _log(session_log, f"Dataset kind: {dataset_kind}")
    _log(session_log, f"Input path: {input_path}")
    _log(session_log, f"Output root: {output_root}")
    _log(session_log, f"Chunk size: {chunk_size}")
    _log(session_log, f"Max retries: {max_retries}")

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        _log(session_log, f"ERROR: Input file not found: {input_path}")
        return 1

    sys.path.append(str(PROJECT_ROOT))

    try:
        import scripts.agents.agent_c as agent_c_mod
    except Exception as import_error:
        print(f"ERROR: Failed to import scripts agent_c: {import_error}")
        return 1

    agent_c_mod.QUIET_MODE = True

    schema_path = Path(
        params.get(
            "schema_path",
            dataset_root / "tables.json",
        )
    )
    _log(session_log, f"Schema path: {schema_path}")
    if not schema_path.exists():
        print(f"ERROR: tables.json not found: {schema_path}")
        _log(session_log, f"ERROR: tables.json not found: {schema_path}")
        return 1

    notebook_pipeline = _build_notebook_pipeline(schema_path, llm_backend)

    tables_snapshot = output_root / "tables.json"
    try:
        shutil.copy2(schema_path, tables_snapshot)
        _log(session_log, f"Schema snapshot saved: {tables_snapshot}")
    except Exception as copy_error:
        _log(session_log, f"WARN: Failed to copy tables.json: {copy_error}")

    input_snapshot = output_root / input_path.name
    try:
        shutil.copy2(input_path, input_snapshot)
        _log(session_log, f"Input snapshot saved: {input_snapshot}")
    except Exception as copy_error:
        _log(session_log, f"WARN: Failed to copy input file: {copy_error}")

    examples = _load_examples(input_path)
    total_examples = len(examples)
    start_index, end_index = _compute_range(from_case, to_case, total_examples)

    _log(session_log, f"Range: start={start_index} end_exclusive={end_index}")

    if start_index >= end_index:
        print(f"Nothing to run: start={start_index}, end={end_index}, total={total_examples}")
        _log(session_log, f"Nothing to run: start={start_index}, end={end_index}, total={total_examples}")
        return 0

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
        trace_path = chunk_folder / "agent_cot.jsonl"
        params_copy_path = chunk_folder / "parameters.json"
        shutil.copy2(args.params, params_copy_path)

        chunk_timer = time.perf_counter()
        _log(log_path, f"CHUNK {chunk_no} START range=[{chunk_start}, {chunk_end})")
        _log(log_path, f"Parameters copied to: {params_copy_path}")
        _log(session_log, f"CHUNK {chunk_no} START range=[{chunk_start}, {chunk_end})")

        chunk_debug_rows: List[Dict[str, Any]] = []
        chunk_ok = 0
        stop_all = False

        with (
            predictions_path.open("w", encoding="utf-8") as pred_f,
            debug_path.open("w", encoding="utf-8") as dbg_f,
            trace_path.open("w", encoding="utf-8") as trace_f,
        ):
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
                            notebook_pipeline=notebook_pipeline,
                            agent_c_mod=agent_c_mod,
                            log_file=log_path,
                            trace_f=trace_f,
                        )
                        pred_f.write(result["prediction_sql"] + "\n")
                        dbg_f.write(json.dumps(result, ensure_ascii=False) + "\n")
                        pred_f.flush()
                        dbg_f.flush()
                        trace_f.flush()
                        chunk_debug_rows.append(result)
                        chunk_ok += 1
                        success = True
                    except Exception as err:
                        last_error = str(err)
                        _log(log_path, f"Q{idx} attempt {attempt} FAILED: {last_error}")
                        _write_trace(
                            trace_f,
                            {
                                "question_index": idx,
                                "step": "error",
                                "attempt": attempt,
                                "error": last_error,
                            },
                        )

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
        _log(session_log, f"CHUNK {chunk_no} END total={chunk_total_ms}ms ok={predicted_count}/{expected_count}")

        if stop_all:
            print(f"Stopped at chunk {chunk_no}. Check logs in: {chunk_folder}")
            _log(session_log, f"STOPPED at chunk {chunk_no}. See: {chunk_folder}")
            return 2

        current = chunk_end
        chunk_no += 1

    print("Done all chunks successfully.")
    print(f"Output root: {output_root}")
    _log(session_log, "RUN COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
