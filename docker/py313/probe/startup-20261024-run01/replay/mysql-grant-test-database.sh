# Grants the Django test database to the application user on first initialization of a fresh data volume.
# The image grants only MYSQL_DATABASE; Django's test runner also needs to CREATE and DROP the test
# database, so give the application user the same rights on exactly that name. `_` and `%` are GRANT
# wildcards and must be escaped to keep the grant from matching other databases.
#
# The official entrypoint sources a non-executable *.sh but executes an executable one, and only the
# sourced form inherits its `docker_process_sql` helper. On Docker Desktop every bind-mounted file
# reports as executable, so this file is always executed there and the helper is unavailable. Run the
# grant through the helper when it exists and fall back to the client directly otherwise, so the same
# file works on Linux (sourced) and on Docker Desktop (executed).
if [ -z "${BRINGUP_TEST_DATABASE:-}" ]; then
    echo "mysql-grant-test-database: BRINGUP_TEST_DATABASE is required" >&2
    exit 1
fi
pattern=$(printf '%s' "$BRINGUP_TEST_DATABASE" | sed 's/[_%]/\\&/g')
# A function keeps the trailing newline: command substitution in "$(...)" would strip it, and the
# entrypoint helper reads the statement from this stream.
grant_sql() {
    printf "GRANT ALL PRIVILEGES ON \`%s\`.* TO '%s'@'%%';\n" "$pattern" "$MYSQL_USER"
}
if type docker_process_sql >/dev/null 2>&1; then
    grant_sql | docker_process_sql
else
    # Executed, not sourced: talk to the temporary server over the same socket the entrypoint uses.
    grant_sql | MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=socket -uroot -hlocalhost \
        --socket=/var/run/mysqld/mysqld.sock --comments
fi
