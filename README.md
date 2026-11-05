# Crack the Cracker — Three Protocols, One Tool

A 60-minute, paired curl lab: HTTP inspection → FTP clues → protected HTTP API → MQTT
unlock → live projected dashboard. Students need only curl, a text editor and LAN access.
All credentials and files are synthetic. **Run only on an isolated lab network with disposable
data. Do not expose this intentionally insecure teaching stack publicly.**

## Prerequisites

Facilitator: Docker Engine/Desktop and Docker Compose v2 with `up --wait`, a reachable
LAN IPv4 address or hostname, and permission to use Docker. Build images before going offline.
Python 3.10+ and curl with `http`, `ftp`, `mqtt` are needed on the facilitator/test workstation
for host-side smoke tests; participants do not need Python or Docker.

Reserve TCP 8080 (HTTP), 2121 (FTP control), 30000–30009 (FTP passive data), 1883 (MQTT).
Allow these inbound only from the isolated lab subnet. Check Docker's firewall behavior
and router/VLAN isolation; do not assume a desktop firewall alone blocks published ports.
The LAN must allow peer connections (no Wi-Fi client isolation).

## Instructor launcher (recommended)

With Python 3.10+ and Docker Compose installed, run from the project directory:

```sh
python3 scripts/instructor.py prepare
python3 scripts/instructor.py start
```

`prepare` asks for the facilitator LAN address, team count (default 10), and FTP passive
address. It creates a private `.env` with a random callback secret, builds the images and
provisions fixtures. Existing `.env` settings and team credentials are preserved. If you
already copied `.env.example`, edit its addresses and replace its placeholder secret first.
Run preparation while internet access is available, before class.

`start` waits for service health and prints the participant guide, projector dashboard and
health URLs. It uses only local images, with building and pulling disabled, so subsequent
sessions can start offline. Running the script without an action also starts the lab.
The script works from any working directory when given its full path. On Windows, use
`python` instead of `python3` if needed.

```sh
python3 scripts/instructor.py status
python3 scripts/instructor.py stop
python3 scripts/instructor.py reset
```

`stop` preserves data. `reset` asks you to type `RESET`, then deletes credentials, uploads
and progress, regenerates fixtures, and restarts the lab. Check LAN firewall access before
participants arrive; the launcher does not change firewall settings.

## Manual configuration and startup

From this project directory:

```sh
cp .env.example .env
```

Edit `.env` in your text editor:

| Variable | Meaning |
|---|---|
| `LAB_HOST` | Facilitator LAN IPv4 or reachable hostname, without scheme/port; used in all generated clues and commands |
| `TEAM_COUNT` | 1–99, default 10; smoke tests require at least 2 |
| `FTP_PASSIVE_ADDRESS` | LAN address advertised in PASV replies; preferably the same LAN IPv4 address |
| `WORKER_CALLBACK_SECRET` | Long random facilitator-only secret, shared by HTTP and worker |

Generate the callback secret with Python's `secrets` module and paste the output into `.env`:

```sh
python3 -c "import secrets; print(secrets.token_hex(32))"
```

If host Python is unavailable, build first and use
`docker compose run --rm --no-deps provision python -c "import secrets; print(secrets.token_hex(32))"`.
Replace the example secret before starting services. Then:

```sh
docker compose build
docker compose run --rm --no-deps provision
docker compose up -d --wait
docker compose ps
```

The provisioning command generates team01 through the configured count with separate roots,
FTP passwords, API tokens, unlock codes and filenames. It uses Python `secrets`. An init
service also gates startup, so `up` cannot start HTTP/FTP against missing fixtures. Provisioning
is idempotent: ordinary starts preserve secrets, receipts and progress. A host/team-count change
is rejected until reset. Interrupted provisioning likewise requires reset; partial data is not used.

Images and Python dependencies are version-pinned. After successful build, `up`, provisioning,
shutdown and reset need no external API or internet. Do not use `--pull always` offline.

## LAN access and handout

Replace `LAB_HOST` in the following addresses with your configured value:

- `http://LAB_HOST:8080/guide` — rendered Markdown participant handout; all command hostnames
  are substituted during provisioning. Save/distribute this file; it contains no solution credentials.
- `http://LAB_HOST:8080/dashboard` — projector dashboard.
- `http://LAB_HOST:8080/health` — `ok`.

The participant guide uses team01 examples. Each pair substitutes its assigned identifier.
Windows users use `curl.exe` in all commands. Some curl builds omit MQTT: prepare a compatible
paired machine or facilitator workstation before the session.

Run a health check **from another LAN machine**, with the configured host substituted:

```sh
curl -v "http://LAB_HOST:8080/health"
```

`docker compose ps` should show HTTP, FTP, MQTT and worker healthy. Provision exits successfully;
it is not a long-running service. Worker health means the broker acknowledged its subscriptions.
Use `docker compose logs http ftp mqtt worker` for diagnosis. Logs and shell history can contain
training credentials; keep them within the lab.

