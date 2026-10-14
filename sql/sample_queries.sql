-- Handy checks after a run (SQLite; works in SQL Server with minor syntax changes)

-- 1. Row counts per source file: loaded vs rejected
SELECT file_name, rows_read, rows_loaded, rows_rejected FROM etl_file_log ORDER BY file_name;

-- 2. Why were records rejected?
SELECT error_column, error_reason, COUNT(*) AS records
FROM error_destination_output GROUP BY error_column, error_reason ORDER BY records DESC;

-- 3. Transactions whose IMSI is missing from the reference table (subscriber_id = -99999)
SELECT COUNT(*) FROM fact_transaction WHERE subscriber_id = -99999;

-- 4. Events per type per day
SELECT date(event_ts) AS day, event_type, COUNT(*) AS events
FROM fact_transaction GROUP BY day, event_type ORDER BY day, event_type;

-- 5. Top 10 busiest cells
SELECT cell, lac, COUNT(*) AS events FROM fact_transaction
GROUP BY cell, lac ORDER BY events DESC LIMIT 10;
