#!/usr/bin/env sh
# Nightly SQLite backup for the Dibble pilot instance.
#
# Uses sqlite3's online .backup (safe under WAL with live readers/writers),
# keeps a rolling window of dated snapshots, and optionally ships the newest
# snapshot off-host with rsync.
#
# Usage:
#   backup_database.sh [DB_PATH] [BACKUP_DIR]
# Environment:
#   DIBBLE_BACKUP_RETAIN   number of snapshots to keep (default 14)
#   DIBBLE_BACKUP_REMOTE   optional rsync target, e.g. user@host:/backups/dibble
set -eu

DB_PATH="${1:-${DIBBLE_DATABASE_PATH:-/data/dibble.db}}"
BACKUP_DIR="${2:-${DIBBLE_BACKUP_DIR:-/backups}}"
RETAIN="${DIBBLE_BACKUP_RETAIN:-14}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
TARGET="${BACKUP_DIR}/dibble-${STAMP}.db"

mkdir -p "${BACKUP_DIR}"

if [ ! -f "${DB_PATH}" ]; then
    echo "backup: database not found at ${DB_PATH}" >&2
    exit 1
fi

sqlite3 "${DB_PATH}" ".backup '${TARGET}'"
gzip "${TARGET}"
echo "backup: wrote ${TARGET}.gz"

# Rotate: keep the newest $RETAIN snapshots.
ls -1t "${BACKUP_DIR}"/dibble-*.db.gz 2>/dev/null | tail -n "+$((RETAIN + 1))" | while read -r old; do
    rm -f "${old}"
    echo "backup: rotated out ${old}"
done

if [ -n "${DIBBLE_BACKUP_REMOTE:-}" ]; then
    rsync -az "${TARGET}.gz" "${DIBBLE_BACKUP_REMOTE}/"
    echo "backup: shipped to ${DIBBLE_BACKUP_REMOTE}"
fi
