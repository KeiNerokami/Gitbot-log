#!/usr/bin/env python3
"""
This file was cleaned up to ensure all names are defined, and to provide a robust
terminal CLI for live management: refresh, commandslist, delete, update, restart,
shutdown and basic 'listen/send/reply' helpers.

Keep this file minimal and robust — heavy logic lives in cogs.

- GPT5.2

"""

import os
import sys
import logging
import threading
import json
import asyncio
from collections import deque
from datetime import datetime, timezone

import nextcord
from nextcord.ext import commands
from dotenv import load_dotenv

# --- Setup ---
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("lunarbot")

# --- Message persistence files ---
message_count_path = "message_counts.json"
if not os.path.exists(message_count_path):
    with open(message_count_path, "w", encoding="utf-8") as f:
        json.dump({}, f)

alt_log_file = "alts_log.json"
msg_delete_log_file = "message_deletes.json"

# --- Intents & bot ---
intents = nextcord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.bans = True
intents.guild_messages = True
intents.invites = True
intents.guild_reactions = True

bot = commands.Bot(
    command_prefix=os.getenv("PREFIX", "!!"),
    intents=intents,
    help_command=None,  # disable default help command
)

# --- Globals referenced by CLI ---
listened_channel_id = None
mentions_log = deque(maxlen=100)
raid_enabled = True

ALLOWED_GUILDS = {
    983593136867643462,
    1241033908212990002,
    1396804437854388244,
    1442581624481910827,
    1433372795412287501,
}


