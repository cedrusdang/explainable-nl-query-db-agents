# Evaluation (Spider Predictions)

This folder contains a chunk-based Spider prediction pipeline that uses the existing agents in `scripts`.

## How to run

Run with the default parameter file `prediction_parameters.json`:

```powershell
python -m evaluation.generate_spider_predictions
```

Or provide a custom parameter file:

```powershell
python -m evaluation.generate_spider_predictions --params evaluation/prediction_parameters.json
```

## Chunk output

Each chunk (default: 10 questions) is saved to:

- `evaluation/test_chunks/test_chuck_1`
- `evaluation/test_chunks/test_chuck_2`
- ...

Each chunk folder contains:

- `predictions.txt`: one SQL query per line
- `predictions_debug.jsonl`: per-question debug records
- `run.log`: detailed timestamped logs for latency tracking
- `summary.json`: chunk summary and suggested next start index
- `parameters.json`: copied parameter file used for that chunk

## Combine all chunks for Spider testing

After chunk generation is complete, combine all `test_chuck_*` folders into one final file:

```powershell
python -m evaluation.combine_spider_chunks
```

Optional strict validation (fails on incomplete/broken chunks):

```powershell
python -m evaluation.combine_spider_chunks --strict
```

Combine outputs:

- `evaluation/predictions_combined.txt`
- `evaluation/predictions_debug_combined.jsonl`
- `evaluation/combine_report.json`

## Retry and safe stop

- If a question fails at any step, the script retries based on `max_retries`
- If it still fails after retries, the run stops immediately at that chunk
- All logs and output files for the chunk are still saved before stopping

## Prerequisites

1. Test data exists at `data/test/spider_query_answers.json` (or another path in params)
2. Required schema/embeddings exist for the current pipeline
3. `OPENAI_API_KEY` is set in the environment
