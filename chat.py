# chat.py: Discord interfacing.

import asyncio
import discord
import platform
import logging
import contextlib
import misc
import os


lock = asyncio.Lock()
_client = None
_logger = logging.getLogger("chat")
_chatqueue = asyncio.Queue()


class ChatTap(object):
    """A context object which holds a queue of messages from the Discord chat."""
    _INSTANCE_COUNTER = 0
    _ACTIVE = set()

    def __init__(self):
        self._id = ChatTap._INSTANCE_COUNTER
        ChatTap._INSTANCE_COUNTER += 1
        self._queue = asyncio.Queue()
        ChatTap._ACTIVE.add(self)

    def __hash__(self):
        return self._id

    def __eq__(self, other):
        return isinstance(other, ChatTap) and self._id == other._id

    async def post_message(self, line: discord.Message):
        await self._queue.put(line)

    async def next_message(self) -> discord.Message:
        return await self._queue.get()

    def close(self):
        ChatTap._ACTIVE.remove(self)


@contextlib.contextmanager
def tap() -> ChatTap:
    """Return a ChatTap object which can be used to receive Discord lines."""
    ct = ChatTap()
    try:
        yield ct
    finally:
        ct.close()


_LAST_EXCEPTION = None


async def delete_message(*args, **kwargs):
    """Get exclusive control of Discord, and delete the specified message."""
    global _LAST_EXCEPTION
    with await lock:
        try:
            return await _client.delete_message(*args, **kwargs)
        except discord.DiscordException as e:
            _logger.error(str(e))
        except Exception as e:
            _logger.error(str(e))
            _LAST_EXCEPTION = e


async def send_message(where, *args, **kwargs) -> discord.Message:
    """Get exclusive control of Discord, and send a message."""
    with await lock:
        return await _send_message_body(where, *args, **kwargs)


@misc.timeout(8)
async def _send_message_body(where, *args, **kwargs):
    global _LAST_EXCEPTION
    try:
        with tap() as ct:
            await _client.send_message(where, *args, **kwargs)
            while True:
                msg = await ct.next_message()
                if msg.author == _client.user:
                    return msg

    except discord.DiscordException as e:
        _logger.error(str(e))
    except Exception as e:
        _logger.error(str(e))
        _LAST_EXCEPTION = e


async def send_info(where, title, text):
    """Send an informational message as a Discord embed.  Useful for successful command responses."""
    e = discord.Embed()
    e.color = 0x007f00
    e.title = title
    e.description = text
    return await send_message(where, embed=e)


async def send_warning(where, title, text):
    """Send a warning message as a Discord embed.  Useful for command responses."""
    e = discord.Embed()
    e.color = 0x7f7f00
    e.title = title
    e.description = text
    return await send_message(where, embed=e)


async def send_error(where, title, text):
    """Sent an error message as a Discord embed.  Useful for command responses."""
    e = discord.Embed()
    e.color = 0x7f0000
    e.title = title
    e.description = text
    return await send_message(where, embed=e)


def fade(msg, duration=2*60):
    """Make a message go away after a while"""
    asyncio.ensure_future(_fade_body(msg, duration))


async def _fade_body(msg, duration):
    await asyncio.sleep(duration)
    await delete_message(msg)


def get_server(id) -> discord.Server:
    """Given a server id, get a Server object that we're connected to, or None"""
    for server in _client.servers:
        if server.id == id:
            return server
    return None


def quote(text):
    """Quote Discord's MarkDown special characters"""
    return text \
        .replace("\\", "\\\\") \
        .replace("*", "\\*") \
        .replace("`", "\\`") \
        .replace("[", "\\[") \
        .replace("_", "\\_") \
        .replace("~", "\\~") \
        .replace(":", "\\:") \
        .replace("<", "\\<")


async def init(token):
    global _client
    if _client is not None:
        return
    _client = discord.Client()

    @_client.event
    async def on_message(msg):
        _logger.info("<%s:%s> %s: %s" % (msg.server, msg.channel, msg.author, msg.content))
        await _chatqueue.put(msg)

    asyncio.ensure_future(_watch_chat())
    asyncio.ensure_future(_cmd_dispatch())
    asyncio.ensure_future(_discord_start_loop(token))
    await _client.wait_until_ready()

    _logger.info('Logged in as ' + _client.user.name + ' (ID:' + _client.user.id + ') | Connected to ' + str(len(_client.servers)) + ' servers | Connected to ' + str(len(set(_client.get_all_members()))) + ' users')
    _logger.info('--------')
    _logger.info('Current Discord.py Version: {} | Current Python Version: {}'.format(discord.__version__, platform.python_version()))
    _logger.info('--------')
    _logger.info('Use this link to invite {}:'.format(_client.user.name))
    _logger.info('https://discordapp.com/oauth2/authorize?client_id={}&scope=bot&permissions=8'.format(_client.user.id))
    _logger.info('--------')


async def _discord_start_loop(token):
    """Reconnect to Discord as needed."""
    global _LAST_EXCEPTION
    while True:
        try:
            started = asyncio.ensure_future(_client.start(token))
            await _client.wait_until_ready()
            await _client.change_presence(game=discord.Game(name="| !help"))
            await asyncio.wait([started])
            _logger.error("Lost Discord connection, dieing now")
            os._exit(1)
            _LAST_EXCEPTION = None
            while _LAST_EXCEPTION is None:
                await asyncio.sleep(1)
            _logger.error(str(_LAST_EXCEPTION))
        except Exception as e:
            _logger.error(str(e))
            pass

        try:
            await _client.logout()
        except Exception as e:
            _logger.error(str(e))


async def _watch_chat():
    """Dispatch all Discord chat messages to all active ChatTaps."""
    while True:
        msg = await _chatqueue.get()
        active = [instance for instance in ChatTap._ACTIVE]
        for instance in active:
            await instance.post_message(msg)


_CMDS = []


def command(name, category):
    """Decorator for a new command."""
    def rewrite(fn):
        async def wrapper(*args, **kwargs):
            return await fn(*args, **kwargs)
        _CMDS.append((name, (fn, wrapper, category)))
        return fn
    return rewrite


def _get_cmd(name):
    matches = [tp for tp in _CMDS if tp[0].lower() == name.lower()]
    if matches:
        return matches[0][1]
    else:
        return None


async def _cmd_dispatch():
    """Dispatch loop for commands"""
    with tap() as ct:
        while True:
            msg = await ct.next_message()
            parts = msg.content.strip().split()
            if len(parts) >= 1 and _get_cmd(parts[0]):
                fade(msg)
                if msg.server is None:
                    await send_error(msg.channel, "Error", "For security purposes, I don't accept direct messages.")
                else:
                    asyncio.ensure_future(_get_cmd(parts[0])[1](msg))


_CHAT_CATEGORY = "Basic commands"


@command("!help", _CHAT_CATEGORY)
async def _help_cmd(msg):
    """Show this help"""
    categories = list(set([tp[1][2] for tp in _CMDS]))
    categories.sort()
    e = discord.Embed()
    e.title = "R99Watch command list"
    e.color = 0x007f00
    for category in categories:
        cmdtext = "\n".join(["**\\[`%s`\\]** %s" %
                             (tp[0].lower(), quote(tp[1][0].__doc__)) for tp in _CMDS if tp[1][2] == category])
        e.add_field(name=category, value=cmdtext, inline=False)
    fade(await send_message(msg.channel, embed=e))


@command("!ping", _CHAT_CATEGORY)
async def _ping_cmd(msg):
    """Ask the bot to send you a message, to make sure it's still there."""
    await send_info(msg.author, "`ping`", "pong!")
