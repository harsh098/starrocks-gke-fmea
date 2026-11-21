-- Run once. DUPLICATE KEY tables do not deduplicate repeated seed inserts.
CREATE DATABASE IF NOT EXISTS fmea;
USE fmea;

CREATE TABLE events (
  event_id BIGINT NOT NULL,
  event_time DATETIME NOT NULL,
  payload VARCHAR(128)
)
ENGINE = OLAP
DUPLICATE KEY(event_id, event_time)
DISTRIBUTED BY HASH(event_id) BUCKETS 4
PROPERTIES (
  "replication_num" = "3",
  "write_quorum" = "MAJORITY"
);

INSERT INTO events VALUES
  (1, '2026-01-01 00:00:00', 'baseline-1'),
  (2, '2026-01-01 00:00:01', 'baseline-2'),
  (3, '2026-01-01 00:00:02', 'baseline-3');
