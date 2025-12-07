
# table_overrides/user_profiles.py
import json
from __main__ import register_table_loader


@register_table_loader("user_profiles")
def load_user_profiles(table, enums, csv_rows):
    """
    Load user_profiles table with proper handling of:
    - Integer primary key (id)
    - UUID foreign key (user_id)
    - Boolean flags (is_teacher, is_student)
    - Email and photo URL fields
    """
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

                # 🔑 Handle integer primary key - use CSV value directly
                if col_name == "id" and not is_uuid_col(col):
                    row[col_name] = int(raw.get(col_name, idx + 1))
                    continue

                # 🔑 Handle UUID foreign key (user_id)
                if col_name == "user_id" and is_uuid_col(col):
                    raw_val = raw.get(col_name)
                    if raw_val and raw_val not in (None, ""):
                        row[col_name] = coerce_csv_value(raw_val, col)
                    else:
                        # Generate stable UUID if missing
                        seed = f"{table.name}:{idx}:user_id"
                        row[col_name] = stable_uuid(seed)
                    continue

                raw_val = raw.get(col_name)

                if raw_val not in (None, ""):
                    # Use CSV value when present
                    row[col_name] = coerce_csv_value(raw_val, col)
                else:
                    # Generic reasonable defaults
                    if col_name == "is_teacher":
                        row[col_name] = False
                    elif col_name == "is_student":
                        row[col_name] = True
                    elif col_name == "full_name":
                        row[col_name] = f"User {idx + 1}"
                    elif col_name == "primary_email":
                        row[col_name] = f"user{idx + 1}@school.edu"
                    elif col_name == "photo_url":
                        row[col_name] = f"https://storage.school.edu/photos/user{idx + 1}.jpg"
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

        if col_name == "id" and not is_uuid_col(col):
            row[col_name] = 1
        elif col_name == "user_id" and is_uuid_col(col):
            seed = f"{table.name}:default:user_id"
            row[col_name] = stable_uuid(seed)
        elif col_name == "is_teacher":
            row[col_name] = False
        elif col_name == "is_student":
            row[col_name] = True
        elif col_name == "full_name":
            row[col_name] = "Sample User"
        elif col_name == "primary_email":
            row[col_name] = "sample.user@school.edu"
        elif col_name == "photo_url":
            row[col_name] = "https://storage.school.edu/photos/sample.jpg"
        else:
            row[col_name] = sample_value(table, col, enums)

    rows.append(row)
    return rows