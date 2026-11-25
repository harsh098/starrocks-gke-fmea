# Experiments

These procedures implement the Part 2 test matrix. They describe what to measure; they do not copy historical PASS/FAIL labels or assume a root cause for a new run. The pool has a fixed size of one worker per zone and no autoscaler. Record the actual worker count before each test.

Before each experiment, run `./scripts/smoke-test.sh` and record [the baseline](../docs/run-record.md). Export `KUBECONFIG="$PWD/.local/kubeconfig"` for the direct kubectl commands below. Capture timestamps, client responses, database membership, replica status, pod events, and relevant FE/BE logs. Run only one disruption at a time. Wait for all three FEs, all three BEs, and every affected tablet's three replicas to recover before the next test.

## Run one test

After deploying and connecting to the lab, run one command from the repository
directory. Each runner selects its own target and probe identifiers. It prints
the relevant observations and saves detailed evidence under the ignored
`.local/runs/` directory. Wait for recovery before selecting another test.

| Test | Command |
| --- | --- |
| FE-1 | `python3 scripts/run-member-test.py FE-1` |
| FE-2 | `python3 scripts/run-member-test.py FE-2` |
| FE-3 | `bash scripts/run-partition-test.sh` |
| BE-1 | `python3 scripts/run-member-test.py BE-1` |
| ESO preparation | `bash scripts/setup-eso-test.sh` |
| CRED-1 | `bash scripts/run-credential-test.sh` |

CRED-1 reports FAIL when it reproduces the stale-password startup failure.
The runner then forces ESO synchronization, verifies recovery, and restores
the original credential. A zero script exit means the reproduction and
recovery completed. The database test verdict remains FAIL.

## FE-1 and FE-2: FE pod loss and rejoin

**Model:** FE process crash-recovery. Force deletion requests replacement with zero grace, but the API response alone does not confirm that the old process has stopped.

Find the leader (`Role = LEADER`) and voting followers:

```bash
./scripts/sql.sh -e 'SHOW FRONTENDS;'
```

Choose one follower first. Record its UID, then force-delete it:

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

Always uncordon the worker on exit, including if the probe fails. Confirm that
the replacement has a new UID and is alive in database membership.
While it is unavailable, attempt a metadata write through a surviving FE and record the client response. A client timeout does not prove the write was absent; query again after recovery. After the follower case has recovered fully, repeat the same test for the leader, sending SQL through a surviving FE. Confirm election, metadata-write recovery, and rejoin. Do not force-delete multiple FEs together in these tests.

**Recorded result: partial success.** One FE follower was force-deleted and its
replacement rejoined successfully using the same volume. All three FEs and BEs
were alive afterward, all twelve baseline tablet replicas were healthy, and the
baseline rows remained readable. This validates that bounded replacement and
rejoin case. It does not establish recovery from abrupt VM loss or simultaneous
loss of multiple voters.

## BE-1: BE availability with one member held down

**Model:** BE process crash-recovery with one tablet replica unavailable. FE metadata quorum and per-tablet write quorum are separate checks. Cordon the chosen BE's worker before force-deleting its pod so the replacement cannot immediately schedule on that worker. With one worker in each zone, the zonal volume has no other eligible worker in its zone.

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

If the insert or any later step fails, uncordon the worker before leaving the lab. Record tablet status at baseline, during the outage, and after recovery. Check that every acknowledged row remains readable, all three BEs rejoin, and every affected tablet has three healthy replicas on distinct BEs. Membership alone does not establish replica health.

Confirm the BE was actually unavailable when the insert was acknowledged. If it recovered before the insert, that write does not demonstrate availability during the fault. Force-deleting a pod does not prove abrupt VM loss. The separately [recorded GKE surge upgrade](surge-upgrade.md) covers actual planned worker replacement.

## FE-3: Zone network partition

**Model injected:** Network partition (link omission), with an explicit TCP reset to remove established cross-zone sessions. No malicious node or arbitrary message content is injected. An FE knowingly reporting committed metadata without a voting majority would be an observed safety violation; a partition alone is not a Byzantine-node test.

Select the populated zone containing the leader:

```bash
./scripts/topology.sh
./scripts/partition.py start us-west4-a
./scripts/partition.py status
./scripts/partition.py verify
```

Replace the example zone with the leader's actual zone. The script labels the six database pods, applies policies to both sides, allows kube-dns and NodeLocal DNS, and resets existing cross-zone TCP sessions using a `netadmin` ephemeral container. It checks DNS from each zone, probes BE heartbeat ports across both sides, and checks new connections between the majority FEs. Using BE probes keeps the network check independent of an isolated FE restarting. It fails if the reset, DNS, or connectivity checks fail. It never treats policy creation alone as proof of a partition.

