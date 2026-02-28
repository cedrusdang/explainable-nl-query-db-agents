from __future__ import annotations
import subprocess
import sys
from pathlib import Path
import datetime
import os

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

    result = subprocess.run(cmd, capture_output=True, text=True)
    # Get base name of prediction file
    pred_base = os.path.splitext(os.path.basename(pred))[0]
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    out_name = f"eval_{pred_base}_{timestamp}.txt"
    out_path = os.path.join(os.path.dirname(pred), out_name)
    # Print results to shell
    print(result.stdout)
    if result.stderr:
        print("--- STDERR ---")
        print(result.stderr)
    # Save results to file
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result.stdout)
        if result.stderr:
            f.write("\n--- STDERR ---\n")
            f.write(result.stderr)
    print(f"Evaluation results saved to: {out_path}")
    return result.returncode

if __name__ == "__main__":
    raise SystemExit(main())