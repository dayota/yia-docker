#!/bin/sh
set -eu
. /yia/read-secret.sh
REDISCLI_AUTH="$(yia_read_secret "$REDIS_PASSWORD_FILE")" || exit 2
export REDISCLI_AUTH
response="$(redis-cli --raw ping 2>/dev/null)" || exit 1
unset REDISCLI_AUTH
test "$response" = PONG
