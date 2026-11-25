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

### FE-1: Follower exit

We started with a follower. We cordoned its worker, force-deleted the pod, and waited for StarRocks to report the FE down. With two voting FEs left, a client connected to a surviving FE could still create a database. We uncordoned the worker and watched the replacement rejoin with the same PVC claims. The probe database was still there.

<details>
<summary>FE-1 output: follower outage and rejoin</summary>

```text
FE-1 baseline 2026-11-25T15:38:32Z
PASS: three workers in three zones
PASS: three ready FEs and three ready BEs, spread across workers
PASS: three alive FE members and three alive BE members
Table	Create Table
events	CREATE TABLE `events` (\n  `event_id` bigint(20) NOT NULL COMMENT "",\n  `event_time` datetime NOT NULL COMMENT "",\n  `payload` varchar(128) NULL COMMENT ""\n) ENGINE=OLAP \nDUPLICATE KEY(`event_id`, `event_time`)\nDISTRIBUTED BY HASH(`event_id`) BUCKETS 4 \nPROPERTIES (\n"compression" = "LZ4",\n"fast_schema_evolution" = "true",\n"replicated_storage" = "true",\n"replication_num" = "3"\n);
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10312	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10313	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10315	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10316	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10317	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10319	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10320	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10321	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10323	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10324	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10325	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
PASS: all four tablets have three healthy replicas on distinct BEs
PASS: baseline rows can be read from the three-replica test table
Id	Name	IP	EditLogPort	HttpPort	QueryPort	RpcPort	Role	ClusterId	Join	Alive	ReplayedJournalId	LastHeartbeat	IsHelper	ErrMsg	StartTime	Version
1	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617937727	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	LEADER	1116536338	true	true	2447	2026-11-25 15:38:44	true		2026-11-25 14:45:46	3.5.21-85fccf8
2	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617959917	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	true	true	2445	2026-11-25 15:38:44	true		2026-11-25 14:46:06	3.5.21-85fccf8
3	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617960063	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	true	true	2445	2026-11-25 15:38:44	true		2026-11-25 14:46:06	3.5.21-85fccf8
BackendId	IP	HeartbeatPort	BePort	HttpPort	BrpcPort	LastStartTime	LastHeartbeat	Alive	SystemDecommissioned	ClusterDecommissioned	TabletNum	DataUsedCapacity	AvailCapacity	TotalCapacity	UsedPct	MaxDiskUsedPct	ErrMsg	Version	Status	DataTotalCapacity	DataUsedPct	CpuCores	MemLimit	NumRunningQueries	MemUsedPct	CpuUsedPct	DataCacheMetrics	Location	StatusCode
10002	starrocks-fmea-be-0.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:38:44	true	false	false	94	75.215 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:38:42"}	24.057 GB	0.00 %	4	12.960GB	0	1.44 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10001	starrocks-fmea-be-1.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:38:44	true	false	false	94	74.056 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:38:42"}	24.057 GB	0.00 %	4	12.960GB	0	1.45 %	0.2 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10003	starrocks-fmea-be-2.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:38:44	true	false	false	94	75.203 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:38:42"}	24.057 GB	0.00 %	4	12.960GB	0	1.44 %	0.0 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10312	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10313	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10315	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10316	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10317	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10319	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10320	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10321	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10323	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10324	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10325	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
node/[lab-worker] cordoned
Warning: Immediate deletion does not wait for confirmation that the running resource has been terminated. The resource may continue to run on the cluster indefinitely.
pod "starrocks-fmea-fe-1" force deleted from starrocks namespace
Fault requested 2026-11-25T15:38:49Z
Id	Name	IP	EditLogPort	HttpPort	QueryPort	RpcPort	Role	ClusterId	Join	Alive	ReplayedJournalId	LastHeartbeat	IsHelper	ErrMsg	StartTime	Version
1	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617937727	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	LEADER	1116536338	true	true	2479	2026-11-25 15:39:14	true		2026-11-25 14:45:46	3.5.21-85fccf8
2	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617959917	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	true	true	2478	2026-11-25 15:39:14	true		2026-11-25 14:46:06	3.5.21-85fccf8
3	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617960063	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	false	false	2463	2026-11-25 15:38:49	true	Connect timed out	NULL	3.5.21-85fccf8
Target confirmed down: true at 2026-11-25T15:39:17Z
NAME                  PHASE     NODE
starrocks-fmea-fe-1   Pending   <none>
Probe: CREATE DATABASE fmea_fe_1_1795621129;
--------------
CREATE DATABASE fmea_fe_1_1795621129
--------------

Probe exit: 0
node/[lab-worker] uncordoned
PASS: three workers in three zones
Traceback (most recent call last):
  File "<string>", line 8, in <module>
    assert all(any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", [])) for p in group), f"{component} pods are not all Ready"
           ~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: fe pods are not all Ready
PASS: three workers in three zones
Traceback (most recent call last):
  File "<string>", line 8, in <module>
    assert all(any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", [])) for p in group), f"{component} pods are not all Ready"
           ~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: fe pods are not all Ready
PASS: three workers in three zones
Traceback (most recent call last):
  File "<string>", line 8, in <module>
    assert all(any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", [])) for p in group), f"{component} pods are not all Ready"
           ~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: fe pods are not all Ready
PASS: three workers in three zones
PASS: three ready FEs and three ready BEs, spread across workers
PASS: three alive FE members and three alive BE members
Table	Create Table
events	CREATE TABLE `events` (\n  `event_id` bigint(20) NOT NULL COMMENT "",\n  `event_time` datetime NOT NULL COMMENT "",\n  `payload` varchar(128) NULL COMMENT ""\n) ENGINE=OLAP \nDUPLICATE KEY(`event_id`, `event_time`)\nDISTRIBUTED BY HASH(`event_id`) BUCKETS 4 \nPROPERTIES (\n"compression" = "LZ4",\n"fast_schema_evolution" = "true",\n"replicated_storage" = "true",\n"replication_num" = "3"\n);
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10312	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10313	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10315	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10316	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10317	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10319	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10320	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10321	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10323	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10324	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10325	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
PASS: all four tablets have three healthy replicas on distinct BEs
PASS: baseline rows can be read from the three-replica test table
Pod UID changed: yes
PVC claims unchanged: yes
Id	Name	IP	EditLogPort	HttpPort	QueryPort	RpcPort	Role	ClusterId	Join	Alive	ReplayedJournalId	LastHeartbeat	IsHelper	ErrMsg	StartTime	Version
1	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617937727	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	LEADER	1116536338	true	true	2506	2026-11-25 15:39:59	true		2026-11-25 14:45:46	3.5.21-85fccf8
2	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617959917	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	true	true	2505	2026-11-25 15:39:59	true		2026-11-25 14:46:06	3.5.21-85fccf8
3	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617960063	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	true	true	2505	2026-11-25 15:39:59	true		2026-11-25 15:39:36	3.5.21-85fccf8
BackendId	IP	HeartbeatPort	BePort	HttpPort	BrpcPort	LastStartTime	LastHeartbeat	Alive	SystemDecommissioned	ClusterDecommissioned	TabletNum	DataUsedCapacity	AvailCapacity	TotalCapacity	UsedPct	MaxDiskUsedPct	ErrMsg	Version	Status	DataTotalCapacity	DataUsedPct	CpuCores	MemLimit	NumRunningQueries	MemUsedPct	CpuUsedPct	DataCacheMetrics	Location	StatusCode
10002	starrocks-fmea-be-0.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:39:59	true	false	false	94	86.307 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:39:42"}	24.057 GB	0.00 %	4	12.960GB	0	1.45 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10001	starrocks-fmea-be-1.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:39:59	true	false	false	94	85.631 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:39:42"}	24.057 GB	0.00 %	4	12.960GB	0	1.45 %	0.2 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10003	starrocks-fmea-be-2.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:39:59	true	false	false	94	86.307 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:39:42"}	24.057 GB	0.00 %	4	12.960GB	0	1.45 %	0.0 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10312	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10313	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10315	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10316	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10317	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10319	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10320	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10321	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10323	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10324	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10325	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
Database
fmea_fe_1_1795621129
Recovery observed 2026-11-25T15:40:01Z
```

