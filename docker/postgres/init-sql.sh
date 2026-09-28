#!/bin/sh
set -eu

# Executed by the official PostgreSQL entrypoint only for a new data volume.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --file /yia-init/init.sql
checksum=$(sha256sum /yia-init/init.sql)
printf '%s\n' "${checksum%% *}" > "$PGDATA/.yia-init-sql.sha256.tmp"
mv "$PGDATA/.yia-init-sql.sha256.tmp" "$PGDATA/.yia-init-sql.sha256"
