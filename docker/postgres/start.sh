#!/bin/sh
set -eu

# Validate without logging/exporting the value; the official entrypoint then
# consumes POSTGRES_PASSWORD_FILE, including its usual trailing-LF handling.
. /yia/read-secret.sh
yia_read_secret "$POSTGRES_PASSWORD_FILE" >/dev/null
exec docker-entrypoint.sh "$@"
