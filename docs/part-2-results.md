# Part 2 experiment records

The new lab runs occurred on 25 November 2026. Logs use UTC. Worker identities and IP addresses are redacted. Credentials and raw startup logs stay in private local storage.

## FE-1

**FE follower restart.** PASS. The two remaining FEs accepted the metadata probe while the follower was down. The probe was present after rejoin. The pod UID changed and the PVC claims stayed the same.

Identify a voting follower and a surviving FE. Record the pod UID and PVC claim names, cordon its worker, then force-delete the follower. Wait for StarRocks to report it down. Create a unique database through the surviving FE. Uncordon, verify the new pod and the same PVC claims, and read back the database name. Check all members and replicas.

[Lab commands](../experiments/README.md#fe-1-and-fe-2-fe-pod-loss-and-rejoin).

<details>
<summary>Captured output</summary>

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

## FE-2

**FE leader restart.** PASS. FE-2 became leader after FE-0 went down. The metadata probe succeeded and remained present after FE-0 rejoined. The pod UID changed and the PVC claims stayed the same.

Identify the current leader and a surviving FE. Cordon the leader’s worker and force-delete the leader pod. Query membership until the original leader is down and a surviving voter has been elected. Create a unique database, uncordon the worker, and verify that the former leader rejoins and the database still exists.

[Lab commands](../experiments/README.md#fe-1-and-fe-2-fe-pod-loss-and-rejoin).

<details>
<summary>Captured output</summary>

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

## FE-3

**Database network partition.** PASS for the observed partition. Majority DDL and insert succeeded and the minority database was absent after recovery.

Find the FE leader’s zone. Apply the partition helper and verify DNS, same-side connectivity, and cross-zone link loss. Attempt distinct database creates on both sides plus an insert from the majority. Remove the partition and reconcile both database names and the insert. Check all members and replicas.

[Lab commands](../experiments/README.md#fe-3-zone-network-partition).

<details>
<summary>Captured output</summary>

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

## BE-1

**Writes with one BE unavailable.** PASS. StarRocks reported one DEAD replica on each of four tablets. The majority insert succeeded, the row was readable after the BE returned, and all 12 replicas reported OK.

Record BE membership and replica status. Cordon the worker and force-delete one BE. Confirm the replacement is Pending and StarRocks marks the target down. Capture tablet status, then insert a unique row. Uncordon and verify the replacement UID, PVC claims, acknowledged row and three healthy replicas per tablet.

[Lab commands](../experiments/README.md#be-1-be-availability-with-one-member-held-down).

<details>
<summary>Captured output</summary>

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

## CRED-1

**BE restart after password rotation.** FAIL as expected. The replacement BE logged MySQL error 1045 during the stale Secret window. The FE heartbeat view marked it down. The other two BEs remained available. Forced sync and pod replacement restored membership and all 12 replicas. The insert acknowledged with two BEs was readable afterward.

Start with ESO polling every hour and confirm the target Secret matches the original password. Rotate StarRocks root and the provider source to a new value. Verify that the target still holds the original value, then restart one BE and inspect startup logs. Record the failed restart separately from recovery. Force ESO to sync, compare the target with the new value, then replace the affected BE and verify registration, acknowledged writes and all replicas.

[Lab commands](../experiments/README.md#cred-1-be-restart-after-a-root-password-change).

<details>
<summary>Captured output</summary>

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

### CRED-1 preliminary trial

We saw root authentication errors, but the first membership query still showed the BE alive. This trial could establish the startup authentication failure and subsequent recovery. The confirmation run waits for the heartbeat view to mark the BE down before running the write probe.

<details>
<summary>Captured output</summary>

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

## SURGE-1

**GKE surge upgrade.** PASS for acknowledged-write retention, membership, and replica recovery. This is the verified 21 November run.

Run continuous SQL probes through the FE Service and through a surviving FE. Request an actual GKE version upgrade with one surge worker and zero unavailable workers. Compare node, pod, and volume identities, replay the client acknowledgments against recovered rows, and verify every replica. Two direct requests failed during leader handoff and neither ID appeared afterward.

[Surge commands](../experiments/surge-upgrade.md) and [recorded client results](validation.md#gke-surge-replay).

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
