import json
import os
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from schema_builder import get_schema_dir


def _call_qwen(prompt: str, api_key: str, api_url: str, model: str) -> str:
    from qwen2_5_7b_instruct_api import chat_completion

    response = chat_completion(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        api_key=api_key,
        api_url=api_url,
        model=model,
        temperature=0,
    )
    return response["choices"][0]["message"]["content"]


PRODUCE_SQL_PROMPT = PromptTemplate(
    input_variables=["user_query", "db_schema_json", "selected_tables"],
    template=(
        "You are generating SQLite SQL for Spider evaluation.\n"
        "Return ONLY valid JSON with EXACTLY these keys:\n"
        '  "relevant_tables": ["..."],\n'
        '  "SQL Code": "..." ,\n'
        '  "reasons": "..." \n\n'
        "Rules for SQL (must follow strictly):\n"
        "- SQLite dialect ONLY.\n"
        "- NO aliases of any kind:\n"
        "  - No column aliases (no 'AS alias', no implicit alias).\n"
        "  - No table aliases (no 'FROM table t', no 'FROM table AS t', no 'JOIN table t').\n"
        "- Do NOT use SQL functions or expressions that wrap columns:\n"
        "  - No LOWER/UPPER/TRIM/CAST/CASE/COALESCE/SUBSTR/INSTR/POSITION/SUBSTRING.\n"
        "- Use only plain column references, aggregation functions (COUNT/SUM/AVG/MIN/MAX), "
        "basic arithmetic (+ - * /), and standard WHERE operators (=, !=, <, >, <=, >=, IN, LIKE, IS, BETWEEN).\n"
        "- Use table_name.column_name ONLY when needed to disambiguate (still no aliases).\n"
        "- Match string values exactly as given in the question or schema when possible (no case-insensitive rewriting).\n"
        "- SQL must be a single line string (no newlines).\n\n"
        "User query: {user_query}\n"
        "DB schema JSON: {db_schema_json}\n"
        "Selected tables: {selected_tables}\n"
    ),
)


def create_chain(api_key: str, model: str = "gpt-5-mini"):
    llm = ChatOpenAI(model=model, temperature=0, api_key=api_key)
    return PRODUCE_SQL_PROMPT | llm


def run(
    api_key,
    payload: dict,
    user_id: int,
    model: str = "gpt-5-mini",
    qwen_api_key: str = None,
    qwen_api_url: str = None,
):
    """
    Agent C entrypoint.
    Expected payload (from Agent B):
    {
        "query": "...",
        "database": "...",
        "relevant_tables": ["..."],
        "reasons": "..."
    }
    """
    try:
        user_query = payload.get("query")
        db_name = payload.get("database")
        selected_tables = payload.get("relevant_tables") or payload.get("tables") or []

        if not user_query:
            return {"error": "query is required"}
        if not db_name:
            return {"error": "database is required"}
        if not selected_tables:
            return {"error": "relevant_tables is required"}

        # Load schema_c.json for this user and pick entries for the selected database
        schema_dir = get_schema_dir(user_id)
        schema_file = os.path.join(schema_dir, "schema_c.json")

        db_schema_json = {}
        if os.path.exists(schema_file):
            with open(schema_file, "r", encoding="utf-8") as f:
                try:
                    all_schema = json.load(f)
                except Exception:
                    all_schema = {}
            db_schema_json = all_schema.get(db_name, {})
        else:
            return {"error": f"schema_c.json not found in {schema_dir}"}

        if "qwen" in model.lower() or qwen_api_url == "local":
            api_url = qwen_api_url or f"https://api-inference.huggingface.co/models/{model}"
            if api_url != "local" and not qwen_api_key:
                return {"error": "qwen_hf_api_key is required for Qwen model"}
            prompt = PRODUCE_SQL_PROMPT.format(
                user_query=user_query,
                db_schema_json=json.dumps(db_schema_json, ensure_ascii=False),
                selected_tables=json.dumps(selected_tables, ensure_ascii=False),
            )
            raw = _call_qwen(prompt, qwen_api_key, api_url, model)
        else:
            chain = create_chain(api_key, model=model)
            response = chain.invoke({
                "user_query": user_query,
                "db_schema_json": json.dumps(db_schema_json, ensure_ascii=False),
                "selected_tables": json.dumps(selected_tables, ensure_ascii=False),
            })

            raw = response.content if hasattr(response, "content") else str(response)

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"error": "invalid LLM output", "raw": raw}

        merged = {
            "query": user_query,
            "database": db_name,
            "relevant_tables": parsed.get("relevant_tables", selected_tables),
            "SQL": parsed.get("SQL") or parsed.get("SQL Code"),
            "reasons": parsed.get("reasons", payload.get("reasons", "")),
        }
        return merged

    except Exception as e:
        err_msg = f"Agent C failed: {str(e)}"
        print(err_msg)
        log_dir = os.environ.get("AGENT_LOG_DIR", os.getcwd())
        log_path = os.path.join(log_dir, "agent_c_error.log")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(err_msg + "\n")
        except Exception:
            pass
        return {"error": err_msg}
