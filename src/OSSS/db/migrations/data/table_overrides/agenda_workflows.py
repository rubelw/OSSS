# table_overrides/agenda_workflows.py
import json
from __main__ import register_table_loader


@register_table_loader("agenda_workflows")
def load_agenda_workflows(table, enums, csv_rows):
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
                    seed = f"{table.name}:{idx}:{json.dumps(seed_payload, sort_keys=True)}"
                    row[col_name] = stable_uuid(seed)
                    continue

                raw_val = raw.get(col_name)

                if raw_val not in (None, ""):
                    row[col_name] = coerce_csv_value(raw_val, col)
                else:
                    if col_name == "active":
                        row[col_name] = True
                    elif col_name == "name":
                        row[col_name] = "Default school board agenda workflow"
                    else:
                        row[col_name] = sample_value(table, col, enums)

            rows.append(row)

        return rows

    # No CSV fallback
    row = {}
    for col in table.columns:
        if is_tsvector_col(col):
            continue
        if col.name == "name":
            row[col.name] = "Default school board agenda workflow"
        elif col.name == "active":
            row[col.name] = True
        else:
            row[col.name] = sample_value(table, col, enums)

    rows.append(row)
    return rows
