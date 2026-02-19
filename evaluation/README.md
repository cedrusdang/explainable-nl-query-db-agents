# Evaluation (Spider Predictions)

This folder contains a chunk-based Spider prediction pipeline that uses the notebook-style Agent A/B plus Agent C.

## How to run

Run with the default parameter file `prediction_parameters.json` (the script will prompt for dataset and range):

```powershell
python -m evaluation.generate_spider_predictions
```

Or provide a custom parameter file:

```powershell
python -m evaluation.generate_spider_predictions --params evaluation/prediction_parameters.json
```

## Chunk output

Each chunk (default: 10 questions) is saved under:

- `evaluation/predict_results/Train_predict_results/test_chuck_1`
- `evaluation/predict_results/Dev_predict_results/test_chuck_1`
- `evaluation/predict_results/Test_predict_results/test_chuck_1`

Each chunk folder contains:

- `predictions.txt`: one SQL query per line
- `predictions_debug.jsonl`: per-question debug records
- `run.log`: detailed timestamped logs for latency tracking
- `summary.json`: chunk summary and suggested next start index
- `parameters.json`: copied parameter file used for that chunk

## Combine all chunks for Spider testing

After chunk generation is complete, combine all `test_chuck_*` folders for the chosen dataset:

```powershell
python -m evaluation.combine_spider_chunks
```

Optional strict validation (fails on incomplete/broken chunks):

```powershell
python -m evaluation.combine_spider_chunks --strict
```

Combine outputs (saved in the same dataset folder):

- `predictions_combined.txt`
- `predictions_debug_combined.jsonl`
- `combine_report.json`

## Retry and safe stop

- If a question fails at any step, the script retries based on `max_retries`
- If it still fails after retries, the run stops immediately at that chunk
- All logs and output files for the chunk are still saved before stopping

## Evaluate EX/EM

Run the evaluator (it will prompt for dataset type and paths if you do not pass args):

```powershell
python -m evaluation.evaluation
```

## Prerequisites

1. Spider dataset exists in `evaluation/spider_data` (train/dev/test/tables.json)
2. `OPENAI_API_KEY` is set in the environment
3. `OPENAI_API_KEY` is set in the environment
