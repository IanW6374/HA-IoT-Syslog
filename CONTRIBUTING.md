# Contributing

Issues and pull requests are welcome. Keep changes focused, add tests for protocol or storage behavior, and update the changelog when behavior changes.

Before opening a pull request, run:

```sh
PYTHONPATH=hamd_syslog/rootfs/app python3 -m unittest discover -s tests -v
python3 -m compileall -q hamd_syslog/rootfs/app
```

Never add real logs, databases, certificates, private keys, credentials, or network details to tests or issue reports.
