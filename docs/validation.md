# Validation

## Static checks

Validated on 21 November 2026 with OpenTofu `1.13.9`, Terraform `1.13.5`, Google provider `6.50.0`, and Helm `3.19.0`.

| Check | Result |
| --- | --- |
| OpenTofu formatting, initialization, and validation | Passed |
| Independent Terraform initialization and validation | Passed |
| Both Helm charts lint and render with the lab values | Passed |
| Rendered StarRocksCluster against the v1.11.1 CRD schema | Passed |
| Images, replicas, Secret references, storage, and internal services | Passed |
| Partition policy tests for both directions, majority connectivity, replacements, unrelated pods, and DNS | Six tests passed |
| Shell syntax | Passed |

`./scripts/validate.sh` runs the OpenTofu checks, chart checksum checks, rendering, schema checks, shell syntax checks, and policy tests. These checks do not require GCP credentials. Terraform was also checked in an independent local directory to keep it separate from the live OpenTofu state.

## Cloud checks

A GKE validation run is in progress. The run uses the optional 50 GiB storage profile because the available SSD quota is below the 600 GiB required by the default profile. No live experiment outcome is established by the static checks above.

## Limits

This lab provides bounded operational tests. It does not prove complete ACID behavior, linearizability, disaster recovery, or production readiness. The partition policy model tests reachability rules; live checks are needed to verify enforcement and database responses in a real cluster. Preserve client responses, image digests, membership, replica state, and timestamps for each run.
