from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0110"
down_revision = "0109"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "student_school_enrollments"

# Inline seed data
ROWS = [
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-02",
        "status": "WITHDRAWN",
        "exit_reason": "student_school_enrollments_exit_reason_1",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "b5d48cb6-b1ff-589e-8a03-ff809c4108d7",
    },
    {
        "student_id": "c69e40d1-eeb3-5ecd-bd7d-46b2543ac349",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-03",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_2",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "e58efdc6-8e58-5d15-b0cc-a6e30c8bfe69",
    },
    {
        "student_id": "244b09b8-8606-55df-8c29-140225ec31b2",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-04",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_3",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "8d5433be-5daa-58ae-97fd-df1a259d1fd2",
    },
    {
        "student_id": "76a9f47b-bfec-5243-8de4-5988f209feb7",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-05",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_4",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "c0bb77ef-b1c0-51bd-8c2a-53906a9a6b44",
    },
    {
        "student_id": "8606c02c-5baa-5b51-9b0c-9cd1bb5fe832",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-06",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_5",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "f236729b-6cf7-5071-ba55-d96c7336f6dd",
    },
    {
        "student_id": "2b779574-bfed-556c-8ce5-9e62cc73025f",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-07",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_6",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "d74e006b-fd5c-5112-a659-874a5b824a23",
    },
    {
        "student_id": "a3eaf728-caaf-5ff6-8e3c-cd6b512df107",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-08",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_7",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "e5559257-2411-5891-b3bb-af9993c6e1ee",
    },
    {
        "student_id": "0e43dc79-c2a4-5c7d-8016-21414e6de33b",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-09",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_8",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "c6e462eb-bef6-5020-bbc3-0dac180338d2",
    },
    {
        "student_id": "938e519e-e267-5750-8a66-5042e402aee4",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-10",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_9",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "843f73c0-a04b-5ea1-bf5b-608fef804ac4",
    },
    {
        "student_id": "4a2214a1-44a5-570f-8471-4ed19fc1599b",  # STU0010
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-11",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_10",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "765e43e9-e9de-4d84-8189-85ef24544253",
    },
    {
        "student_id": "b01bb891-24d3-570c-af91-53fe613ae196",  # STU0011
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-12",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_11",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "f46ec2c3-41fc-41e8-bb2d-dcd81f113978",
    },
    {
        "student_id": "ef91495c-164c-5ddb-b295-335d72682832",  # STU0012
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-13",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_12",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "d8a0dfd6-b342-4586-ab64-13760e25763e",
    },
    {
        "student_id": "f3382e77-e831-5dcf-9245-8b7f5e066e47",  # STU0013
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-14",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_13",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "68c4ee72-ff64-444b-96c6-1fac78ae1303",
    },
    {
        "student_id": "243c331c-4187-5fc3-a753-8507ae672faf",  # STU0014
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-15",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_14",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "2ef5e0a3-60c4-4970-87c4-df72c6765745",
    },
    {
        "student_id": "873413a0-5c8e-525a-87cd-a28ce74d588c",  # STU0015
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-16",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_15",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "b48b5694-5b83-4ef6-ab30-87d39c29b19d",
    },
    {
        "student_id": "d118e568-a365-59f5-8427-ee23dbffba8d",  # STU0016
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-17",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_16",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "2ec601b3-943e-4d9e-89ba-3ba77973185d",
    },
    {
        "student_id": "c7b7b486-2fd7-52f5-b454-98bb1848f523",  # STU0017
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-18",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_17",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "08ef903e-82d5-4bc9-b479-c3ab496b0db2",
    },
    {
        "student_id": "e940a7d2-e5fa-5d70-8e5c-775d38fb5ac2",  # STU0018
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-19",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_18",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "de2335a4-2b10-4b93-ada1-b5ab6ec59405",
    },
    {
        "student_id": "5d0f6db8-b7f9-5abb-b987-7cf9108f2786",  # STU0019
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-20",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_19",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "111e900c-0247-45b2-a05d-1ef44d0e9389",
    },
    {
        "student_id": "e708eec0-67d0-5cc5-9072-c557c702e17e",  # STU0020
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-21",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_20",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "f5fd4e9d-fcb1-448f-8214-48b431bf6012",
    },
    {
        "student_id": "31f5a3ca-2d95-554a-aca1-133d1fb6b801",  # STU0021
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-22",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_21",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "b7bfbea6-410e-4f12-9549-8502e63a7e43",
    },
    {
        "student_id": "f7e1a4da-5ab8-53c9-bfae-486e3ce17996",  # STU0022
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-23",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_22",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "e83f283d-8956-404e-a1e0-75f17310656a",
    },
    {
        "student_id": "b764d434-5af3-54c8-b0fd-98455c00902d",  # STU0023
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-24",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_23",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "7367d137-b533-4e0c-bdeb-447e83cf7120",
    },
    {
        "student_id": "3ed705a2-f42c-550a-a203-b744278d9a67",  # STU0024
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-25",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_24",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "59963228-109a-45fe-b46a-d622a5407aa2",
    },
    {
        "student_id": "6fcdb723-443f-5ef6-b747-0da6e15a2929",  # STU0025
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-26",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_25",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "bda37cf5-c6c2-4c63-8191-8a5a72d578e9",
    },
    {
        "student_id": "9431f538-cf40-5512-a032-eb9a1642f494",  # STU0026
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-27",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_26",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "b4c0baf7-cfac-49ce-9acf-679af11acd11",
    },
    {
        "student_id": "f8032d9f-f1b7-53db-bbf4-9838d331c2b4",  # STU0027
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-28",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_27",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "756635f0-1806-433e-98e3-0221ef8b0f45",
    },
    {
        "student_id": "87d1678a-5117-5b0a-87d9-001c72c9135d",  # STU0028
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-29",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_28",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "ff2cfdab-65ac-4203-836c-6b2e916f3dea",
    },
    {
        "student_id": "538483fc-c5b9-5a08-a634-be26e3923bea",  # STU0029
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-30",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_29",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "67d9f6a3-0ec2-45a0-aaed-4357206ac63c",
    },
    {
        "student_id": "6b3638aa-2a58-58f8-b860-57262708cb69",  # STU0030
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-31",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_30",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "477898cf-f0d7-41a2-91fd-0a5cde4b2405",
    },
    {
        "student_id": "09a8b3a1-8f23-5856-a57a-78c0930c0d40",  # STU0031
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-02-01",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_31",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "32ff04e2-c186-4fff-83be-50e82ae3a310",
    },
    {
        "student_id": "db0dc5de-2e18-576e-a3ea-152b301cced5",  # STU0032
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-02-02",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_32",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "b410bbd8-45cd-42c2-af2b-c7991d319f0a",
    },
    {
        "student_id": "42b94771-000e-52a3-a9b1-869af66783fc",  # STU0033
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-02-03",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_33",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "f6c6d919-07c4-4ca3-a5fb-07d4d76dde55",
    },

]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate Python/DB value."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean needs special handling because SQLAlchemy is strict
    if isinstance(t, sa.Boolean):
        if isinstance(raw, str):
            v = raw.strip().lower()
            if v in ("true", "t", "1", "yes", "y"):
                return True
            if v in ("false", "f", "0", "no", "n"):
                return False
            log.warning(
                "Invalid boolean for %s.%s: %r; using NULL",
                TABLE_NAME,
                col.name,
                raw,
            )
            return None
        return bool(raw)

    # Otherwise, pass raw through and let the DB cast it
    return raw


def upgrade() -> None:
    """Seed fixed student_school_enrollments rows inline.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in ROWS:
        row = {}
        for col in table.columns:
            if col.name not in raw_row:
                continue
            value = _coerce_value(col, raw_row[col.name])
            row[col.name] = value

        if not row:
            continue

        nested = bind.begin_nested()
        try:
            bind.execute(table.insert().values(**row))
            nested.commit()
            inserted += 1
        except (IntegrityError, DataError, StatementError) as exc:
            nested.rollback()
            log.warning(
                "Skipping row for %s due to error: %s. Row: %s",
                TABLE_NAME,
                exc,
                raw_row,
            )

    log.info("Inserted %s rows into %s (inline seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
