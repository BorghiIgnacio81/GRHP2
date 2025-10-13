# Gunicorn systemd: graceful reload and safer defaults

This file contains a suggested `systemd` unit and best-practices to avoid producing 500 errors during deployments caused by abrupt `systemctl restart` calls.

Why: your service was receiving SIGTERM and restarting while requests were in flight, producing 500s. Use `ExecReload` + a graceful reload to minimise disruption.

Suggested unit override (create `/etc/systemd/system/gunicorn.service.d/override.conf` or edit the unit):

```
[Service]
# Make sure the working directory and user match your current unit
ExecStart=/usr/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 gestion_rrhh.wsgi:application
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
TimeoutStopSec=30
Restart=on-failure
RestartSec=5
```

Notes:
- `ExecReload` sends `SIGHUP` to the master process which triggers a graceful reload (workers are restarted one-by-one without dropping connections).
- Adjust `--workers` to a sensible value: typically `workers = 2 * cpu + 1`.
- Increase `TimeoutStopSec` if you have long-running requests.
- After changing the unit files run:

```bash
sudo systemctl daemon-reload
sudo systemctl reload-or-restart gunicorn
```

If you prefer to keep the existing unit file, add the `ExecReload` line under `[Service]` by using `systemctl edit gunicorn` which creates the override file safely.

Troubleshooting:
- If you still see `WORKER TIMEOUT` or `was sent SIGKILL! Perhaps out of memory?` in journalctl, check memory usage and consider reducing worker memory footprint, adding swap, or decreasing workers.
