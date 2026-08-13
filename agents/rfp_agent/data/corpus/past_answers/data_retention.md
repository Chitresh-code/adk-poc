# Past answer: data retention and deletion

**Question asked (Q4 2025 RFP, healthcare-adjacent prospect):** What is
your data retention policy, and how quickly is data deleted after contract
termination?

**Answer given:** Active customer data is retained for the duration of the
subscription. On termination, data is soft-deleted immediately (no longer
accessible via the product) and hard-deleted from primary storage within
30 days. Encrypted backups are purged on a rolling 90-day cycle, so
residual data may exist in backups for up to 90 days after hard deletion.
We do not offer same-day permanent erasure across all backup tiers; this
has come up with regulated customers before and we've accommodated a
documented 90-day maximum in the DPA when asked.
