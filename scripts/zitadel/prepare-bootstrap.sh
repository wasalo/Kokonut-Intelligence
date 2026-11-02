#!/bin/sh
# The API writes the token; the Login UI reads it via the shared group.
set -eu

for value in "${KOKONUT_ZITADEL_API_UID:-}" "${KOKONUT_ZITADEL_LOGIN_GID:-}"; do
    case "$value" in
        ''|*[!0-9]*|0*) echo 'Invalid nonzero bootstrap identity' >&2; exit 1 ;;
    esac
    [ "$value" -le 2147483647 ] || { echo 'Bootstrap identity out of range' >&2; exit 1; }
done

directory=/zitadel/bootstrap
token=$directory/login-client.pat
[ -d "$directory" ] && [ ! -L "$directory" ] || exit 1
if [ -e "$token" ] || [ -L "$token" ]; then
    [ -f "$token" ] && [ ! -L "$token" ] || exit 1
else
    umask 077
    : > "$token"
fi
chown "$KOKONUT_ZITADEL_API_UID:$KOKONUT_ZITADEL_LOGIN_GID" "$directory" "$token"
chmod 0750 "$directory"
chmod 0640 "$token"
