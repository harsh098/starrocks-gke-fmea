#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$ROOT"
lab_context
umask 077
mkdir -p .local/runs
run_dir="$ROOT/.local/runs/CRED-1-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 700 "$run_dir"
exec 3>&1
exec > "$run_dir/run.log" 2>&1
trap 'code=$?; echo "Runner stopped with exit $code. Inspect the private run log before another test." >&3' ERR
echo 'CRED-1: starting hourly ESO sync and password rotation test.' >&3
old="$run_dir/original-password"
kubectl -n starrocks get secret starrocks-admin-password -o jsonpath='{.data.password}' | base64 -d > "$old"
test -s "$old"
new="$run_dir/new-password"
be=starrocks-fmea-be-0
fe=starrocks-fmea-fe-0
python3 -c 'import secrets; print(secrets.token_hex(24), end="")' > "$new"
sql() {
  { cat "$1"; printf '\n%s\n' "$2"; } |
    kubectl -n starrocks exec -i "$fe" -c fe -- bash -c '
      IFS= read -r MYSQL_PWD
      export MYSQL_PWD
      exec mysql --batch --connect-timeout=10 -h 127.0.0.1 -P 9030 -u root
    '
}
rotate() {
  local password
  password=$(cat "$2")
  sql "$1" "SET PASSWORD FOR 'root'@'%' = PASSWORD('$password');" > "$run_dir/rotation-private.log" 2>&1
}
target_matches() {
  kubectl -n starrocks get secret starrocks-admin-password -o jsonpath='{.data.password}' | base64 -d | cmp -s - "$1"
}
sync_eso() {
  kubectl -n starrocks annotate externalsecret starrocks-admin-password force-sync="$(date +%s%N)" --overwrite
}
provider_update() {
  kubectl -n starrocks-eso-source create secret generic starrocks-admin-password --from-file=password="$1" --dry-run=client -o yaml |
    kubectl apply --server-side --force-conflicts -f -
}
wait_target() {
  for try in {1..30}; do
    if target_matches "$1"; then return; fi
    sleep 2
  done
  return 1
}
restore() {
  if ! sql "$old" 'SELECT 1;' >/dev/null 2>&1; then rotate "$new" "$old" || return; fi
  provider_update "$old" && sync_eso && wait_target "$old" || return
  kubectl -n starrocks delete pod "$be" --wait=false
  for attempt in {1..20}; do
    if ./scripts/smoke-test.sh; then echo 'Original credential and baseline restored'; return; fi
    sleep 5
  done
  return 1
}
./scripts/smoke-test.sh
kubectl -n starrocks get externalsecret starrocks-admin-password -o custom-columns=POLICY:.spec.refreshPolicy,INTERVAL:.spec.refreshInterval,REFRESH:.status.refreshTime
target_matches "$old"
refreshed_before=$(kubectl -n starrocks get externalsecret starrocks-admin-password -o jsonpath='{.status.refreshTime}')
sync_eso
for attempt in {1..30}; do
  refreshed_now=$(kubectl -n starrocks get externalsecret starrocks-admin-password -o jsonpath='{.status.refreshTime}')
  [[ -n $refreshed_now && $refreshed_now != "$refreshed_before" ]] && break
  [[ $attempt != 30 ]]
  sleep 2
done
echo "Hourly ESO baseline sync observed at $refreshed_now"
target_matches "$old"
trap 'restore' EXIT
rotate "$old" "$new"
provider_update "$new"
target_matches "$old"
echo "Database and provider rotated; target Secret still matches original at $(date -u +%FT%TZ)"
old_uid=$(kubectl -n starrocks get pod "$be" -o jsonpath='{.metadata.uid}')
kubectl -n starrocks delete pod "$be" --wait=false
for attempt in {1..24}; do
  uid=$(kubectl -n starrocks get pod "$be" -o jsonpath='{.metadata.uid}' 2>/dev/null || true)
  if [[ -n $uid && $uid != "$old_uid" ]]; then
    kubectl -n starrocks logs "$be" -c be --tail=100 > "$run_dir/be-startup.log" 2>&1 || true
    kubectl -n starrocks logs "$be" -c be --previous --tail=100 >> "$run_dir/be-startup.log" 2>&1 || true
    if grep -Eqi 'access denied.*root' "$run_dir/be-startup.log"; then break; fi
  fi
  sleep 4
done
if grep -Eqi 'access denied.*root' "$run_dir/be-startup.log"; then
  echo 'BE startup logs contain Access denied for root'
  grep -Eim 1 'ERROR 1045.*Access denied.*root' "$run_dir/be-startup.log" >&3
else
  echo 'Expected authentication failure was not reproduced.' >&3
  exit 1
fi
target_matches "$old"
down=false
for attempt in {1..18}; do
  snapshot=$(sql "$new" 'SHOW BACKENDS;')
  if printf '%s\n' "$snapshot" | awk -F '\t' -v be="$be." 'index($2,be)==1 && $9=="false" {found=1} END{exit !found}'; then
    down=true
    break
  fi
  sleep 4
done
echo "BE confirmed down: $down at $(date -u +%FT%TZ)"
[[ $down == true ]]
echo "Membership: selected BE Alive=false." >&3
kubectl -n starrocks get pod "$be" -o custom-columns=NAME:.metadata.name,PHASE:.status.phase,READY:.status.containerStatuses[0].ready,RESTARTS:.status.containerStatuses[0].restartCount
target_matches "$old"
sql "$new" 'SHOW BACKENDS; ADMIN SHOW REPLICA STATUS FROM fmea.events;'

event_id=$(date +%s%N)
rc=0
sql "$new" "INSERT INTO fmea.events VALUES ($event_id, NOW(), 'stale-credential');" || rc=$?
echo "Outage insert exit: $rc, event_id: $event_id"
[[ $rc == 0 ]]
echo "Write with two BEs: acknowledged." >&3
sync_eso
wait_target "$new"
echo "Target Secret matches new value at $(date -u +%FT%TZ)"
echo "Fix: forced ESO sync; target Secret matches the rotated password." >&3
kubectl -n starrocks delete pod "$be" --wait=false
recovered=false
for attempt in {1..60}; do
  if snapshot=$(sql "$new" 'SHOW BACKENDS; ADMIN SHOW REPLICA STATUS FROM fmea.events;') &&
    printf '%s\n' "$snapshot" | awk -F '\t' '$9=="true"{be++} $13=="OK" && $12=="NORMAL" && $10=="false"{ok++} END{exit !(be==3 && ok==12)}'; then
    printf '%s\n' "$snapshot"
    recovered=true
    break
  fi
  sleep 5
done
echo "Recovery verified: $recovered at $(date -u +%FT%TZ)"
[[ $recovered == true ]]
row=$(sql "$new" "SELECT event_id FROM fmea.events WHERE event_id=$event_id;" | tail -n 1)
[[ $row == "$event_id" ]]
echo 'Recovery: BE registered, acknowledged row present, all 12 replicas OK.' >&3
restore
trap - EXIT

echo 'Status: FAIL — stale credentials prevented BE restart.' >&3
echo 'Fix: verified; original credential and baseline restored.' >&3
echo "Private evidence: .local/runs/$(basename "$run_dir")" >&3