</details>

### FE-2: Leader exit

After restoring the baseline, we repeated the test with the leader. FE-2 took over from FE-0 while the old leader’s replacement was held Pending. A surviving FE accepted our metadata probe, and the former leader rejoined after we uncordoned the worker. Both tests passed. The pod exit gave us a controlled process outage. An abrupt VM failure would need its own run.

<details>
<summary>FE-2 output: leader election and rejoin</summary>

```text
FE-2 baseline 2026-11-25T15:40:23Z
PASS: three workers in three zones
PASS: three ready FEs and three ready BEs, spread across workers
PASS: three alive FE members and three alive BE members
Table	Create Table
events	CREATE TABLE `events` (\n  `event_id` bigint(20) NOT NULL COMMENT "",\n  `event_time` datetime NOT NULL COMMENT "",\n  `payload` varchar(128) NULL COMMENT ""\n) ENGINE=OLAP \nDUPLICATE KEY(`event_id`, `event_time`)\nDISTRIBUTED BY HASH(`event_id`) BUCKETS 4 \nPROPERTIES (\n"compression" = "LZ4",\n"fast_schema_evolution" = "true",\n"replicated_storage" = "true",\n"replication_num" = "3"\n);
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10312	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10313	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10315	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10316	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10317	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10319	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10320	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10321	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10323	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10324	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10325	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
PASS: all four tablets have three healthy replicas on distinct BEs
PASS: baseline rows can be read from the three-replica test table
Id	Name	IP	EditLogPort	HttpPort	QueryPort	RpcPort	Role	ClusterId	Join	Alive	ReplayedJournalId	LastHeartbeat	IsHelper	ErrMsg	StartTime	Version
1	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617937727	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	LEADER	1116536338	true	true	2525	2026-11-25 15:40:34	true		2026-11-25 14:45:46	3.5.21-85fccf8
2	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617959917	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	true	true	2523	2026-11-25 15:40:34	true		2026-11-25 14:46:06	3.5.21-85fccf8
3	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617960063	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	true	true	2523	2026-11-25 15:40:34	true		2026-11-25 15:39:36	3.5.21-85fccf8
BackendId	IP	HeartbeatPort	BePort	HttpPort	BrpcPort	LastStartTime	LastHeartbeat	Alive	SystemDecommissioned	ClusterDecommissioned	TabletNum	DataUsedCapacity	AvailCapacity	TotalCapacity	UsedPct	MaxDiskUsedPct	ErrMsg	Version	Status	DataTotalCapacity	DataUsedPct	CpuCores	MemLimit	NumRunningQueries	MemUsedPct	CpuUsedPct	DataCacheMetrics	Location	StatusCode
10002	starrocks-fmea-be-0.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:40:34	true	false	false	94	86.307 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:39:42"}	24.057 GB	0.00 %	4	12.960GB	0	1.46 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10001	starrocks-fmea-be-1.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:40:34	true	false	false	94	85.631 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:39:42"}	24.057 GB	0.00 %	4	12.960GB	0	1.45 %	0.0 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10003	starrocks-fmea-be-2.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:40:34	true	false	false	94	86.307 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:39:42"}	24.057 GB	0.00 %	4	12.960GB	0	1.45 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10312	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10313	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10315	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10316	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10317	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10319	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10320	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10321	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10323	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10324	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10325	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
node/[lab-worker] cordoned
Warning: Immediate deletion does not wait for confirmation that the running resource has been terminated. The resource may continue to run on the cluster indefinitely.
pod "starrocks-fmea-fe-0" force deleted from starrocks namespace
Fault requested 2026-11-25T15:40:40Z
Id	Name	IP	EditLogPort	HttpPort	QueryPort	RpcPort	Role	ClusterId	Join	Alive	ReplayedJournalId	LastHeartbeat	IsHelper	ErrMsg	StartTime	Version
1	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617937727	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	false	false	2525	2026-11-25 15:40:39	true	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local	NULL	3.5.21-85fccf8
2	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617959917	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	LEADER	1116536338	true	true	2533	2026-11-25 15:40:59	true		2026-11-25 14:46:06	3.5.21-85fccf8
3	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617960063	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	true	true	2532	2026-11-25 15:40:59	true		2026-11-25 15:39:36	3.5.21-85fccf8
Target confirmed down: true at 2026-11-25T15:41:01Z
NAME                  PHASE     NODE
starrocks-fmea-fe-0   Pending   <none>
Probe: CREATE DATABASE fmea_fe_2_1795621240;
--------------
CREATE DATABASE fmea_fe_2_1795621240
--------------

Probe exit: 0
node/[lab-worker] uncordoned
PASS: three workers in three zones
Traceback (most recent call last):
  File "<string>", line 8, in <module>
    assert all(any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", [])) for p in group), f"{component} pods are not all Ready"
           ~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: fe pods are not all Ready
PASS: three workers in three zones
Traceback (most recent call last):
  File "<string>", line 8, in <module>
    assert all(any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", [])) for p in group), f"{component} pods are not all Ready"
           ~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: fe pods are not all Ready
PASS: three workers in three zones
PASS: three ready FEs and three ready BEs, spread across workers
PASS: three alive FE members and three alive BE members
Table	Create Table
events	CREATE TABLE `events` (\n  `event_id` bigint(20) NOT NULL COMMENT "",\n  `event_time` datetime NOT NULL COMMENT "",\n  `payload` varchar(128) NULL COMMENT ""\n) ENGINE=OLAP \nDUPLICATE KEY(`event_id`, `event_time`)\nDISTRIBUTED BY HASH(`event_id`) BUCKETS 4 \nPROPERTIES (\n"compression" = "LZ4",\n"fast_schema_evolution" = "true",\n"replicated_storage" = "true",\n"replication_num" = "3"\n);
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10312	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10313	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10315	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10316	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10317	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10319	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10320	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10321	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10323	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10324	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10325	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
PASS: all four tablets have three healthy replicas on distinct BEs
PASS: baseline rows can be read from the three-replica test table
Pod UID changed: yes
PVC claims unchanged: yes
Id	Name	IP	EditLogPort	HttpPort	QueryPort	RpcPort	Role	ClusterId	Join	Alive	ReplayedJournalId	LastHeartbeat	IsHelper	ErrMsg	StartTime	Version
1	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617937727	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	true	true	2553	2026-11-25 15:41:34	true		2026-11-25 15:41:19	3.5.21-85fccf8
2	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617959917	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	LEADER	1116536338	true	true	2555	2026-11-25 15:41:34	true		2026-11-25 14:46:06	3.5.21-85fccf8
3	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617960063	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	true	true	2553	2026-11-25 15:41:34	true		2026-11-25 15:39:36	3.5.21-85fccf8
BackendId	IP	HeartbeatPort	BePort	HttpPort	BrpcPort	LastStartTime	LastHeartbeat	Alive	SystemDecommissioned	ClusterDecommissioned	TabletNum	DataUsedCapacity	AvailCapacity	TotalCapacity	UsedPct	MaxDiskUsedPct	ErrMsg	Version	Status	DataTotalCapacity	DataUsedPct	CpuCores	MemLimit	NumRunningQueries	MemUsedPct	CpuUsedPct	DataCacheMetrics	Location	StatusCode
10002	starrocks-fmea-be-0.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:41:34	true	false	false	94	0.000 B	24.416 GB	24.440 GB	0.10 %	0.10 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:40:44"}	24.416 GB	0.00 %	4	12.960GB	0	1.46 %	0.0 %	N/A		OK
10001	starrocks-fmea-be-1.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:41:34	true	false	false	94	0.000 B	24.416 GB	24.440 GB	0.10 %	0.10 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:40:44"}	24.416 GB	0.00 %	4	12.960GB	0	1.45 %	0.1 %	N/A		OK
10003	starrocks-fmea-be-2.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:41:34	true	false	false	94	0.000 B	24.416 GB	24.440 GB	0.10 %	0.10 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:40:44"}	24.416 GB	0.00 %	4	12.960GB	0	1.45 %	0.2 %	N/A		OK
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10312	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10313	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10315	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10316	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10317	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10319	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10320	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10321	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10323	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10324	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10325	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
Database
fmea_fe_2_1795621240
Recovery observed 2026-11-25T15:41:38Z
```

