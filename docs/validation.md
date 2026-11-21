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

A GKE validation run is in progress. The run uses the optional 25 GiB storage profile because the available SSD quota is below the 750 GiB required by the default profile including worker boot disks. No live experiment outcome is established by the static checks above.

The initial attempt hit `ZONE_RESOURCE_POOL_EXHAUSTED` for temporary `e2-medium` default workers in two zones. The lab now uses the current provider's support for creating GKE without a default pool. This requires GKE `1.36.4-gke.1469000` or later and allocates only the intended N2 experiment workers. If those workers also encounter a capacity error, inspect the managed instance group's errors and select an available machine type or region for a new run.

## Limits

This lab provides bounded operational tests. It does not prove complete ACID behavior, linearizability, disaster recovery, or production readiness. The partition policy model tests reachability rules; live checks are needed to verify enforcement and database responses in a real cluster. Preserve client responses, image digests, membership, replica state, and timestamps for each run.
