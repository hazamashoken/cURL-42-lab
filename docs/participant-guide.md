# Crack the Cracker — Three Protocols, One Tool

Work in pairs. Your tools are curl and a text editor. Learn to inspect HTTP responses,
transfer files with FTP, and exchange MQTT messages, then connect the three in a final mission.
Only use this isolated training network and your assigned synthetic team data.

The facilitator supplies a rendered copy of this guide at `http://LAB_HOST:8080/guide`.
In the source guide, replace `LAB_HOST` with the facilitator's LAN address (no scheme or port).
Examples use `team01`: replace **every** occurrence with your assigned team identifier.
Replace `FTP_PASSWORD` with your check-in password; do not type placeholder labels literally.
Keep URLs quoted. Commands are single lines and work in Bash and PowerShell.
On Windows, replace `curl` with **`curl.exe`** in every command to avoid PowerShell aliases.

## 00–05 · Preflight and mission

```sh
curl --version
```

Find the `Protocols:` line. It must include `http`, `ftp`, and `mqtt`.
Some curl builds lack MQTT. Tell the facilitator now: pair with a compatible machine or
use the prepared facilitator workstation. No Docker, jq, Python, or package installation
is needed on your computer. Open two terminals and a text editor.

## 05–18 · HTTP: look beyond the body

```sh
curl "http://LAB_HOST:8080/start"
curl -i "http://LAB_HOST:8080/start"
curl -L "http://LAB_HOST:8080/start"
curl -v "http://LAB_HOST:8080/health"
curl --data-urlencode "team=team01" "http://LAB_HOST:8080/check-in"
```

Compare each response with your partner:

- The first command shows the **body**, the response's content. It says the briefing moved.
- `-i` also shows **headers** and the **status code**. `302` means redirect;
  `Location` identifies its destination. Find the extra clue header.
- `-L` follows redirects. The final briefing has status `200` (success).
- `-v` shows request and connection details on stderr; `>` marks sent headers and `<`
  received headers. `/health` returns `ok`. Avoid sharing verbose logs containing credentials.
- `--data-urlencode` sends a URL-encoded **form submission** with POST. No inline JSON is needed.
  Check-in returns your FTP username, password, address, and next objective.
  An unknown team gets `400` (invalid request); `401` means authentication is needed,
  `403` means access is denied, and `404` means the resource was not found.

Save your team's FTP credentials in your local notes. Do not overwrite another team's work.

## 18–28 · FTP: retrieve and leave a receipt

```sh
curl --list-only -u "team01:FTP_PASSWORD" "ftp://LAB_HOST:2121/"
curl -u "team01:FTP_PASSWORD" -o "briefing.txt" "ftp://LAB_HOST:2121/briefing.txt"
```

`--list-only` lists filenames. `-u` supplies the username and password.
`-o` writes the downloaded data into a local file. Open `briefing.txt` in your text editor.
Notice that another challenge file exists: save it for the final mission.

Create `receipt.txt` in your current terminal directory using your editor. Put your team
identifier and a short message in it, then save it as plain text.

```sh
curl -u "team01:FTP_PASSWORD" -T "receipt.txt" "ftp://LAB_HOST:2121/uploads/receipt.txt"
curl --list-only -u "team01:FTP_PASSWORD" "ftp://LAB_HOST:2121/uploads/"
```

`-T` uploads a local file. You can write only inside `uploads/`; the briefing and challenge
files are read-only. Each team has its own FTP root. A successful upload may print no body.

## 28–38 · MQTT: listen, then speak

Use the chat topic in your FTP briefing. Start Terminal A first:

```sh
curl -N --max-time 30 "mqtt://LAB_HOST:1883/lab/team01/chat"
```

While A is running, use Terminal B:

```sh
curl -d "hello-from-team01" "mqtt://LAB_HOST:1883/lab/team01/chat"
```

A plain MQTT URL **subscribes**. `-d` **publishes** the given text payload.
`-N` disables output buffering. Start the subscriber before publishing; messages are not
saved for later listeners. If you miss a message, restart the subscriber and publish again.
For troubleshooting, add `-v` and look for the subscription acknowledgement (SUBACK)
before sending. Your partner can publish after you have started listening.

The subscriber keeps listening until Ctrl+C or its deadline. Curl's timeout message and
exit code **28 at 30 seconds are expected**. Subscriber output may include binary
topic-length bytes followed by the topic and payload: odd leading characters are normal.
Look for your message, rather than expecting clean JSON or one payload per line.

MQTT is anonymous in this lab. Team topic names organize the exercise; **they do not
enforce access control**. Stay on your own team's topics.

## 38–55 · Final mission

Your objective: open your team's cracker on the projected dashboard.
Start at `http://LAB_HOST:8080/challenge/team01`.

1. Inspect the HTTP response beyond its body. Find the exact name of your next file.
2. Retrieve that file from your team's FTP root. Read its API endpoint and authentication clue.
3. Call the protected API as your team. It gives your topics and one-time unlock code.
4. Listen on your result topic **before** sending anything.
5. Publish the exact code to your unlock topic. No added spaces, quotes in the payload, or newline.
6. Read the result and check the dashboard. An incorrect code keeps your team locked.
   Repeating a successful code reports “already unlocked” without changing the completion time.

The filename and credentials differ between teams. Use the evidence you discover;
do not guess another team's values. Ask for a hint if stuck for more than two minutes.

## 55–60 · Debrief

Which information was in headers versus bodies? Why did FTP need a second connection?
Why did MQTT listener order matter? Which lab shortcuts would be unsafe in a real system?