def terminal_listener():
    """Interactive terminal command loop used while the bot is running.

    Runs in a separate thread. Commands are designed to be safe and schedule
    async work on the bot event loop when needed.
    """
    global listened_channel_id

    scheduled_shutdown = None

    def console_print(*args, **kwargs):
        prefix = getattr(getattr(bot, "user", None), "name", os.getenv("BOT_NAME", "Bot"))
        sep = kwargs.pop("sep", " ")
        end = kwargs.pop("end", "\n")
        message = sep.join(str(a) for a in args) if args else ""
        print(f"{prefix}> {message}", end=end)

    def parse_time(s: str) -> int | None:
        try:
            if s == "now":
                return 0
            if s.endswith("s"):
                return int(s[:-1])
            if s.endswith("m"):
                return int(s[:-1]) * 60
            if s.endswith("h"):
                return int(s[:-1]) * 3600
            return int(s)
        except Exception:
            return None

    while True:
        try:
            cmd_raw = input()
        except EOFError:
            break
        if cmd_raw is None:
            continue

        cmd = cmd_raw.strip()
        if not cmd:
            continue

        lcmd = cmd.lower()

        if lcmd == "refresh":
            console_print("Refreshing all cogs...")
            COGS_DIR = os.path.join(os.path.dirname(__file__), "cogs")
            for fn in os.listdir(COGS_DIR):
                if fn.endswith('.py') and not fn.startswith('_'):
                    cog_name = f'cogs.{fn[:-3]}'
                    try:
                        bot.reload_extension(cog_name)
                        console_print(f"Reloaded {cog_name}")
                        logger.info(f"Reloaded {cog_name} via terminal Refresh")
                    except Exception as e:
                        console_print(f"Failed to reload {cog_name}: {e}")
                        logger.error(f"Failed to reload {cog_name}: {e}")

        elif lcmd.startswith("listen "):
            parts = cmd.split()
            if len(parts) < 2:
                console_print("Usage: listen <start|stop|list> [channelid]")
                continue
            action = parts[1].lower()
            if action == "start":
                if len(parts) != 3:
                    console_print("Usage: listen start <channelid>")
                    continue
                try:
                    cid = int(parts[2])
                    listened_channel_id = cid
                    console_print(f"Listening to channel {cid}")
                except Exception as e:
                    console_print(f"Invalid channel id: {e}")
            elif action == "stop":
                if listened_channel_id is not None:
                    console_print(f"Stopped listening to channel {listened_channel_id}")
                    listened_channel_id = None
                else:
                    console_print("No channel is currently being listened to.")
            elif action == "list":
                if listened_channel_id is not None:
                    console_print(f"Currently listening to channel: {listened_channel_id}")
                else:
                    console_print("No channel is currently being listened to.")
            else:
                console_print("Unknown listen command. Use start, stop, or list.")

        elif lcmd.startswith("send "):
            message = cmd[5:].strip()
            if not message:
                console_print("Usage: send <message>")
                continue
            if listened_channel_id is None:
                console_print("No channel is currently being listened to. Use 'listen start <channelid>' first.")
                continue

            async def send_message():
                channel = bot.get_channel(listened_channel_id)
                if channel is None:
                    console_print(f"Channel {listened_channel_id} not found or bot has no access.")
                    return
                try:
                    await channel.send(message)
                    console_print(f"Sent message to {listened_channel_id}")
                except Exception as e:
                    console_print(f"Failed to send: {e}")

            if bot.is_closed():
                console_print("Cannot send message: bot is not running.")
            else:
                bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(send_message()))

        elif lcmd.startswith("reply "):
            parts = cmd.split(" ", 2)
            async def reply_core():
                if len(parts) < 3:
                    console_print("Usage:\n  reply <messageID> <message>\n  reply user <messageID> <message>\n  reply dms <userID> <message>")
                    return

                sub = parts[1]
                remainder = parts[2]

                # reply by fetching message author
                if sub == "user":
                    try:
                        message_id, reply_msg = remainder.strip().split(" ", 1)
                    except ValueError:
                        console_print("Usage: reply user <messageID> <message>")
                        return

                    found = None
                    for g in bot.guilds:
                        for ch in g.text_channels:
                            try:
                                msg = await ch.fetch_message(int(message_id))
                                found = msg
                                break
                            except Exception:
                                continue
                        if found:
                            break

                    if not found:
                        console_print("Message ID not found in accessible channels.")
                        return

                    user = found.author
                    try:
                        await user.send(reply_msg)
                        console_print(f"Sent message to user {user.id}")
                    except Exception as e:
                        console_print(f"Failed to send DM: {e}")

                elif sub == "dms":
                    try:
                        user_id_str, reply_msg = remainder.strip().split(" ", 1)
                        user_id = int(user_id_str)
                    except ValueError:
                        console_print("Usage: reply dms <userID> <message>")
                        return

                    try:
                        user = await bot.fetch_user(user_id)
                        await user.send(reply_msg)
                        console_print(f"Sent DM to user {user_id}")
                    except Exception as e:
                        console_print(f"Failed to send DM: {e}")

                else:
                    # default: reply to message by id
                    try:
                        message_id, reply_msg = cmd.split(" ", 2)[1:]
                    except ValueError:
                        console_print("Usage: reply <messageID> <message>")
                        return

                    found = None
                    for g in bot.guilds:
                        for ch in g.text_channels:
                            try:
                                msg = await ch.fetch_message(int(message_id))
                                found = msg
                                break
                            except Exception:
                                continue
                        if found:
                            break

                    if not found:
                        console_print("Message not found in accessible channels.")
                        return

                    try:
                        await found.reply(reply_msg)
                        console_print(f"Replied to message {message_id}")
                    except Exception as e:
                        console_print(f"Failed to reply: {e}")

            bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(reply_core()))

        elif lcmd == "antiraid on":
            raid_enabled = True
            console_print("Anti-raid ENABLED via terminal.")

        elif lcmd == "antiraid off":
            raid_enabled = False
            console_print("Anti-raid DISABLED via terminal.")

        elif lcmd == "mentions list":
            if not mentions_log:
                console_print("No mentions recorded.")
            else:
                for entry in mentions_log:
                    console_print(f"{entry['channel_id']}: {entry['message_id']} \"{entry['content']}\" {entry['user_id']}")

        elif lcmd == "commandslist":
            console_print("Prefix commands:")
            for c in sorted(bot.commands, key=lambda x: x.name):
                console_print(f" - {c.name}: {c.help or 'no help'}")

            console_print("Application (slash) commands:")
            try:
                app_cmds = getattr(bot, "application_commands", [])
                for app in sorted(app_cmds, key=lambda a: getattr(a, 'name', str(a))):
                    name = getattr(app, "name", None) or getattr(app, "qualified_name", str(app))
                    is_global = getattr(app, "is_global", False)
                    console_print(f" - {name} (global: {is_global})")
            except Exception as e:
                console_print(f"Failed to list application commands: {e}")

        elif lcmd.startswith("delete "):
            target = cmd[len("delete "):].strip()
            if not target:
                console_print("Usage: delete <command_name>")
                continue

            async def delete_core():
                removed_any = False
                if bot.get_command(target):
                    try:
                        bot.remove_command(target)
                        removed_any = True
                        console_print(f"Removed prefix command: {target}")
                    except Exception as e:
                        console_print(f"Failed to remove prefix command {target}: {e}")

                try:
                    app_cmds = getattr(bot, "application_commands", [])
                    to_remove = [app for app in app_cmds if getattr(app, 'name', None) == target]
                    if to_remove:
                        for app in to_remove:
                            try:
                                bot._connection.remove_application_command(app)
                                removed_any = True
                                console_print(f"Queued removal of application command: {target}")
                            except Exception as e:
                                console_print(f"Failed to queue removal of application command {target}: {e}")

                        try:
                            await bot.sync_application_commands()
                            console_print(f"Synchronized application command deletions for: {target}")
                        except Exception as e:
                            console_print(f"Failed to sync application commands after deletion: {e}")
                except Exception as e:
                    console_print(f"Error while checking application commands: {e}")

                if not removed_any:
                    console_print(f"No command named '{target}' was found as a prefix or application command.")

            bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(delete_core()))

        elif lcmd.startswith("update "):
            target = cmd[len("update "):].strip()
            if not target:
                console_print("Usage: update <command_name>")
                continue

            async def update_core():
                deleted = False
                if bot.get_command(target):
                    try:
                        bot.remove_command(target)
                        deleted = True
                        console_print(f"Removed prefix command: {target}")
                    except Exception as e:
                        console_print(f"Failed to remove prefix command {target}: {e}")

                try:
                    app_cmds = getattr(bot, "application_commands", [])
                    to_remove = [app for app in app_cmds if getattr(app, 'name', None) == target]
                    if to_remove:
                        for app in to_remove:
                            try:
                                bot._connection.remove_application_command(app)
                                deleted = True
                                console_print(f"Queued removal of application command: {target}")
                            except Exception as e:
                                console_print(f"Failed to queue removal of application command {target}: {e}")

                        try:
                            await bot.sync_application_commands()
                            console_print(f"Synchronized deletions of {target} to Discord")
                        except Exception as e:
                            console_print(f"Failed to sync application commands after deletion: {e}")
                except Exception as e:
                    console_print(f"Error while checking application commands: {e}")

                console_print("Reloading all cogs to pick up any new/changed command implementations...")
                COGS_DIR = os.path.join(os.path.dirname(__file__), "cogs")
                for fn in os.listdir(COGS_DIR):
                    if fn.endswith('.py') and not fn.startswith('_'):
                        cog_name = f'cogs.{fn[:-3]}'
                        try:
                            bot.reload_extension(cog_name)
                            console_print(f"Reloaded {cog_name}")
                        except Exception as e:
                            console_print(f"Failed to reload {cog_name}: {e}")

                try:
                    await bot.sync_application_commands()
                    console_print(f"Synchronized application commands (update completed for: {target})")
                except Exception as e:
                    console_print(f"Failed to sync application commands after reload: {e}")

            bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(update_core()))

        elif lcmd == "restart":
            console_print("Restarting bot...")

            async def restart_core():
                try:
                    await bot.close()
                except Exception as e:
                    console_print(f"Error during bot.close(): {e}")
                try:
                    python = sys.executable
                    os.execv(python, [python] + sys.argv)
                except Exception as e:
                    console_print(f"Failed to exec new process: {e}")

            bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(restart_core()))

        elif lcmd.startswith("shutdown"):
            parts = cmd.split()
            if len(parts) == 1:
                console_print("Usage: shutdown <time>|now|cancel  (e.g. shutdown 30s or shutdown 5m)")
                continue

            sub = parts[1].lower()
            if sub == "cancel":
                if scheduled_shutdown is not None and not scheduled_shutdown.done():
                    scheduled_shutdown.cancel()
                    scheduled_shutdown = None
                    console_print("Scheduled shutdown cancelled.")
                else:
                    console_print("No scheduled shutdown to cancel.")
                continue

            seconds = parse_time(sub)
            if seconds is None:
                console_print("Invalid time format for shutdown. Use e.g. 30s, 5m, 1h, now, or cancel")
                continue

            async def shutdown_core(delay: int):
                if delay > 0:
                    console_print(f"Shutdown scheduled in {delay} seconds. Use 'shutdown cancel' to abort.")
                    try:
                        await asyncio.sleep(delay)
                    except asyncio.CancelledError:
                        console_print("Shutdown task was cancelled.")
                        return
                console_print("Shutting down now...")
                try:
                    await bot.close()
                except Exception as e:
                    console_print(f"Error while closing bot: {e}")
                try:
                    os._exit(0)
                except Exception:
                    pass

            if sub == "now":
                bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(shutdown_core(0)))
            else:
                scheduled_shutdown = bot.loop.create_task(shutdown_core(seconds))

        else:
            console_print("Unknown command. Available: refresh, restart, shutdown, listen, send, delete, update, commandslist, antiraid on/off, mentions list")


