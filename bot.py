import discord
from discord.ext import commands

import yaml
import logging
import sys
import traceback

# 1. Setup Logging first
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
handler = logging.StreamHandler()
handler.setFormatter(formatter)

# Discord Logger
logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# Filter out the PyNaCl warning since we don't need voice
class PyNaClFilter(logging.Filter):
    def filter(self, record):
        return "PyNaCl is not installed" not in record.getMessage()

logging.getLogger("discord.client").addFilter(PyNaClFilter())

# Bot Logger
log = logging.getLogger("bot")
log.setLevel(logging.INFO)
log.addHandler(handler)


class InvalidConfigValue(Exception):
    pass


class InvalidRefreshRate(InvalidConfigValue):
    def __init__(self, refresh_rate):
        super().__init__(f"Refresh rate must be 30 or higher. You have it set to {refresh_rate}.")


class InvalidServerType(InvalidConfigValue):
    def __init__(self, server_type):
        super().__init__(f"Server type must be either Java or Bedrock. You have it set to {server_type}.")


initial_extensions = [
    "cogs.status",
    "cogs.admin",
    "cogs.help",
]


def get_prefix(bot, message):
    prefixes = [bot.config["prefix"]]
    return commands.when_mentioned_or(*prefixes)(bot, message)


description = """
A simple Discord bot that displays the status and player count of a Minecraft server in the sidebar.
"""


class ServerStatus(commands.Bot):
    def __init__(self):
        # Intents are mandatory in 2.0+
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.reactions = True

        self.log = log
        self.init_ok = False
        self.restart_signal = None

        log.info("Starting bot...")
        log.info("Loading config file...")
        self.config = self.load_config("config.yml")

        # Config checks
        if self.config["server-type"].lower() not in ["java", "bedrock"]:
            raise InvalidServerType(self.config["server-type"])

        if self.config["refresh-rate"] < 30:
            raise InvalidRefreshRate(self.config["refresh-rate"])

        super().__init__(
            command_prefix=get_prefix,
            description=description,
            case_insensitive=True,
            activity=discord.Game("Starting up..."),
            help_command=commands.MinimalHelpCommand(),
            intents=intents,
        )

    def load_config(self, filename):
        with open(filename, "r") as f:
            return yaml.safe_load(f)

    async def setup_hook(self):
        log.info("Loading extensions...")
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
            except Exception as e:
                log.error(f"Failed to load extension {extension}: {e}")

        # Optional Jishaku support
        try:
            await self.load_extension("jishaku")
            jishaku_cmd = self.get_command("jishaku")
            if jishaku_cmd:
                jishaku_cmd.hidden = True
        except Exception:
            log.info("jishaku is not installed, continuing...")

        # We removed the pre-login status update here because the bot 
        # is not connected to the websocket yet. The Status cog will 
        # handle the first update automatically upon login.

    async def on_command(self, ctx):
        destination = None

        if ctx.guild is None:
            destination = "Private Message"
        else:
            destination = f"#{ctx.channel} ({ctx.guild})"

        log.info(f"{ctx.author} in {destination}: {ctx.message.content}")

    async def send_unexpected_error(self, ctx, error):
        em = discord.Embed(
            title=":warning: Unexpected Error",
            color=discord.Color.gold(),
        )

        description = (
            "An unexpected error has occured:"
            f"```py\n{error}```\n"
        )

        em.description = description
        await ctx.send(embed=em)

    async def on_command_error(self, ctx, error):
        red_tick = "\N{CROSS MARK}"

        if hasattr(ctx, "handled"):
            return

        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send(f"{red_tick} This command can't be used in DMs.")

        elif isinstance(error, commands.ArgumentParsingError):
            await ctx.send(f"{red_tick} {error}")

        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"{red_tick} You are on cooldown. Try again in {int(error.retry_after)} seconds.")

        elif isinstance(error, commands.BotMissingPermissions):
            perms = ""
            for perm in error.missing_permissions:
                formatted = str(perm).replace("_", " ").replace("guild", "server").capitalize()
                perms += f"\n- `{formatted}`"
            await ctx.send(f"{red_tick} I am missing some required permission(s):{perms}")

        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"{red_tick} {error}")

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"{red_tick} Missing a required argument: `{error.param.name}`")

        elif isinstance(error, commands.CommandInvokeError) and str(ctx.command) == "help":
            pass

        elif isinstance(error, commands.CommandInvokeError):
            original = error.original
            if not isinstance(original, discord.HTTPException):
                print(f"Ignoring exception in command {ctx.command}:", file=sys.stderr)
                traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
                await self.send_unexpected_error(ctx, error)

    async def on_ready(self):
        log.info(f"Logged in as {self.user.name} - {self.user.id}")
        self.init_ok = True

    def run(self):
        log.info("Logging into Discord...")
        # log_handler=None ensures we use the custom logging setup defined at the top
        super().run(self.config["bot-token"], log_handler=None)


if __name__ == "__main__":
    bot = ServerStatus()
    bot.run()
