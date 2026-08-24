# HAMD Syslog

HAMD Syslog stores device and audit events in a searchable local database. It is designed to match the remote logging support in Home Assistant Modular Device v2.

## First start with generated TLS

The default settings enable encrypted syslog on TCP port 6514 and disable unencrypted UDP.

1. Set **TLS server names** to every hostname or IP address that HAMD devices will use for this Home Assistant host. Separate multiple values with commas. For example: `homeassistant.local,192.168.1.20`.
2. Start the app, then open its web interface.
3. Select **Download HAMD CA (.der)**. This is the public CA certificate; the CA private key never leaves app storage.
4. On each HAMD portal, open **Maintenance > Certificates**, import the file as **Syslog trusted CA**, and allow the requested restart.
5. In the HAMD logging configuration, enable device logs and/or audit events, select **TLS**, enter one of the exact server names from step 1, and use port `6514`.

Hostname verification is intentional. If a device connects to `192.168.1.20`, that IP must be listed in **TLS server names**; listing only `homeassistant.local` is not sufficient.

Changing the server-name list issues a replacement server certificate from the same generated CA, so the CA normally does not need to be reinstalled on devices. Deleting the app's `/data/tls` directory creates a new CA and requires the new trust anchor to be installed on every device.

## TLS modes

### Home Assistant IoT Certificate Authority (recommended for HAMD fleets)

If Home Assistant already has a certificate and key issued by [Home Assistant IoT Certificate Authority](https://github.com/IanW6374/HA-IoT-Certificate-Authority), select `custom` mode and point the certificate options at those existing `/ssl` files. Common filenames are `fullchain.pem` and `privkey.pem`, but use the actual filenames on your system.

The certificate must include the hostname or IP address configured on HAMD devices and must allow TLS server authentication. Prefer a full-chain PEM so the syslog listener presents the leaf and online intermediate certificates together. The private key is mounted read-only and remains in `/ssl`.

Install the IoT CA root certificate as **Syslog trusted CA** on each HAMD device. You can download it in DER format directly from the IoT Certificate Authority app. If the same root PEM is present in `/ssl`, set **Custom CA certificate** to that filename and HAMD Syslog will also expose its convenient DER download button.

HAMD Syslog does not currently enrol or renew this shared Home Assistant identity. Its lifecycle remains managed by the IoT Certificate Authority and the mechanism that places the renewed files in `/ssl`; restart HAMD Syslog after renewal so it loads the replacement identity.

### Generated

`generated` is the default. On first start, the app creates:

- a 3,072-bit RSA certificate authority valid for ten years
- a 2,048-bit RSA server certificate valid for 825 days
- a server certificate containing every configured DNS name and IP address as a subject alternative name

The server certificate is automatically replaced when it has fewer than 30 days remaining or when the configured server names change. TLS 1.2 or newer is required and TLS compression is disabled.

### Custom

Select `custom` to use files from Home Assistant's `/ssl` directory. The filenames are relative to `/ssl` and cannot escape that directory.

- **Custom server certificate**: PEM server certificate or full chain
- **Custom server private key**: matching unencrypted PEM private key
- **Custom CA certificate**: optional PEM issuing CA, made available through the DER and PEM download endpoints

The `/ssl` mount is read-only. Restart the app after replacing custom certificate files.

## Search and filtering

The ingress interface supports:

- free-text matching across message, raw record, device hostname, and application
- source separation between HAMD device logs and `HAMD-Audit` audit events
- exact device, application, severity, and transport filters
- received-time range filters
- newest-first pagination and CSV export

The event timestamp supplied by the device is displayed when valid. Retention always uses the server's trusted received time, preventing an incorrect device clock from bypassing or prematurely triggering cleanup.

## Options

| Option | Default | Description |
| --- | --- | --- |
| `udp_enabled` | `false` | Listen for unencrypted RFC 5424 datagrams on the configured host mapping for UDP 514. |
| `tls_enabled` | `true` | Listen for encrypted, RFC 6587 octet-counted messages on the configured host mapping for TCP 6514. |
| `tls_mode` | `generated` | Use a locally generated CA or custom `/ssl` files. |
| `tls_server_names` | `homeassistant.local` | Comma-separated DNS names and IP addresses placed in the generated certificate. |
| `tls_certificate` | `fullchain.pem` | Custom server certificate filename beneath `/ssl`. |
| `tls_private_key` | `privkey.pem` | Custom server private-key filename beneath `/ssl`. |
| `tls_ca_certificate` | `iot-ca-root.pem` | Optional custom CA filename beneath `/ssl`. |
| `retention_days` | `30` | Keep events for 1–3,650 days. |
| `purge_interval_hours` | `6` | Run automatic cleanup every 1–168 hours and once at startup. |
| `max_message_kib` | `64` | Reject individual messages above this limit. |

The Home Assistant Network panel can change the host-side port without changing the standard container ports. Configure HAMD with the effective host-side port shown there.

## Storage and backups

Events are stored in `/data/syslog.db` using SQLite WAL mode. The generated CA and private keys are stored under `/data/tls`. Home Assistant app backups include `/data`; protect backups because they contain both retained logs and generated private keys.

Cleanup deletes records whose received time is older than the configured period and incrementally reclaims free database pages. A bounded 10,000-event queue prevents unlimited memory growth. If the database cannot keep up, dropped events are counted and shown in the status cards and app log.

## Troubleshooting

### TLS connection fails

- Confirm the device's configured host exactly matches a generated certificate name.
- Confirm **Syslog trusted CA** is installed on the device.
- Confirm TCP 6514 (or the host-side remapped port) is reachable from the device VLAN.
- Restart the app after any option or custom-certificate change.
- Review the app log for handshake or framing errors.

### No UDP events arrive

Enable `udp_enabled`, restart the app, and check the UDP 514 host mapping. UDP is intentionally disabled by default and provides neither encryption nor server authentication.

### Events are stored but not found

Clear all filters and search again. Time filters are converted from browser-local time to UTC. The app classifies only the exact RFC 5424 application name `HAMD-Audit` as an audit event.