# --- Cog Loader ---
COGS_DIR = os.path.join(os.path.dirname(__file__), "cogs")
for fn in os.listdir(COGS_DIR):
    if fn.endswith('.py') and not fn.startswith('_'):
        try:
            bot.load_extension(f'cogs.{fn[:-3]}')
            logger.info(f"Loaded cog: {fn}")
        except Exception as e:
            logger.error(f"Failed to load cog {fn}: {e}")


# --- Optional: Reload command for owner only ---
@bot.command(hidden=True)
#@commands.is_owner()
async def reload(ctx, cog: str):
    allowed_ids = 972357305226125322
    """Reload a cog. Usage: !reload embed"""
    if ctx.author.id != allowed_ids:
        return
    try:
        bot.reload_extension(f'cogs.{cog}')
        await ctx.send(f"Reloaded cogs.{cog}")
        logger.info(f"Reloaded cog: {cog}")
    except Exception as e:
        await ctx.send(f"Failed to reload: {e}")
        logger.error(f"Failed to reload cog {cog}: {e}")


# --- Bot events ---
@bot.event
async def on_ready():
    logger.info(f"Bot is running as {bot.user} (ID: {bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guild(s).")
    try:
        await bot.sync_application_commands()
        logger.info("Application commands synced successfully")
    except Exception as e:
        logger.error(f"Failed to sync application commands: {e}")

    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")


