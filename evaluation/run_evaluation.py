from __future__ import annotations
import subprocess
import sys
from pathlib import Path

def main() -> int:
    # --- QUICK RUN (edit these) ---
    gold   = r"C:\Users\dtt16\Desktop\CapStone\explainable-nl-query-db-agents\evaluation\spider_data\test_gold.sql"
    pred   = r"C:\Users\dtt16\Desktop\CapStone\explainable-nl-query-db-agents\evaluation\test_set_model_gpt-5-mini\predictions_model_gpt-5-mini.tsv"
    db_dir = r"C:\Users\dtt16\Desktop\CapStone\explainable-nl-query-db-agents\evaluation\spider_data\test_database"
    table  = r"C:\Users\dtt16\Desktop\CapStone\explainable-nl-query-db-agents\evaluation\spider_data\test_tables.json"
    etype  = "all"   # all | exec | match

    eval_py = Path(__file__).with_name("evaluation.py")
    cmd = [sys.executable, str(eval_py),
           "--gold", gold,
           "--pred", pred,
           "--db", db_dir,
           "--table", table,
           "--etype", etype]
    return subprocess.call(cmd)

if __name__ == "__main__":
    raise SystemExit(main())