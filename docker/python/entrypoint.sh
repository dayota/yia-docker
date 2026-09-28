#!/bin/sh
set -eu

yia_uid="${YIA_UID:-1000}"
yia_gid="${YIA_GID:-1000}"
case "$yia_uid" in
    ''|*[!0-9]*) echo "YIA_UID must be a positive integer" >&2; exit 64 ;;
esac
case "$yia_gid" in
    ''|*[!0-9]*) echo "YIA_GID must be a positive integer" >&2; exit 64 ;;
esac
if [ "$yia_uid" -eq 0 ] || [ "$yia_gid" -eq 0 ]; then
    echo "YIA_UID and YIA_GID must be greater than zero" >&2
    exit 64
fi

if [ "$(id -u)" -ne 0 ]; then
    exec "$@"
fi

groupmod -o -g "$yia_gid" yia
usermod -o -u "$yia_uid" -g "$yia_gid" yia
if [ -d .venv ]; then
    chown yia:yia .venv
fi
exec gosu yia "$@"
