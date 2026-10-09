# Changelog

## 0.3.8

- Move certificate details and the public CA download from Overview to Settings.
- Remove the redundant configuration/restart instruction from Settings, and
  update certificate setup documentation to match the current device menus.

## 0.3.7

- Standardise checkbox-first controls, required markers, aligned form fields,
  helper typography and accessible notification/error feedback.
- Show receiver refresh failures on Overview, Settings and Events without
  discarding previously loaded data or overwriting newer manual-action status.
- Serve the shared form stylesheet through ingress and cover it in regression
  tests. Retain filtered TXT/CSV downloads and existing filter behaviour.

## 0.3.6

- Show compact icons only for required fields; leave optional fields unmarked.

## 0.3.5

- Group TXT and CSV buttons under Download events; export all events matching
  the applied view filters across pages. Preserve the legacy .log endpoint.
- Use the portfolio's required/optional field labels.

## 0.3.4

- Download all events matching the applied filters as a plain-text syslog
  file or CSV, without the old silent 500-event cap. Stream from a read-only
  SQLite snapshot so ingestion continues and exports use bounded memory.
- Keep filters and the Events page in place when requesting a download.
  Protect spreadsheet CSV fields against formula execution.

## 0.3.3

- Align form labels and single-line controls with the IoT portals' shared
  42 px height, including search fields. Preserve taller text areas and lists.

## 0.3.2

- Match Home Assistant's compact 14 px Roboto type scale, 32 px maximum page
  heading, 1,200 px content width, tighter controls and lower-radius panels.

## 0.3.1

- Align the portal type scale, heading sizes, panel density and page spacing
  more closely with the Home Assistant add-on experience.

## 0.3.0

- Adopt the shared IoT portal shell, brand mark, typography, spacing and panel hierarchy.
- Make Overview metrics direct links to the relevant Events or Settings page.
- Standardise responsive cards and interaction feedback with IoT-MD Management.

## 0.2.2

- Align portal actions and feedback with the IoT MD interaction model.
- Refresh receiver status and event results in place with visible busy, success
  and error states instead of page reloads.
- Group filter actions consistently at the bottom-right and make export,
  pagination and refresh controls reflect their current availability.
- Stop polling event data while another page is open and avoid duplicate filter
  values when receiver status is refreshed.

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