@bot.event
async def on_disconnect():
    logger.warning("Bot disconnected from Discord.")


@bot.event
async def on_resumed():
    logger.info("Bot resumed session.")


# --- Run Bot ---
token = os.getenv('Token')
if not token:
    logger.critical("No bot token found in environment variable 'Token'. Exiting.")
    exit(1)


if __name__ == '__main__':
    threading.Thread(target=terminal_listener, daemon=True).start()
    bot.run(token)
#import dependencies

#dependencies.setup(update=False)

import nextcord
from nextcord.ext import commands
import os


import nextcord
from nextcord.ext import commands
import os
import logging
from dotenv import load_dotenv
import threading
from collections import deque
import json
import asyncio
import time
from datetime import datetime, timezone

# --- Message Count File Initialization ---
message_count_path = "message_counts.json"
if not os.path.exists(message_count_path):
    with open(message_count_path, "w") as f:
        json.dump({}, f)

# Alt log file and message delete log file
alt_log_file = "alts_log.json"
msg_delete_log_file = "message_deletes.json"

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("lunarbot")

def terminal_listener():
    global listened_channel_id
    scheduled_shutdown = None

    def console_print(*args, **kwargs):
        prefix = getattr(getattr(bot, "user", None), "name", os.getenv("BOT_NAME", "Bot"))
        sep = kwargs.pop("sep", " ")
        end = kwargs.pop("end", "\n")
        message = sep.join(str(a) for a in args) if args else ""
        print(f"{prefix}> {message}", end=end)

    def parse_time(s: str) -> int | None:
        try:
            if s == "now":
                return 0
            if s.endswith("s"):
                return int(s[:-1])
            if s.endswith("m"):
                return int(s[:-1]) * 60
            if s.endswith("h"):
                return int(s[:-1]) * 3600
            return int(s)
        except Exception:
            return None

    while True:
        try:
            cmd = input().strip()
        except EOFError:
            # input closed — exit thread
            break

        if not cmd:
            continue

        lcmd = cmd.lower()

        if lcmd == "refresh":
            console_print("Refreshing all cogs...")
            COGS_DIR = os.path.join(os.path.dirname(__file__), "cogs")
            for fn in os.listdir(COGS_DIR):
                if fn.endswith('.py') and not fn.startswith('_'):
                    cog_name = f'cogs.{fn[:-3]}'
                    try:
                        bot.reload_extension(cog_name)
                        console_print(f"Reloaded {cog_name}")
                        logger.info(f"Reloaded {cog_name} via terminal Refresh")
                    except Exception as e:
                        console_print(f"Failed to reload {cog_name}: {e}")
                        logger.error(f"Failed to reload {cog_name}: {e}")

        elif lcmd.startswith("listen "):
            parts = cmd.split()
            if len(parts) < 2:
                console_print("Usage: listen <start|stop|list> [channelid]")
                continue
            action = parts[1].lower()
            if action == "start":
                if len(parts) != 3:
                    console_print("Usage: listen start <channelid>")
                    continue
                try:
                    channel_id = int(parts[2])
                    listened_channel_id = channel_id
                    console_print(f"Listening to channel {channel_id}")
                    logger.info(f"Listening to channel {channel_id}")
                except Exception as e:
                    console_print(f"Invalid channel ID: {e}")
            elif action == "stop":
                if listened_channel_id is not None:
                    console_print(f"Stopped listening to channel {listened_channel_id}")
                    logger.info(f"Stopped listening to channel {listened_channel_id}")
                    listened_channel_id = None
                else:
                    console_print("No channel is currently being listened to.")
            elif action == "list":
                if listened_channel_id is not None:
                    console_print(f"Currently listening to channel: {listened_channel_id}")
                else:
                    console_print("No channel is currently being listened to.")
            else:
                console_print("Unknown listen command. Use start, stop, or list.")

        elif lcmd.startswith("send "):
            message = cmd[5:].strip()
            if not message:
                console_print("Usage: send <message>")
                continue
            if listened_channel_id is None:
                console_print("No channel is currently being listened to. Use 'listen start <channelid>' first.")
                continue

            async def send_message():
                channel = bot.get_channel(listened_channel_id)
                if channel is None:
                    logger.error(f"Channel ID {listened_channel_id} not found or bot has no access.")
                    console_print(f"Channel ID {listened_channel_id} not found or bot has no access.")
                    return
                try:
                    await channel.send(message)
                    logger.info(f"Sent message to channel {listened_channel_id} via terminal command.")
                    console_print(f"Sent message to {listened_channel_id}")
                except Exception as e:
                    logger.error(f"Failed to send message to {listened_channel_id}: {e}")
                    console_print(f"Failed to send message: {e}")

            if bot.is_closed():
                logger.error("Cannot send message: bot is not running.")
                console_print("Cannot send message: bot is not running.")
            else:
                bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(send_message()))

        elif lcmd.startswith("reply "):
            parts = cmd.split(" ", 2)

            async def reply_core():
                if len(parts) < 3:
                    console_print("Usage:")
                    console_print("  reply <messageID> <message>")
                    console_print("  reply user <messageID> <message>")
                    console_print("  reply dms <userID> <message>")
                    return

                subcommand = parts[1]
                remainder = parts[2]

                if subcommand == "user":
                    try:
                        message_id, reply_msg = remainder.strip().split(" ", 1)
                    except ValueError:
                        console_print("Usage: reply user <messageID> <message>")
                        return

                    # Fetch message directly without relying on mentions_log
                    user_id = None
                    for guild in bot.guilds:
                        for channel in guild.text_channels:
                            try:
                                msg = await channel.fetch_message(int(message_id))
                                user_id = msg.author.id
                                raise StopIteration
                            except Exception:
                                continue
                    if user_id is None:
                        console_print("Message ID not found in accessible channels.")
                        return

                    user = None
                    for guild in bot.guilds:
                        user = guild.get_member(user_id)
                        if user:
                            break
                    if not user:
                        try:
                            user = await bot.fetch_user(user_id)
                        except Exception as e:
                            console_print(f"Failed to fetch user: {e}")
                            return

                    try:
                        await user.send(reply_msg)
                        console_print(f"Sent message to user {user_id}")
                    except Exception as e:
                        console_print(f"Failed to send DM: {e}")

                elif subcommand == "dms":
                    try:
                        user_id_str, reply_msg = remainder.strip().split(" ", 1)
                        user_id = int(user_id_str)
                    except ValueError:
                        console_print("Usage: reply dms <userID> <message>")
                        return

                    user = None
                    for guild in bot.guilds:
                        user = guild.get_member(user_id)
                        if user:
                            break
                    if not user:
                        try:
                            user = await bot.fetch_user(user_id)
                        except Exception as e:
                            console_print(f"Failed to fetch user: {e}")
                            return

                    try:
                        await user.send(reply_msg)
                        console_print(f"Sent DM to user {user_id}")
                    except Exception as e:
                        console_print(f"Failed to send DM: {e}")

                else:
                    # Default: reply to message by directly fetching it
                    try:
                        message_id, reply_msg = cmd.split(" ", 2)[1:]
                    except ValueError:
                        console_print("Usage: reply <messageID> <message>")
                        return

                    for guild in bot.guilds:
                        for channel in guild.text_channels:
                            try:
                                msg = await channel.fetch_message(int(message_id))
                                await msg.reply(reply_msg)
                                console_print(f"Replied to message {message_id}")
                                return
                            except Exception:
                                continue

                    console_print("Message not found in accessible channels.")

            bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(reply_core()))

        elif lcmd == "antiraid on":
            global raid_enabled
            raid_enabled = True
            console_print("Anti-raid ENABLED via terminal.")
            logger.info("Anti-raid ENABLED via terminal.")

        elif lcmd == "antiraid off":
            raid_enabled = False
            console_print("Anti-raid DISABLED via terminal.")
            logger.info("Anti-raid DISABLED via terminal.")

        elif lcmd == "mentions list":
            if not mentions_log:
                console_print("No mentions recorded.")
            else:
                for entry in mentions_log:
                    console_print(f"{entry['channel_id']}: {entry['message_id']} \"{entry['content']}\" \"{entry['user_id']}\"")

        elif lcmd == "commandslist":
            console_print("Prefix commands:")
            for c in sorted(bot.commands, key=lambda x: x.name):
                console_print(f" - {c.name}: {c.help or 'no help'}")

            console_print("\nApplication (slash) commands:")
            try:
                app_cmds = getattr(bot, "application_commands", [])
                for app in sorted(app_cmds, key=lambda a: getattr(a, 'name', str(a))):
                    name = getattr(app, "name", None) or getattr(app, "qualified_name", str(app))
                    is_global = getattr(app, "is_global", False)
                    console_print(f" - {name} (global: {is_global})")
            except Exception as e:
                console_print(f"Failed to list application commands: {e}")

        elif lcmd.startswith("delete "):
            target = cmd[len("delete "):].strip()
            if not target:
                console_print("Usage: delete <command_name>")
                continue

            async def delete_core():
                removed_any = False

                if bot.get_command(target):
                    try:
                        bot.remove_command(target)
                        removed_any = True
                        console_print(f"Removed prefix command: {target}")
                        logger.info(f"Removed prefix command: {target} via terminal")
                    except Exception as e:
                        console_print(f"Failed to remove prefix command {target}: {e}")

                try:
                    app_cmds = getattr(bot, "application_commands", [])
                    to_remove = [app for app in app_cmds if getattr(app, 'name', None) == target]
                    if to_remove:
                        for app in to_remove:
                            try:
                                bot._connection.remove_application_command(app)
                                removed_any = True
                                console_print(f"Queued removal of application command: {target}")
                                logger.info(f"Queued removal of application command: {target} via terminal")
                            except Exception as e:
                                console_print(f"Failed to queue removal of application command {target}: {e}")

                        try:
                            await bot.sync_application_commands()
                            console_print(f"Synchronized application command deletions for: {target}")
                        except Exception as e:
                            console_print(f"Failed to sync application commands after deletion: {e}")
                except Exception as e:
                    console_print(f"Error while checking application commands: {e}")

                if not removed_any:
                    console_print(f"No command named '{target}' was found as a prefix or application command.")

            bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(delete_core()))

        elif lcmd.startswith("update "):
            target = cmd[len("update "):].strip()
            if not target:
                console_print("Usage: update <command_name>")
                continue

            async def update_core():
                deleted = False
                if bot.get_command(target):
                    try:
                        bot.remove_command(target)
                        deleted = True
                        console_print(f"Removed prefix command: {target}")
                    except Exception as e:
                        console_print(f"Failed to remove prefix command {target}: {e}")

                try:
                    app_cmds = getattr(bot, "application_commands", [])
                    to_remove = [app for app in app_cmds if getattr(app, 'name', None) == target]
                    if to_remove:
                        for app in to_remove:
                            try:
                                bot._connection.remove_application_command(app)
                                deleted = True
                                console_print(f"Queued removal of application command: {target}")
                            except Exception as e:
                                console_print(f"Failed to queue removal of application command {target}: {e}")

                        try:
                            await bot.sync_application_commands()
                            console_print(f"Synchronized deletions of {target} to Discord")
                        except Exception as e:
                            console_print(f"Failed to sync application commands after deletion: {e}")
                except Exception as e:
                    console_print(f"Error while checking application commands: {e}")

                console_print("Reloading all cogs to pick up any new/changed command implementations...")
                COGS_DIR = os.path.join(os.path.dirname(__file__), "cogs")
                for fn in os.listdir(COGS_DIR):
                    if fn.endswith('.py') and not fn.startswith('_'):
                        cog_name = f'cogs.{fn[:-3]}'
                        try:
                            bot.reload_extension(cog_name)
                            console_print(f"Reloaded {cog_name}")
                        except Exception as e:
                            console_print(f"Failed to reload {cog_name}: {e}")

                try:
                    await bot.sync_application_commands()
                    console_print(f"Synchronized application commands (update completed for: {target})")
                except Exception as e:
                    console_print(f"Failed to sync application commands after reload: {e}")

            bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(update_core()))

        elif lcmd == "restart":
            console_print("Restarting bot...")

            async def restart_core():
                try:
                    await bot.close()
                except Exception as e:
                    console_print(f"Error during bot.close(): {e}")
                try:
                    python = sys.executable
                    os.execv(python, [python] + sys.argv)
                except Exception as e:
                    console_print(f"Failed to exec new process: {e}")

            bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(restart_core()))

        elif lcmd.startswith("shutdown"):
            parts = cmd.split()
            if len(parts) == 1:
                console_print("Usage: shutdown <time>|now|cancel  (e.g. shutdown 30s or shutdown 5m)")
                continue

            sub = parts[1].lower()
            if sub == "cancel":
                if scheduled_shutdown is not None and not scheduled_shutdown.done():
                    scheduled_shutdown.cancel()
                    scheduled_shutdown = None
                    console_print("Scheduled shutdown cancelled.")
                else:
                    console_print("No scheduled shutdown to cancel.")
                continue

            seconds = parse_time(sub)
            if seconds is None:
                console_print("Invalid time format for shutdown. Use e.g. 30s, 5m, 1h, now, or cancel")
                continue

            async def shutdown_core(delay: int):
                if delay > 0:
                    console_print(f"Shutdown scheduled in {delay} seconds. Use 'shutdown cancel' to abort.")
                    try:
                        await asyncio.sleep(delay)
                    except asyncio.CancelledError:
                        console_print("Shutdown task was cancelled.")
                        return
                console_print("Shutting down now...")
                try:
                    await bot.close()
                except Exception as e:
                    console_print(f"Error while closing bot: {e}")
                try:
                    os._exit(0)
                except Exception:
                    pass

            if sub == "now":
                bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(shutdown_core(0)))
            else:
                scheduled_shutdown = bot.loop.create_task(shutdown_core(seconds))

        else:
            console_print("Unknown command. Available: refresh, restart, shutdown, listen, send, delete, update, commandslist, antiraid on/off, mentions list")

