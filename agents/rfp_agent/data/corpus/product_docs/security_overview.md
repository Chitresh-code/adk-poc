# Product doc: security overview

Northbound is built on Google Cloud infrastructure. Application
environments are isolated per deployment tier (dev, staging, production)
with no shared databases or credentials across tiers. Production access
for engineering staff requires a signed just-in-time access request,
auto-expiring after 8 hours, logged to an immutable audit trail.

Vulnerability management: dependency scanning runs on every merge to main;
third-party penetration testing is performed twice a year by an external
firm, with findings tracked to remediation in our internal issue tracker.
We do not currently publish penetration test reports externally, but a
summary of findings and remediation status is shared under NDA on request.
