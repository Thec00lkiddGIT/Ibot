# Ibot setup in Visual Studio Code

## 1. Open the project

1. Open **Visual Studio Code**
2. **File → Open Folder…** → choose `Desktop/Ibot`

## 2. Full Disk Access (read messages)

1. **System Settings → Privacy & Security → Full Disk Access**
2. Click **+** → **Applications** → **Visual Studio Code**  
   (`/Applications/Visual Studio Code.app`)
3. Turn the toggle **ON**
4. **Quit VS Code completely** (Cmd+Q), then reopen it

Verify in the VS Code terminal (**Terminal → New Terminal**):

```bash
cd ~/Desktop/Ibot
python3 bot.py --check
```

You need: `SQLite OK: True`

## 3. Automation (send messages)

Reading works with Full Disk Access only. **Sending** needs Automation.

1. Keep **Messages.app** open and signed into iMessage
2. In VS Code terminal run (use a real contact from step 4):

```bash
python3 bot.py --test-send "+15551234567"
```

Use your phone number or email as it appears in iMessage.

3. macOS should show a prompt: **“Visual Studio Code” wants to control “Messages”** → click **OK**
4. If no prompt: **System Settings → Privacy & Security → Automation** → **Visual Studio Code** → enable **Messages**

Run `--test-send` again. You should see **ibot test** in that chat in Messages.

```bash
python3 bot.py --check
```

Both database and Automation should be OK.

## 4. See your chat target

```bash
python3 debug_recent.py
```

Copy the handle (phone/email) from the line where you sent `!ping`.

## 5. Test typewrite (edit in place)

With **Messages open** on a chat where **your last message** is visible:

```bash
python3 bot.py --probe-ui
python3 bot.py --test-edit "hello test"
```

`--probe-ui` should print `ok:scroll-areas=…` (0 is OK - it uses a window fallback).  
`--test-edit` should change your **last bubble** to `hello test`. If it says `no-edit-menu`, right‑click that message - you must see **Edit**.

## 6. Run the bot

**If you type `!ping` yourself in Messages on this Mac:**

```bash
python3 bot.py --self --verbose
```

**If someone else texts you:**

```bash
python3 bot.py --verbose
```

When it works you’ll see:

```text
[12345] (you) +1…: '!ping'
  send: find_chat(...) → ok:id
[12345] → pong sent to +1… (check Messages)
```

And **pong** appears in the Messages thread.

## Common issues

| Symptom | Fix |
|--------|-----|
| `SQLite OK: False` | FDA on **VS Code**, not only Terminal. Quit VS Code (Cmd+Q), reopen. |
| Logs `!ping` but no **pong** in Messages | Run `--test-send`. Fix **Automation → Messages**. |
| `reply failed: Not authorized` | Same as above |
| Sees messages, never `→ pong sent` | Use `--self` if you send from this Mac |
| `--test-send` works, bot doesn’t | Run with `--verbose`; exact text must be `!ping` |

## 7. Optional: run in VS Code debugger

Create `.vscode/launch.json` if you want - running in the integrated terminal is enough for normal use.