</details>

## Isolate the leader’s zone

This time we left the workers in place and blocked traffic between database pods in the leader’s zone and those in the other two zones. Before trying any writes, we checked that DNS still worked and that the intended links were blocked.

<!-- Diagram slot: three zones with the old leader isolated and the two communicating FEs on the majority side. -->

The majority side accepted a database creation and an insert. On the isolated side, the SQL connection was refused. Once we removed the partition, we looked up both probe databases and the row. The majority’s changes were present, the minority database was absent, and all replicas recovered. That is the observed behavior for this simulated database partition.

<details>
<summary>FE-3 output: partition probes and recovery</summary>

```text
FE-3 baseline 2026-11-25T15:43:04Z, isolated pod starrocks-fmea-fe-2
PASS: three workers in three zones
PASS: three ready FEs and three ready BEs, spread across workers
PASS: three alive FE members and three alive BE members
Table	Create Table
events	CREATE TABLE `events` (\n  `event_id` bigint(20) NOT NULL COMMENT "",\n  `event_time` datetime NOT NULL COMMENT "",\n  `payload` varchar(128) NULL COMMENT ""\n) ENGINE=OLAP \nDUPLICATE KEY(`event_id`, `event_time`)\nDISTRIBUTED BY HASH(`event_id`) BUCKETS 4 \nPROPERTIES (\n"compression" = "LZ4",\n"fast_schema_evolution" = "true",\n"replicated_storage" = "true",\n"replication_num" = "3"\n);
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	3	-1	3	3	0	2	false	false	NORMAL	OK
10310	10312	10003	3	-1	3	3	0	2	false	false	NORMAL	OK
10310	10313	10002	3	-1	3	3	0	2	false	false	NORMAL	OK
10314	10315	10001	3	-1	3	3	0	2	false	false	NORMAL	OK
10314	10316	10003	3	-1	3	3	0	2	false	false	NORMAL	OK
10314	10317	10002	3	-1	3	3	0	2	false	false	NORMAL	OK
10318	10319	10001	3	-1	3	3	0	2	false	false	NORMAL	OK
10318	10320	10003	3	-1	3	3	0	2	false	false	NORMAL	OK
10318	10321	10002	3	-1	3	3	0	2	false	false	NORMAL	OK
10322	10323	10001	3	-1	3	3	0	2	false	false	NORMAL	OK
10322	10324	10003	3	-1	3	3	0	2	false	false	NORMAL	OK
10322	10325	10002	3	-1	3	3	0	2	false	false	NORMAL	OK
PASS: all four tablets have three healthy replicas on distinct BEs
PASS: baseline rows can be read from the three-replica test table
Resetting cross-zone connections in starrocks-fmea-be-0
Resetting cross-zone connections in starrocks-fmea-be-1
Resetting cross-zone connections in starrocks-fmea-be-2
Resetting cross-zone connections in starrocks-fmea-fe-0
Resetting cross-zone connections in starrocks-fmea-fe-1
Resetting cross-zone connections in starrocks-fmea-fe-2
PASS: DNS resolution works from all three zones.
PASS: new BE connections work within the majority and time out across the partition; majority FEs can connect.
Now check FE quorum, BE health, and writes from each side. Run partition.py stop to recover.
PASS: DNS resolution works from all three zones.
PASS: new BE connections work within the majority and time out across the partition; majority FEs can connect.
Now check FE quorum, BE health, and writes from each side. Run partition.py stop to recover.
--------------
CREATE DATABASE fmea_majority_1795621580
--------------

Majority DDL exit: 0
ERROR 2003 (HY000): Can't connect to MySQL server on '127.0.0.1:9030' (111)
command terminated with exit code 1
Minority DDL exit: 1
--------------
INSERT INTO fmea.events VALUES (1795621580223852564, NOW(), 'partition')
--------------

Majority INSERT exit: 0
networkpolicy.networking.k8s.io "fmea-partition-default" deleted from starrocks namespace
networkpolicy.networking.k8s.io "fmea-partition-isolated" deleted from starrocks namespace
networkpolicy.networking.k8s.io "fmea-partition-majority" deleted from starrocks namespace

Partition policies and temporary labels removed. Check database membership and replica recovery.
PASS: three workers in three zones
Traceback (most recent call last):
  File "<string>", line 8, in <module>
    assert all(any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", [])) for p in group), f"{component} pods are not all Ready"
           ~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: fe pods are not all Ready
PASS: three workers in three zones
Traceback (most recent call last):
  File "<string>", line 8, in <module>
    assert all(any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", [])) for p in group), f"{component} pods are not all Ready"
           ~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: fe pods are not all Ready
PASS: three workers in three zones
Traceback (most recent call last):
  File "<string>", line 8, in <module>
    assert all(any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", [])) for p in group), f"{component} pods are not all Ready"
           ~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: fe pods are not all Ready
PASS: three workers in three zones
PASS: three ready FEs and three ready BEs, spread across workers
PASS: three alive FE members and three alive BE members
Table	Create Table
events	CREATE TABLE `events` (\n  `event_id` bigint(20) NOT NULL COMMENT "",\n  `event_time` datetime NOT NULL COMMENT "",\n  `payload` varchar(128) NULL COMMENT ""\n) ENGINE=OLAP \nDUPLICATE KEY(`event_id`, `event_time`)\nDISTRIBUTED BY HASH(`event_id`) BUCKETS 4 \nPROPERTIES (\n"compression" = "LZ4",\n"fast_schema_evolution" = "true",\n"replicated_storage" = "true",\n"replication_num" = "3"\n);
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10310	10312	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10310	10313	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
10314	10315	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10314	10316	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10314	10317	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
10318	10319	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10318	10320	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10318	10321	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
10322	10323	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10322	10324	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10322	10325	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
PASS: all four tablets have three healthy replicas on distinct BEs
PASS: baseline rows can be read from the three-replica test table
Database
fmea_majority_1795621580
event_id	event_time	payload
1795621580223852564	2026-11-25 15:46:26	partition
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10310	10312	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10310	10313	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
10314	10315	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10314	10316	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10314	10317	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
10318	10319	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10318	10320	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10318	10321	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
10322	10323	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10322	10324	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10322	10325	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
Recovery observed 2026-11-25T15:47:09Z
```

