# table_overrides/guardian_invitations.py
import json
from __main__ import register_table_loader


@register_table_loader("guardian_invitations")
def load_guardian_invitations(table, enums, csv_rows):
    """
    Load guardian_invitations table with proper handling of:
    - UUID primary key (id)
    - UUID foreign key (user_id)
    - Integer foreign key (student_user_id)
    - Enum state (GuardianInvitationState)
    - Email field
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

                # 🔑 Always generate UUID for `id`, ignore CSV id entirely
                if col_name == "id" and is_uuid_col(col):
                    seed_payload = {k: v for k, v in raw.items() if k != "id"}
                    seed = f"{table.name}:{idx}:{json.dumps(seed_payload, sort_keys=True)}"
                    row[col_name] = stable_uuid(seed)
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

                # 🔑 Handle integer foreign key (student_user_id)
                if col_name == "student_user_id":
                    raw_val = raw.get(col_name)
                    if raw_val and raw_val not in (None, ""):
                        row[col_name] = int(raw_val)
                    else:
                        # Default to first student
                        row[col_name] = 1
                    continue

                raw_val = raw.get(col_name)

                if raw_val not in (None, ""):
                    # Use CSV value when present
                    row[col_name] = coerce_csv_value(raw_val, col)
                else:
                    # Generic reasonable defaults
                    if col_name == "state":
                        # Default to PENDING state
                        row[col_name] = "PENDING"
                    elif col_name == "invited_email":
                        row[col_name] = f"guardian{idx + 1}@email.com"
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
            seed = f"{table.name}:default"
            row[col_name] = stable_uuid(seed)
        elif col_name == "user_id" and is_uuid_col(col):
            seed = f"{table.name}:default:user_id"
            row[col_name] = stable_uuid(seed)
        elif col_name == "student_user_id":
            row[col_name] = 1
        elif col_name == "state":
            row[col_name] = "PENDING"
        elif col_name == "invited_email":
            row[col_name] = "sample.guardian@email.com"
        else:
            row[col_name] = sample_value(table, col, enums)

    rows.append(row)
    return rows