"""Simple shell UI to build schema files and run agents."""

import os
import sys
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Ensure local imports work when running from repo root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
	sys.path.insert(0, SCRIPT_DIR)

from schema_builder import build_schema_ab, build_schema_c
import a_db_select
import b_table_select
import c_sql_generate

load_dotenv()

QWEN_DEFAULT_API_URL = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-7B-Instruct"

PENDING_LOGS: List[Tuple[str, str]] = []


def _prompt_non_empty_dir(prompt_text: str) -> str:
	while True:
		value = input(prompt_text).strip().strip('"')
		if value and os.path.isdir(value):
			return value
		print("Invalid folder path. Please try again.")


def _prompt_existing_file(prompt_text: str) -> str:
	while True:
		value = input(prompt_text).strip().strip('"')
		if value and os.path.isfile(value):
			return value
		print("Invalid file path. Please try again.")


def _prompt_test_name() -> str:
	value = input("Test name (default: default): ").strip()
	return value or "default"


def _prompt_yes_no(prompt_text: str, default: str = "n") -> bool:
	default = default.lower()
	suffix = "[Y/n]" if default == "y" else "[y/N]"
	while True:
		value = input(f"{prompt_text} {suffix}: ").strip().lower()
		if not value:
			return default == "y"
		if value in ("y", "yes"):
			return True
		if value in ("n", "no"):
			return False
		print("Please enter y or n.")


def _prompt_api_key() -> str:
	value = os.getenv("OPENAI_API_KEY")
	if value:
		return value
	return input("OPENAI_API_KEY not set. Enter API key: ").strip()


def _log(message: str, log_path: Optional[str], activity: str = "INFO") -> None:
	stamp = _utc_now_iso()
	line = f"{stamp} [{activity}] {message}"
	print(line)
	if log_path:
		with open(log_path, "a", encoding="utf-8") as f:
			f.write(line + "\n")
	else:
		PENDING_LOGS.append((activity, message))


def _flush_pending_logs(log_path: str) -> None:
	for activity, message in PENDING_LOGS:
		_log(message, log_path, activity=activity)
	PENDING_LOGS.clear()


def _utc_now_iso() -> str:
	return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _prompt_model_choice() -> Tuple[str, str]:
	while True:
		value = input("Select model [1=ChatGPT 5 mini, 2=Qwen 2.5 7B] (default: 1): ").strip()
		if not value or value == "1":
			return "openai", "gpt-5-mini"
		if value == "2":
			return "open-source", "Qwen/Qwen2.5-7B-Instruct"
		print("Please enter 1 or 2.")


def _prompt_qwen_mode() -> str:
	while True:
		value = input("Qwen mode [1=Local, 2=HF API (cloud)] (default: 1): ").strip()
		if not value or value == "1":
			return "local"
		if value == "2":
			return "hf-api"
		print("Please enter 1 or 2.")


def _sanitize_name(value: str) -> str:
	clean = []
	for ch in value:
		if ch.isalnum() or ch in ("-", "_"):
			clean.append(ch.lower())
		else:
			clean.append("_")
	result = "".join(clean).strip("_")
	return result or "model"


def _init_qwen_once(log_path: Optional[str], qwen_mode: str, model_name: str) -> None:
	try:
		from qwen2_5_7b_instruct_api import chat_completion
	except Exception as exc:
		_log(f"Qwen init failed to import client: {exc}", log_path, activity="Qwen init")
		return

	api_key = None
	api_url = "local" if qwen_mode == "local" else QWEN_DEFAULT_API_URL
	if qwen_mode != "local":
		api_key = os.getenv("HUGGINGFACEHUB_API_TOKEN")
		if not api_key:
			_log("Qwen init skipped (missing HF API token in .env).", log_path, activity="Qwen init")
			return

	try:
		result = chat_completion(
			messages=[
				{"role": "system", "content": "You are a helpful assistant."},
				{"role": "user", "content": "Say hello."},
			],
			api_key=api_key,
			api_url=api_url,
			model=model_name,
			max_tokens=32,
		)
		content = result["choices"][0]["message"]["content"]
		_log(f"Qwen init success. Sample output: {content}", log_path, activity="Qwen init")
	except Exception as exc:
		_log(f"Qwen init failed: {exc}", log_path, activity="Qwen init")