</details>

## Take one BE out of service

We cordoned a worker and force-deleted only its BE pod. Once StarRocks marked that BE down, it reported one `DEAD` replica on each of our four tablets. A write to the existing table still succeeded with the two replicas available on each tablet.

We uncordoned the worker, let the BE rejoin, and read the same row back. All twelve replicas returned to `OK`. Those two checks tell us different things: the acknowledged write survived and the table regained its full redundancy.

<details>
<summary>BE-1 output: tablet health, insert, and readback</summary>

```text
BE-1 baseline 2026-11-25T15:41:41Z
PASS: three workers in three zones
PASS: three ready FEs and three ready BEs, spread across workers
PASS: three alive FE members and three alive BE members
Table	Create Table
events	CREATE TABLE `events` (\n  `event_id` bigint(20) NOT NULL COMMENT "",\n  `event_time` datetime NOT NULL COMMENT "",\n  `payload` varchar(128) NULL COMMENT ""\n) ENGINE=OLAP \nDUPLICATE KEY(`event_id`, `event_time`)\nDISTRIBUTED BY HASH(`event_id`) BUCKETS 4 \nPROPERTIES (\n"compression" = "LZ4",\n"fast_schema_evolution" = "true",\n"replicated_storage" = "true",\n"replication_num" = "3"\n);
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10312	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10313	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10315	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10316	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10317	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10319	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10320	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10321	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10323	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10324	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10325	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
PASS: all four tablets have three healthy replicas on distinct BEs
PASS: baseline rows can be read from the three-replica test table
Id	Name	IP	EditLogPort	HttpPort	QueryPort	RpcPort	Role	ClusterId	Join	Alive	ReplayedJournalId	LastHeartbeat	IsHelper	ErrMsg	StartTime	Version
1	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617937727	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	true	true	2579	2026-11-25 15:41:54	true		2026-11-25 15:41:19	3.5.21-85fccf8
2	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617959917	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	LEADER	1116536338	true	true	2581	2026-11-25 15:41:54	true		2026-11-25 14:46:06	3.5.21-85fccf8
3	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617960063	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	true	true	2579	2026-11-25 15:41:54	true		2026-11-25 15:39:36	3.5.21-85fccf8
BackendId	IP	HeartbeatPort	BePort	HttpPort	BrpcPort	LastStartTime	LastHeartbeat	Alive	SystemDecommissioned	ClusterDecommissioned	TabletNum	DataUsedCapacity	AvailCapacity	TotalCapacity	UsedPct	MaxDiskUsedPct	ErrMsg	Version	Status	DataTotalCapacity	DataUsedPct	CpuCores	MemLimit	NumRunningQueries	MemUsedPct	CpuUsedPct	DataCacheMetrics	Location	StatusCode
10002	starrocks-fmea-be-0.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:41:54	true	false	false	94	104.292 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:41:45"}	24.057 GB	0.00 %	4	12.960GB	0	1.46 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10001	starrocks-fmea-be-1.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:41:54	true	false	false	94	102.061 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:41:44"}	24.057 GB	0.00 %	4	12.960GB	0	1.45 %	0.0 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10003	starrocks-fmea-be-2.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:41:54	true	false	false	94	104.292 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:41:44"}	24.057 GB	0.00 %	4	12.960GB	0	1.45 %	0.0 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10312	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10313	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10315	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10316	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10317	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10319	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10320	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10321	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10323	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10324	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10325	10002	2	-1	2	2	0	2	false	false	NORMAL	OK
node/[lab-worker] cordoned
Warning: Immediate deletion does not wait for confirmation that the running resource has been terminated. The resource may continue to run on the cluster indefinitely.
pod "starrocks-fmea-be-0" force deleted from starrocks namespace
Fault requested 2026-11-25T15:41:57Z
BackendId	IP	HeartbeatPort	BePort	HttpPort	BrpcPort	LastStartTime	LastHeartbeat	Alive	SystemDecommissioned	ClusterDecommissioned	TabletNum	DataUsedCapacity	AvailCapacity	TotalCapacity	UsedPct	MaxDiskUsedPct	ErrMsg	Version	Status	DataTotalCapacity	DataUsedPct	CpuCores	MemLimit	NumRunningQueries	MemUsedPct	CpuUsedPct	DataCacheMetrics	Location	StatusCode
10002	starrocks-fmea-be-0.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:41:54	false	false	false	94	104.292 KB	24.057 GB	24.440 GB	1.57 %	1.57 %	java.net.UnknownHostException: starrocks-fmea-be-0.starrocks-fmea-be-search.starrocks.svc.cluster.local	3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:41:45"}	24.057 GB	0.00 %	4	12.960GB	0	1.45 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		DISCONNECTED
10001	starrocks-fmea-be-1.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:42:19	true	false	false	94	102.061 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:41:44"}	24.057 GB	0.00 %	4	12.960GB	0	1.45 %	0.0 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10003	starrocks-fmea-be-2.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:42:19	true	false	false	94	104.292 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:41:44"}	24.057 GB	0.00 %	4	12.960GB	0	1.46 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
Target confirmed down: true at 2026-11-25T15:42:21Z
NAME                  PHASE     NODE
starrocks-fmea-be-0   Pending   <none>
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10312	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10310	10313	10002	2	-1	2	2	0	2	false	false	NORMAL	DEAD
10314	10315	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10316	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10314	10317	10002	2	-1	2	2	0	2	false	false	NORMAL	DEAD
10318	10319	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10320	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10318	10321	10002	2	-1	2	2	0	2	false	false	NORMAL	DEAD
10322	10323	10001	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10324	10003	2	-1	2	2	0	2	false	false	NORMAL	OK
10322	10325	10002	2	-1	2	2	0	2	false	false	NORMAL	DEAD
Probe: INSERT INTO fmea.events VALUES (1795621317927661348, NOW(), 'be-outage');
--------------
INSERT INTO fmea.events VALUES (1795621317927661348, NOW(), 'be-outage')
--------------

Probe exit: 0
node/[lab-worker] uncordoned
PASS: three workers in three zones
Traceback (most recent call last):
  File "<string>", line 8, in <module>
    assert all(any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", [])) for p in group), f"{component} pods are not all Ready"
           ~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: be pods are not all Ready
PASS: three workers in three zones
Traceback (most recent call last):
  File "<string>", line 8, in <module>
    assert all(any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", [])) for p in group), f"{component} pods are not all Ready"
           ~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: be pods are not all Ready
PASS: three workers in three zones
PASS: three ready FEs and three ready BEs, spread across workers
PASS: three alive FE members and three alive BE members
Table	Create Table
events	CREATE TABLE `events` (\n  `event_id` bigint(20) NOT NULL COMMENT "",\n  `event_time` datetime NOT NULL COMMENT "",\n  `payload` varchar(128) NULL COMMENT ""\n) ENGINE=OLAP \nDUPLICATE KEY(`event_id`, `event_time`)\nDISTRIBUTED BY HASH(`event_id`) BUCKETS 4 \nPROPERTIES (\n"compression" = "LZ4",\n"fast_schema_evolution" = "true",\n"replicated_storage" = "true",\n"replication_num" = "3"\n);
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	3	-1	3	3	0	2	false	false	NORMAL	OK
10310	10312	10003	3	-1	3	3	0	2	false	false	NORMAL	OK
10310	10313	10002	3	-1	3	3	0	2	false	false	NORMAL	OK
10314	10315	10001	3	-1	3	3	0	2	false	false	NORMAL	OK
10314	10316	10003	3	-1	3	3	0	2	false	false	NORMAL	OK
10314	10317	10002	3	-1	3	3	0	2	false	false	NORMAL	OK
10318	10319	10001	3	-1	3	3	0	2	false	false	NORMAL	OK
10318	10320	10003	3	-1	3	3	0	2	false	false	NORMAL	OK
10318	10321	10002	3	-1	3	3	0	2	false	false	NORMAL	OK
10322	10323	10001	3	-1	3	3	0	2	false	false	NORMAL	OK
10322	10324	10003	3	-1	3	3	0	2	false	false	NORMAL	OK
10322	10325	10002	3	-1	3	3	0	2	false	false	NORMAL	OK
PASS: all four tablets have three healthy replicas on distinct BEs
PASS: baseline rows can be read from the three-replica test table
Pod UID changed: yes
PVC claims unchanged: yes
Id	Name	IP	EditLogPort	HttpPort	QueryPort	RpcPort	Role	ClusterId	Join	Alive	ReplayedJournalId	LastHeartbeat	IsHelper	ErrMsg	StartTime	Version
1	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617937727	starrocks-fmea-fe-0.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	true	true	2652	2026-11-25 15:42:59	true		2026-11-25 15:41:19	3.5.21-85fccf8
2	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617959917	starrocks-fmea-fe-2.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	LEADER	1116536338	true	true	2653	2026-11-25 15:42:59	true		2026-11-25 14:46:06	3.5.21-85fccf8
3	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local_9010_1795617960063	starrocks-fmea-fe-1.starrocks-fmea-fe-search.starrocks.svc.cluster.local	9010	8030	9030	9020	FOLLOWER	1116536338	true	true	2652	2026-11-25 15:42:59	true		2026-11-25 15:39:36	3.5.21-85fccf8
BackendId	IP	HeartbeatPort	BePort	HttpPort	BrpcPort	LastStartTime	LastHeartbeat	Alive	SystemDecommissioned	ClusterDecommissioned	TabletNum	DataUsedCapacity	AvailCapacity	TotalCapacity	UsedPct	MaxDiskUsedPct	ErrMsg	Version	Status	DataTotalCapacity	DataUsedPct	CpuCores	MemLimit	NumRunningQueries	MemUsedPct	CpuUsedPct	DataCacheMetrics	Location	StatusCode
10002	starrocks-fmea-be-0.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 15:42:39	2026-11-25 15:42:59	true	false	false	94	58.885 KB	24.413 GB	24.440 GB	0.11 %	0.11 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:42:45"}	24.413 GB	0.00 %	4	12.960GB	0	1.40 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10001	starrocks-fmea-be-1.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:42:59	true	false	false	94	63.339 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:42:44"}	24.057 GB	0.00 %	4	12.960GB	0	1.46 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10003	starrocks-fmea-be-2.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:42:59	true	false	false	94	63.677 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:42:45"}	24.057 GB	0.00 %	4	12.960GB	0	1.46 %	0.0 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	3	-1	3	3	0	2	false	false	NORMAL	OK
10310	10312	10003	3	-1	3	3	0	2	false	false	NORMAL	OK
10310	10313	10002	3	-1	3	3	0	2	false	false	NORMAL	OK
10314	10315	10001	3	-1	3	3	0	2	false	false	NORMAL	OK
10314	10316	10003	3	-1	3	3	0	2	false	false	NORMAL	OK
10314	10317	10002	3	-1	3	3	0	2	false	false	NORMAL	OK
10318	10319	10001	3	-1	3	3	0	2	false	false	NORMAL	OK
10318	10320	10003	3	-1	3	3	0	2	false	false	NORMAL	OK
10318	10321	10002	3	-1	3	3	0	2	false	false	NORMAL	OK
10322	10323	10001	3	-1	3	3	0	2	false	false	NORMAL	OK
10322	10324	10003	3	-1	3	3	0	2	false	false	NORMAL	OK
10322	10325	10002	3	-1	3	3	0	2	false	false	NORMAL	OK
event_id	event_time	payload
1795621317927661348	2026-11-25 15:42:26	be-outage
Recovery observed 2026-11-25T15:43:00Z
```

