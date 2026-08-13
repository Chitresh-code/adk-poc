# Past answer: data residency

**Question asked (Q1 2026 RFP, EU-based logistics prospect):** Where is
customer data physically stored, and can it stay within the EU?

**Answer given:** Production data is stored in Google Cloud's
europe-west1 (Belgium) region by default for EU customers. US customers
default to us-central1 (Iowa). We do not currently support splitting a
single tenant's data across regions, or per-field residency controls
within a region. Backups replicate to a second region on the same
continent (europe-west4 for EU tenants) for disaster recovery; they never
cross the EU/US boundary for EU tenants.