# --- Cog Loader ---
COGS_DIR = os.path.join(os.path.dirname(__file__), "cogs")
for fn in os.listdir(COGS_DIR):
    if fn.endswith('.py') and not fn.startswith('_'):
        try:
            bot.load_extension(f'cogs.{fn[:-3]}')
            logger.info(f"Loaded cog: {fn}")
        except Exception as e:
            logger.error(f"Failed to load cog {fn}: {e}")

# --- Optional: Reload command for owner only ---
@bot.command(hidden=True)
#@commands.is_owner()
async def reload(ctx, cog: str):
    allowed_ids = 972357305226125322
    """Reload a cog. Usage: !reload embed"""
    if ctx.author.id != allowed_ids:
        return
    try:
        bot.reload_extension(f'cogs.{cog}')
        await ctx.send(f"Reloaded cogs.{cog}")
        logger.info(f"Reloaded cog: {cog}")
    except Exception as e:
        await ctx.send(f"Failed to reload: {e}")
        logger.error(f"Failed to reload cog {cog}: {e}")

# --- Bot events ---+

@bot.event
async def on_ready():
    logger.info(f"Bot is running as {bot.user} (ID: {bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guild(s).")
    # Sync all application (slash) commands with Discord
    try:
        await bot.sync_application_commands()
        logger.info("Application commands synced successfully")
    except Exception as e:
        logger.error(f"Failed to sync application commands: {e}")

    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")


@bot.event
async def on_disconnect():
    logger.warning("Bot disconnected from Discord.")

@bot.event
async def on_resumed():
    logger.info("Bot resumed session.")

# --- Run Bot ---
token = os.getenv('Token')
if not token:
    logger.critical("No bot token found in environment variable 'Token'. Exiting.")
    exit(1)


if __name__ == '__main__':
    threading.Thread(target=terminal_listener, daemon=True).start()
    bot.run(token)
