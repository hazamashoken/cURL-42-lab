# Facilitator guide

## Instructor commands

Before class, run `python3 scripts/instructor.py prepare` from the project directory.
Answer the LAN address, team count and passive address prompts; the script generates the
internal secret and builds/provisions the lab. It preserves an existing `.env`.

At the session, run `python3 scripts/instructor.py start`. Open the printed dashboard URL
on the projector and distribute the printed guide URL. Use `status` to inspect containers,
`stop` to shut down without losing progress, and `reset` to regenerate the lab after typing
`RESET` at its destructive-action prompt. Preparation requires internet on the first build;
start and reset use the local images. The instructor needs Python 3.10+; students do not.

## Preparation checklist

- Use an isolated LAN and disposable training data. Never expose the stack publicly or
  configure router port forwarding. This lab intentionally uses clear-text HTTP/FTP/MQTT.
- Prepare Docker Engine/Desktop with Compose v2 supporting `up --wait`. Build/pull all
  images before the session; startup and reset use local images and need no internet.
- Configure `.env` using the README. Use a stable LAN IPv4 address (DHCP reservation is useful).
  `FTP_PASSIVE_ADDRESS` must resolve to that machine from participant computers.
- Allow inbound TCP 8080, 2121, 1883, and 30000–30009 **from the lab subnet only** in host
  firewalls. Docker published ports may bypass some host firewall frontends; enforce
  isolation at the router/VLAN too. Disable wireless client isolation on the lab SSID.
- Run the smoke suite before class, including application restart. Reset afterward: the
  suite uploads files and completes team01. Confirm all cards are locked.
- Test again from another LAN computer, especially forced PASV; a check inside a container
  cannot validate the advertised address or host firewall path.
- Check participant curl `Protocols:` for HTTP, FTP, MQTT. Prepare a compatible paired
  machine/facilitator workstation in advance; do not rely on downloads during the session.
- Assign pairs team01 through the configured count. Distribute only the rendered participant
  guide from `/guide`, and project `/dashboard`. Do not distribute `.env`, fixtures, or solutions.
- Confirm each pair has a text editor and two terminals. Windows uses `curl.exe`.

## Delivery, minute by minute

| Minutes | Facilitation |
|---|---|
| 00–02 | Pair students, assign identifiers, introduce the cracker mission. |
| 02–05 | Check curl protocols, switch incompatible machines, open editor and terminals. |
| 05–08 | Request `/start`, compare body versus `-i` headers. |
| 08–11 | Explain 302/Location; follow with `-L`. |
| 11–14 | Use verbose health request; identify request versus response lines. |
| 14–18 | Submit the check-in form and save FTP credentials. |
| 18–21 | List FTP root and download briefing. |
| 21–24 | Read briefing; identify the chat topic. |
| 24–28 | Create and upload receipt, confirm listing. |
| 28–31 | Explain broker, topic, publisher and subscriber; start Terminal A. |
| 31–35 | Publish from Terminal B; swap roles and repeat. |
| 35–38 | Discuss timeout, binary prefixes, subscriber-first ordering and anonymous topics. |
| 38–41 | Reveal final objective; teams inspect challenge headers. |
| 41–45 | Retrieve the distinct challenge file; identify bearer authentication. |
| 45–49 | Call protected API; locate result and unlock topics. |
| 49–53 | Subscribe, publish exact code, observe dashboard. |
| 53–55 | Retry missed results; demonstrate idempotency. |
| 55–60 | Debrief protocol boundaries, authentication and insecure shortcuts. |

Shortened path: drop creation/upload of `receipt.txt` (24–28). Keep the FTP listing and
briefing download: they establish skills needed for the final challenge. Use the saved
four minutes for MQTT compatibility or final-stage help.

## Expected HTTP behavior

| Request | Expected |
|---|---|
| GET `/start` | 302; Location `/briefing`; X-Lab-Clue `look-beyond-the-body` |
| GET `/briefing` | 200, readable plain text |
| GET `/health` | 200, `ok` |
| POST `/check-in`, valid form team | 200, own FTP credentials/address/next objective |
| POST `/check-in`, missing or invalid team | 400 |
| GET `/challenge/team01` | 200, X-Next-File gives distinct challenge filename |
| GET `/api/team01/mission` | 401 without correct team bearer token; 200 with it |
| POST `/internal/complete/team01` | 403 without worker secret; worker-only completion |
| GET `/dashboard`, `/progress` | 200, public progress without secrets |
| GET `/guide` | 200, plain-text Markdown participant guide with configured host |
| Unknown team challenge/API or unknown path | 404 |

