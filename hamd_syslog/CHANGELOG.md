# Changelog

## 0.1.2

- Rename the app and its user-facing interface from HAMD Syslog to IoT Syslog.
- Describe the service as a generic IoT syslog receiver with first-class IoTMD support.
- Classify new `IoTMD-Audit` records as audit events while retaining classification of stored legacy `HAMD-Audit` records.
- Retain the existing Home Assistant slug, persistent data path, and container image name for in-place upgrades.

## 0.1.1

- Refresh the visible event page automatically every five seconds.
- Preserve active search filters and pagination during automatic refreshes.
- Ignore stale overlapping responses and refresh immediately when the browser tab becomes visible.
- Display the time of the most recent successful event refresh.

## 0.1.0

- Receive RFC 5424 syslog over authenticated TLS with RFC 6587 octet-counted framing.
- Optionally receive unencrypted UDP syslog.
- Generate and retain a dedicated local certificate authority and server certificate.
- Download the trust anchor directly in HAMD-compatible DER format.
- Search and filter stored events by text, source, device, application, severity, transport, and time.
- Distinguish `HAMD` device logs from `HAMD-Audit` audit events.
- Automatically purge events after a user-defined retention period.
- Export the currently filtered result set as CSV.
- Publish installable multi-architecture images on the initial repository commit and manual workflow runs.
