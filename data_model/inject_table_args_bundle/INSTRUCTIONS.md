# Inject `__table_args__` comments into your models

**What this does**
- Inserts or updates `__table_args__ = {"comment": "..."}`
  right after `__tablename__` for each model, merging with any
  existing `__table_args__` kwargs (constraints remain intact).
- Comment is built from `table_comments.json`: a description and
  a list of school positions (comma-separated).

**Dry-run**
```bash
python3 inject_table_args.py --models-dir /absolute/path/to/OSSS/src/OSSS/db/models --mapping table_comments.json
```

**Write changes + produce a zip of changed files**
```bash
python3 inject_table_args.py --models-dir /absolute/path/to/OSSS/src/OSSS/db/models --mapping table_comments.json --write
# => changed_models_with_table_args.zip
```

**Customize**
Edit `table_comments.json` to refine per-table text and positions.