def _discover_sqlite_files(data_dir: str) -> List[str]:
	found = []
	for root, _dirs, files in os.walk(data_dir):
		for name in files:
			lower = name.lower()
			if lower.endswith(".sqlite") or lower.endswith(".db"):
				found.append(os.path.join(root, name))
	return found


def _build_db_mapping(db_paths: List[str]) -> Dict[str, str]:
	mapping: Dict[str, str] = {}
	for path in db_paths:
		base = os.path.splitext(os.path.basename(path))[0]
		parent = os.path.basename(os.path.dirname(path))
		db_key = parent if base == parent else base

		if db_key in mapping:
			suffix = 2
			while f"{db_key}_{suffix}" in mapping:
				suffix += 1
			db_key = f"{db_key}_{suffix}"

		mapping[db_key] = path
	return mapping


def _ensure_django_settings(media_root: str) -> None:
	try:
		from django.conf import settings
		if not settings.configured:
			settings.configure(MEDIA_ROOT=media_root)
			return
		# If already configured but MEDIA_ROOT is empty, override for this session
		if not getattr(settings, "MEDIA_ROOT", None):
			setattr(settings, "MEDIA_ROOT", media_root)
	except Exception:
		# If Django is unavailable, fail later when agents try to access settings
		pass


def _load_or_create_config(config_path: str) -> Tuple[dict, bool]:
	defaults = {
		"agent_a_model": "gpt-5-mini",
		"agent_a_top_k": 5,
		"embedding_backend": "openai",
		"embedding_model": "ssmits/Qwen2.5-7B-embed-base",
		"retry_count": 3,
		"retry_wait_sec": 120,
	}

	if os.path.exists(config_path) and os.path.getsize(config_path) > 0:
		try:
			with open(config_path, "r", encoding="utf-8") as f:
				data = json.load(f)
				if isinstance(data, dict):
					merged = defaults.copy()
					merged.update(data)
					return merged, False
		except Exception:
			pass

	with open(config_path, "w", encoding="utf-8") as f:
		json.dump(defaults, f, indent=2)
	return defaults, True


def _load_questions(question_file: str) -> List[dict]:
	# Try standard Spider JSON list first
	try:
		with open(question_file, "r", encoding="utf-8") as f:
			data = json.load(f)
			if isinstance(data, list):
				return data
	except Exception:
		pass

	# Fallback: JSONL format (one object per line)
	items = []
	with open(question_file, "r", encoding="utf-8") as f:
		for line in f:
			line = line.strip()
			if not line:
				continue
			try:
				items.append(json.loads(line))
			except Exception:
				continue
	return items


def _load_tracking(tracking_file: str, question_file: str) -> dict:
	if os.path.exists(tracking_file) and os.path.getsize(tracking_file) > 0:
		with open(tracking_file, "r", encoding="utf-8") as f:
			try:
				return json.load(f)
			except Exception:
				pass
	return {
		"question_file": question_file,
		"last_index": -1,
		"last_attempted": -1,
		"status": "new",
		"updated_at": _utc_now_iso(),
		"failures": [],
	}


def _save_tracking(tracking_file: str, payload: dict) -> None:
	payload["updated_at"] = _utc_now_iso()
	with open(tracking_file, "w", encoding="utf-8") as f:
		json.dump(payload, f, indent=2)


def _append_complete_result(result_path: str, record: dict) -> None:
	data = []
	if os.path.exists(result_path) and os.path.getsize(result_path) > 0:
		try:
			with open(result_path, "r", encoding="utf-8") as f:
				loaded = json.load(f)
				if isinstance(loaded, list):
					data = loaded
		except Exception:
			data = []

	data.append(record)
	with open(result_path, "w", encoding="utf-8") as f:
		json.dump(data, f, indent=2)