</details>

## Rotate the password, then restart a BE

Password rotation exposed a failure that a routine rollout could miss. We began with ESO already polling hourly and confirmed that StarRocks and the Kubernetes Secret had the same root password. Then we rotated the database password and updated the credential at the provider. While the Kubernetes Secret still held the old value, we restarted one BE.

<!-- Diagram slot: password rotation updates StarRocks and the provider, then a stale Kubernetes Secret supplies the old password to the replacement BE. Show the forced sync and restart on the recovery path. -->

The replacement pulled the old password into `MYSQL_PWD` and logged MySQL error 1045, `Access denied`. StarRocks marked the BE down and one replica per tablet went offline. The other two BEs still accepted an insert. **CRED-1 failed** because the restarted BE needed operator intervention to return to service.

We forced ESO to sync the new password from the provider. After confirming the Kubernetes Secret held the new value, we replaced the affected BE again so its container received that value at startup. The BE rejoined, all twelve replicas returned to `OK`, and we could read the row acknowledged during the outage.

<details>
<summary>CRED-1 output: stale password failure, forced sync, and recovery</summary>

```text
PASS: three workers in three zones
PASS: three ready FEs and three ready BEs, spread across workers
PASS: three alive FE members and three alive BE members
Table	Create Table
events	CREATE TABLE `events` (\n  `event_id` bigint(20) NOT NULL COMMENT "",\n  `event_time` datetime NOT NULL COMMENT "",\n  `payload` varchar(128) NULL COMMENT ""\n) ENGINE=OLAP \nDUPLICATE KEY(`event_id`, `event_time`)\nDISTRIBUTED BY HASH(`event_id`) BUCKETS 4 \nPROPERTIES (\n"compression" = "LZ4",\n"fast_schema_evolution" = "true",\n"replicated_storage" = "true",\n"replication_num" = "3"\n);
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10310	10312	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10310	10313	10002	5	-1	5	5	0	3	false	false	NORMAL	OK
10314	10315	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10314	10316	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10314	10317	10002	5	-1	5	5	0	3	false	false	NORMAL	OK
10318	10319	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10318	10320	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10318	10321	10002	5	-1	5	5	0	3	false	false	NORMAL	OK
10322	10323	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10322	10324	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10322	10325	10002	5	-1	5	5	0	3	false	false	NORMAL	OK
PASS: all four tablets have three healthy replicas on distinct BEs
PASS: baseline rows can be read from the three-replica test table
POLICY     INTERVAL   REFRESH
Periodic   1h         2026-11-25T15:49:41Z
externalsecret.external-secrets.io/starrocks-admin-password annotated
Hourly ESO baseline sync observed at 2026-11-25T15:50:14Z
secret/starrocks-admin-password serverside-applied
Database and provider rotated; target Secret still matches original at 2026-11-25T15:50:20Z
pod "starrocks-fmea-be-0" deleted from starrocks namespace
BE startup logs contain Access denied for root
MySQL ERROR 1045 (28000): Access denied for user 'root' (using password: YES)
BE confirmed down: true at 2026-11-25T15:50:39Z
NAME                  PHASE     READY   RESTARTS
starrocks-fmea-be-0   Running   false   0
BackendId	IP	HeartbeatPort	BePort	HttpPort	BrpcPort	LastStartTime	LastHeartbeat	Alive	SystemDecommissioned	ClusterDecommissioned	TabletNum	DataUsedCapacity	AvailCapacity	TotalCapacity	UsedPct	MaxDiskUsedPct	ErrMsg	Version	Status	DataTotalCapacity	DataUsedPct	CpuCores	MemLimit	NumRunningQueries	MemUsedPct	CpuUsedPct	DataCacheMetrics	Location	StatusCode
10002	starrocks-fmea-be-0.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 15:50:08	2026-11-25 15:50:18	false	false	false	94	63.812 KB	24.412 GB	24.440 GB	0.11 %	0.11 %	java.net.ConnectException: Connection refused	3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:50:09"}	24.412 GB	0.00 %	4	12.960GB	0	1.35 %	0.0 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		DISCONNECTED
10001	starrocks-fmea-be-1.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:50:38	true	false	false	94	83.341 KB	24.057 GB	24.440 GB	1.56 %	1.56 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:50:29"}	24.058 GB	0.00 %	4	12.960GB	1	1.46 %	12.6 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10003	starrocks-fmea-be-2.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:50:38	true	false	false	94	81.741 KB	24.057 GB	24.440 GB	1.56 %	1.56 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:49:58"}	24.057 GB	0.00 %	4	12.960GB	1	1.47 %	12.4 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10310	10312	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10310	10313	10002	5	-1	5	5	0	3	false	false	NORMAL	DEAD
10314	10315	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10314	10316	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10314	10317	10002	5	-1	5	5	0	3	false	false	NORMAL	DEAD
10318	10319	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10318	10320	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10318	10321	10002	5	-1	5	5	0	3	false	false	NORMAL	DEAD
10322	10323	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10322	10324	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10322	10325	10002	5	-1	5	5	0	3	false	false	NORMAL	DEAD
Outage insert exit: 0, event_id: 1795621843343604115
externalsecret.external-secrets.io/starrocks-admin-password annotated
Target Secret matches new value at 2026-11-25T15:50:47Z
pod "starrocks-fmea-be-0" deleted from starrocks namespace
BackendId	IP	HeartbeatPort	BePort	HttpPort	BrpcPort	LastStartTime	LastHeartbeat	Alive	SystemDecommissioned	ClusterDecommissioned	TabletNum	DataUsedCapacity	AvailCapacity	TotalCapacity	UsedPct	MaxDiskUsedPct	ErrMsg	Version	Status	DataTotalCapacity	DataUsedPct	CpuCores	MemLimit	NumRunningQueries	MemUsedPct	CpuUsedPct	DataCacheMetrics	Location	StatusCode
10002	starrocks-fmea-be-0.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 15:51:48	2026-11-25 15:52:08	true	false	false	94	63.812 KB	24.412 GB	24.440 GB	0.11 %	0.11 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:51:48"}	24.412 GB	0.00 %	4	12.960GB	0	1.40 %	0.3 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10001	starrocks-fmea-be-1.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:52:08	true	false	false	94	101.586 KB	24.057 GB	24.440 GB	1.56 %	1.56 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:51:29"}	24.058 GB	0.00 %	4	12.960GB	0	1.46 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10003	starrocks-fmea-be-2.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:52:08	true	false	false	94	99.986 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:51:58"}	24.057 GB	0.00 %	4	12.960GB	0	1.47 %	0.2 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	6	-1	6	6	0	4	false	false	NORMAL	OK
10310	10312	10003	6	-1	6	6	0	2	false	false	NORMAL	OK
10310	10313	10002	6	-1	6	6	0	3	false	false	NORMAL	OK
10314	10315	10001	6	-1	6	6	0	4	false	false	NORMAL	OK
10314	10316	10003	6	-1	6	6	0	2	false	false	NORMAL	OK
10314	10317	10002	6	-1	6	6	0	3	false	false	NORMAL	OK
10318	10319	10001	6	-1	6	6	0	4	false	false	NORMAL	OK
10318	10320	10003	6	-1	6	6	0	2	false	false	NORMAL	OK
10318	10321	10002	6	-1	6	6	0	3	false	false	NORMAL	OK
10322	10323	10001	6	-1	6	6	0	4	false	false	NORMAL	OK
10322	10324	10003	6	-1	6	6	0	2	false	false	NORMAL	OK
10322	10325	10002	6	-1	6	6	0	3	false	false	NORMAL	OK
Recovery verified: true at 2026-11-25T15:52:10Z
event_id	event_time	payload
1795621843343604115	2026-11-25 15:50:45	stale-credential
secret/starrocks-admin-password serverside-applied
externalsecret.external-secrets.io/starrocks-admin-password annotated
pod "starrocks-fmea-be-0" deleted from starrocks namespace
PASS: three workers in three zones
PASS: three ready FEs and three ready BEs, spread across workers
PASS: three alive FE members and three alive BE members
Table	Create Table
events	CREATE TABLE `events` (\n  `event_id` bigint(20) NOT NULL COMMENT "",\n  `event_time` datetime NOT NULL COMMENT "",\n  `payload` varchar(128) NULL COMMENT ""\n) ENGINE=OLAP \nDUPLICATE KEY(`event_id`, `event_time`)\nDISTRIBUTED BY HASH(`event_id`) BUCKETS 4 \nPROPERTIES (\n"compression" = "LZ4",\n"fast_schema_evolution" = "true",\n"replicated_storage" = "true",\n"replication_num" = "3"\n);
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	6	-1	6	6	0	4	false	false	NORMAL	OK
10310	10312	10003	6	-1	6	6	0	2	false	false	NORMAL	OK
10310	10313	10002	6	-1	6	6	0	3	false	false	NORMAL	OK
10314	10315	10001	6	-1	6	6	0	4	false	false	NORMAL	OK
10314	10316	10003	6	-1	6	6	0	2	false	false	NORMAL	OK
10314	10317	10002	6	-1	6	6	0	3	false	false	NORMAL	OK
10318	10319	10001	6	-1	6	6	0	4	false	false	NORMAL	OK
10318	10320	10003	6	-1	6	6	0	2	false	false	NORMAL	OK
10318	10321	10002	6	-1	6	6	0	3	false	false	NORMAL	OK
10322	10323	10001	6	-1	6	6	0	4	false	false	NORMAL	OK
10322	10324	10003	6	-1	6	6	0	2	false	false	NORMAL	OK
10322	10325	10002	6	-1	6	6	0	3	false	false	NORMAL	OK
PASS: all four tablets have three healthy replicas on distinct BEs
PASS: baseline rows can be read from the three-replica test table
Original credential and baseline restored
```

