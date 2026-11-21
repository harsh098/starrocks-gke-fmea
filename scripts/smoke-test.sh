#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
lab_context
require python3
kubectl get nodes -l starrocks-lab=true -o json | python3 -c '
import json, sys
nodes = json.load(sys.stdin)["items"]
assert len(nodes) == 3, "Expected exactly three lab workers"
zones = {n["metadata"]["labels"]["topology.kubernetes.io/zone"] for n in nodes}
assert len(zones) == 3, "Expected a worker in each of three zones"
print("PASS: three workers in three zones")
'
kubectl -n "$NAMESPACE" get pods -l "$SELECTOR" -o json | python3 -c '
import json, sys
pods = json.load(sys.stdin)["items"]
for component in ("fe", "be"):
    group = [p for p in pods if p["metadata"]["labels"].get("app.kubernetes.io/component") == component]
    assert len(group) == 3, f"Expected three {component} pods"
    assert len({p["spec"]["nodeName"] for p in group}) == 3, f"{component} pods must use distinct workers"
    assert all(any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", [])) for p in group), f"{component} pods are not all Ready"
print("PASS: three ready FEs and three ready BEs, spread across workers")
'
"$ROOT/scripts/sql.sh" --batch -e "SHOW FRONTENDS; SHOW BACKENDS;" \
  > "$ROOT/.local/membership.tsv"
python3 - "$ROOT/.local/membership.tsv" <<'PY'
import csv, sys
rows = list(csv.reader(open(sys.argv[1]), delimiter='\t'))
groups = []
for row in rows:
    if 'Alive' in row and ('EditLogPort' in row or 'HeartbeatPort' in row):
        groups.append((row, []))
    elif groups:
        groups[-1][1].append(row)
assert len(groups) == 2, 'Expected FE and BE membership tables'
for header, members in groups:
    assert len(members) == 3, 'Expected three registered members'
    alive = header.index('Alive')
    assert all(r[alive].lower() == 'true' for r in members), 'A registered member is not alive'
    if 'Role' in header:
        roles = [r[header.index('Role')] for r in members]
        assert roles.count('LEADER') == 1 and roles.count('FOLLOWER') == 2, 'Expected one leader and two voting followers'
print('PASS: three alive FE members and three alive BE members')
PY
# Safe to rerun. Do not reseed an existing table.
exists=$("$ROOT/scripts/sql.sh" --batch --skip-column-names -e \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='fmea' AND table_name='events';")
if [[ "$exists" == "0" ]]; then
  "$ROOT/scripts/sql.sh" < "$ROOT/experiments/seed.sql"
fi
"$ROOT/scripts/sql.sh" -e "SHOW CREATE TABLE fmea.events;"
"$ROOT/scripts/sql.sh" --batch -e "ADMIN SHOW REPLICA STATUS FROM fmea.events;" > "$ROOT/.local/replicas.tsv"
cat "$ROOT/.local/replicas.tsv"
python3 - "$ROOT/.local/replicas.tsv" <<'PY'
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1]), delimiter='\t'))
tablets = {}
for row in rows:
    assert row['Status'] == 'OK' and row['State'] == 'NORMAL', 'A tablet replica is not healthy'
    assert row['IsBad'].lower() == 'false', 'A tablet replica is marked bad'
    tablets.setdefault(row['TabletId'], set()).add(row['BackendId'])
assert len(rows) == 12 and len(tablets) == 4, 'Expected four tablets with twelve replicas'
assert all(len(backends) == 3 for backends in tablets.values()), 'Each tablet needs replicas on three distinct BEs'
print('PASS: all four tablets have three healthy replicas on distinct BEs')
PY
"$ROOT/scripts/sql.sh" --batch --skip-column-names -e \
  "SELECT COUNT(*) FROM fmea.events WHERE event_id IN (1,2,3);" | grep -qx 3
echo "PASS: baseline rows can be read from the three-replica test table"
