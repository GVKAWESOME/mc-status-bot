import discord
from discord.ext import commands


class HelpCommand(commands.MinimalHelpCommand):
    """Modified MinimalHelpCommand that doesn't display categories"""

    def __init__(self, **kwargs):
        kwargs.setdefault("sort_commands", False)
        super().__init__(**kwargs)

    def get_opening_note(self):
        command_name = self.invoked_with
        if not command_name:
            command_name = "help"
        # FIX IS HERE: changed self.clean_prefix -> self.context.clean_prefix
        return "Use `{0}{1} [command]` for more info on a command.".format(self.context.clean_prefix, command_name)

    def add_bot_commands_formatting(self, commands):
        for command in commands:
            self.add_subcommand_formatting(command)

    def add_subcommand_formatting(self, command):
        # Safer check for short_doc
        short_doc = command.short_doc if command.short_doc else ""
        if short_doc:
            fmt = "`{0}{1}` \N{EN DASH} {2}"
            # FIX IS HERE
            self.paginator.add_line(fmt.format(self.context.clean_prefix, command.qualified_name, short_doc))
        else:
            fmt = "`{0}{1}`"
            # FIX IS HERE
            self.paginator.add_line(fmt.format(self.context.clean_prefix, command.qualified_name))

    def add_command_formatting(self, command):
        if command.description:
            self.paginator.add_line(command.description, empty=True)

        signature = self.get_command_signature(command)
        if command.aliases:
            self.paginator.add_line(f"`{signature.strip()}`")
            self.add_aliases_formatting(command.aliases)
        else:
            self.paginator.add_line(signature, empty=True)

        if command.help:
            try:
                self.paginator.add_line(command.help, empty=True)
            except RuntimeError:
                for line in command.help.splitlines():
                    self.paginator.add_line(line)
                self.paginator.add_line()

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        if bot.description:
            self.paginator.add_line(bot.description, empty=True)

        note = self.get_opening_note()
        if note:
            self.paginator.add_line(note, empty=True)

        self.paginator.add_line("**Commands**")

        all_commands = []
        for cog, cmds in mapping.items():
            all_commands.extend(cmds)

        filtered = await self.filter_commands(all_commands, sort=True)

        commands = sorted(filtered, key=lambda c: c.name) if self.sort_commands else list(filtered)
        self.add_bot_commands_formatting(commands)

        note = self.get_ending_note()
        if note:
            self.paginator.add_line()
            self.paginator.add_line(note)

        await self.send_pages()

    async def command_callback(self, ctx, *, command=None):
        """Removes cog help from the help command."""
        await self.prepare_help_command(ctx, command)
        bot = ctx.bot

        if command is None:
            mapping = self.get_bot_mapping()
            return await self.send_bot_help(mapping)

        keys = command.split(" ")
        cmd = bot.all_commands.get(keys[0])
        
        if cmd is None:
            string = self.command_not_found(self.remove_mentions(keys[0]))
            return await self.send_error_message(string)

        for key in keys[1:]:
            try:
                found = cmd.all_commands.get(key)
            except AttributeError:
                string = self.subcommand_not_found(cmd, self.remove_mentions(key))
                return await self.send_error_message(string)
            else:
                if found is None:
                    string = self.subcommand_not_found(cmd, self.remove_mentions(key))
                    return await self.send_error_message(string)
                cmd = found

        if isinstance(cmd, commands.Group):
            return await self.send_group_help(cmd)
        else:
            return await self.send_command_help(cmd)


async def setup(bot):
    bot._original_help_command = bot.help_command
    bot.help_command = HelpCommand()
