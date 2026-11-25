# StarRocks on Kubernetes FMEA — Part 2: Experiments and Recovery

> Working draft. The test outcomes and output excerpts come from the linked run records.

## Introduction

In [Part 1](https://dok.community/blog/starrocks-kubernetes-fmea-part-1/), we used Failure Modes and Effects Analysis (FMEA) to turn operational risks in a StarRocks deployment on GKE into testable questions. We described the three voting Frontends (FEs), three Backends (BEs), zonal disks, and the two different quorum rules: a majority of voting FEs for metadata, and a majority of replicas of each affected tablet for writes.

Here we run those tests and report what clients, StarRocks, and Kubernetes actually showed. We separate the fault we injected from the failure it was meant to model, and we check recovery at both membership and tablet level.

## Audience and Key Takeaways

This article is for SREs, Kubernetes administrators, and engineers evaluating a stateful database on Kubernetes. It shows how to define pass and fail criteria before a disruption, collect evidence while it is active, and verify recovery afterward. The commands and [experiment repository](https://github.com/harsh098/starrocks-gke-fmea) let readers reproduce the bounded tests in their own disposable lab.

**Key takeaways.** Check FE metadata writes and BE tablet writes independently. Confirm the database sees the affected member as down during the probe and verify all replicas afterward.

## Test-Driven Design

We start each case with a baseline, state the expected outcome, inject one fault, record the client response, and check the database again after recovery. A client timeout leaves the outcome of a write unknown until we query for it. A Ready pod does not establish FE or BE membership, and an alive BE does not establish tablet health.

The test pool has a fixed size: one worker in each of three zones, three workers total. There is no cluster autoscaler. Before each run, we record the worker count, pod placement, FE leader and voting membership, BE membership, and tablet replica health. We run one disruption at a time and restore full health before the next case. The six database volumes are zonal, so a replacement pod may remain Pending when its zone has no eligible worker.

| Test Area | Test case # | Test | Assumed failure mode | PASS CRITERIA | FAIL CRITERIA |
| --- | --- | --- | --- | --- | --- |
| FE recovery | [FE-1](#fe-1-follower-exit-and-rejoin) | Force-exit one FE follower. | FE process crash-recovery. | Two surviving voters commit metadata writes; the follower rejoins; baseline data remains readable. | Metadata writes fail despite a reachable majority, or the follower does not rejoin. |
| FE recovery | [FE-2](#fe-2-leader-exit-and-election) | Force-exit the FE leader. | FE process crash-recovery and leader handoff. | A surviving voter becomes leader; metadata writes resume; the former leader rejoins. | No leader is elected with two healthy voters, or membership does not recover. |
| FE partition | [FE-3](#fe-3-simulated-database-network-partition) | Isolate one FE from its voting peers. | Network partition through link omission. | Majority-side metadata writes succeed; no minority-side write is confirmed committed; membership recovers. | A minority-side write is confirmed committed without quorum, or the reachable majority cannot operate. |
| BE availability | [BE-1](#be-1-writes-with-one-be-unavailable) | Cordon one worker, force-delete its BE pod, and write while that BE is unavailable. | BE process crash-recovery; one replica of each affected tablet is unavailable. | Existing-table writes succeed with two healthy replicas; acknowledged rows survive; the BE rejoins and every affected tablet returns to three healthy replicas. | Writes fail despite two healthy replicas, acknowledged rows disappear, or replica health does not recover. |
| Credential rotation | [CRED-1](#cred-1-be-restart-after-password-rotation) | Start with ESO polling hourly. Rotate the database and provider passwords, then restart one BE before ESO updates the target Secret. | Stale startup credential after password rotation. | The replacement BE authenticates and becomes healthy without manual Secret sync. | The replacement BE cannot authenticate or become healthy because the target Secret still contains the old password. |
| GKE maintenance | [SURGE-1](#surge-1-gke-surge-upgrade-and-recovery) | Upgrade the node pool with GKE surge replacement and continuous clients. | Planned worker replacement and FE/BE process restart. | Acknowledged writes survive; FE and BE membership, PVC bindings, and tablet health recover. | An acknowledged write is absent, a member fails to rejoin, or tablet redundancy remains degraded. |

CRED-1 failed during the verified stale Secret window. The case records the failure and the steps we used to recover. A forced pod exit is an abrupt database-process disruption, not proof of abrupt VM-loss behavior. The partition injects link omission, not Byzantine node behavior.

## Lab and Evidence

We used `1.36.4-gke.2377000`, StarRocks Operator and Helm charts `1.11.4`, and StarRocks FE/BE images `3.5.21`. The shared-nothing cluster has three voting FEs and three BEs, with one of each per worker. The test table has three replicas per tablet and `MAJORITY` write quorum. We used six 25 GiB zonal database volumes.

For each run, capture the repository commit, UTC timestamps, image digests, fault injection, client responses, FE leadership, BE membership, tablet replica status, pod UIDs, Kubernetes events, and recovery actions. Keep credentials, cloud identifiers, and raw private logs out of the public article.

**Baseline commands:**

```bash
./scripts/topology.sh
./scripts/smoke-test.sh
./scripts/sql.sh -e 'SHOW FRONTENDS; SHOW BACKENDS; ADMIN SHOW REPLICA STATUS FROM fmea.events;'
```

**Baseline observations:** Three Ready workers across three zones, three alive FEs, three alive BEs, and four tablets with three healthy replicas each. Baseline rows were readable.

## FE-1: Follower Exit and Rejoin

Identify a voting follower and a surviving FE. Record the pod UID and PVC claim names, cordon its worker, then force-delete the follower. Wait for StarRocks to report it down. Create a unique database through the surviving FE. Uncordon, verify the new pod and the same PVC claims, and read back the database name. Check all members and replicas.

**Commands**

```bash
./scripts/sql.sh -e 'SHOW FRONTENDS;'
```

```bash
POD=starrocks-fmea-fe-1
SURVIVOR=starrocks-fmea-fe-0
NODE=$(kubectl -n starrocks get pod "$POD" -o jsonpath='{.spec.nodeName}')
kubectl -n starrocks get pod "$POD" -o jsonpath='{.metadata.uid}{"\n"}'
kubectl cordon "$NODE"
kubectl -n starrocks delete pod "$POD" --grace-period=0 --force --wait=false
SR_FE_POD="$SURVIVOR" ./scripts/sql.sh -e 'SHOW FRONTENDS;'
# Once the target is down and two voters remain reachable:
PROBE="fmea_fe_$(date +%s)"
SR_FE_POD="$SURVIVOR" ./scripts/sql.sh -e "CREATE DATABASE $PROBE;"
kubectl uncordon "$NODE"
kubectl -n starrocks rollout status statefulset/starrocks-fmea-fe --timeout=10m
kubectl -n starrocks get pod "$POD" -o jsonpath='{.metadata.uid}{"\n"}'
SR_FE_POD="$SURVIVOR" ./scripts/sql.sh -e "SHOW FRONTENDS; SHOW DATABASES LIKE '$PROBE';"
./scripts/smoke-test.sh
```

**FE follower restart.** PASS. The two remaining FEs accepted the metadata probe while the follower was down. The probe was present after rejoin. The pod UID changed and the PVC claims stayed the same.

**Captured output**

```text
Fault requested 2026-11-25T15:38:49Z
Target confirmed down: true at 2026-11-25T15:39:17Z
Probe: CREATE DATABASE fmea_fe_1_1795621129;
Probe exit: 0
Pod UID changed: yes
PVC claims unchanged: yes
fmea_fe_1_1795621129
Recovery observed 2026-11-25T15:40:01Z
```

[Test procedure](../experiments/README.md#fe-1-and-fe-2-fe-pod-loss-and-rejoin) · [Full output and run record](part-2-results.md#fe-1) · [Test matrix](#test-driven-design)

## FE-2: Leader Exit and Election

Identify the current leader and a surviving FE. Cordon the leader’s worker and force-delete the leader pod. Query membership until the original leader is down and a surviving voter has been elected. Create a unique database, uncordon the worker, and verify that the former leader rejoins and the database still exists.

**Commands**

```bash
./scripts/sql.sh -e 'SHOW FRONTENDS;'
```

```bash
POD=starrocks-fmea-fe-0
SURVIVOR=starrocks-fmea-fe-1
NODE=$(kubectl -n starrocks get pod "$POD" -o jsonpath='{.spec.nodeName}')
kubectl -n starrocks get pod "$POD" -o jsonpath='{.metadata.uid}{"\n"}'
kubectl cordon "$NODE"
kubectl -n starrocks delete pod "$POD" --grace-period=0 --force --wait=false
SR_FE_POD="$SURVIVOR" ./scripts/sql.sh -e 'SHOW FRONTENDS;'
# Once the target is down and two voters remain reachable:
PROBE="fmea_fe_$(date +%s)"
SR_FE_POD="$SURVIVOR" ./scripts/sql.sh -e "CREATE DATABASE $PROBE;"
kubectl uncordon "$NODE"
kubectl -n starrocks rollout status statefulset/starrocks-fmea-fe --timeout=10m
kubectl -n starrocks get pod "$POD" -o jsonpath='{.metadata.uid}{"\n"}'
SR_FE_POD="$SURVIVOR" ./scripts/sql.sh -e "SHOW FRONTENDS; SHOW DATABASES LIKE '$PROBE';"
./scripts/smoke-test.sh
```

**FE leader restart.** PASS. FE-2 became leader after FE-0 went down. The metadata probe succeeded and remained present after FE-0 rejoined. The pod UID changed and the PVC claims stayed the same.

**Captured output**

```text
Fault requested 2026-11-25T15:40:40Z
Target confirmed down: true at 2026-11-25T15:41:01Z
Probe: CREATE DATABASE fmea_fe_2_1795621240;
Probe exit: 0
Pod UID changed: yes
PVC claims unchanged: yes
fmea_fe_2_1795621240
Recovery observed 2026-11-25T15:41:38Z
```

[Test procedure](../experiments/README.md#fe-1-and-fe-2-fe-pod-loss-and-rejoin) · [Full output and run record](part-2-results.md#fe-2) · [Test matrix](#test-driven-design)

## FE-3: Simulated Database Network Partition

Find the FE leader’s zone. Apply the partition helper and verify DNS, same-side connectivity, and cross-zone link loss. Attempt distinct database creates on both sides plus an insert from the majority. Remove the partition and reconcile both database names and the insert. Check all members and replicas.

**Commands**

```bash
./scripts/topology.sh
./scripts/partition.py start us-west4-a
./scripts/partition.py status
./scripts/partition.py verify
```

```bash
SR_FE_POD=starrocks-fmea-fe-0 ./scripts/sql.sh -e 'SHOW FRONTENDS; SHOW BACKENDS;'
SR_FE_POD=starrocks-fmea-fe-1 ./scripts/sql.sh -e 'SHOW FRONTENDS; SHOW BACKENDS;'
```

```bash
MAJORITY_FE=starrocks-fmea-fe-0
MINORITY_FE=starrocks-fmea-fe-2
RUN_ID=$(date +%s)
EVENT_ID=$(date +%s%N)
SR_FE_POD="$MAJORITY_FE" timeout 30 ./scripts/sql.sh --verbose \
  -e "CREATE DATABASE fmea_majority_$RUN_ID;"
SR_FE_POD="$MINORITY_FE" timeout 25 ./scripts/sql.sh --verbose \
  -e "CREATE DATABASE fmea_minority_$RUN_ID;"
SR_FE_POD="$MAJORITY_FE" timeout 30 ./scripts/sql.sh --verbose \
  -e "INSERT INTO fmea.events VALUES ($EVENT_ID, NOW(), 'partition');"
```

```bash
./scripts/partition.py stop
./scripts/smoke-test.sh
./scripts/sql.sh -e "SHOW DATABASES LIKE 'fmea_majority_$RUN_ID'; SHOW DATABASES LIKE 'fmea_minority_$RUN_ID';"
./scripts/sql.sh -e "SELECT * FROM fmea.events WHERE event_id=$EVENT_ID;"
./scripts/sql.sh -e 'ADMIN SHOW REPLICA STATUS FROM fmea.events;'
```

**Database network partition.** PASS for the observed partition. Majority DDL and insert succeeded and the minority database was absent after recovery.

**Captured output**

```text
Majority DDL exit: 0
ERROR 2003 (HY000): Can't connect to MySQL server on '127.0.0.1:9030' (111)
Minority DDL exit: 1
Majority INSERT exit: 0
fmea_majority_1795621580
1795621580223852564	2026-11-25 15:46:26	partition
Recovery observed 2026-11-25T15:47:09Z
```

[Test procedure](../experiments/README.md#fe-3-zone-network-partition) · [Full output and run record](part-2-results.md#fe-3) · [Test matrix](#test-driven-design)

## BE-1: Writes with One BE Unavailable

Record BE membership and replica status. Cordon the worker and force-delete one BE. Confirm the replacement is Pending and StarRocks marks the target down. Capture tablet status, then insert a unique row. Uncordon and verify the replacement UID, PVC claims, acknowledged row and three healthy replicas per tablet.

**Commands**

```bash
./scripts/topology.sh
POD=starrocks-fmea-be-0
NODE=$(kubectl -n starrocks get pod "$POD" -o jsonpath='{.spec.nodeName}')
EVENT_ID=$(date -u +%s%N)
kubectl cordon "$NODE"
kubectl -n starrocks delete pod "$POD" --grace-period=0 --force --wait=false
./scripts/sql.sh -e 'SHOW BACKENDS;'
# Wait until StarRocks reports the selected BE unavailable before the write.
# Record tablet health while the BE is unavailable.
./scripts/sql.sh -e 'ADMIN SHOW REPLICA STATUS FROM fmea.events;'
./scripts/sql.sh -e "INSERT INTO fmea.events VALUES ($EVENT_ID, NOW(), 'during-be-outage');"
kubectl uncordon "$NODE"
kubectl -n starrocks rollout status statefulset/starrocks-fmea-be --timeout=10m
./scripts/sql.sh -e 'SHOW BACKENDS;'
./scripts/sql.sh -e 'ADMIN SHOW REPLICA STATUS FROM fmea.events;'
./scripts/sql.sh -e "SELECT * FROM fmea.events WHERE event_id=$EVENT_ID;"
./scripts/smoke-test.sh
```

**Writes with one BE unavailable.** PASS. StarRocks reported one DEAD replica on each of four tablets. The majority insert succeeded, the row was readable after the BE returned, and all 12 replicas reported OK.

**Captured output**

```text
Fault requested 2026-11-25T15:41:57Z
Target confirmed down: true at 2026-11-25T15:42:21Z
10310	10313	10002	2	-1	2	2	0	2	false	false	NORMAL	DEAD
10314	10317	10002	2	-1	2	2	0	2	false	false	NORMAL	DEAD
10318	10321	10002	2	-1	2	2	0	2	false	false	NORMAL	DEAD
10322	10325	10002	2	-1	2	2	0	2	false	false	NORMAL	DEAD
Probe: INSERT INTO fmea.events VALUES (1795621317927661348, NOW(), 'be-outage');
Probe exit: 0
Pod UID changed: yes
PVC claims unchanged: yes
1795621317927661348	2026-11-25 15:42:26	be-outage
Recovery observed 2026-11-25T15:43:00Z
```

[Test procedure](../experiments/README.md#be-1-be-availability-with-one-member-held-down) · [Full output and run record](part-2-results.md#be-1) · [Test matrix](#test-driven-design)

## CRED-1: BE Restart After Password Rotation

Start with ESO polling every hour and confirm the target Secret matches the original password. Rotate StarRocks root and the provider source to a new value. Verify that the target still holds the original value, then restart one BE and inspect startup logs. Record the failed restart separately from recovery. Force ESO to sync, compare the target with the new value, then replace the affected BE and verify registration, acknowledged writes and all replicas.

**Commands**

```bash
kubectl -n starrocks-eso-source create secret generic starrocks-admin-password \
  --from-file=password=.local/current-root-password --dry-run=client -o yaml \
  | kubectl apply --server-side --force-conflicts -f -
```

```bash
kubectl -n starrocks get secret starrocks-admin-password -o jsonpath='{.data.password}' \
  | base64 --decode | cmp -s - .local/root-password
```

```bash
kubectl -n starrocks exec -it starrocks-fmea-fe-0 -c fe -- mysql -h 127.0.0.1 -P 9030 -u root --password
# At the SQL prompt, use a private lab value in this statement:
# SET PASSWORD FOR 'root'@'%' = PASSWORD('<new-lab-password>');
```

```bash
kubectl -n starrocks delete pod starrocks-fmea-be-0 --wait=false
kubectl -n starrocks logs starrocks-fmea-be-0 -c be --previous
```

```bash
kubectl -n starrocks annotate externalsecret "$ES" force-sync="$(date +%s%N)" --overwrite
kubectl -n starrocks get secret starrocks-admin-password -o jsonpath='{.data.password}' \
  | base64 --decode | cmp -s - .local/current-root-password
```

```bash
kubectl -n starrocks delete pod starrocks-fmea-be-0 --wait=false
# Verify BE registration and three healthy replicas per tablet from a surviving FE.
```

**BE restart after password rotation.** FAIL as expected. The replacement BE logged MySQL error 1045 during the stale Secret window. The FE heartbeat view marked it down. The other two BEs remained available. Forced sync and pod replacement restored membership and all 12 replicas. The insert acknowledged with two BEs was readable afterward.

**Captured output**

```text
Hourly ESO baseline sync observed at 2026-11-25T15:50:14Z
Database and provider rotated; target Secret still matches original at 2026-11-25T15:50:20Z
BE startup logs contain Access denied for root
MySQL ERROR 1045 (28000): Access denied for user 'root' (using password: YES)
BE confirmed down: true at 2026-11-25T15:50:39Z
10310	10313	10002	5	-1	5	5	0	3	false	false	NORMAL	DEAD
10314	10317	10002	5	-1	5	5	0	3	false	false	NORMAL	DEAD
10318	10321	10002	5	-1	5	5	0	3	false	false	NORMAL	DEAD
10322	10325	10002	5	-1	5	5	0	3	false	false	NORMAL	DEAD
Outage insert exit: 0, event_id: 1795621843343604115
Target Secret matches new value at 2026-11-25T15:50:47Z
Recovery verified: true at 2026-11-25T15:52:10Z
1795621843343604115	2026-11-25 15:50:45	stale-credential
Original credential and baseline restored
```

| FMEA field | Credential rotation finding |
| --- | --- |
| Failure mode | A BE replacement starts with the old password and fails to authenticate to the FE. |
| Trigger | Root rotation and a BE restart before ESO synchronizes the target Secret. |
| Detection | Startup error 1045, BE heartbeat state, and tablet replica health. |
| Effect | Loss of one BE reduces tablet redundancy. Several failed restarts can exhaust write quorum. |
| Control | Force ESO sync after the provider update, verify the target Secret, and check each member after restart. |

### Why the failure matters

A 15-minute refresh interval still leaves a window after rotation. An ESO interruption can extend it. A BE that restarts while the Secret is stale can fail to return. If enough BEs restart during the window, the affected tablets can lose write quorum. In the rotation workflow, force ESO to sync after the provider update, check the target Secret, then replace the affected BE. Check registration and tablet health before restarting another member.

[Test procedure](../experiments/README.md#cred-1-be-restart-after-a-root-password-change) · [Full output and run record](part-2-results.md#cred-1) · [Test matrix](#test-driven-design)

## SURGE-1: GKE Surge Upgrade and Recovery

Run continuous SQL probes through the FE Service and through a surviving FE. Request an actual GKE version upgrade with one surge worker and zero unavailable workers. Compare node, pod, and volume identities, replay the client acknowledgments against recovered rows, and verify every replica. Two direct requests failed during leader handoff and neither ID appeared afterward.

**Commands**

```bash
source scripts/common.sh
lab_context
python3 scripts/capture-surge.py \
  --output .local/surge-01 \
  --probe-database fmea_surge_01 \
  --duration 5400
```

```bash
kubectl apply -f experiments/surge-client.yaml
kubectl -n starrocks rollout status deployment/fmea-surge-client
kubectl -n starrocks logs deployment/fmea-surge-client -c client \
  --follow --timestamps --prefix
```

```bash
source scripts/common.sh
lab_context
GKE_PROJECT=$("$TF" -chdir="$ROOT/infra" output -raw project_id)
GKE_REGION=$("$TF" -chdir="$ROOT/infra" output -raw region)
GKE_CLUSTER=$("$TF" -chdir="$ROOT/infra" output -raw cluster_name)
gcloud container node-pools describe experiments \
  --cluster "$GKE_CLUSTER" --region "$GKE_REGION" --project "$GKE_PROJECT"
gcloud container get-server-config \
  --region "$GKE_REGION" --project "$GKE_PROJECT"
```

```bash
TARGET_VERSION=YOUR_SELECTED_VERSION
gcloud container clusters upgrade "$GKE_CLUSTER" \
  --node-pool experiments --cluster-version "$TARGET_VERSION" \
  --region "$GKE_REGION" --project "$GKE_PROJECT"
```

```bash
kubectl -n starrocks scale deployment/fmea-surge-client --replicas=0
touch .local/surge-01/STOP
./scripts/smoke-test.sh
```

**GKE surge upgrade.** PASS for acknowledged-write retention, membership, and replica recovery. This is the verified 21 November run.

**Captured totals**

```json
{
  "workers_replaced": 3,
  "database_pods_replaced": 6,
  "gke_before": "1.36.4-gke.2377000",
  "gke_after": "1.36.5-gke.1259000",
  "image_digests_unchanged": true,
  "all_six_pvc_and_pv_uids_and_disk_handles_unchanged": true,
  "direct_client_successes": 192,
  "exec_probe_successes": 87,
  "unique_acknowledged_writes_verified": 279,
  "rows_after_recovery": 279,
  "ddl_successes": 26,
  "probe_replicas_healthy": 3,
  "baseline_replicas_healthy": 12
}
```

[Test procedure](../experiments/surge-upgrade.md) · [Full output and run record](part-2-results.md#surge-1) · [Test matrix](#test-driven-design)

## Operational Lessons and Limits

- **FE metadata and BE writes:** FE metadata writes require two voting FEs. Existing-table writes require two healthy replicas of each affected tablet under MAJORITY.
- **Client outcomes:** Record client errors, then look up the exact operation or probe ID after recovery before deciding whether to retry.
- **Membership and tablet recovery:** Check database membership and replica status separately. After recovery we checked all twelve baseline replicas and read back acknowledged inserts.
- **Password rotation:** Force ESO synchronization after updating the provider. Verify the target Secret before replacing the affected BE.
- **Maintenance tip:** Prefer blue-green node upgrades for planned maintenance because replacement capacity and soak time let operators inspect recovery before removing the old pool. After an abrupt FE interruption, inspect BDB JE startup, rollback/replay, metadata freshness, election, and rejoin.
- **Scope:** The scope covers single member disruptions and a simulated partition. Dedicated VM loss, simultaneous loss of voting FEs, backup restore, and comprehensive consistency testing remain outside the run.

## Conclusion

Read each run record for the observed result, client response, and recovery evidence. Use the run template to record another lab run. [Run template](run-record.md).
