#!/usr/bin/env python3
"""
Agent B: Table and Column Selector

Selects relevant tables and columns from a database based on a user query.
Used after Agent A picks the database.

USAGE:
    python3 -m src.agents.agent_b
    # or
    from src.agents.agent_b import agent_b
    result = agent_b("How many students are enrolled?", "college_2", mode="medium")

MODES:
    - "light": Only tables and columns
    - "medium": Includes query, database, tables, columns, reasons
    - "heavy": Adds full schema and raw LLM response

Depends on processed schemas and OpenAI API.

Example output:
{
    "User Query": "How many students are enrolled?",
    "Database Name": "college_2",
    "Tables": ["student", "enrollment"],
    "Columns": ["student_id", "name", "enrollment_date"],
    "Reasons": "Student table contains enrollment data..."
}
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Union

# Import project config
from src.config import PROJECT_ROOT, SCHEMA_PROCESSED_FILE

# Add project root to Python path
sys.path.append(str(PROJECT_ROOT))

# Import LangChain components
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate


# --- 1.1 Setup ---
def setup_llm():
    """Initialize and return the LLM for table/column selection"""
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        return llm
    except Exception as e:
        print(f"Error setting up LLM: {e}")
        return None


# --- 1.2 Prompt Template ---
list_tables_prompt = PromptTemplate(
    input_variables=["user_query", "db_schema_json"],
    template="""
Given the relevant database schema, return the tables and columns that are most relevant to the user's query.

User query: {user_query}
DB schema JSON: {db_schema_json}

Respond ONLY with a valid JSON object (no extra text, no backticks). 
The JSON must include the following keys: "relevant_tables", "relevant_columns", and "reasons". 

Example format (output must match this structure exactly): 

{{
  "relevant_tables": ["table1", "table2"],
  "relevant_columns": ["column1", "column2", "column3"],
  "reasons": "Explanation of why these tables and columns are relevant to the query"
}}

Do not include any text outside the JSON object.
""",
)


# --- 1.3 Main Agent Function ---
def agent_b(user_query: str, db_name: str, mode: str = "medium") -> Dict[str, Any]:
    """
    Select relevant tables and columns from a database schema based on a user query.

    Args:
        user_query (str): The natural language question to answer
        db_name (str): Name of the database (selected by Agent A)
        mode (str): Output mode - "light", "medium", or "heavy"

    Returns:
        Dict[str, Any]: Structured selection results based on mode

    Raises:
        ValueError: If mode is not one of the supported options
        FileNotFoundError: If processed schema file doesn't exist
        json.JSONDecodeError: If LLM response is not valid JSON
    """

    # Setup LLM
    llm = setup_llm()
    if llm is None:
        return {"error": "Failed to setup LLM"}

    # Create chain
    db_chain = list_tables_prompt | llm

    try:
        # Load schema lines
        if not SCHEMA_PROCESSED_FILE.exists():
            raise FileNotFoundError(
                f"Processed schema file not found: {SCHEMA_PROCESSED_FILE}"
            )

        with open(SCHEMA_PROCESSED_FILE, "r", encoding="utf-8") as f:
            schema_lines = f.readlines()

        # Parse JSON lines and filter for the selected database
        full_schema = []
        for line in schema_lines:
            try:
                parsed_line = json.loads(line.strip())
                if parsed_line.get("database") == db_name:
                    full_schema.append(parsed_line)
            except json.JSONDecodeError:
                continue  # Skip invalid JSON lines

        if not full_schema:
            return {"error": f"No schema found for database: {db_name}"}

        # Run LLM
        response = db_chain.invoke(
            {"user_query": user_query, "db_schema_json": full_schema}
        )

        # Parse LLM output into dict
        llm_selection_content = (
            response.content if hasattr(response, "content") else str(response)
        )

        try:
            parsed = json.loads(llm_selection_content)
        except json.JSONDecodeError as e:
            return {
                "error": f"Failed to parse LLM response as JSON: {e}",
                "raw_response": llm_selection_content,
            }

        # Return based on mode
        if mode == "light":
            return {
                "Tables": parsed.get("relevant_tables", []),
                "Columns": parsed.get("relevant_columns", []),
            }

        elif mode == "medium":
            return {
                "User Query": user_query,
                "Database Name": db_name,
                "Tables": parsed.get("relevant_tables", []),
                "Columns": parsed.get("relevant_columns", []),
                "Reasons": parsed.get("reasons", ""),
            }

        elif mode == "heavy":
            return {
                "User Query": user_query,
                "Database Name": db_name,
                "Full Schema": full_schema,
                "Tables": parsed.get("relevant_tables", []),
                "Columns": parsed.get("relevant_columns", []),
                "Reasons": parsed.get("reasons", ""),
                "Raw LLM Response": response,
            }

        else:
            raise ValueError(
                f"Unknown mode: {mode}. Must be 'light', 'medium', or 'heavy'"
            )

    except Exception as e:
        return {"error": f"Error in agent_b: {str(e)}"}


# --- 1.4 Test Function ---
def test_agent_b():
    """Test the Agent B with sample queries"""
    print("=" * 60)
    print("TESTING AGENT B: TABLE AND COLUMN SELECTOR")
    print("=" * 60)

    # Test queries with different databases
    test_cases = [
        {
            "query": "How many heads of the departments are older than 56?",
            "db_name": "department_management",
            "mode": "medium",
        },
        {
            "query": "What are the names of all students enrolled in computer science?",
            "db_name": "college_2",
            "mode": "light",
        },
        {
            "query": "Show me information about singers and their concerts",
            "db_name": "music_1",
            "mode": "heavy",
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['query']}")
        print(f"Database: {test_case['db_name']}")
        print(f"Mode: {test_case['mode']}")
        print("-" * 50)

        result = agent_b(test_case["query"], test_case["db_name"], test_case["mode"])

        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            # Pretty print the result, using json.dumps for complex values
            for key, value in result.items():
                if isinstance(value, (dict, list)):
                    pretty_value = json.dumps(value, indent=2, ensure_ascii=False)
                    print(f"{key}: {pretty_value}")
                else:
                    print(f"{key}: {value}")

        print("\n" + "=" * 60)


# --- 1.5 Main Execution ---
if __name__ == "__main__":
    # Check if processed schemas exist
    if not SCHEMA_PROCESSED_FILE.exists():
        print("Error: Processed schema file not found!")
        print("Please run: python3 -m scripts.process_schemas")
        sys.exit(1)

    # Run tests
    test_agent_b()
