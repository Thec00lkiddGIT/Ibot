"""Echo script - IbotScript example."""

from ibot.ibotscript import ibotScript, log

# bot is injected when Ibot loads this script


@ibotScript(
    name="Echo Script",
    author="Ibot",
    description="Echoes your message back",
    usage="!echo <text>",
)
def echo_script():
    @bot.command(name="echo", description="Echoes your message")
    def echo_cmd(ctx, *, args: str):
        if not args:
            ctx.send("Usage: !echo <text>")
            return
        ctx.send(f"🔊 {args}")
        log("echo handled", type_="INFO")


echo_script()
