# IoT Syslog for Home Assistant

IoT Syslog is a Home Assistant app (formerly called an add-on) for collecting, searching, and retaining logs from IoT devices, including the [IoT Modular Device](https://github.com/IanW6374/IoT-Modular-Device) project.

It receives the protocol implemented by IoTMD and other standards-compliant senders:

- RFC 5424 syslog using the `local0` facility
- encrypted TCP with TLS and RFC 6587 octet-counted framing on port 6514
- optional, unencrypted UDP on port 514
- `IoTMD` application names for device logs and `IoTMD-Audit` for audit events

## Features

- TLS enabled and UDP disabled by default
- dedicated local CA and server certificate generated on first start
- device-compatible CA download in DER format
- custom certificate support from Home Assistant's `/ssl` directory
- searchable ingress interface with source, device, application, severity, transport, and time filters
- SQLite persistence in the app's backed-up `/data` directory
- configurable retention from 1 to 3,650 days with automatic cleanup
- bounded messages and ingest queue to protect the Home Assistant host
- CSV export for the current filters
- `aarch64` and `amd64` images published through GitHub Container Registry

## Install

1. In Home Assistant, open **Settings > Apps > App store** (shown as **Add-ons** on older releases).
2. Open the repository menu, choose **Repositories**, and add:

   `https://github.com/IanW6374/HA-IoT-Syslog`

3. Install **IoT Syslog**.
4. Read the app documentation before starting it, especially the TLS server-name requirement.

Detailed setup and option descriptions are in [hamd_syslog/DOCS.md](hamd_syslog/DOCS.md).

For IoTMD deployments using [Home Assistant IoT Certificate Authority](https://github.com/IanW6374/HA-IoT-Certificate-Authority), the recommended production setup is `custom` TLS mode with that CA's existing Home Assistant certificate and key mounted read-only from `/ssl`. The app does not copy or re-enrol the private key.

## Security model

TLS provides encryption in transit and authenticates the server to each IoTMD device. IoTMD validates the issuing CA and checks that its configured syslog host is present in the certificate's subject alternative names. The current IoTMD client does not present a client certificate, so this is server-authenticated TLS rather than mutual TLS.

Generated private keys remain in the app's persistent `/data/tls` directory and are never offered for download. The search interface is exposed only through authenticated Home Assistant ingress. UDP is available for compatibility but is unencrypted and disabled by default.

Do not commit production certificates, private keys, databases, or exported logs to this repository.

## Development

Run the unit suite from the repository root:

```sh
PYTHONPATH=hamd_syslog/rootfs/app python3 -m unittest discover -s tests -v
```

The GitHub workflow builds and publishes multi-architecture images using the current Home Assistant builder actions.

## License

MIT License. See [LICENSE](LICENSE).
