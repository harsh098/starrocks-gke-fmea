# Validation

## Static checks

Validated on 21 November 2026 with OpenTofu `1.13.9`, Terraform `1.13.5`, Google provider `8.12.0`, and Helm `3.19.0`. The revised OpenTofu configuration, including the blue-green default, was checked again on 22 November 2026 (IST).

| Check | Result |
| --- | --- |
| OpenTofu formatting, initialization, and validation | Passed |
| Independent Terraform initialization and validation | Passed |
| Both Helm charts lint and render with the lab values | Passed |
| Rendered StarRocksCluster against the v1.11.4 CRD schema | Passed |
| Images, replicas, Secret references, storage, and internal services | Passed |
| Partition tests for FE/BE labels, reachability rules, replacements, DNS, and debug-container exit status | Nine tests passed |
| Shell syntax | Passed |

`./scripts/validate.sh` runs the OpenTofu checks, chart checksum checks, rendering, schema checks, shell syntax checks, and policy tests. These checks do not require GCP credentials. Terraform was also checked in an independent local directory to keep it separate from the live OpenTofu state.

## Cloud checks

Validated on GKE `1.36.4-gke.2377000` in `us-west4`, with three `n2-standard-8` workers, Operator and Helm charts `1.11.4`, and StarRocks `3.5.21`. The run used the optional six 25 GiB database volumes. That differs from the article's six 100 GiB volumes. Including worker boot disks, the demo uses 300 GiB of SSD quota.

| Live check | Result |
| --- | --- |
| OpenTofu apply without a temporary default node pool | Passed; 11 infrastructure resources created |
| Follow-up infrastructure plan | No changes |
| Fresh operator, cluster, and disk deployment | Passed |
| FE membership | One leader and two voting followers, all alive |
| BE membership and placement | Three alive BEs; one FE and one BE per zone |
| Baseline writes and reads | Passed |
| Tablet recovery check | Four tablets, each with three healthy replicas |
| DNS-preserving leader-zone partition | DNS works in all zones; cross-zone BE connections time out; majority FEs remain connected |
| Majority metadata and tablet writes during that partition | Both succeeded |
| Metadata write attempted on the isolated FE | Local SQL connection refused; no successful write acknowledgment observed |
| Recovery | All six members and all twelve test-table replicas healthy; the acknowledged write remained readable |
| Forced FE follower deletion | Partial success: replacement pod rejoined with the same volume; membership, all twelve replicas, and baseline reads recovered |

The partition helper explicitly allows both `kube-dns` and `node-local-dns` pods. An earlier probe omitted the NodeLocal DNS label and timed out; that run was discarded as a confounded experiment. The helper now checks DNS before reporting a valid partition. It also checks the debug container's exit status after each TCP reset.

The initial attempt hit `ZONE_RESOURCE_POOL_EXHAUSTED` for temporary `e2-medium` default workers in two zones. The lab now uses the current provider's support for creating GKE without a default pool. This requires GKE `1.36.4-gke.1469000` or later and allocates only the intended N2 experiment workers. If those workers also encounter a capacity error, inspect the managed instance group's errors and select an available machine type or region for a new run.

The failed infrastructure attempt and earlier database volumes were removed. The final demo was installed with fresh volumes and the 1.11.4 CRD. Credential rotation remains a documented procedure. The actual GKE surge replay below was run separately.

## GKE surge replay

On 21 November 2026, the lab control plane and then its worker pool were upgraded
from `1.36.4-gke.2377000` to `1.36.5-gke.1259000`. The pool used `SURGE`,
`maxSurge=1`, and `maxUnavailable=0`, with one worker per zone. An earlier
same-version request completed without replacing workers and was excluded from
the replacement result.

StarRocks stayed on `3.5.21`, with operator `1.11.4` and six 25 GiB database volumes.
Container image digests were compared before and after and were unchanged.

| Check | Observed outcome |
| --- | --- |
| Actual replacement | All three original workers and all six original database pods replaced; final workers run the target version |
| Storage bindings | All six PVC UIDs, PV UIDs, volume bindings, and disk handles unchanged |
| Leadership | FE-2 was leader before its drain; FE-1 became leader; FE-2 rejoined as follower |
| Acknowledged inserts | All 279 unique acknowledged IDs remained readable: 192 direct-client inserts and 87 exec probes |
| Direct SQL errors | Two during leader handoff: socket closed by peer and connection timeout; both IDs were absent after recovery |
| Table DDL | 26 create/drop pairs succeeded; two were rejected with only two BEs alive and three replicas requested; one failed with a closed connection |
| Recovery | Three alive FEs, three alive BEs, twelve healthy baseline replicas, and three healthy probe replicas |
| Infrastructure after upgrade | OpenTofu plan reported no changes |

The direct SQL client used the FE Service. Its logs were streamed locally and
retrieved from Cloud Logging across the client's own eviction. Successful insert
IDs from both clients were compared with the complete recovered table, including
a duplicate-ID check. The temporary client Deployment was removed; the probe
database and private evidence were retained for inspection.

The exec capture also recorded a Kubernetes `No agent available` transport error
during the control-plane upgrade. It is not counted as a database error. The
three-replica table-creation rejections are distinct from majority writes to an
existing table and do not establish loss of FE quorum.

This run exercised worker replacement, leader handoff, acknowledged-write
retention, and full replica recovery. Follow the
[surge procedure](../experiments/surge-upgrade.md) for another run.

## Limits

The forced-deletion result covers one FE follower. Abrupt VM loss and simultaneous
loss of multiple voting FEs were outside the experiment scope. The subsequent
[CRED-1 run](part-2-results.md#cred-1) reproduced an ESO stale-password
startup failure and verified recovery after forced sync and BE replacement.

Blue-green upgrades are configured for the next deployment and have passed static
validation; they have not yet been exercised in this lab.

This lab provides bounded operational tests. It does not prove complete ACID behavior, linearizability, disaster recovery, or production readiness. The partition policy model tests reachability rules; live checks are needed to verify enforcement and database responses in a real cluster. Preserve client responses, image digests, membership, replica state, and timestamps for each run.

## Lab lifecycle

The first environment was decommissioned on 22 November 2026 (IST). OpenTofu
destroyed all eleven managed resources; the worker VMs, boot disks, and six
database disks were verified deleted. Project APIs remained enabled as
configured by `disable_on_destroy = false`.

The lab was recreated on 25 November 2026 (IST) for the revised Part 2 tests.
OpenTofu added eleven resources and a follow-up plan reported no changes. The
fixed pool has three Ready workers, one per zone, on GKE
`1.36.4-gke.2377000`. Operator and charts remain `1.11.4`; FE and BE images
remain `3.5.21`. The new deployment uses six bound 25 GiB volumes. The baseline
smoke check passed: three ready and alive FEs, three ready and alive BEs, four
tablets with three healthy replicas on distinct BEs, and readable baseline rows.
The [Part 2 experiment records](part-2-results.md) document the subsequent
live fault tests and link each case to the commands and captured output.