Existing allow policies can bypass a partition because NetworkPolicy permissions are additive. The script therefore refuses to start if the dedicated `starrocks` namespace already has policies. Recreated pods stay blocked by the default policy until the experiment is stopped; restart-induced membership changes require a new run. Node traffic, API-server exec access, and DNS are exceptions to the simulation, so this is not a complete physical zone outage. The script does not change GKE control-plane networking.

Query each side locally, selecting actual pods from the topology output:

```bash
SR_FE_POD=starrocks-fmea-fe-0 ./scripts/sql.sh -e 'SHOW FRONTENDS; SHOW BACKENDS;'
SR_FE_POD=starrocks-fmea-fe-1 ./scripts/sql.sh -e 'SHOW FRONTENDS; SHOW BACKENDS;'
```

Attempt a **metadata mutation** from each side with distinct database names. For example, run `CREATE DATABASE fmea_partition_minority` on the isolated FE and `CREATE DATABASE fmea_partition_majority` on the majority side. Record the actual response. After recovery, check whether either mutation committed. Avoid treating a successful read or a stale leadership label as a committed metadata write.

Separately attempt an insert on the majority side and inspect per-tablet write availability. Record errors, success responses, and the data visible after recovery. The FE quorum check and the BE replica acknowledgment check are different experiments even when the same partition affects both.

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

Choose FE names from the actual topology and run the probes individually so
the expected minority error does not skip the other checks.

Always remove the partition, including after a failed test:

```bash
./scripts/partition.py stop
./scripts/smoke-test.sh
./scripts/sql.sh -e "SHOW DATABASES LIKE 'fmea_majority_$RUN_ID'; SHOW DATABASES LIKE 'fmea_minority_$RUN_ID';"
./scripts/sql.sh -e "SELECT * FROM fmea.events WHERE event_id=$EVENT_ID;"
./scripts/sql.sh -e 'ADMIN SHOW REPLICA STATUS FROM fmea.events;'
```

Repeat by isolating a follower's zone only after full recovery. Ephemeral debug containers remain in pod history until the pod is replaced.

## CRED-1: BE restart after a root password change

**Model:** Node crash-recovery with a stale startup credential. Password rotation is a configuration change; it is not itself a crash.

Record the existing `starrocks-admin-password` Secret in a protected local file before changing anything. Do not commit it or include the password in logs. The initial generated password is also in `.local/root-password` if you created the cluster with this repo.

**PASS:** The replacement BE authenticates and becomes healthy without manual
Secret synchronization.

**FAIL (expected):** Startup logs show the replacement BE cannot authenticate
and return to service while the target Secret still contains the old password.
Record that verdict before attempting recovery.

For the failure reproduction, keep the Kubernetes Secret stale after rotating the database
password, confirm the mismatch, and restart one BE while it is stale. This lab
uses a manually managed Secret; no controller refreshes it automatically.
`MYSQL_PWD` is read from the Secret when a container starts and has no refresh
interval inside an existing container.

