# Experiments

These procedures adapt the reference sandbox's FMEA scenarios. They describe what to measure; they do not copy historical PASS/FAIL labels or assume a root cause for a new run.

Before each experiment, run `./scripts/smoke-test.sh` and record [the baseline](../docs/run-record.md). Export `KUBECONFIG="$PWD/.local/kubeconfig"` for the direct kubectl commands below. Capture timestamps, client responses, database membership, replica status, pod events, and relevant FE/BE logs. Run only one disruption at a time.

## 1. FE follower or leader restart

**Model:** Node crash-recovery. Pod deletion requests graceful termination, so it is not an abrupt process-kill test.

Find the leader (`Role = LEADER`) and voting followers:

```bash
./scripts/sql.sh -e 'SHOW FRONTENDS;'
```

Choose one follower first. Replace the example pod name with the member you selected:

```bash
kubectl -n starrocks delete pod starrocks-fmea-fe-1
./scripts/sql.sh -e "CREATE DATABASE IF NOT EXISTS fmea_restart_probe;"
./scripts/sql.sh -e 'SHOW FRONTENDS;'
kubectl -n starrocks rollout status statefulset/starrocks-fmea-fe --timeout=10m
./scripts/smoke-test.sh
```

Repeat with the leader after full recovery. If FE-0 is the target, set `SR_FE_POD=starrocks-fmea-fe-1` (or another live FE) for the SQL calls.

Check that the two surviving voters can commit metadata, that a leader is elected when needed, and that the restarted member rejoins. Measure interruption and recovery times. A client timeout alone does not prove that an operation was not committed; query the database afterward.

## 2. BE restart

**Model:** Node crash-recovery. FE metadata quorum and per-tablet write quorum are separate checks.

```bash
kubectl -n starrocks delete pod starrocks-fmea-be-0
./scripts/sql.sh -e "INSERT INTO fmea.events VALUES (10, '2026-01-01 00:01:00', 'during-be-restart');"
./scripts/sql.sh -e 'SHOW BACKENDS; SELECT * FROM fmea.events WHERE event_id=10;'
kubectl -n starrocks rollout status statefulset/starrocks-fmea-be --timeout=10m
./scripts/sql.sh -e 'ADMIN SHOW REPLICA STATUS FROM fmea.events;'
```

Check whether the acknowledged write remains readable, all three BEs rejoin, and every affected tablet has three healthy replicas after recovery. Membership alone does not establish replica health. Use a new event ID on repeated runs because this table uses `DUPLICATE KEY`.

Confirm that the BE is actually unavailable when testing write availability, or run a timestamped client workload in a second terminal throughout the disruption. If the BE has already recovered before the insert, that insert does not demonstrate behavior during a fault.

## 3. Planned worker drain and abrupt worker replacement

**Models:** Planned disruption and database-member crash-recovery; abrupt worker loss adds a node crash-stop assumption for the old worker.

List placement and choose one worker:

```bash
./scripts/topology.sh
NODE=<one-lab-worker-name>
kubectl cordon "$NODE"
kubectl drain "$NODE" --ignore-daemonsets --delete-emptydir-data --timeout=10m
```

One worker hosts one FE and one BE. Operator `1.11.4` exposes no PDB field in `StarRocksCluster`; this baseline does not create a standalone PDB either. Draining another worker before recovery can remove both majorities.

There is only one worker in each zone. Its zonal volumes cannot attach to a worker in another zone, so replacement pods may remain Pending while the selected worker is cordoned. This is an expected placement limit, separate from a failed database restart.

```bash
kubectl uncordon "$NODE"
./scripts/smoke-test.sh
./scripts/sql.sh -e 'ADMIN SHOW REPLICA STATUS FROM fmea.events;'
```

For a separate abrupt-loss test, reset one lab VM without draining. Determine its project, zone, and instance name from the chosen node's provider ID. A reset reboots the same VM rather than proving permanent worker replacement:

```bash
kubectl get node "$NODE" -o jsonpath='{.spec.providerID}{"\n"}'
# providerID is gce://PROJECT/ZONE/INSTANCE. Use those exact values:
gcloud compute instances reset INSTANCE --zone ZONE --project PROJECT
```

If you need permanent worker replacement, use the node pool's managed instance group's `recreate-instances` operation for that one VM and record it as a separate experiment. Do not delete the Kubernetes Node object as a substitute for losing the VM. Check disk attachment, FE startup logs, member identity, and tablet recovery. Do not infer a metadata-corruption cause from a single failed restart, and do not delete metadata PVCs as routine recovery.

