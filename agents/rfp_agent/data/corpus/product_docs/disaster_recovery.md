# Product doc: backup and disaster recovery

Full backups run nightly, incremental backups every 4 hours, retained on
a rolling 30-day window. Recovery point objective (RPO) is 4 hours;
recovery time objective (RTO) is 4 hours for a full regional failover.
Failover to a secondary region is a manual, operator-initiated process
today, not automatic; we've run it twice in the last two years, both as
planned drills rather than live incidents.

Customers cannot self-serve restore individual records from backup; a
restore request goes through support and is scoped to the smallest unit
that recovers the affected data without overwriting unrelated changes made
since the backup.
