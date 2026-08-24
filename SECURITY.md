# Security policy

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature for this repository. Do not include certificates, private keys, exported logs, device credentials, IP addresses, or other sensitive operational data in a public issue.

Include the affected version, a minimal reproduction, and the security impact. You should receive an acknowledgement within seven days.

## Supported versions

Security fixes are provided for the latest published app version. Upgrade to the latest release before reporting an issue that may already have been corrected.

## Deployment guidance

- Keep UDP disabled unless a sender cannot support TLS.
- Restrict ports 514 and 6514 to trusted device networks with host or network firewalls.
- Protect Home Assistant backups because app data contains retained logs and generated TLS private keys.
- Never publish the app's `/data` directory or custom `/ssl` private keys.
