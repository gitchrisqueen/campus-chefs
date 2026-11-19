#!/bin/sh
# Creates the owner and app roles (plan 5.2). Idempotent: compose runs it on
# first init, and CI runs the same script against its service container.
set -eu

owner_pw="${CC_OWNER_PASSWORD:-$(cat /run/cc-secrets/db_owner_password)}"
app_pw="${CC_APP_PASSWORD:-$(cat /run/cc-secrets/db_app_password)}"
db="${POSTGRES_DB:-campuschefs}"

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname "${db}" \
  -v owner_pw="${owner_pw}" -v app_pw="${app_pw}" -v db="${db}" <<'SQL'
SELECT 'CREATE ROLE campuschefs_owner LOGIN CREATEDB'
  WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'campuschefs_owner') \gexec
SELECT 'CREATE ROLE campuschefs_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE'
  WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'campuschefs_app') \gexec
ALTER ROLE campuschefs_owner WITH LOGIN CREATEDB PASSWORD :'owner_pw';  -- a psql variable, not a literal (public-readiness: allow)
ALTER ROLE campuschefs_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_pw';  -- a psql variable, not a literal (public-readiness: allow)
ALTER DATABASE :"db" OWNER TO campuschefs_owner;
GRANT CONNECT ON DATABASE :"db" TO campuschefs_app;
GRANT USAGE ON SCHEMA public TO campuschefs_app;
ALTER DEFAULT PRIVILEGES FOR ROLE campuschefs_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO campuschefs_app;
ALTER DEFAULT PRIVILEGES FOR ROLE campuschefs_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO campuschefs_app;
SQL
echo "01-roles: owner and app roles ready"
