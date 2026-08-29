# Changelog

## Unreleased

## 0.2.1

- Align the ingress UI with the IoT app family by separating Overview, Events
  and Settings into real routes with a persistent branded tab bar.
- Add a read-only active-configuration summary while retaining Home Assistant
  app configuration as the source of truth.

## 0.2.0

- Establish IoT Syslog as a clean Home Assistant app identity.
- Align the ingress header, brand mark, navigation, typography, colour palette and cards with IoT Certificate Authority.
- Receive RFC 5424 syslog over authenticated TLS with RFC 6587 octet-counted framing.
- Optionally receive unencrypted UDP syslog.
- Generate and retain a dedicated local certificate authority and server certificate.
- Search and filter stored events by text, source, device, application, severity, transport and time.
- Classify the IoT MD protocol application names `IoTMD` and `IoTMD-Audit` as device and audit events.
- Refresh visible results automatically while preserving filters and pagination.
- Automatically purge events after a configurable retention period.
- Export filtered results as CSV.
