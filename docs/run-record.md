# Experiment run record

Copy this file into a local ignored directory for each experiment. Remove account details and credentials before sharing results.

| Field | Value |
| --- | --- |
| Date and run ID | |
| Repository commit | |
| GKE version and dataplane | |
| Operator and chart versions | |
| FE and BE image digests (`status.containerStatuses[].imageID`) | |
| Worker type, count, and zones | |
| Storage classes and disk zones | |
| FE voting members and leader | |
| BE members; tablet replication and write quorum | |
| Assumed node/network model | |
| Fault actually injected | |
| Preconditions and baseline evidence | |
| Expected safety behavior | |
| Expected availability and interruption limit | |
| Expected recovery and time limit | |
| Fault start/end UTC | |
| Actual client responses and acknowledged writes | |
| FE leadership and membership observations | |
| BE registration and tablet recovery observations | |
| Kubernetes events, restarts, and placement | |
| Recovery steps and operator effort | |
| Pass, fail, or inconclusive, with evidence | |
| Remaining uncertainty | |

A timeout can leave the outcome of a write unknown. Reconcile it after recovery. State whether a result tests safety, availability, recovery, or more than one. Do not label an entire database production-ready from this bounded set of checks.
