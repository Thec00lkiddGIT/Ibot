# Ibot Script Hub

Script Hub is where you add your own iMessage commands without touching Ibot's core code. Scripts sit in `scripts/hub/` and show up under the **Script Hub** tab.

> Full guide: **`docs/IBOTSCRIPT_GUIDE.md`**

## Quick start

1. Open Ibot and go to **Script Hub** (wrench icon in the sidebar).
2. Click **New script**, fill in the name and command.
3. Edit the Python, hit **Save to hub**.
4. With the bot **Running**, send `!yourcommand` in iMessage.

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

Still works for simple scripts:

```python
def run(args: str) -> str | list[str]:
    name = args.strip() or "friend"
    return f"Hello, {name}!"
```

## Command rules

| Rule | Detail |
|------|--------|
| Prefix | Users type `!yourcommand` - you don't add the `!` in code |
| Name | 2-32 chars, lowercase letters/digits/underscore, starts with a letter |
| Reserved | Built-ins (`ping`, `weather`, `youtube`, etc.) are taken |
| Reply | Return `str` or `list[str]` for multiple bubbles |

## Files on disk

```
scripts/hub/
  manifest.json
  echo.py
  your_script_id.py
  json/
```

- **manifest.json** - names, authors, enabled flags (let the app manage this)
- **`<id>.py`** - your script code

## Testing

- Bot must be **Running**
- Same Mac? Enable **React to my messages (--self)**
- By default only **new** messages count unless **Catch up** was on before you started

## If something breaks

| Problem | Try this |
|---------|----------|
| Command does nothing | Script enabled? Name right? Bot running? |
| "already a built-in command" | Pick another name |
| Save fails | Fix syntax, hit **Test** first |
| Import errors | Stick to Python stdlib when you can |

## Security

Hub scripts run as you, with full Python access. Only run scripts you trust. Everything stays local in your Ibot folder.