## 4. Zone network partition

**Model injected:** Network partition (link omission), with an explicit TCP reset to remove established cross-zone sessions. No malicious node or arbitrary message content is injected. An FE knowingly reporting committed metadata without a voting majority would be an observed safety violation; a partition alone is not a Byzantine-node test.

Select the populated zone containing the leader:

```bash
./scripts/topology.sh
./scripts/partition.py start us-west4-a
./scripts/partition.py status
./scripts/partition.py verify
```

Replace the example zone with the leader's actual zone. The script labels the six database pods, applies policies to both sides, allows DNS, resets existing cross-zone TCP sessions using a `netadmin` ephemeral container, and probes new FE connections. It fails if the reset or connectivity checks fail. It never treats policy creation alone as proof of a partition.

Existing allow policies can bypass a partition because NetworkPolicy permissions are additive. The script therefore refuses to start if the dedicated `starrocks` namespace already has policies. Recreated pods stay blocked by the default policy until the experiment is stopped; restart-induced membership changes require a new run. Node traffic, API-server exec access, and DNS are exceptions to the simulation, so this is not a complete physical zone outage. The script does not change GKE control-plane networking.

Query each side locally, selecting actual pods from the topology output:

```bash
SR_FE_POD=starrocks-fmea-fe-0 ./scripts/sql.sh -e 'SHOW FRONTENDS; SHOW BACKENDS;'
SR_FE_POD=starrocks-fmea-fe-1 ./scripts/sql.sh -e 'SHOW FRONTENDS; SHOW BACKENDS;'
```

Attempt a **metadata mutation** from each side with distinct database names. For example, run `CREATE DATABASE fmea_partition_minority` on the isolated FE and `CREATE DATABASE fmea_partition_majority` on the majority side. Record the actual response. After recovery, check whether either mutation committed. Avoid treating a successful read or a stale leadership label as a committed metadata write.

Separately attempt an insert on the majority side and inspect per-tablet write availability. Record errors, success responses, and the data visible after recovery. The FE quorum check and the BE replica acknowledgment check are different experiments even when the same partition affects both.

Always remove the partition, including after a failed test:

```bash
./scripts/partition.py stop
./scripts/smoke-test.sh
./scripts/sql.sh -e 'ADMIN SHOW REPLICA STATUS FROM fmea.events;'
```

Repeat by isolating a follower's zone only after full recovery. Ephemeral debug containers remain in pod history until the pod is replaced.

## 5. BE restart after a root password change

**Model:** Node crash-recovery with a stale startup credential. Password rotation is a configuration change; it is not itself a crash.

Record the existing `starrocks-admin-password` Secret in a protected local file before changing anything. Do not commit it or include the password in logs. The initial generated password is also in `.local/root-password` if you created the cluster with this repo.

1. Change the database root password through an interactive MySQL session, using `SET PASSWORD FOR 'root'@'%' = PASSWORD('<new-lab-password>');` with your own lab-only value. Keep the Kubernetes Secret unchanged for this first phase.
2. Restart **one** BE. Inspect its startup logs and registration. Check write availability while two healthy BE replicas remain. Do not restart another BE while the first is unhealthy.
3. Update the existing Kubernetes Secret's `password` key to the current database password. Supply it through a protected file, rather than a command-line literal:

   ```bash
   kubectl -n starrocks create secret generic starrocks-admin-password \
     --from-file=password=.local/current-root-password \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

4. Delete only the failed BE pod so its replacement reads the updated Secret. Verify registration and replica health before restarting any other member.
5. Existing FE pods still have the old `MYSQL_PWD` environment value, so `sql.sh` may now fail to authenticate. For this phase, use an interactive MySQL password prompt on a surviving FE:

   ```bash
   kubectl -n starrocks exec -it starrocks-fmea-fe-0 -c fe -- \
     mysql --host=127.0.0.1 --port=9030 --user=root --password
   ```

6. Recover the lab by returning the database password and Secret to the original value, or by completing a controlled one-at-a-time FE/BE restart with the new value. Check both groups and all tablet replicas after each member. Updating the Secret alone does not update running containers or rotate the database password.

For this pinned chart, the FE initialization job runs on the initial Helm install. Do not assume rerunning `deploy.sh` rotates credentials or fixes a drifted password. See the [versioned operator guide](https://github.com/StarRocks/starrocks-kubernetes-operator/blob/v1.11.4/doc/change_root_password_howto.md).
