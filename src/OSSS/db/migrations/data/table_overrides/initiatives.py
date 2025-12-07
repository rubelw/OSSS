# table_overrides/initiatives.py
import json
from __main__ import register_table_loader


@register_table_loader("initiatives")
def load_initiatives(table, enums, csv_rows):
    # Lazy import helpers so they exist by the time this runs
    from __main__ import (
        is_tsvector_col,
        is_uuid_col,
        stable_uuid,
        coerce_csv_value,
        sample_value,
    )

    rows = []

    if csv_rows:
        for idx, raw in enumerate(csv_rows):
            row = {}

            for col in table.columns:
                if is_tsvector_col(col):
                    continue

                col_name = col.name

                # 🔑 Always generate UUID for `id`, ignore CSV id entirely
                if col_name == "id" and is_uuid_col(col):
                    seed_payload = {k: v for k, v in raw.items() if k != "id"}
                    seed = f"{{table.name}}:{{idx}}:{{json.dumps(seed_payload, sort_keys=True)}}"
                    row[col_name] = stable_uuid(seed)
                    continue

                raw_val = raw.get(col_name)

                if raw_val not in (None, ""):
                    # Use CSV value when present
                    row[col_name] = coerce_csv_value(raw_val, col)
                else:
                    # Generic reasonable defaults
                    if col_name == "active":
                        row[col_name] = True
                    elif col_name == "name":
                        row[col_name] = "Sample initiatives"
                    elif col_name.endswith("_name"):
                        row[col_name] = f"Sample {{col_name.replace('_', ' ')}}"
                    else:
                        row[col_name] = sample_value(table, col, enums)

            rows.append(row)

        return rows

    # No CSV fallback — synthesize a single sample row
    row = {}
    for col in table.columns:
        if is_tsvector_col(col):
            continue

        col_name = col.name

        if col_name == "id" and is_uuid_col(col):
            seed = f"{{table.name}}:default"
            row[col_name] = stable_uuid(seed)
        elif col_name == "active":
            row[col_name] = True
        elif col_name == "name":
            row[col_name] = "Sample initiatives"
        elif col_name.endswith("_name"):
            row[col_name] = f"Sample {{col_name.replace('_', ' ')}}"
        else:
            row[col_name] = sample_value(table, col, enums)

    rows.append(row)
    return rows
