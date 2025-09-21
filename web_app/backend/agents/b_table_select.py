import json
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate


def create_chain(api_key: str):
    llm = ChatOpenAI(model="gpt-5-mini", temperature=0, api_key=api_key)

    list_tables_prompt = PromptTemplate(
        input_variables=["user_query", "db_schema_json"],
        template=(
            "Given the selected database schema, return ONLY valid JSON:\n"
            "{{\n"
            '  "relevant_tables": ["..."],\n'
            '  "reasons": "..." \n'
            "}}\n\n"
            "User query: {user_query}\n"
            "DB schema JSON: {db_schema_json}\n"
        ),
    )
    return list_tables_prompt | llm


def run(api_key, payload: dict):
    """
    Agent B entrypoint.
    Expects payload from Agent A:
    {
        "query": "...",
        "database": "...",
        "tables": ["..."],
        "columns": ["..."],
        "reasons": "..."
    }
    """
    try:
        user_query = payload.get("query")
        db_name = payload.get("database")

        if not user_query:
            return {"error": "query is required"}
        if not db_name:
            return {"error": "database is required"}

        db_schema_json = {
            "tables": payload.get("tables", []),
            "columns": payload.get("columns", []),
        }

        chain = create_chain(api_key)
        response = chain.invoke({
            "user_query": user_query,
            "db_schema_json": json.dumps(db_schema_json, ensure_ascii=False)
        })
        raw = response.content if hasattr(response, "content") else str(response)

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"error": "invalid LLM output", "raw": raw}

        # Merge Agent A’s payload with Agent B’s findings
        merged = {
            "query": user_query,
            "database": db_name,
            "tables": payload.get("tables", []),
            "columns": payload.get("columns", []),
            "relevant_tables": parsed.get("relevant_tables", []),
            "reasons": parsed.get("reasons", ""),
        }
        return merged

    except Exception as e:
        return {"error": f"Agent B failed: {str(e)}"}
