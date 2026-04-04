# One-Call Markdown Fact Checker (DSPy v3.0.3)

This repository contains a single-call DSPy pipeline that:
- Fact-checks all claims in a markdown article against a provided `context` file.
- Rewrites or generalizes any statements that cannot be cited.
- Emits a compact JSON change report.

## Files
- `fact_checker_one_call.py` — main script.
- `article-1` — sample article you uploaded.
- `context-1` — sample context/sources you uploaded.
- `uploaded_previews.json` — quick peek at your uploaded sources (first 5,000 chars).

## Usage
1. Install DSPy 3.0.3 and set a provider (example OpenAI shown):
```python
import dspy
dspy.settings.configure(lm=dspy.OpenAI(model="gpt-4o-mini"))
```

2. Run:
```bash
python fact_checker_one_call.py --article /mnt/data/article-1 --context /mnt/data/context-1
```

3. Outputs:
- `/mnt/data/fact_checked_article.md`
- `/mnt/data/fact_check_report.json`

### Optional: Two-stage mode (still fewer calls)
```bash
python fact_checker_one_call.py --two_stage
```

### Optional: GEPA optimization
Provide small train/dev folders with pairs named `article-1, context-1`, `article-2, context-2`, etc.
```bash
python fact_checker_one_call.py --optimize --train /path/to/train_dir --dev /path/to/dev_dir
```

This uses `dspy.GEPA` to evolve the program's prompt based on a simple automated metric (citation coverage + JSON validity).

---
**Note:** If your current environment doesn't have API keys configured, run the code where your DSPy LLM provider is set up.