def _run_agents(
	api_key: str,
	user_id: str,
	question_text: str,
	fallback_db: str,
	config: dict,
) -> Tuple[dict, str]:
	result_a = a_db_select.run(
		api_key,
		{"query": question_text},
		user_id,
		model=config.get("agent_a_model", "gpt-5-mini"),
		top_k=int(config.get("agent_a_top_k", 5)),
		qwen_api_key=config.get("qwen_hf_api_key"),
		qwen_api_url=config.get("qwen_api_url"),
		embedding_backend=config.get("embedding_backend", "openai"),
		embedding_model=config.get("embedding_model", "ssmits/Qwen2.5-7B-embed-base"),
	)
	if isinstance(result_a, dict) and result_a.get("error"):
		selected_db = None
	else:
		selected_db = result_a.get("database") if isinstance(result_a, dict) else None

	if not selected_db:
		selected_db = fallback_db

	result_b = b_table_select.run(
		api_key,
		{"query": question_text, "database": selected_db},
		user_id,
		model=config.get("agent_model", "gpt-5-mini"),
		qwen_api_key=config.get("qwen_hf_api_key"),
		qwen_api_url=config.get("qwen_api_url"),
	)
	if isinstance(result_b, dict) and result_b.get("error"):
		return {
			"error": result_b.get("error"),
			"agent_a": result_a,
			"agent_b": result_b,
		}, "b"

	result_c = c_sql_generate.run(
		api_key,
		{
			"query": question_text,
			"database": selected_db,
			"relevant_tables": result_b.get("relevant_tables", []),
			"reasons": result_b.get("reasons", ""),
		},
		user_id,
		model=config.get("agent_model", "gpt-5-mini"),
		qwen_api_key=config.get("qwen_hf_api_key"),
		qwen_api_url=config.get("qwen_api_url"),
	)
	if isinstance(result_c, dict) and result_c.get("error"):
		return {
			"error": result_c.get("error"),
			"agent_a": result_a,
			"agent_b": result_b,
			"agent_c": result_c,
		}, "c"

	return {
		"database": selected_db,
		"tables": result_b.get("relevant_tables", []),
		"sql": result_c.get("SQL"),
		"reasons": result_c.get("reasons", ""),
		"agent_a": result_a,
		"agent_b": result_b,
		"agent_c": result_c,
	}, "ok"


