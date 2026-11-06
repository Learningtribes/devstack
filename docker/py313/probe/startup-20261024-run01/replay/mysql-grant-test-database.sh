# Sourced by the official mysql entrypoint during first initialization of a fresh data volume.
# The image grants only MYSQL_DATABASE; Django's test runner also needs to CREATE and DROP the
# test database, so give the application user the same rights on exactly that name. `_` and `%`
# are GRANT wildcards and must be escaped to keep the grant from matching other databases.
if [ -z "${PY313_TEST_DATABASE:-}" ] || ! type docker_process_sql >/dev/null 2>&1; then
    echo "mysql-grant-test-database: PY313_TEST_DATABASE and the entrypoint SQL helper are required" >&2
    exit 1
fi
pattern=$(printf '%s' "$PY313_TEST_DATABASE" | sed 's/[_%]/\\&/g')
printf "GRANT ALL PRIVILEGES ON \`%s\`.* TO '%s'@'%%';\n" "$pattern" "$MYSQL_USER" | docker_process_sql
