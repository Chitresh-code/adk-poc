# Past answer: SSO and SCIM

**Question asked (Q3 2025 RFP, higher-ed prospect):** Do you support SAML
SSO and SCIM provisioning?

**Answer given:** SAML 2.0 SSO is supported on our Business and Enterprise
plans, tested against Okta, Azure AD, and Google Workspace as identity
providers. SCIM 2.0 for automated user provisioning/deprovisioning is
available on Enterprise only. Just-in-time (JIT) provisioning via SAML is
available on all plans that support SSO, so customers without SCIM can
still auto-create accounts on first login. We do not support OIDC as an
alternative to SAML today; SAML is the only supported SSO protocol.