For a lab with External Secrets Operator (ESO), follow the
[ESO reproduction](#eso-reproduction-and-recovery) instead of manually
updating the target Secret.

To recover, synchronize the correct Secret and replace the affected
BE container. In deployments with External Secrets Operator, a short refresh
interval or forced sync can update the Secret sooner; a reloader or controlled
rollout can then replace containers. Secret synchronization does not refresh an
existing process's environment. Restart one member at a time and verify quorum,
membership, and tablet health between replacements. The baseline lab does not
install ESO or a reloader; this remediation is guidance until tested there.

1. Change the database root password through an interactive MySQL session, using `SET PASSWORD FOR 'root'@'%' = PASSWORD('<new-lab-password>');` with your own lab-only value. Keep the Kubernetes Secret unchanged for this first phase.
2. Restart **one** BE. Inspect its startup logs and registration. Check write availability and tablet status while the other two BEs remain healthy. Do not restart another BE while the first is unhealthy.
3. Update the existing Kubernetes Secret's `password` key to the current database password. Supply it through a protected file, rather than a command-line literal:

   ```bash
   kubectl -n starrocks create secret generic starrocks-admin-password \
     --from-file=password=.local/current-root-password \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

4. Delete only the failed BE pod so its replacement reads the updated Secret. Verify registration, acknowledged reads, and three healthy replicas for every affected tablet before restarting any other member.
5. Existing FE pods still have the old `MYSQL_PWD` environment value, so `sql.sh` may now fail to authenticate. For this phase, use an interactive MySQL password prompt on a surviving FE:

   ```bash
   kubectl -n starrocks exec -it starrocks-fmea-fe-0 -c fe -- \
     mysql --host=127.0.0.1 --port=9030 --user=root --password
   ```

6. Recover the lab by returning the database password and Secret to the original value, or by completing a controlled one-at-a-time FE/BE restart with the new value. Check both groups and all tablet replicas after each member. Updating the Secret alone does not update running containers or rotate the database password.

For this pinned chart, the FE initialization job runs on the initial Helm install. Do not assume rerunning `deploy.sh` rotates credentials or fixes a drifted password. See the [versioned operator guide](https://github.com/StarRocks/starrocks-kubernetes-operator/blob/v1.11.4/doc/change_root_password_howto.md).

### ESO reproduction and recovery

For the standalone GKE lab, install ESO with the pinned chart and use the
Kubernetes provider in a dedicated source namespace. The manifest merges only
the password key into the existing StarRocks Secret and configures hourly
polling at creation. Run from the repository root after deployment.

```bash
helm upgrade --install external-secrets external-secrets \
  --repo https://charts.external-secrets.io --version 2.12.0 \
  --namespace external-secrets --create-namespace --wait
kubectl create namespace starrocks-eso-source --dry-run=client -o yaml | kubectl apply -f -
kubectl -n starrocks-eso-source create secret generic starrocks-admin-password \
  --from-file=password=.local/root-password
kubectl apply -f experiments/eso-lab.yaml
kubectl -n starrocks wait --for=condition=Ready \
  secretstore/starrocks-password-source externalsecret/starrocks-admin-password --timeout=100s
```

Use a lab with ESO and a working SecretStore. Start with an ExternalSecret in
the `starrocks` namespace that maps the provider's lab root password to
`starrocks-admin-password`, key `password`. Seed the provider with the
current database password and confirm that ESO has synchronized it before
starting. Pause any reloader for this workload during fault injection so
only the selected BE restarts. Set `ES` below to the ExternalSecret's actual
name.

**Before the test**, configure ESO with the one-hour polling patch and request
a baseline sync. Wait for `refreshTime` to advance and confirm the target Secret still
matches the original password before rotating it.

```bash
ES=starrocks-admin-password
kubectl -n starrocks patch externalsecret "$ES" --type=merge \
  --patch-file=experiments/password-sync-delay.patch.yaml
kubectl -n starrocks get externalsecret "$ES" -o jsonpath='{.status.refreshTime}{"\n"}'
kubectl -n starrocks annotate externalsecret "$ES" force-sync="$(date +%s%N)" --overwrite
kubectl -n starrocks get externalsecret "$ES" -o jsonpath='{.status.refreshTime}{"\n"}'
```

Rotate the database password and write the same new value to the provider.
For the Kubernetes provider in this lab, save the exact password bytes in
the protected `.local/current-root-password` file and update the source Secret:

```bash
kubectl -n starrocks-eso-source create secret generic starrocks-admin-password \
  --from-file=password=.local/current-root-password --dry-run=client -o yaml \
  | kubectl apply --server-side --force-conflicts -f -
```

For other providers, use their normal credential update procedure. Before restarting
one BE, verify that the target Secret still contains the original password.
Use the protected file captured at baseline to compare without printing either
value:

```bash
kubectl -n starrocks get secret starrocks-admin-password -o jsonpath='{.data.password}' \
  | base64 --decode | cmp -s - .local/root-password
```

If the comparison fails, stop and reestablish the stale window. The next
periodic sync depends on the preceding refresh time. Keep the other two BEs
healthy and capture the affected BE's startup logs, client write results, and
tablet replica status. Wait for the FE heartbeat view to mark the restarted
BE unavailable before measuring writes with two BEs. A startup authentication
failure can appear before that view changes. Check the Secret again if the
expected failure does not occur.

**Recovery.** Force ESO to sync the provider's current password, then
wait for the target Secret to match the new password. Save the exact new
password bytes in the protected `.local/current-root-password` file first.
Repeat the comparison until it succeeds before replacing the affected pod.

```bash
kubectl -n starrocks annotate externalsecret "$ES" force-sync="$(date +%s%N)" --overwrite
kubectl -n starrocks get secret starrocks-admin-password -o jsonpath='{.data.password}' \
  | base64 --decode | cmp -s - .local/current-root-password
```

Replace the affected BE container. Verify that it registers, read back all
acknowledged writes, and use `ADMIN SHOW REPLICA STATUS FROM fmea.events` to
verify three healthy replicas per affected tablet. Restore the intended ESO
refresh settings after the experiment. For subsequent rotations, prefer a
short interval or forced sync followed by a controlled rollout. If using a
reloader, verify that its rollout preserves quorum and checks recovery before
replacing another member.

See the [ESO refresh policies and manual sync documentation](https://external-secrets.io/latest/api/externalsecret/).
The [ESO run](../docs/part-2-results.md#cred-1) reproduced the expected
startup failure and verified recovery. The manual variant remains available
for labs without ESO. A shorter interval still leaves a stale window, and an
ESO interruption can extend it. Running BEs can continue until they restart.
If enough BEs restart and cannot return to service, affected tablets can lose
write quorum.
