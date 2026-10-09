#!/bin/sh
# E4 HTTP gate: r2-e4-http.sh <out-dir>. Login credentials come from
# .py36-r2-config/e4-login.env (E4_LOGIN_EMAIL, E4_LOGIN_PASSWORD); never printed.
set -u
OUT=$1
LMS=http://127.0.0.1:18200
CMS=http://127.0.0.1:18210
# Studio's course listing needs the SiteConfiguration of a configured site;
# use the canonical devstack hosts rather than adding Site rows to shared MySQL.
LMS_HOST='Host: localhost:18000'
CMS_HOST='Host: localhost:18010'
. /Users/noahwang/workspace/hawthorn/.py36-r2-config/e4-login.env
mkdir -p "${OUT}"
JAR="${OUT}/cms.cookies"
rm -f "${JAR}"

req() {
    label=$1; shift
    code=$(curl -sS -o "${OUT}/${label}.body" -D "${OUT}/${label}.headers" -w '%{http_code} %{content_type} %{size_download}' "$@")
    echo "${label}: exit=$? http=${code} location=$(tr -d '\r' < "${OUT}/${label}.headers" | sed -n 's/^[Ll]ocation: //p')"
}

req lms-login -H "${LMS_HOST}" "${LMS}/login"
req lms-heartbeat -H "${LMS_HOST}" "${LMS}/heartbeat"; echo "  $(cat "${OUT}/lms-heartbeat.body")"
req cms-root -H "${CMS_HOST}" -c "${JAR}" "${CMS}/"
req cms-signin -H "${CMS_HOST}" -c "${JAR}" -b "${JAR}" "${CMS}/signin"
CSRF=$(awk '$6 == "csrftoken" {print $7}' "${JAR}")
req cms-login-post -H "${CMS_HOST}" -c "${JAR}" -b "${JAR}" -H "X-CSRFToken: ${CSRF}" -H "Referer: http://localhost:18010/signin" \
    --data-urlencode "email=${E4_LOGIN_EMAIL}" --data-urlencode "password=${E4_LOGIN_PASSWORD}" "${CMS}/login_post"
echo "  $(cat "${OUT}/cms-login-post.body")"
req cms-authenticated-root -H "${CMS_HOST}" -c "${JAR}" -b "${JAR}" "${CMS}/"
req cms-heartbeat -H "${CMS_HOST}" "${CMS}/heartbeat"; echo "  $(cat "${OUT}/cms-heartbeat.body")"
req cms-static -H "${CMS_HOST}" "${CMS}/static/studio/bundles/LoginFactory.js"
rm -f "${JAR}"