</details>

<details>
<summary>Earlier attempt: authentication failure before the heartbeat changed</summary>

```text
PASS: three workers in three zones
PASS: three ready FEs and three ready BEs, spread across workers
PASS: three alive FE members and three alive BE members
Table	Create Table
events	CREATE TABLE `events` (\n  `event_id` bigint(20) NOT NULL COMMENT "",\n  `event_time` datetime NOT NULL COMMENT "",\n  `payload` varchar(128) NULL COMMENT ""\n) ENGINE=OLAP \nDUPLICATE KEY(`event_id`, `event_time`)\nDISTRIBUTED BY HASH(`event_id`) BUCKETS 4 \nPROPERTIES (\n"compression" = "LZ4",\n"fast_schema_evolution" = "true",\n"replicated_storage" = "true",\n"replication_num" = "3"\n);
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10310	10312	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10310	10313	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
10314	10315	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10314	10316	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10314	10317	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
10318	10319	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10318	10320	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10318	10321	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
10322	10323	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10322	10324	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10322	10325	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
PASS: all four tablets have three healthy replicas on distinct BEs
PASS: baseline rows can be read from the three-replica test table
POLICY     INTERVAL   REFRESH
Periodic   1h         2026-11-25T15:40:55Z
externalsecret.external-secrets.io/starrocks-admin-password annotated
Hourly ESO baseline sync observed at 2026-11-25T15:47:27Z
secret/starrocks-admin-password serverside-applied
Database and provider rotated; target Secret still matches original at 2026-11-25T15:47:33Z
pod "starrocks-fmea-be-0" deleted from starrocks namespace
BE startup logs contain Access denied for root
BackendId	IP	HeartbeatPort	BePort	HttpPort	BrpcPort	LastStartTime	LastHeartbeat	Alive	SystemDecommissioned	ClusterDecommissioned	TabletNum	DataUsedCapacity	AvailCapacity	TotalCapacity	UsedPct	MaxDiskUsedPct	ErrMsg	Version	Status	DataTotalCapacity	DataUsedPct	CpuCores	MemLimit	NumRunningQueries	MemUsedPct	CpuUsedPct	DataCacheMetrics	Location	StatusCode
10002	starrocks-fmea-be-0.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 15:42:39	2026-11-25 15:47:33	true	false	false	94	105.711 KB	24.056 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:46:58"}	24.056 GB	0.00 %	4	12.960GB	0	1.43 %	0.2 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10001	starrocks-fmea-be-1.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:47:48	true	false	false	94	107.263 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:47:29"}	24.057 GB	0.00 %	4	12.960GB	0	1.46 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10003	starrocks-fmea-be-2.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:47:48	true	false	false	94	107.263 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:46:58"}	24.057 GB	0.00 %	4	12.960GB	0	1.46 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10310	10312	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10310	10313	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
10314	10315	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10314	10316	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10314	10317	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
10318	10319	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10318	10320	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10318	10321	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
10322	10323	10001	4	-1	4	4	0	2	false	false	NORMAL	OK
10322	10324	10003	4	-1	4	4	0	4	false	false	NORMAL	OK
10322	10325	10002	4	-1	4	4	0	3	false	false	NORMAL	OK
Outage insert exit: 0, event_id: 1795621672140399047
externalsecret.external-secrets.io/starrocks-admin-password annotated
Target Secret matches new value at 2026-11-25T15:47:56Z
pod "starrocks-fmea-be-0" deleted from starrocks namespace
BackendId	IP	HeartbeatPort	BePort	HttpPort	BrpcPort	LastStartTime	LastHeartbeat	Alive	SystemDecommissioned	ClusterDecommissioned	TabletNum	DataUsedCapacity	AvailCapacity	TotalCapacity	UsedPct	MaxDiskUsedPct	ErrMsg	Version	Status	DataTotalCapacity	DataUsedPct	CpuCores	MemLimit	NumRunningQueries	MemUsedPct	CpuUsedPct	DataCacheMetrics	Location	StatusCode
10002	starrocks-fmea-be-0.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 15:49:08	2026-11-25 15:49:28	true	false	false	94	104.863 KB	24.056 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:49:08"}	24.056 GB	0.00 %	4	12.960GB	0	1.38 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10001	starrocks-fmea-be-1.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:49:28	true	false	false	94	65.341 KB	24.057 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:49:29"}	24.057 GB	0.00 %	4	12.960GB	0	1.46 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
10003	starrocks-fmea-be-2.starrocks-fmea-be-search.starrocks.svc.cluster.local	9050	9060	8040	8060	2026-11-25 14:46:39	2026-11-25 15:49:28	true	false	false	94	65.341 KB	24.056 GB	24.440 GB	1.57 %	1.57 %		3.5.21-85fccf8	{"lastSuccessReportTabletsTime":"2026-11-25 15:48:58"}	24.057 GB	0.00 %	4	12.960GB	0	1.46 %	0.1 %	Status: Normal, DiskUsage: 0B/10GB, MemUsage: 0B/0B		OK
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10310	10312	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10310	10313	10002	5	-1	5	5	0	3	false	false	NORMAL	OK
10314	10315	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10314	10316	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10314	10317	10002	5	-1	5	5	0	3	false	false	NORMAL	OK
10318	10319	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10318	10320	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10318	10321	10002	5	-1	5	5	0	3	false	false	NORMAL	OK
10322	10323	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10322	10324	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10322	10325	10002	5	-1	5	5	0	3	false	false	NORMAL	OK
Recovery verified: true at 2026-11-25T15:49:32Z
event_id	event_time	payload
1795621672140399047	2026-11-25 15:47:54	stale-credential
secret/starrocks-admin-password serverside-applied
externalsecret.external-secrets.io/starrocks-admin-password annotated
pod "starrocks-fmea-be-0" deleted from starrocks namespace
PASS: three workers in three zones
PASS: three ready FEs and three ready BEs, spread across workers
PASS: three alive FE members and three alive BE members
Table	Create Table
events	CREATE TABLE `events` (\n  `event_id` bigint(20) NOT NULL COMMENT "",\n  `event_time` datetime NOT NULL COMMENT "",\n  `payload` varchar(128) NULL COMMENT ""\n) ENGINE=OLAP \nDUPLICATE KEY(`event_id`, `event_time`)\nDISTRIBUTED BY HASH(`event_id`) BUCKETS 4 \nPROPERTIES (\n"compression" = "LZ4",\n"fast_schema_evolution" = "true",\n"replicated_storage" = "true",\n"replication_num" = "3"\n);
TabletId	ReplicaId	BackendId	Version	LastFailedVersion	LastSuccessVersion	CommittedVersion	SchemaHash	VersionNum	IsBad	IsSetBadForce	State	Status
10310	10311	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10310	10312	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10310	10313	10002	5	-1	5	5	0	3	false	false	NORMAL	OK
10314	10315	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10314	10316	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10314	10317	10002	5	-1	5	5	0	3	false	false	NORMAL	OK
10318	10319	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10318	10320	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10318	10321	10002	5	-1	5	5	0	3	false	false	NORMAL	OK
10322	10323	10001	5	-1	5	5	0	2	false	false	NORMAL	OK
10322	10324	10003	5	-1	5	5	0	4	false	false	NORMAL	OK
10322	10325	10002	5	-1	5	5	0	3	false	false	NORMAL	OK
PASS: all four tablets have three healthy replicas on distinct BEs
PASS: baseline rows can be read from the three-replica test table
Original credential and baseline restored
```

