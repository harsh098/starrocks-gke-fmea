# Validation

## Static checks

Validated on 21 November 2026 with OpenTofu `1.13.9`, Terraform `1.13.5`, Google provider `8.12.0`, and Helm `3.19.0`.

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

The partition helper explicitly allows both `kube-dns` and `node-local-dns` pods. An earlier probe omitted the NodeLocal DNS label and timed out; that run was discarded as a confounded experiment. The helper now checks DNS before reporting a valid partition. It also checks the debug container's exit status after each TCP reset.

The initial attempt hit `ZONE_RESOURCE_POOL_EXHAUSTED` for temporary `e2-medium` default workers in two zones. The lab now uses the current provider's support for creating GKE without a default pool. This requires GKE `1.36.4-gke.1469000` or later and allocates only the intended N2 experiment workers. If those workers also encounter a capacity error, inspect the managed instance group's errors and select an available machine type or region for a new run.

The failed infrastructure attempt and earlier database volumes were removed. The final demo was installed with fresh volumes and the 1.11.4 CRD. Planned drains, VM resets, and credential rotation are documented procedures; they were not run as part of this validation.

## Limits

This lab provides bounded operational tests. It does not prove complete ACID behavior, linearizability, disaster recovery, or production readiness. The partition policy model tests reachability rules; live checks are needed to verify enforcement and database responses in a real cluster. Preserve client responses, image digests, membership, replica state, and timestamps for each run.
