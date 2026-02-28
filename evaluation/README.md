# Evaluation

This folder includes the schema builders, agents, and a CLI (Predicting.py) to build schemas and run agent-based SQL generation for Spider-style question files.

## Step-by-step Guide (Evaluation Folder)

### 1) Open a terminal in the evaluation folder
```
cd evaluation
```

### 2) (Optional) Create and activate a virtual environment
Windows (PowerShell):
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:
```
python3 -m venv .venv
source .venv/bin/activate
```

### 3) Install dependencies for this folder
```
python -m pip install -r requirements.txt
```

### 4) Run the CLI (Predicting.py)
```
python Predicting.py
```

### 5) Answer the prompts
You will be asked for:
0. Whether to initialize Qwen once (optional test call).
1. Data folder path (must contain .sqlite or .db files).
2. Test name (for example: train, dev, test). Default is "default".
3. Model choice (1=ChatGPT 5 mini, 2=Qwen 2.5 7B).
4. If Qwen is selected, choose mode (1=Local, 2=HF API cloud).
5. Spider question file path (for example: dev.json).
6. Whether to continue from an existing tracking file.

### Output Location
All outputs are under your current working directory (folder name includes the model tag):

```
<cwd>/<test_name>_model_<model_tag>/schema/schema_ab.jsonl
<cwd>/<test_name>_model_<model_tag>/schema/schema_c.json
<cwd>/<test_name>_model_<model_tag>/predictions_model_<model_tag>.tsv
<cwd>/<test_name>_model_<model_tag>/tracking_process_model_<model_tag>/progress.json
<cwd>/<test_name>_model_<model_tag>/log_<model_tag>.txt
<cwd>/<test_name>_model_<model_tag>/config_model_<model_tag>.json
```

If schema files already exist, the script will ask whether to rebuild them or reuse the existing ones. When reusing, it continues to the next steps.

### Predictions Format (Spider Evaluation)
The predictions file is written in Spider evaluation format:

```
<SQL>\t<db_id>
```

One line per question. This matches the expected input format for evaluation scripts that read prediction lines as `SQL<TAB>db_id`.

### Logging and Tracking
- Every action is printed to the shell and appended to `log_<model_tag>.txt` with an ISO timestamp and activity tag.
- `progress.json` tracks progress so you can continue after an interruption.

### Config (config.json)
The script reads settings from `config_model_<model_tag>.json` in the test folder. Edit this file to change parameters for future runs:

```
{
   "agent_a_model": "gpt-5-mini",
   "agent_a_top_k": 5,
   "embedding_backend": "openai",
   "embedding_model": "ssmits/Qwen2.5-7B-embed-base",
   "qwen_api_url": "local",
   "retry_count": 3,
   "retry_wait_sec": 120
}
```

### Qwen2.5 (Hugging Face Inference API)
There is a separate script for Qwen to behave like a ChatGPT-style API (messages[] role/content):

```
python qwen2_5_7b_instruct_api.py --messages messages.json --config <cwd>/<test_name>_model_<model_tag>/config_model_<model_tag>.json
```

Example `messages.json`:
```
[
   {"role": "system", "content": "You are a helpful assistant."},
   {"role": "user", "content": "Say hello."}
]
```

Config keys (same file `config.json`). For local Qwen, set `qwen_api_url` to `local`. For HF API, set `HUGGINGFACEHUB_API_TOKEN` in your `.env`:
```
{
   "qwen_hf_api_key": "<HF_TOKEN>",
   "qwen_api_url": "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-7B-Instruct",
   "qwen_model": "Qwen/Qwen2.5-7B-Instruct"
}

Local mode example:
```
{
   "qwen_api_url": "local",
   "qwen_model": "Qwen/Qwen2.5-7B-Instruct"
}
```

Local mode requires enough RAM/GPU to load the model.

Unsupported ChatGPT fields (ignored with a warning):
`stop`, `logprobs`, `top_logprobs`, `frequency_penalty`, `presence_penalty`, `n`,
`response_format`, `tools`, `tool_choice`, `seed`, `stream`.

### Qwen2.5 Embeddings (Local)
Embeddings are handled by a separate local script:

```
python qwen2_5_7b_embed_base_embedding.py --texts texts.json
```

Example `texts.json`:
```
[
   "table: singer, columns: name, age",
   "table: stadium, columns: location, capacity"
]
```

### 6) Evaluate later (optional)
If you want to evaluate predictions using the Spider evaluation script:

```
python evaluation.py \
   --gold spider_data/dev_gold.sql \
   --pred <cwd>/<test_name>_model_<model_tag>/predictions_model_<model_tag>.tsv \
   --db spider_data/database \
   --table spider_data/tables.json \
   --etype all
```

Replace `dev_gold.sql` with the correct gold file for your split.

### Example (Windows)
```
Data folder path: C:\Users\dtt16\Desktop\CapStone\explainable-nl-query-db-agents\evaluation\spider_data\database
Test name (default: default): dev
```

Result:
```
C:\Users\dtt16\Desktop\CapStone\explainable-nl-query-db-agents\dev_model_gpt-5-mini\schema\schema_ab.jsonl
C:\Users\dtt16\Desktop\CapStone\explainable-nl-query-db-agents\dev_model_gpt-5-mini\schema\schema_c.json
C:\Users\dtt16\Desktop\CapStone\explainable-nl-query-db-agents\dev_model_gpt-5-mini\predictions_model_gpt-5-mini.tsv
C:\Users\dtt16\Desktop\CapStone\explainable-nl-query-db-agents\dev_model_gpt-5-mini\tracking_process_model_gpt-5-mini\progress.json
C:\Users\dtt16\Desktop\CapStone\explainable-nl-query-db-agents\dev_model_gpt-5-mini\log_gpt-5-mini.txt
C:\Users\dtt16\Desktop\CapStone\explainable-nl-query-db-agents\dev_model_gpt-5-mini\config_model_gpt-5-mini.json
```
