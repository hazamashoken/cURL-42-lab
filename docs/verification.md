# Verification record

Verified in the supplied workspace on 2026-11-05. This is an implementation and local-test
record, **not a claim that the Compose stack has been exercised on a LAN**.

## Passed

- 16 unittest cases (zero failures), executed with Python 3.14.2 and the pinned Flask 3.1.1
  stack copied from an existing local package cache into `/tmp/cracker-venv`:
  `/tmp/cracker-venv/bin/python -m unittest discover -s tests -v`.
- Coverage includes redirect and clue headers, check-in validation, protected API tokens,
  callback authorization, sequential and concurrent idempotency, persistence across app
  recreation, reset data lifecycle, fixture configuration validation, public secret exclusion,
  exact worker payload/team validation, callback success/duplicates and callback outage handling.
- Worker-to-HTTP unit tests substitute only the network transport and dispatch to the real
  Flask test client. They do not exercise a broker or TCP sockets.
- `docker compose --env-file .env.example config --quiet` — valid Compose configuration.
- `python3 -m compileall -q lab tests scripts` — Python syntax checks pass.
- `sh -n scripts/reset.sh` — shell syntax passes.
- `node --check /tmp/cracker-dashboard.js` — extracted dashboard JavaScript syntax passes.
- `python3 tests/smoke.py --help` — smoke test entry point works.
- `python3 scripts/instructor.py --help` — launcher entry point works.
- Six launcher tests cover private configuration creation, preserving settings, invalid input,
  offline startup flags/URLs, cancelled/confirmed reset and stopping on failure. Docker calls
  are substituted in these tests; live startup remains unverified.
- Separate standards and specification reviews of the launcher found no substantive issues.
- Local curl 8.22.0 advertises HTTP, FTP and MQTT in `Protocols:`.

## Blocked or unverified

- Docker client is installed, but `docker version` reports permission denied for
  `/var/run/docker.sock`. Image builds, container startup, Compose restart and the actual
  reset command could not execute.
- Dependency download failed because package-index DNS/network access is unavailable.
  Flask and its pinned dependencies were available in the local cache; pyftpdlib and
  paho-mqtt were not. Their runtime imports and protocol behavior remain untested here.
  The container uses pinned Python 3.12.11; the local unit run used Python 3.14.2.
- Attempting a local HTTP listener failed with `PermissionError: [Errno 1] Operation not
  permitted` at socket creation, so even standalone actual-curl HTTP testing was blocked.
- `python3 tests/smoke.py --host 127.0.0.1 --restart-http` was attempted: **0 integration
  tests ran**, setup failed with curl exit 7 because no stack was listening. This is not a pass.
- Consequently actual-curl HTTP/FTP/MQTT, external-LAN PASV reachability, broker delivery,
  subscriber readiness, container restart persistence and reset recovery are unverified.
- Projector/browser rendering and animation were inspected in source, not run in a browser.
- The supplied `.git` is a read-only placeholder, not a usable Git repository. `git status`
  reports “not a git repository”; no commit could be created.

Before class, build and run the stack on an authorized facilitator machine, run the full
smoke suite with `--restart-http`, reset, then run again from another LAN machine (restart
check is explicitly skipped there). Reset once more before admitting participants.

## Review

Separate standards and specification reviews inspected all newly created files (the initial
workspace was empty, so no Git diff baseline was available).

### Standards

Two findings fixed: resolve the passive FTP hostname to IPv4 before assigning it to
pyftpdlib, and pin its Python 3.12 compatibility dependencies. No substantive code-smell
findings remained. Runtime correctness still requires the integration run above.

### Specification

One behavior finding fixed: the dashboard now removes cards for teams absent after a reset
with a smaller team count. The previously pending verification document is this file.
No other missing implementation requirements were identified by inspection.

## Documentation references used

- [Flask application factories](https://flask.palletsprojects.com/en/stable/patterns/appfactories/)
  informed the testable app setup.
- [pyftpdlib API](https://pyftpdlib.readthedocs.io/en/latest/api.html) documents per-user
  permissions and directory overrides.
- [Paho Python client](https://github.com/eclipse-paho/paho.mqtt.python) documents version-2
  callbacks and subscribing on reconnect.
- [curl MQTT implementation notes](https://github.com/curl/curl/blob/master/docs/internals/MQTT.md)
  document subscription/publish behavior and limitations.
- [Mosquitto authentication](https://mosquitto.org/documentation/authentication-methods/)
  documents the explicit anonymous-listener setting.
- [pyasyncore](https://pypi.org/project/pyasyncore/) and
  [pyasynchat](https://pypi.org/project/pyasynchat/) provide the compatibility modules required
  by the pinned FTP library on Python 3.12; both are pinned to 1.0.5.
