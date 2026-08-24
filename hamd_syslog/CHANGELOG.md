# Changelog

## 0.1.0

- Receive RFC 5424 syslog over authenticated TLS with RFC 6587 octet-counted framing.
- Optionally receive unencrypted UDP syslog.
- Generate and retain a dedicated local certificate authority and server certificate.
- Download the trust anchor directly in HAMD-compatible DER format.
- Search and filter stored events by text, source, device, application, severity, transport, and time.
- Distinguish `HAMD` device logs from `HAMD-Audit` audit events.
- Automatically purge events after a user-defined retention period.
- Export the currently filtered result set as CSV.
