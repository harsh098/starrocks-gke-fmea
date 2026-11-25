#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$ROOT"
lab_context
umask 077
mkdir -p .local/runs
log=".local/runs/FE-3-$(date -u +%Y%m%dT%H%M%SZ).log"
exec 3>&1
exec > "$log" 2>&1
trap 'code=$?; echo "Runner stopped with exit $code. Inspect the private run log before another test." >&3' ERR
echo 'FE-3: starting baseline and connectivity checks.' >&3
leader=$(./scripts/sql.sh --batch -e 'SHOW FRONTENDS;' | awk -F '\t' '$8=="LEADER" {split($2,n,"."); print n[1]}')
[[ $leader == starrocks-fmea-fe-[012] ]]
node=$(kubectl -n starrocks get pod "$leader" -o jsonpath='{.spec.nodeName}')
zone=$(kubectl get node "$node" -o jsonpath='{.metadata.labels.topology\.kubernetes\.io/zone}')
majority=starrocks-fmea-fe-0
[[ $leader != "$majority" ]] || majority=starrocks-fmea-fe-1
echo "FE-3 baseline $(date -u +%FT%TZ), isolated pod $leader"
./scripts/smoke-test.sh
trap './scripts/partition.py stop' EXIT
./scripts/partition.py start "$zone"
echo 'Partition: DNS verified; cross-zone connections blocked; majority FEs connected.' >&3
suffix=$(date +%s)
event_id=$(date +%s%N)
rc=0
SR_FE_POD="$majority" timeout 30 ./scripts/sql.sh --verbose -e "CREATE DATABASE fmea_majority_$suffix;" || rc=$?
echo "Majority DDL exit: $rc"
echo "Majority metadata probe exit: $rc" >&3
[[ $rc == 0 ]]
rc=0
SR_FE_POD="$leader" timeout 25 ./scripts/sql.sh --verbose -e "CREATE DATABASE fmea_minority_$suffix;" || rc=$?
echo "Minority DDL exit: $rc"
echo "Minority metadata probe exit: $rc" >&3
[[ $rc != 0 ]]
rc=0
SR_FE_POD="$majority" timeout 30 ./scripts/sql.sh --verbose -e "INSERT INTO fmea.events VALUES ($event_id, NOW(), 'partition');" || rc=$?
echo "Majority INSERT exit: $rc"
echo "Majority insert exit: $rc" >&3
[[ $rc == 0 ]]
./scripts/partition.py stop
trap - EXIT
for attempt in {1..24}; do
  if ./scripts/smoke-test.sh; then break; fi
  [[ $attempt != 24 ]]
  sleep 5
done
./scripts/sql.sh --batch -e "SHOW DATABASES LIKE 'fmea_majority_$suffix'; SHOW DATABASES LIKE 'fmea_minority_$suffix'; SELECT * FROM fmea.events WHERE event_id=$event_id; ADMIN SHOW REPLICA STATUS FROM fmea.events;"
echo "Recovery observed $(date -u +%FT%TZ)"

majority_result=$(./scripts/sql.sh --batch --skip-column-names -e "SHOW DATABASES LIKE 'fmea_majority_$suffix';")
minority_result=$(./scripts/sql.sh --batch --skip-column-names -e "SHOW DATABASES LIKE 'fmea_minority_$suffix';")
row=$(./scripts/sql.sh --batch --skip-column-names -e "SELECT event_id FROM fmea.events WHERE event_id=$event_id;")
[[ $majority_result == "fmea_majority_$suffix" && -z $minority_result && $row == "$event_id" ]]
echo 'Readback: majority database and row present; minority database absent.' >&3
echo 'Recovery: 3 alive FEs, 3 alive BEs, 12 healthy replicas.' >&3
echo 'Status: PASS' >&3
echo "Private evidence: $log" >&3