## Progressive hints (give one at a time)

| Stage | Hint 1 | Hint 2 | Hint 3 |
|---|---|---|---|
| 1: HTTP clue | What did the HTTP exercise show besides the body? | Include response headers. | Use `-i`; read `X-Next-File` at `/challenge/YOUR_TEAM`. |
| 2: FTP file | Your next clue is already in your FTP directory. | It is not `briefing.txt`; use the exact filename from HTTP. | Reuse `-u` and `-o` with that filename; open the download in your editor. |
| 3: API | The downloaded file identifies an endpoint and a credential. | This credential belongs in a request header. | Use `-H "Authorization: Bearer YOUR_TOKEN"` with that endpoint. |
| 4: Listen | MQTT does not save these responses for late listeners. | Use the API's result topic in a second terminal. | A plain `mqtt://` URL with `-N --max-time 30` subscribes; `-v` shows acknowledgement. |
| 5: Publish | Send the API's code, not the token or FTP password. | Use the unlock topic, not the result topic. | `-d "EXACT_CODE"` publishes plain text; remove extra spaces/newlines. |
| 6: Verify/retry | Look in the listening terminal and at the projected card. | If it timed out, subscribe again before retrying. | Resend the same valid code: “already unlocked” confirms completion without changing the timestamp. |

## FTP passive-mode troubleshooting

Start with the rendered guide's host and known team credentials. Add `-v` to its FTP
listing command. The TCP 2121 connection carries login and commands. Curl normally asks
for EPSV; its response gives a passive port. A **second** connection carries listing/file
data using TCP 30000–30009. Login success followed by a stalled listing usually means the
data path is blocked, not a wrong password.

To test the advertised PASV address rather than curl's modern EPSV/default address reuse:

```sh
curl -v --disable-epsv --no-ftp-skip-pasv-ip --list-only -u "team01:FTP_PASSWORD" "ftp://LAB_HOST:2121/"
```

Replace placeholders first. Check the `227` address matches the reachable LAN IPv4 address
and its port falls in the published range. Check all ten ports in firewall rules, Docker
port mappings, VPN routing, LAN DNS and Wi-Fi client isolation. Do not advertise a Docker
container IP or a loopback address. Ten passive ports serve short transfers; stagger retries
if many teams transfer simultaneously. Keep the trailing slash for directory URLs.
`530` means authentication failed; `550` on a root upload is expected permission enforcement.

## MQTT recovery

If `mqtt` is missing from `curl --version`, use a prepared compatible workstation or have
the pair share a compatible participant computer. Participants still use curl; they need
no Docker or paho installation. Confirm compatibility before the hour starts.

A result is not retained: subscribe again and republish if missed. Curl timeout 28 at the
specified deadline is normal. Binary prefix bytes/topic text in subscriber output are also
normal. For a silent worker, check `docker compose ps` and `docker compose logs worker mqtt`.
Worker health becomes ready only after the broker acknowledges unlock subscriptions.
A callback failure yields a retry message; restore HTTP health and resend. When MQTT
reconnects, the worker subscribes again. Do not send unlocks while the worker is unhealthy.

## Security lessons and boundaries

`/check-in` deliberately reveals a team's FTP credentials to **anyone who knows its identifier**.
That is broken authorization, not a production design. HTTP headers and FTP files carry
clues but do not encrypt them. Bearer tokens are credentials; possession grants access.
FTP roots and permissions isolate file operations, but all services and credentials remain
synthetic and disposable. Never use real passwords or copy real files into uploads.

MQTT is anonymous with no topic ACLs. Topic naming organizes teams; it does **not** prevent
reading, spoofing results, or publishing into another team's topics. Treat the HTTP-owned
dashboard as the completion record. A real system would authenticate clients, authorize
per-topic actions, encrypt transports, and rate-limit or otherwise limit resource use.
The callback uses a separate secret, checks it before changing state, and is not a
participant exercise endpoint. Do not expose it outside the isolated network.

Reset deletes all lab credentials, receipts and completion times. Ordinary `stop`, `down`
(without `--volumes`), and container restarts preserve them. Changing host/team count requires
reset so downloaded clues and published instructions cannot silently disagree.
