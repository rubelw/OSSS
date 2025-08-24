#!/usr/bin/env bash

#!/usr/bin/env bash
set -euo pipefail

# Run this from the repo root (where alembic.ini lives).
ROOT_DIR="$(pwd)"

ALEMBIC_INI="${ROOT_DIR}/alembic.ini"
ALEMBIC_INI_BAK="${ROOT_DIR}/alembic.ini_bak"
# also handle accidental typo file names gracefully
ALEMBIX_INI="${ROOT_DIR}/alembix.ini"         # typo variant (if present)

# Alembic's fresh init output
NEW_MIGR_DIR="${ROOT_DIR}/migrations"

# Your project migrations path (to be backed up and later restored)
SRC_MIGR_DIR="${ROOT_DIR}/src/OSSS/db/migrations"
# requested typo name + corrected name; we prefer the corrected name but handle both
SRC_MIGR_DIR_BAK_TYPO="${ROOT_DIR}/src/OSSS/db/micrations_bak"
SRC_MIGR_DIR_BAK="${ROOT_DIR}/src/OSSS/db/migrations_bak"

echo "==> Checking for 'alembic' command..."
command -v alembic >/dev/null 2>&1 || { echo "Error: 'alembic' is not installed/in PATH."; exit 1; }

echo "==> Backing up src/OSSS/db/migrations ..."
if [[ -d "$SRC_MIGR_DIR" ]]; then
  if [[ -d "$SRC_MIGR_DIR_BAK" || -d "$SRC_MIGR_DIR_BAK_TYPO" ]]; then
    echo "Error: a migrations backup already exists (${SRC_MIGR_DIR_BAK} or ${SRC_MIGR_DIR_BAK_TYPO})."
    exit 1
  fi
  # Use the corrected name; if you want the exact typo, switch to SRC_MIGR_DIR_BAK_TYPO.
  mv "$SRC_MIGR_DIR" "$SRC_MIGR_DIR_BAK"
  echo "    Moved '$SRC_MIGR_DIR' -> '$SRC_MIGR_DIR_BAK'"
else
  echo "    No '$SRC_MIGR_DIR' directory found to back up (skipping)."
fi

echo "==> Backing up alembic.ini (if not already backed up)..."
if [[ -f "$ALEMBIC_INI" && ! -f "$ALEMBIC_INI_BAK" ]]; then
  mv "$ALEMBIC_INI" "$ALEMBIC_INI_BAK"
  echo "    Moved '$ALEMBIC_INI' -> '$ALEMBIC_INI_BAK'"
else
  if [[ -f "$ALEMBIC_INI_BAK" ]]; then
    echo "    Backup already exists: '$ALEMBIC_INI_BAK' (leaving as-is)."
  else
    echo "    No '$ALEMBIC_INI' found (skipping backup)."
  fi
fi

echo "==> Running 'alembic init migrations' to clear-out and generate fresh files..."
# This will create ROOT_DIR/migrations and ROOT_DIR/alembic.ini (fresh)
alembic init migrations

echo "==> Removing freshly generated 'alembic.ini' (per instructions)..."
# Handle both correct and typo file names
if [[ -f "$ALEMBIC_INI" ]]; then
  rm -f "$ALEMBIC_INI"
  echo "    Deleted '$ALEMBIC_INI'"
fi
if [[ -f "$ALEMBIX_INI" ]]; then
  rm -f "$ALEMBIX_INI"
  echo "    Deleted typo file '$ALEMBIX_INI'"
fi

echo "==> Removing freshly generated '/migrations' directory..."
if [[ -d "$NEW_MIGR_DIR" ]]; then
  rm -rf "$NEW_MIGR_DIR"
  echo "    Deleted '$NEW_MIGR_DIR'"
fi

echo "==> Restoring backups (alembic.ini_bak and src/OSSS/db/migrations_bak)..."
if [[ -f "$ALEMBIC_INI_BAK" ]]; then
  mv "$ALEMBIC_INI_BAK" "$ALEMBIC_INI"
  echo "    Restored '$ALEMBIC_INI_BAK' -> '$ALEMBIC_INI'"
else
  echo "    No '$ALEMBIC_INI_BAK' to restore (skipping)."
fi

# Prefer restoring from the corrected backup name; fall back to typo backup if needed.
if [[ -d "$SRC_MIGR_DIR_BAK" ]]; then
  mv "$SRC_MIGR_DIR_BAK" "$SRC_MIGR_DIR"
  echo "    Restored '$SRC_MIGR_DIR_BAK' -> '$SRC_MIGR_DIR'"
elif [[ -d "$SRC_MIGR_DIR_BAK_TYPO" ]]; then
  mv "$SRC_MIGR_DIR_BAK_TYPO" "$SRC_MIGR_DIR"
  echo "    Restored '$SRC_MIGR_DIR_BAK_TYPO' -> '$SRC_MIGR_DIR'"
else
  echo "    No migrations backup found to restore (skipping)."
fi

echo "✅ Done."
