import os
import json
from django.conf import settings
from .sql_connector import SQLiteConnector

SCHEMA_DIR = settings.SCHEMA_DIR
os.makedirs(SCHEMA_DIR, exist_ok=True)


def schema_extractor(db_name: str):
    """
    Extract schema (tables, columns, PK, FK) for one SQLite database.
    """
    connector = SQLiteConnector()

    # Get table names
    res_tables = connector.execute(db_name, "SELECT name FROM sqlite_master WHERE type='table';")
    if "error" in res_tables:
        return res_tables
    table_names = res_tables["result"]

    schema = {"tables": {}}

    for table_dict in table_names:
        table_name = table_dict["name"]

        # Columns + PK
        res_cols = connector.execute(db_name, f"PRAGMA table_info({table_name});")
        if "error" in res_cols:
            return res_cols
        cols_raw = res_cols["result"]
        columns = [col["name"] for col in cols_raw]
        pk_cols = [col["name"] for col in cols_raw if col["pk"]]

        # FKs
        res_fks = connector.execute(db_name, f"PRAGMA foreign_key_list({table_name});")
        if "error" in res_fks:
            return res_fks
        fks_raw = res_fks["result"]
        fk_list = [
            {"from_column": fk["from"], "ref_table": fk["table"], "ref_column": fk["to"]}
            for fk in fks_raw
        ]

        schema["tables"][table_name] = {
            "columns": columns,
            "primary_key": pk_cols,
            "foreign_keys": fk_list,
        }

    return schema


def build_schema_ab(sql_file_paths: str):
    """
    Build schema for Agent A/B (flat JSONL with {db, table, columns}).
    Save as schema_ab.jsonl and wipe old embeddings.
    """
    # --- reset embeddings folder to avoid stale data ---
    embeddings_folder = os.path.join(SCHEMA_DIR, "embeddings")
    if os.path.exists(embeddings_folder):
        for f in os.listdir(embeddings_folder):
            os.remove(os.path.join(embeddings_folder, f))
        os.rmdir(embeddings_folder)

    json_sql = json.loads(sql_file_paths)
    lines = []

    for db_name in json_sql:
        schema = schema_extractor(db_name)
        if "error" in schema:
            return schema
        for table, info in schema["tables"].items():
            obj = {
                "database": db_name,
                "table": table,
                "columns": info.get("columns", []),
            }
            lines.append(json.dumps(obj, ensure_ascii=False))

    out_path = os.path.join(SCHEMA_DIR, "schema_ab.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return {"file": out_path, "count": len(lines), "embeddings": "reset"}



def build_schema_c(sql_file_paths: str):
    """
    Build schema for Agent C (nested JSON {db: {tables: {...}}}).
    Save as schema_c.json
    """
    json_sql = json.loads(sql_file_paths)
    combined_schema = {}

    for db_name in json_sql:
        schema = schema_extractor(db_name)
        if "error" in schema:
            return schema
        combined_schema[db_name] = schema

    out_path = os.path.join(SCHEMA_DIR, "schema_c.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(combined_schema, f, indent=4, ensure_ascii=False)

    return {"file": out_path, "databases": list(combined_schema.keys())}


def run(request, media_path: str):
    """
    Django endpoint for schema build.

    Expected request.data:
    {
        "sql_file_paths": "{ 'db1': 'path/to/file', ... }",
        "version": "ab" | "c"
    }
    """
    try:
        data = request.data
        sql_file_paths = data.get("sql_file_paths", "{}")
        version = data.get("version", "").lower()

        if not sql_file_paths:
            return {"error": "sql_file_paths is required"}
        if version not in ("ab", "c"):
            return {"error": "version must be 'ab' or 'c'"}

        if version == "ab":
            result = build_schema_ab(sql_file_paths)
        else:  # version == "c"
            result = build_schema_c(sql_file_paths)

        return {"success": True, "version": version, **result}

    except Exception as e:
        return {"error": f"Schema build failed: {str(e)}"}
