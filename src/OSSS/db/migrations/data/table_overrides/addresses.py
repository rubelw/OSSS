# table_overrides/addresses.py
import json
from __main__ import register_table_loader


@register_table_loader("addresses")
def load_addresses(
    table,
    enums,
    csv_rows,
):
    # Import helpers lazily so they exist by now
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
                    row[col_name] = sample_value(table, col, enums)

            rows.append(row)

        return rows

    # Fallback if no CSV
    row = {}
    for col in table.columns:
        if is_tsvector_col(col):
            continue
        row[col.name] = sample_value(table, col, enums)
    rows.append(row)
    return rows
