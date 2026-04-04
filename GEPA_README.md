
# GEPA Train/Dev Example Sets

This folder contains paired markdown **articles** and text **contexts** for optimizing the one-call fact checker with **DSPy GEPA**.

- Train dir: `/mnt/data/gepa_train`
- Dev dir: `/mnt/data/gepa_dev`

## Filenames
Pairs use `article-N.md` and `context-N.txt`. Your loader matches by the `N` index.

## Intent
Each article contains: 
- specific numeric claims to *support or generalize*; and
- plain-language context with ranges/notes your model must cite (or generalize when evidence is missing).

Use:
```bash
python /mnt/data/fact_checker_one_call.py --optimize --train /mnt/data/gepa_train --dev /mnt/data/gepa_dev
```

The script’s metric rewards:
- higher share of factual sentences that are either cited or generalized; and
- valid JSON change report output.
