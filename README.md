# Ibot

macOS iMessage selfbot. Watches your local Messages database and replies through the Messages app.

## Requirements

- macOS with iMessage enabled and signed into the Messages app
- Python 3.10+ (stdlib only)

## Setup

1. **Full Disk Access** - required to read `~/Library/Messages/chat.db`  
   System Settings → Privacy & Security → Full Disk Access.

   **Important:** FDA is per-app. If you run the bot from **Cursor’s terminal**, add **Cursor** (`/Applications/Cursor.app`) - enabling **Terminal** alone is not enough. Quit Cursor (Cmd+Q) after changing the setting.

   **Ibot.app (from the DMG):** macOS needs the **Python file inside the app**, not just the Ibot icon.

   1. System Settings → Privacy & Security → Full Disk Access → **+**
   2. Press **Cmd+Shift+G** and paste the **full** path (must start with `/Applications`):
   ```
   /Applications/Ibot.app/Contents/Resources/Ibot/.venv/bin/python3
   ```
   3. Select **python3**, click Open, enable the toggle, then quit Ibot (Cmd+Q) and reopen.

   In the app, open the **Permissions** tab and use **Copy path** if you need the exact path for your install.

   Verify:
   ```bash
   python3 bot.py --check
   ```

2. **Automation** - macOS will prompt the first time the bot sends a message. Allow **Terminal** (or your runner) to control **Messages**.

3. **API keys (`config.env`)** - created automatically on first launch:

   ```
   ~/Library/Application Support/Ibot/config.env
   ```

   Open Ibot → **Permissions** → **Edit config**, or in Terminal:

   ```bash
   open -e ~/Library/Application\ Support/Ibot/config.env
   ```

   Dev installs can still use a project-root `.env`; it is copied to Application Support the first time the app runs.

## Run

Run from **Terminal.app** (with FDA on Terminal) or **Cursor** (with FDA on Cursor):

```bash
cd /Users/oblivion/Desktop/Ibot
python3 bot.py --verbose
```

### GUI app

Native macOS dashboard (WebKit - **not Chrome**):

```bash
./scripts/setup_gui.sh          # one time
source .venv/bin/activate
python3 gui.py
```

Real app window with the dark dashboard, your logo, notification center, and Start bot button.

Or double-click **Ibot.app** on Desktop after `./scripts/build_app.sh`.

Optional: `python3 gui.py --web` for a browser tab.


### Testing `!ping`

- **From another phone / contact** → normal mode: `python3 bot.py`
- **From this Mac** (you typing in Messages) → those are stored as *your* sends. Use:
  ```bash
  python3 bot.py --self --verbose
  ```

### Troubleshooting

```bash
python3 bot.py --check          # FDA ok?
python3 debug_recent.py         # see last messages + decoded text
python3 bot.py --reset-state    # re-watch from "now"
python3 bot.py --catch-up -v    # process backlog from .state.json
```

By default the bot only handles messages that arrive **after** you start it. To process backlog since last run:

```bash
python3 bot.py --catch-up --verbose
```

## Commands

| Command | Response |
|---------|----------|
| `!ping` | `pong` |
| `!gay` | Random `YOU are 0-100% gay` |
| `!word` | Sends one random word |
| `!dadjoke` | Random dad joke (API Ninjas) |
| `!qr https://example.com` | QR code PNG + embed caption (API Ninjas) |
| `!youtube search rick roll` | YouTube search results (SerpAPI) |
| `!youtube video dQw4w9WgXcQ` | Video metadata (title, views, description) |
| `!youtube trans dQw4w9WgXcQ` | Video transcript (English) |
| `!weather Groves` | Weather for that city (C99.nl API) |
| `!check example.com` | Check URL against all school filters (GLSeries) |
| `!check linewize example.com` | Check one filter only |
| `!bulk url1 url2` | Bulk check up to 3 URLs |
| `!typewrite Hello World` | **Edits** your command bubble in place: H → He → Hel → … (1s steps) |

### Script Hub (IbotScript)

Write your own commands in Python. Open **Script Hub** in the app or see **`docs/IBOTSCRIPT_GUIDE.md`**.

Example: `!echo hello` -> `🔊 hello` (sample in `scripts/hub/`)

Old `run(args)` scripts still work. New ones should use `@ibotScript` and `@bot.command`.

**GLSeries:** set `GLSERIES_TOKEN` in `.env`. Results are sent as embed-style messages with filter name, category, and blocked/allowed status.

Example `!check` reply:

```
━━━━━━━━━━━━━━━━━━━━
🔗 URL Check
example.com
━━━━━━━━━━━━━━━━━━━━

Linewize
  Category: Computing
  Status: Allowed

GoGuardian
  Category: Educational Resources
  Status: Blocked

━━━━━━━━━━━━━━━━━━━━
46 filters · 12 blocked
```

Copy `.env.example` values into Application Support (see above). For dev clones, you can copy `.env.example` to `.env` in the project folder.

Example:

```
!weather Groves
```

```
Weather - Groves, US

Clear · clear sky
24 (C)  (low 22.99 (C), high 24 (C))

Humidity: 83%
Wind: 2.06 m/s @ 210°
Pressure: 1012 hPa

Sunrise: 19:17 (07:17 PM)
Sunset: 09:08 (09:08 AM)
Coords: 29.9483, -93.9171
```

## How it works

- Polls `chat.db` for incoming messages (`is_from_me = 0`)
- Decodes message text from `text` or `attributedBody` (Ventura+)
- Sends replies with AppleScript via the Messages app
- Stores the last processed message ROWID in `.state.json`

## Notes

- Selfbots may violate Apple's terms of service; use at your own risk on your own account.
- Keep Messages.app running in the background for reliable sends.
