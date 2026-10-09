#!/bin/bash
# Full E4 gate in one log window: r2-e4-run.sh <out-dir>. Expects the E4 stack
# to be absent; leaves it running for inspection (cleanup is explicit).
set -u
OUT=$1
PY36=/Users/noahwang/workspace/hawthorn/devstack-py36-r2-env/docker/py36
WORKER=py36-r2-worker-20261009
cd "${PY36}" || exit 1
mkdir -p "${OUT}"

wait_heartbeats() {
    for _ in $(seq 1 60); do
        curl -s -o /dev/null -w '%{http_code}' -H 'Host: localhost:18000' http://127.0.0.1:18200/heartbeat | grep -q 200 &&
            curl -s -o /dev/null -w '%{http_code}' -H 'Host: localhost:18010' http://127.0.0.1:18210/heartbeat | grep -q 200 &&
            return 0
        sleep 3
    done
    return 1
}

wait_worker_ready() {
    for _ in $(seq 1 40); do
        docker logs --since "$1" "${WORKER}" 2>&1 | grep -q PY36_R2_E4_WORKER_READY && return 0
        sleep 2
    done
    return 1
}

./run-r2-e4-services.sh start > "${OUT}/start.txt" 2>&1 || { cat "${OUT}/start.txt"; exit 1; }
wait_heartbeats || { echo 'heartbeats not ready'; exit 1; }
date -u +%Y-%m-%dT%H:%M:%SZ > "${OUT}/window-start.txt"

./r2-e4-http.sh "${OUT}/http" > "${OUT}/http-gate.txt" 2>&1
for svc in lms cms; do
    ./run-r2-e4-services.sh shell "${svc}" < r2-evidence/e4/e4_course_read.py > "${OUT}/course-${svc}.txt" 2>&1
done
./run-r2-e4-services.sh tasks heartbeat success controlled_failure success:post inspect > "${OUT}/tasks-pre-restart.txt" 2>&1
echo "exit=$?" >> "${OUT}/tasks-pre-restart.txt"

{
    stop_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "RESTART stop_at=${stop_at}"
    start_s=$(date +%s)
    docker stop --timeout 15 "${WORKER}"
    echo "RESTART stop_seconds=$(( $(date +%s) - start_s ))"
    docker inspect "${WORKER}" --format 'RESTART stopped exit={{.State.ExitCode}} oom={{.State.OOMKilled}}'
    docker logs --since "${stop_at}" "${WORKER}" 2>&1 | grep -E 'shutdown|Shutdown' | sed 's/^/RESTART log: /'
    start_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "RESTART start_at=${start_at}"
    docker start "${WORKER}"
    wait_worker_ready "${start_at}" && echo 'RESTART worker_ready=true' || echo 'RESTART worker_ready=false'
    docker inspect "${WORKER}" --format 'RESTART running={{.State.Running}} restarts={{.RestartCount}}'
} > "${OUT}/worker-restart.txt" 2>&1
./run-r2-e4-services.sh tasks heartbeat:post_restart success:post_restart inspect > "${OUT}/tasks-post-restart.txt" 2>&1
echo "exit=$?" >> "${OUT}/tasks-post-restart.txt"
docker exec py36-r2-rabbitmq-20261009 rabbitmqctl list_queues -p py36-r2-20261009 \
    name messages_ready messages_unacknowledged consumers > "${OUT}/rabbit-queues.txt" 2>&1

date -u +%Y-%m-%dT%H:%M:%SZ > "${OUT}/window-end.txt"
since=$(cat "${OUT}/window-start.txt")
for c in py36-r2-lms-20261009 py36-r2-cms-20261009 "${WORKER}" py36-r2-rabbitmq-20261009; do
    docker logs --since "${since}" "${c}" > "${OUT}/log-${c}.txt" 2>&1
done
echo "E4_RUN_DONE out=${OUT}"