</details>

The failure mode belongs in the FMEA because a shorter polling interval still leaves a gap between rotation and synchronization. An ESO interruption can extend it. If enough BEs restart during that gap and cannot return, affected tablets can lose write quorum. We would make forced sync and verification of the target Secret part of the rotation procedure, then check membership and replica health after each replacement. The run covered one BE outage. The effect of overlapping BE failures remains a risk to test separately.

## What a real GKE upgrade adds

In a separate surge run, GKE upgraded the node pool and replaced all three workers and all six database pods. The persistent volume bindings stayed the same. Two direct SQL requests failed around leader handoff, and neither probe ID appeared afterward. All 279 acknowledged inserts remained readable, and database membership and tablet replicas recovered.

<details>
<summary>SURGE-1 output: verified results from the November 21 run</summary>

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

</details>

We also saw a useful distinction for operators. An existing table could accept a majority write with two BEs, but attempts to create a new table with three replicas were rejected when only two BEs were available. For planned maintenance, we prefer blue-green upgrades because replacement capacity and soak time give us room to verify recovery before the old pool is removed. We used surge in this run.

## What we check before moving on

Each disruption ends with three questions. Did the client receive an acknowledgment? Did the affected member rejoin? Did the table regain every replica? Keeping those checks separate exposed both the short interruption during a leader handoff and the longer recovery work after the stale credential failure.

If you reproduce the lab, capture the outcome of each probe and tear down the environment when you finish. The [experiment guide](../experiments/README.md) has the full procedures.

```bash
./scripts/teardown.sh
```
