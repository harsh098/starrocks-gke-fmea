# GKE surge upgrade and FE identity recovery

This experiment replaces actual GKE workers while recording FE identity, storage,
membership, and client results. A pod deletion does not exercise the same sequence.
Use only the lab cluster. Keep the captured files private: they include infrastructure
names, addresses, and logs.

## Capture before changing workers

Use the tools and credentials from the main README. From the repository root:

```bash
source scripts/common.sh
lab_context
python3 scripts/capture-surge.py \
  --output .local/surge-01 \
  --probe-database fmea_surge_01 \
  --duration 5400
```

Leave this terminal running. Use a new output directory and database for each run.
The collector creates a small three-replica probe table, attempts inserts and DDL,
and records successful insert acknowledgments separately from failed or timed-out
requests. It captures pod UIDs, image digests, node identity, PVC/PV bindings,
volume attachments, persisted FE `ROLE` files, logs, and membership.

The table-creation probes request three replicas. They can be rejected while only
two BEs are alive, even when existing tables can still accept majority writes.
Record that as a placement/capacity requirement, not as loss of the FE quorum.

`ReadJeGroup.java` queries the live replication group over JE's admin protocol. It
prints the group UUID, ID sequence, and numeric ID-to-name mapping. It does not open
the metadata directory. The helper uses the JE 18.3.20 jar in the pinned lab image.

In a second terminal, after the probe setup succeeds:

```bash
kubectl apply -f experiments/surge-client.yaml
kubectl -n starrocks rollout status deployment/fmea-surge-client
kubectl -n starrocks logs deployment/fmea-surge-client -c client \
  --follow --timestamps --prefix
```

Set `SURGE_DATABASE` in the manifest to the collector's database for a different
run. This client sends SQL through the FE Service and logs each insert ID and exit
code. It runs on the same workers, so it can also be evicted. Reconnect log capture
when its pod changes, and preserve old logs before deletion, or use Cloud Logging.
The collector's exec probes depend on Kubernetes control-plane connectivity;
transport errors such as `No agent available` do not establish a database failure.

## Trigger a genuine version upgrade

In another terminal:

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

Choose an available target version compatible with the control plane. If the target
requires a control-plane upgrade, upgrade the control plane first and wait for its
operation to finish. Then upgrade the worker pool:

```bash
TARGET_VERSION=YOUR_SELECTED_VERSION
gcloud container clusters upgrade "$GKE_CLUSTER" \
  --node-pool experiments --cluster-version "$TARGET_VERSION" \
  --region "$GKE_REGION" --project "$GKE_PROJECT"
```

The baseline pool has `maxSurge=1` and `maxUnavailable=0`. Allow quota for an extra
worker, including its boot disk. GKE processes this regional pool one zone at a
time. The replacement must be in the original volume's zone. Record actual worker
UID/provider-ID changes: a completed upgrade operation alone does not prove that
workers were replaced. Our same-version request completed without replacing them.

Keep the StarRocks image fixed for the first run. The old reference used a mutable
`3.5-latest` tag; a replacement worker could have pulled a different binary. Test
any image change separately with both digests recorded.

## Observe and preserve

Check these conditions throughout the run:

- Does each FE retain its original persisted name and original PVC/PV binding?
- Does the JE group retain a consistent numeric ID-to-name mapping?
- Can the surviving voting majority elect or retain a leader?
- Which client operations succeed, fail explicitly, or have an unknown outcome?
- Do returning FEs rejoin, and do all tablet replicas recover?

If the identity exception appears, preserve its complete stack trace and all
metadata evidence before any repair. Cancel further upgrade progression using the
active operation ID; cancellation allows already-started replacements to finish.
Do not delete PVCs, reset the replication group, or remove followers before saving
the failed state. The collector marks an observed identity/integrity error with
`IDENTITY_OR_INTEGRITY_FAILURE` and stops its own probes. It does not cancel GKE
operations itself.

After the upgrade and recovery, stop the direct writer and collector:

```bash
kubectl -n starrocks scale deployment/fmea-surge-client --replicas=0
touch .local/surge-01/STOP
./scripts/smoke-test.sh
```

Read the probe table and compare IDs against `acknowledged.json` and captured
`WRITE ... code=0` records. Every recorded acknowledgment must remain readable.
Check replica health for the probe table as well as the baseline table. A timeout
can occur after commit; verify its ID before retrying. Preserve evidence before
removing the probe database and client Deployment.

Successful recovery validates this run's conditions. It does not establish why an
earlier upgrade failed. The historical error has a known related bootstrap path in
[StarRocks issue 7498](https://github.com/StarRocks/starrocks/issues/7498), with a
guard added by [PR 8039](https://github.com/StarRocks/starrocks/pull/8039). That path
is a hypothesis to investigate, not an established cause of the GKE incident.

References: [GKE surge behavior](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/node-pool-upgrade-strategies),
[manual upgrades](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/upgrading-a-cluster).

See the [validated run](../docs/validation.md#gke-surge-replay) for observed outcomes.