def main() -> None:
	print("Step 1: Select data folder, test name, and model")
	data_dir = _prompt_non_empty_dir("Data folder path: ")
	test_name = _prompt_test_name()
	model_source, model_name = _prompt_model_choice()
	qwen_mode = None
	init_qwen = False
	if "qwen" in model_name.lower():
		print("Step 0: Initialize Qwen (optional warm-up)")
		init_qwen = _prompt_yes_no("Initialize Qwen now?", default="n")
		qwen_mode = _prompt_qwen_mode()
	model_tag = _sanitize_name(model_name)

	test_root = os.path.join(os.getcwd(), f"{test_name}_model_{model_tag}")
	os.makedirs(test_root, exist_ok=True)
	log_path = os.path.join(test_root, f"log_{model_tag}.txt")
	# Set env var for agent error logs
	os.environ["AGENT_LOG_DIR"] = test_root
	_flush_pending_logs(log_path)
	_log(f"Test name: {test_name}", log_path, activity="Setup")
	_log(f"Model name: {model_name}", log_path, activity="Setup")
	_log("Data folder set.", log_path, activity="Setup")

	config_path = os.path.join(test_root, f"config_model_{model_tag}.json")
	config, created = _load_or_create_config(config_path)
	config["agent_a_model"] = model_name
	config["agent_model"] = model_name
	config["model_source"] = model_source
	if "qwen" in model_name.lower():
		config["embedding_backend"] = "hf"
		config["qwen_model"] = model_name
		if qwen_mode == "hf-api":
			config["qwen_api_url"] = QWEN_DEFAULT_API_URL
			config["model_source"] = "hf-api"
		else:
			config["qwen_api_url"] = "local"
			config["model_source"] = "open-source"
	else:
		config["embedding_backend"] = "openai"
	with open(config_path, "w", encoding="utf-8") as f:
		json.dump(config, f, indent=2)
	if created:
		_log("Config created.", log_path, activity="Setup")
	_log(f"Config loaded: {config}", log_path, activity="Setup")

	if config.get("model_source") == "open-source":
		_log("Qwen local selected. LLM + embeddings run locally.", log_path, activity="Setup")
	elif config.get("model_source") == "hf-api":
		_log("Qwen HF API selected. LLM runs in the cloud.", log_path, activity="Setup")

	if init_qwen:
		_init_qwen_once(log_path, qwen_mode or "local", model_name)

	_log("Step 2: Build schema files", log_path, activity="Schema")
	db_paths = _discover_sqlite_files(data_dir)
	if not db_paths:
		_log("No .sqlite or .db files found in the selected folder.", log_path, activity="Schema")
		return

	db_mapping = _build_db_mapping(db_paths)
	schema_dir = os.path.join(test_root, "schema")
	os.makedirs(schema_dir, exist_ok=True)

	schema_ab_path = os.path.join(schema_dir, "schema_ab.jsonl")
	schema_c_path = os.path.join(schema_dir, "schema_c.json")
	if os.path.exists(schema_ab_path) or os.path.exists(schema_c_path):
		if os.path.exists(schema_ab_path) and os.path.getsize(schema_ab_path) == 0:
			_log("Warning: schema_ab.jsonl exists but is empty.", log_path, activity="Schema")
		if os.path.exists(schema_c_path) and os.path.getsize(schema_c_path) == 0:
			_log("Warning: schema_c.json exists but is empty.", log_path, activity="Schema")
		if not _prompt_yes_no("Schema already exists. Rebuild it?", default="n"):
			_log("Using existing schema files.", log_path, activity="Schema")
			ab_result = {"file": schema_ab_path}
			c_result = {"file": schema_c_path}
			goto_step_3 = True
		else:
			goto_step_3 = False
	else:
		goto_step_3 = False
	if not goto_step_3:
		ab_result = build_schema_ab(db_mapping, schema_dir)
		if isinstance(ab_result, dict) and ab_result.get("error"):
			_log(f"Failed to build schema_ab: {ab_result['error']}", log_path, activity="Schema")
			return

		c_result = build_schema_c(db_mapping, schema_dir)
		if isinstance(c_result, dict) and c_result.get("error"):
			_log(f"Failed to build schema_c: {c_result['error']}", log_path, activity="Schema")
			return

	_log("Schema build completed", log_path, activity="Schema")
	_log("schema_ab.jsonl ready.", log_path, activity="Schema")
	_log("schema_c.json ready.", log_path, activity="Schema")

	_log("Step 3: Select Spider question file and tracking state", log_path, activity="Questions")
	question_file = _prompt_existing_file("Spider question file path: ")
	_log(f"Question file: {os.path.basename(question_file)}", log_path, activity="Questions")

	tracking_dir = os.path.join(test_root, f"tracking_process_model_{model_tag}")
	os.makedirs(tracking_dir, exist_ok=True)
	tracking_file = os.path.join(tracking_dir, "progress.json")

	continue_test = _prompt_yes_no(
		"Is this test already in progress (continue from tracking file)?",
		default="n",
	)

	tracking = _load_tracking(tracking_file, question_file)
	if continue_test:
		_log("Using tracking file.", log_path, activity="Continue test")
	else:
		tracking = _load_tracking(tracking_file, question_file)
		tracking["last_index"] = -1
		tracking["last_attempted"] = -1
		tracking["status"] = "new"
		tracking["failures"] = []
		_save_tracking(tracking_file, tracking)
		_log("Tracking file reset.", log_path, activity="New test")

	_log("Step 4: Run agents (A -> B -> C) and write results", log_path, activity="Run")
	api_key = ""
	if model_source == "openai":
		api_key = _prompt_api_key()
		if not api_key:
			_log("Missing API key. Exiting.", log_path, activity="Run")
			return

	media_root = os.getcwd()
	_ensure_django_settings(media_root)
	user_id = f"{test_name}_model_{model_tag}"

	questions = _load_questions(question_file)
	if not questions:
		_log("No questions found in the selected file.", log_path, activity="Questions")
		return
	_log(f"Total questions: {len(questions)}", log_path, activity="Questions")

	results_path = os.path.join(test_root, f"predictions_model_{model_tag}.tsv")
	complete_result_path = os.path.join(test_root, f"complete_result_model_{model_tag}.json")
	_log("Predictions file ready.", log_path, activity="Run")
	_log("Complete result file ready.", log_path, activity="Run")
	_log("Tracking file ready.", log_path, activity="Run")
	start_index = int(tracking.get("last_index", -1)) + 1
	for idx in range(start_index, len(questions)):
		item = questions[idx]
		question_text = item.get("question") or item.get("query") or ""
		fallback_db = item.get("db_id") or ""
		if not question_text:
			_log(f"Skipping index {idx}: missing question text.", log_path, activity="Run")
			tracking["last_attempted"] = idx
			_save_tracking(tracking_file, tracking)
			continue
		if not fallback_db:
			_log(f"Skipping index {idx}: missing db_id.", log_path, activity="Run")
			tracking["last_attempted"] = idx
			_save_tracking(tracking_file, tracking)
			continue

		attempt = 0
		last_error = None
		retry_count = int(config.get("retry_count", 3))
		retry_wait = int(config.get("retry_wait_sec", 120))
		while attempt < retry_count:
			attempt += 1
			progress_pct = round(((idx + 1) / len(questions)) * 100.0, 2)
			_log(
				f"Index {idx} start (progress {progress_pct}%).",
				log_path,
				activity="Run",
			)
			attempt_start = _utc_now_iso()
			result, stage = _run_agents(api_key, user_id, question_text, fallback_db, config)
			attempt_end = _utc_now_iso()
			if stage == "ok" and result.get("sql"):
				# Ensure SQL is single-line (remove newlines and excessive spaces)
				sql = result.get('sql')
				if sql:
					sql = ' '.join(sql.split())
				with open(results_path, "a", encoding="utf-8") as f:
					f.write(f"{sql}\t{fallback_db}\n")
				record = {
					"index": idx,
					"db_id": fallback_db,
					"question": question_text,
					"start_time": attempt_start,
					"end_time": attempt_end,
					"final_sql": result.get("sql"),
					"final_db": result.get("database"),
					"final_tables": result.get("tables", []),
					"reasons": result.get("reasons", ""),
					"agent_a": result.get("agent_a"),
					"agent_b": result.get("agent_b"),
					"agent_c": result.get("agent_c"),
				}
				_append_complete_result(complete_result_path, record)
				tracking["last_index"] = idx
				tracking["last_attempted"] = idx
				tracking["status"] = "running"
				_save_tracking(tracking_file, tracking)
				_log(f"Completed index {idx}.", log_path, activity="Complete")
				break
			else:
				last_error = result.get("error") if isinstance(result, dict) else "unknown"
				if attempt < retry_count:
					_log(
						f"Retry {attempt}/{retry_count} failed at stage {stage}. Waiting {retry_wait} seconds...",
						log_path,
						activity="Retry",
					)
					time.sleep(retry_wait)
				else:
					_log(
						f"Failed index {idx} after {retry_count} attempts: {last_error}",
						log_path,
						activity="Fail",
					)
					tracking["last_attempted"] = idx
					tracking.setdefault("failures", []).append(
						{"index": idx, "error": last_error, "stage": stage}
					)
					_save_tracking(tracking_file, tracking)


if __name__ == "__main__":
	main()
