# StarRocks on Kubernetes FMEA, Part 2: Running the experiments

In [Part 1](https://dok.community/blog/starrocks-kubernetes-fmea-part-1/), we designed a failure modes and effects analysis for StarRocks on GKE. We started with the operations the deployment needed to support and asked what could interrupt them. Here we build the lab, introduce those failures one by one, and see what it takes to recover.

This is for SREs and Kubernetes engineers testing a stateful workload. You can reproduce the lab and use the same checks to distinguish a client error, a member that cannot rejoin, and a database that has yet to restore all its replicas.

## Set up the lab

We ran StarRocks 3.5.21 in shared-nothing mode on a regional GKE Standard cluster, using StarRocks Operator 1.11.4. A fixed pool of three workers put one voting Frontend (FE) and one Backend (BE) in each zone. Each member had its own zonal disk. With no autoscaler and one worker per zone, cordoning a worker let us hold a replacement pod Pending until we were ready to observe recovery.

![StarRocks on GKE architecture from Part 1, showing the Frontend and Backend groups](https://dok.community/blog/starrocks-kubernetes-fmea-part-1/starrocks-deployment_hu_cca5da8fd6eb2c59.webp)

*The deployment topology from Part 1. For these runs we used the lab’s six 25 GiB volumes.*

To follow along, start with a disposable GCP project with billing enabled and quota for three eight-vCPU workers and 300 GiB of SSD capacity. Use the [lab setup guide](../README.md#requirements) to install OpenTofu, Helm, `kubectl`, and the Google Cloud CLI and its GKE auth plugin.

```bash
git clone https://github.com/harsh098/starrocks-gke-fmea.git
cd starrocks-gke-fmea
gcloud auth login
gcloud auth application-default login
cp infra/terraform.tfvars.example infra/terraform.tfvars
```

In `infra/terraform.tfvars`, set `project_id` and set `admin_cidr` to your public IPv4 address followed by `/32`. Then provision the cluster and install StarRocks with the smaller disk profile:

```bash
tofu -chdir=infra init
tofu -chdir=infra plan -out=lab.tfplan
tofu -chdir=infra apply lab.tfplan
./scripts/connect.sh
export KUBECONFIG="$PWD/.local/kubeconfig"
SR_VALUES_FILE=deploy/small-storage-values.yaml ./scripts/deploy.sh
./scripts/topology.sh
./scripts/smoke-test.sh
```

The smoke test seeds `fmea.events` and checks the baseline. We started with three alive FEs, three alive BEs, and four tablets with three healthy replicas each. For the password experiment, we also installed External Secrets Operator (ESO) and configured its first sync with a one-hour refresh interval. The [experiment guide](../experiments/README.md) covers that setup and gives the complete commands for each test.

## Decide what counts as a pass

With three voting FEs, metadata changes require a majority of two. Data writes have a separate rule. Our test table used `MAJORITY`, so a write needed acknowledgments from two replicas of each affected tablet. We chose client probes that could exercise each rule independently and checked the results while the fault was active.

| Test | What we need to see |
| --- | --- |
| FE-1 and FE-2 · Follower and leader exit | The remaining voters can commit metadata, and the replaced FE rejoins. |
| FE-3 · Database network partition | The majority accepts writes, the minority probe is absent afterward, and the cluster recovers. |
| BE-1 · One backend down | An existing table accepts a write with two replicas available. The row survives and every tablet returns to three healthy replicas. |
| CRED-1 · BE restart after password rotation | The replacement BE returns to service without someone forcing a Secret sync. |
| SURGE-1 · GKE worker upgrade | Acknowledged writes survive worker replacement, and membership, storage bindings, and replica health recover. |

## Remove a follower, then the leader

We started with a follower. We cordoned its worker, force-deleted the pod, and waited for StarRocks to report the FE down. With two voting FEs left, a client connected to a surviving FE could still create a database. We uncordoned the worker and watched the replacement rejoin with the same PVC claims. The probe database was still there.

After restoring the baseline, we repeated the test with the leader. FE-2 took over from FE-0 while the old leader’s replacement was held Pending. A surviving FE accepted our metadata probe, and the former leader rejoined after we uncordoned the worker. Both tests passed. The pod exit gave us a controlled process outage. An abrupt VM failure would need its own run.

## Isolate the leader’s zone

This time we left the workers in place and blocked traffic between database pods in the leader’s zone and those in the other two zones. Before trying any writes, we checked that DNS still worked and that the intended links were blocked.

<!-- Diagram slot: three zones with the old leader isolated and the two communicating FEs on the majority side. -->

The majority side accepted a database creation and an insert. On the isolated side, the SQL connection was refused. Once we removed the partition, we looked up both probe databases and the row. The majority’s changes were present, the minority database was absent, and all replicas recovered. That is the observed behavior for this simulated database partition.

## Take one BE out of service

We cordoned a worker and force-deleted only its BE pod. Once StarRocks marked that BE down, it reported one `DEAD` replica on each of our four tablets. A write to the existing table still succeeded with the two replicas available on each tablet.

We uncordoned the worker, let the BE rejoin, and read the same row back. All twelve replicas returned to `OK`. Those two checks tell us different things: the acknowledged write survived and the table regained its full redundancy.

## Rotate the password, then restart a BE

Password rotation exposed a failure that a routine rollout could miss. We began with ESO already polling hourly and confirmed that StarRocks and the Kubernetes Secret had the same root password. Then we rotated the database password and updated the credential at the provider. While the Kubernetes Secret still held the old value, we restarted one BE.

<!-- Diagram slot: password rotation updates StarRocks and the provider, then a stale Kubernetes Secret supplies the old password to the replacement BE. Show the forced sync and restart on the recovery path. -->

The replacement pulled the old password into `MYSQL_PWD` and logged MySQL error 1045, `Access denied`. StarRocks marked the BE down and one replica per tablet went offline. The other two BEs still accepted an insert. **CRED-1 failed** because the restarted BE needed operator intervention to return to service.

We forced ESO to sync the new password from the provider. After confirming the Kubernetes Secret held the new value, we replaced the affected BE again so its container received that value at startup. The BE rejoined, all twelve replicas returned to `OK`, and we could read the row acknowledged during the outage.

The failure mode belongs in the FMEA because a shorter polling interval still leaves a gap between rotation and synchronization. An ESO interruption can extend it. If enough BEs restart during that gap and cannot return, affected tablets can lose write quorum. We would make forced sync and verification of the target Secret part of the rotation procedure, then check membership and replica health after each replacement. The run covered one BE outage. The effect of overlapping BE failures remains a risk to test separately.

## What a real GKE upgrade adds

In a separate surge run, GKE upgraded the node pool and replaced all three workers and all six database pods. The persistent volume bindings stayed the same. Two direct SQL requests failed around leader handoff, and neither probe ID appeared afterward. All 279 acknowledged inserts remained readable, and database membership and tablet replicas recovered.

We also saw a useful distinction for operators. An existing table could accept a majority write with two BEs, but attempts to create a new table with three replicas were rejected when only two BEs were available. For planned maintenance, we prefer blue-green upgrades because replacement capacity and soak time give us room to verify recovery before the old pool is removed. We used surge in this run.

## What we check before moving on

Each disruption ends with three questions. Did the client receive an acknowledgment? Did the affected member rejoin? Did the table regain every replica? Keeping those checks separate exposed both the short interruption during a leader handoff and the longer recovery work after the stale credential failure.

If you reproduce the lab, capture the outcome of each probe and tear down the environment when you finish. The [experiment guide](../experiments/README.md) has the full procedures, and the [run records](part-2-results.md) have the captured output.

```bash
./scripts/teardown.sh
```