## Tests

Fast application/fixture/worker tests, using the built Python image:

```sh
docker compose run --rm --no-deps http python -m unittest discover -s tests -v
```

Alternatively, on a development host with dependencies available:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Run integration tests on a **fresh/reset lab**, with at least two teams, from the facilitator
host in this directory. Replace the host placeholder; the script uses actual curl over published
ports, outside the Compose network:

```sh
python3 tests/smoke.py --host LAB_HOST --restart-http
```

For a second LAN workstation (no Docker needed), copy `tests/smoke.py` and run:

```sh
python3 smoke.py --host LAB_HOST
```

That run explicitly skips the Compose restart test; run the restart check on the facilitator
host separately after resetting. The script requires all three curl protocols and fails clearly
if one is missing. MQTT readiness is confirmed by receipt of a unique probe before each test
publication, not by assuming a sleep is long enough. FTP is tested with both normal passive
mode and forced PASV honoring the advertised address.

Coverage: redirects/headers, check-in validation, FTP auth/list/download/upload, read-only files
and team isolation, missing/wrong/cross-team tokens, callback auth, MQTT chat, bad/good unlocks,
non-retained result delivery, duplicates, application restart persistence, and public progress
without secrets. Tests modify receipts and complete team01: **reset after testing**.
See [verification record](docs/verification.md) for what could actually run in the build workspace.

## Shutdown and reset

```sh
docker compose down
```

This preserves named volumes. Resume with `docker compose up -d --wait`.

Explicit reset, from the facilitator's POSIX shell:

```sh
./scripts/reset.sh
```

This stops services, deletes this Compose project's fixture, FTP and progress volumes,
regenerates secrets/files, then starts and waits for readiness. All uploads and completion
records are lost. On PowerShell run the equivalent commands directly:

```sh
docker compose down --volumes --remove-orphans
docker compose run --rm --no-deps provision
docker compose up -d --wait
```

Confirm all dashboard cards are locked; old credentials no longer work. Re-download the guide
if the configured host changed. Do not reset during class unless intentionally restarting the lab.

## Design and file map

| Path | Responsibility |
|---|---|
| `lab/provision.py` | One-time fixtures and rendered participant guide |
| `lab/web.py` | Flask routes, secret-checked callback, SQLite completion ownership |
| `lab/ftp.py` | Authenticated pyftpdlib server, per-team roots, upload-only write permissions |
| `lab/worker.py` | Paho unlock subscriptions, exact code validation, HTTP callback, non-retained results |
| `lab/templates/dashboard.html` | No-build HTML/CSS/JS dashboard, two-second read-only polling |
| `mosquitto/` | Pinned broker image and anonymous isolated-lab listener |
| `tests/` | Unit tests and actual-curl integration checks |

The HTTP app alone mounts the SQLite progress volume. Worker and FTP do not have database
access. All services that need credentials mount fixtures, but only provisioning writes them;
no static directory or public route serves the complete config. Only the generated participant
guide is served at `/guide`. Check-in intentionally reveals one team's FTP credentials.
An atomic SQLite insert ensures repeated valid unlocks preserve the first UTC completion time.
The dashboard displays local-time equivalents. Result messages are not retained; users can
resubscribe and resend after a missed response or callback outage.

The broker is anonymous: team topic names are organization, not access control. MQTT results
can be spoofed by other lab clients; the HTTP-owned dashboard is the completion record.

## Troubleshooting

| Symptom | Check |
|---|---|
| Docker socket denied | Use a facilitator account authorized to access Docker; verify `docker version`. |
| Provision reports changed/incomplete config | Stop and reset; existing fixtures are never silently overwritten. |
| HTTP not reachable | Host IP/DNS, port 8080, Wi-Fi peer isolation, VPN and firewall. |
| FTP login succeeds, listing stalls | Passive data ports and advertised address; see forced-PASV diagnostic in facilitator guide. |
| FTP 530 | Team/password typo or stale pre-reset credentials. Anonymous FTP is disabled. |
| FTP 550 on upload | Only `uploads/` is writable; local source file must exist. |
| API 401 | Use that team's token with exact `Authorization: Bearer ...` header. |
| Curl reports unsupported MQTT | Use a prechecked paired machine/facilitator workstation. |
| No MQTT result | Subscribe first, check worker health, publish exact code to unlock topic. |
| Curl ends with timeout 28 | Expected at MQTT `--max-time` deadline. |
| MQTT output has odd bytes | Topic-length bytes/topic prefix can be present; look for payload text. |
| Callback unavailable result | Check HTTP and shared secret; restore service, resubscribe and retry. |

Teaching materials: [participant guide](docs/participant-guide.md),
[facilitator guide](docs/facilitator-guide.md), [private solutions](docs/solutions.md).
