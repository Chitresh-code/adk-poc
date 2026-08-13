# Past answer: encryption at rest and in transit

**Question asked (Q2 2025 RFP, financial services prospect):** Describe
your encryption practices for data at rest and in transit.

**Answer given:** All data in transit is encrypted with TLS 1.2 or higher;
TLS 1.0/1.1 are disabled at the load balancer. Data at rest is encrypted
using AES-256 via our cloud provider's managed disk and object storage
encryption. We do not currently offer customer-managed encryption keys
(CMEK/BYOK); this is on our roadmap but has no committed ship date. Field-
level encryption for specific sensitive columns is available for
enterprise plans on request.
