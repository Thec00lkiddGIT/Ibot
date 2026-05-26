# Ibot Script Hub

Script Hub is where you add your own iMessage commands. User scripts are stored in Application Support (not inside the app bundle).

> Full guide: **`docs/IBOTSCRIPT_GUIDE.md`**

## Quick start

1. Open Ibot and go to **Script Hub** (wrench icon).
2. Click **New script**, fill in the name and command.
3. Edit the Python, hit **Save to hub**.
4. With the bot **Running**, send `!yourcommand` in iMessage.

## Where files live

```
~/Library/Application Support/Ibot/
  config.env           # API keys (auto-created, visible in Finder)
  .state.json          # poll watermark
  .gui_settings.json   # dashboard toggles
  scripts/hub/         # your Script Hub scripts
    manifest.json
    echo.py
    json/
```

The app creates this folder on first launch. You can edit `config.env` from **Permissions → Edit config**.

## IbotScript format (recommended)

```python
from ibot.ibotscript import ibotScript

@ibotScript(name="Hello", author="You", description="Says hi", usage="!hello <name>")
def hello_script():
    @bot.command(name="hello", description="Says hi")
    def hello_cmd(ctx, *, args: str):
        name = args.strip() or "friend"
        ctx.send(f"Hello, {name}!")

hello_script()
```

## Legacy `run(args)` format

Still works for simple scripts.

## Command rules

| Rule | Detail |
|------|--------|
| Prefix | Users type `!yourcommand` |
| Name | 2-32 chars, lowercase, starts with a letter |
| Reserved | Built-ins are taken |
| Reply | Return `str` or `list[str]` |

## Testing

- Bot must be **Running**
- Same Mac? Enable **React to my messages (--self)**

## Security

Hub scripts run as you with full Python access. Only run scripts you trust.
