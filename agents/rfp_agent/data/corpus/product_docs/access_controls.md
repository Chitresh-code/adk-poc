# Product doc: role-based access control

Northbound ships four built-in roles: Viewer, Editor, Admin, and Billing
Admin. Enterprise plans can additionally define custom roles with
per-object permission sets (view/edit/delete, scoped to record type).
Permissions are enforced server-side on every API call, not just hidden in
the UI.

Audit logging: every permission change, login, and data export is recorded
with actor, timestamp, and IP address, retained for 12 months and
exportable via API on Enterprise plans. Standard plans can view the last
30 days of audit log in-product but cannot export it.
