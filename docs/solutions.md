# Facilitator only — complete worked solution

Do not distribute this file with the participant guide. These are Bash/PowerShell-compatible
single-line commands. On Windows use `curl.exe`. Replace `LAB_HOST` everywhere with the
configured address, and `team01` with the assigned team. The rendered participant guide uses
the configured host automatically; this facilitator source uses placeholders deliberately.

```sh
curl --version
curl "http://LAB_HOST:8080/start"
curl -i "http://LAB_HOST:8080/start"
curl -L "http://LAB_HOST:8080/start"
curl -v "http://LAB_HOST:8080/health"
curl --data-urlencode "team=team01" "http://LAB_HOST:8080/check-in"
```

Copy the returned FTP password into `FTP_PASSWORD` below.

```sh
curl --list-only -u "team01:FTP_PASSWORD" "ftp://LAB_HOST:2121/"
curl -u "team01:FTP_PASSWORD" -o "briefing.txt" "ftp://LAB_HOST:2121/briefing.txt"
```

Read `briefing.txt` in the editor. Create a plain-text `receipt.txt`, save it in the working
directory, then upload and list it:

```sh
curl -u "team01:FTP_PASSWORD" -T "receipt.txt" "ftp://LAB_HOST:2121/uploads/receipt.txt"
curl --list-only -u "team01:FTP_PASSWORD" "ftp://LAB_HOST:2121/uploads/"
```

Chat Terminal A, then Terminal B while A listens:

```sh
curl -N --max-time 30 "mqtt://LAB_HOST:1883/lab/team01/chat"
curl -d "hello-from-team01" "mqtt://LAB_HOST:1883/lab/team01/chat"
```

Inspect challenge headers:

```sh
curl -i "http://LAB_HOST:8080/challenge/team01"
```

Copy the **entire** `X-Next-File` value (including `.txt`) into `CHALLENGE_FILENAME`:

```sh
curl -u "team01:FTP_PASSWORD" -o "mission.txt" "ftp://LAB_HOST:2121/CHALLENGE_FILENAME"
```

Open `mission.txt`. Copy its API bearer token into `TEAM_TOKEN` and use its endpoint:

```sh
curl -i -H "Authorization: Bearer TEAM_TOKEN" "http://LAB_HOST:8080/api/team01/mission"
```

Expect `200` and plain-text unlock topic, result topic, and code. A missing, wrong,
or different team's token returns `401`. Copy the code exactly into `UNLOCK_CODE`.
Start result Terminal A first (adding `-v` shows SUBACK for readiness):

```sh
curl -v -N --max-time 30 "mqtt://LAB_HOST:1883/lab/team01/result"
```

After subscription acknowledgement, publish in Terminal B:

```sh
curl -d "UNLOCK_CODE" "mqtt://LAB_HOST:1883/lab/team01/unlock"
```

A prints `team01: Unlocked! Cracker cracked.` The dashboard at
`http://LAB_HOST:8080/dashboard` opens that cracker within about two seconds.
The subscriber will still run until timeout; exit 28 at its deadline is normal.

Publish again while listening: expect `team01: already unlocked.` The completion timestamp
stays unchanged. Publish `wrong`: expect an incorrect-code message, with no state change.
If the result was missed, subscribe again and resend the code. Results are never retained.

These credentials and unlock codes are unique to each reset. Never paste examples from a
previous session. The internal callback secret is facilitator-only and is not needed to solve
any stage; participants must not call the callback directly.
