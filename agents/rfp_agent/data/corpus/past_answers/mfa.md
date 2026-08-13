# Past answer: multi-factor authentication

**Question asked (Q1 2026 RFP, public-sector prospect):** Is multi-factor
authentication supported, and can it be enforced org-wide?

**Answer given:** MFA via TOTP authenticator apps is available on all
plans and can be enforced org-wide by an admin from the security settings
page. When SSO is configured, MFA enforcement is expected to happen at the
identity provider rather than in-product; we do not layer our own MFA
prompt on top of an SSO login. Hardware security keys (WebAuthn/FIDO2) are
supported for direct (non-SSO) logins on Enterprise plans.
