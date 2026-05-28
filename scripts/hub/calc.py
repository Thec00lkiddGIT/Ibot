from ibot.ibotscript import ibotScript, log

@ibotScript(
    name="Calculator",
    author="Ibot",
    description="Simple calculator for math expressions",
    usage="!calc <math expression>",
)
def calculator_script():
    """
    CALCULATOR SCRIPT
    -----------------

    COMMANDS:
    !calc <expression> - Solves math problems

    EXAMPLES:
    !calc 5 + 5
    !calc 10 * 4
    !calc (8 + 2) / 5
    """

    @bot.command(
        name="calc",
        description="Calculate a math expression",
        usage="!calc <expression>",
    )
    def calc_command(ctx, *, args: str):
        expression = args.strip()

        if not expression:
            ctx.send("Usage: !calc <expression>")
            return

        try:
            allowed_chars = "0123456789+-*/(). %"
            for char in expression:
                if char not in allowed_chars:
                    ctx.send("Only basic math is allowed.")
                    return
            result = eval(expression)
            ctx.reply_embed(
                title="Calculator",
                content=f"Expression: {expression}\nResult: {result}",
            )
            log(f"Calculated: {expression} = {result}", type_="INFO")
        except Exception as e:
            ctx.send(f"Error: {str(e)}")
            log(f"Calculator error: {e}", type_="ERROR")


calculator_script()
