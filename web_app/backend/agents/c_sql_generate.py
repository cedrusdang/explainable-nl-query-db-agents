import json
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate


def create_chain(api_key: str):
    llm = ChatOpenAI(model="gpt-5-mini", temperature=0, api_key=api_key)

    produce_sql_prompt = PromptTemplate(
        input_variables=["user_query", "db_schema_json", "selected_tables"],
        template=(
            "Given the selected database schema and selected table names, return ONLY valid JSON:\n"
            "{{\n"
            '  "relevant_tables": ["..."],\n'
            '  "SQL": "...",\n'
            '  "reasons": "..." \n'
            "}}\n\n"
            "User query: {user_query}\n"
            "DB schema JSON: {db_schema_json}\n"
            "Selected tables: {selected_tables}\n"
        ),
    )
    return produce_sql_prompt | llm


def run(api_key, payload: dict):
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
        selected_tables = payload.get("relevant_tables", [])

        if not user_query:
            return {"error": "query is required"}
        if not db_name:
            return {"error": "database is required"}
        if not selected_tables:
            return {"error": "relevant_tables is required"}

        db_schema_json = {
            "database": db_name,
            "tables": selected_tables,
        }

        chain = create_chain(api_key)
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

        # merge payload with new keys
        merged = {
            "query": user_query,
            "database": db_name,
            "relevant_tables": parsed.get("relevant_tables", selected_tables),
            "SQL": parsed.get("SQL") or parsed.get("SQL Code"),
            "reasons": parsed.get("reasons", payload.get("reasons", "")),
        }
        return merged

    except Exception as e:
        return {"error": f"Agent C failed: {str(e)}"}
