# IbotScript Guide v1.0

*Same idea as NightyScript, but for iMessage on your Mac.*

## 1. Overview

**IbotScript** lets you add your own Python commands to **Ibot**. You write the logic; Ibot handles reading Messages and sending replies.

> **Heads up:** This is iMessage on macOS, not Discord. No `discord.py`, no servers or channels, no embed objects. You reply with `ctx.send()` or formatted text via `forwardEmbedMethod()`.

> **Imports:** Stick to normal Python plus IbotScript helpers:
> ```python
> from ibot.ibotscript import ibotScript, getConfigData, updateConfigData, getScriptsPath, forwardEmbedMethod, log
> ```
> `bot` shows up automatically when your script loads. Don't import it yourself.

> **Where scripts live:** `scripts/hub/` in your Ibot folder, or the **Script Hub** tab in the app.

## 2. Script structure

Use `@ibotScript` at the top (same role as Nighty's `@nightyScript`):

```python
from ibot.ibotscript import ibotScript, log

@ibotScript(
    name="Script Name",
    author="YourName",
    description="What it does",
    usage="!mycommand <args>",
)
def script_function():
    @bot.command(name="mycommand", description="Does something")
    def mycommand_handler(ctx, *, args: str):
        ctx.send(f"You said: {args}")
        log("handled mycommand", type_="INFO")

script_function()  # Don't skip this - it registers your commands
```

| Field | What it's for |
|-------|----------------|
| `name` | Shows up in Script Hub |
| `author` | Your name |
| `description` | Short summary |
| `usage` | How to use it (`!` prefix, `[optional]` args, `--flags`) |

Call **`script_function()` at the bottom** or your commands won't load.

## 2.1 Docs inside your script

Worth adding a docstring in the entry function:

```python
def script_function():
    """
    MY SCRIPT
    ---------

    What this script does.

    COMMANDS:
    !mycommand <args> - Does something

    EXAMPLES:
    !mycommand hello - Example usage

    NOTES:
    - Bot needs to be Running in the Ibot dashboard
    """
```

## 3. Command prefix

People type **`!command`** in iMessage. In your `usage` field you can write `!mycommand <args>` so it's clear. Ibot strips the prefix - your handler only gets the args.

## 4. Core stuff

### 4.1 Config (`getConfigData`, `updateConfigData`)

```python
value = getConfigData().get("my_key", "default")
updateConfigData("my_key", "new_value")
```

- Saved per script in `scripts/hub/config.json`
- Use clear keys like `myscript_debug`, not just `debug`
- Always pass a default with `.get(key, default)`

### 4.2 JSON files

```python
from pathlib import Path
import json

BASE_DIR = Path(getScriptsPath()) / "json"
DATA_FILE = BASE_DIR / "my_data.json"

BASE_DIR.mkdir(parents=True, exist_ok=True)

def load_data():
    try:
        with open(DATA_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"items": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
```

Keep JSON under `scripts/hub/json/`.

### 4.3 Commands (`@bot.command`)

```python
@bot.command(name="command", usage="!command <arg>", description="Desc", aliases=["c"])
def command_handler(ctx, *, args: str):
    if not args:
        ctx.send("Usage: !command <arg>")
        return
    ctx.send(f"Result: {args}")
```

| Parameter | What you get |
|-----------|----------------|
| `ctx` | Context for this message (see below) |
| `args` | Everything after the command name |

- **`ctx.send(text)`** - add a reply bubble
- **`ctx.reply_embed(content=..., title=...)`** - nicer formatted text block

**Tips:**
- Split args with `.split()`, `.strip()`, or `re` if you need to
- Show usage when someone runs the command empty
- `log("msg", type_="INFO")` helps when debugging

### 4.3.1 Subcommands

Pack related stuff under one command:

```python
@bot.command(name="main", description="Main command with subcommands")
def main_cmd(ctx, *, args: str):
    parts = args.strip().split(maxsplit=1)
    sub = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    if sub == "help":
        ctx.send("!main do thing\n!main setting on")
        return
    if sub == "do":
        ctx.send(f"Doing: {rest}")
        return
    ctx.send("Unknown subcommand. Try !main help")
```

### 4.4 Listeners (`@bot.listen`)

Auto-reply when someone sends a normal message (not a command):

```python
@bot.listen("on_message")
def message_handler(message):
    if message.is_from_me:
        return
    if "keyword" in message.content.lower():
        return "Auto-reply text"
```

Right now the main event is **`on_message`**. It runs when the message wasn't already handled as a `!command`.

Return a `str` or `list[str]` to send a reply.

### 4.5 Fancy text (`forwardEmbedMethod`)

No Discord embeds here. You can still send a clean block:

```python
text = forwardEmbedMethod(
    title="Weather",
    content="Clear · 72°F\nHumidity: 40%",
)
ctx.send(text)
```

Or use `ctx.reply_embed(title="Weather", content="...")`.

### 4.6 Logging

```python
log("Information", type_="INFO")
log("Warning", type_="WARNING")
log("Critical error", type_="ERROR")
```

## 5. Full example

```python
from ibot.ibotscript import ibotScript, getConfigData, updateConfigData, log

ENABLED_KEY = "greeter_enabled"

@ibotScript(
    name="Greeter",
    author="Ibot",
    description="Replies when someone says hello",
    usage="!greet on/off · listens for 'hello'",
)
def greeter_script():
    if getConfigData().get(ENABLED_KEY) is None:
        updateConfigData(ENABLED_KEY, True)

    @bot.command(name="greet", description="Turn auto-greet on or off")
    def greet_cmd(ctx, *, args: str):
        arg = args.strip().lower()
        if arg == "on":
            updateConfigData(ENABLED_KEY, True)
            ctx.send("Greeter on.")
        elif arg == "off":
            updateConfigData(ENABLED_KEY, False)
            ctx.send("Greeter off.")
        else:
            ctx.send("Usage: !greet on/off")

    @bot.listen("on_message")
    def on_message(message):
        if message.is_from_me:
            return
        if not getConfigData().get(ENABLED_KEY, True):
            return
        if "hello" in message.content.lower():
            return "Hey there!"

greeter_script()
```

## 6. Script Hub in the app

| Button | What it does |
|--------|----------------|
| **New script** | Starts a Nighty-style template |
| **Save to hub** | Checks your code and saves it |
| **Test** | Runs the handler without sending a real iMessage |
| **Enabled** | Off = bot ignores that script |

## 7. Old `run(args)` format

Some older scripts look like this and still work:

```python
def run(args: str) -> str | list[str]:
    return f"Echo: {args}"
```

For anything new, use `@ibotScript` + `@bot.command`.

## 8. iMessage gotchas

- Bot has to show **Running** on the dashboard
- Testing from the same Mac? Turn on **React to my messages**
- Replies go through AppleScript into Messages.app
- You need Full Disk Access so Ibot can read `chat.db`

---

**On disk:** `scripts/hub/manifest.json` (info about each script) and `scripts/hub/<id>.py` (your code)
