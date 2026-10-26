#!/bin/sh
# Create a dedicated, non-superuser ZITADEL role and database on first boot.
set -eu

: "${KOKONUT_ZITADEL_DATABASE_PASSWORD:?ZITADEL database role password is required}"

psql --no-psqlrc --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv zitadel_password KOKONUT_ZITADEL_DATABASE_PASSWORD
SELECT format(
    'CREATE ROLE zitadel LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT',
    :'zitadel_password'
) \gexec
CREATE DATABASE zitadel OWNER zitadel;
SQL
