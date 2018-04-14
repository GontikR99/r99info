# spam.py: Manage server spam channel bindings, implement sending messages to spam channel on all servers.

import asyncio
import chat
import discord
import dbm
import os
import os.path

_servermap = dbm.open(os.path.join(os.environ["HOME"], "r99infospam.db"), "c")


async def init():
    asyncio.ensure_future(_sync_db())


async def _sync_db():
    global _servermap
    while True:
        _servermap.close()
        _servermap = dbm.open(os.path.join(os.environ["HOME"], "r99infospam.db"), "c")
        await asyncio.sleep(5)

_SPAM_CATEGORY = "Spam management"


@chat.command("!bind", _SPAM_CATEGORY)
async def bind(msg):
    """(admin) Have the bot place all of its messages in the channel the command was sent in"""
    if msg.author.server_permissions.administrator:
        _servermap[msg.server.id] = msg.channel.name
        chat.fade(await chat.send_info(msg.channel, "`bind`", "Sending spam to this channel"))
    else:
        chat.fade(await chat.send_error(msg.channel, "`bind`", "You are not a server administrator, "+msg.author.mention))


@chat.command("!unbind", _SPAM_CATEGORY)
async def unbind(msg):
    """(admin) Request that the bot not send any further spam to this server."""
    if msg.author.server_permissions.administrator:
        if msg.server.id in _servermap:
            del _servermap[msg.server.id]
        chat.fade(await chat.send_info(msg.channel, "`unbind`", "No longer sending bot spam to this server"))
    else:
        chat.fade(await chat.send_error(msg.channel, "`unbind`", "You are not a server administrator, "+msg.author.mention))


async def send(*args, **kwargs):
    """Send a message/embed/etc to all spam channels."""
    dead_ids = []
    for idbytes in _servermap.keys():
        server_id = str(idbytes, "utf8")
        channame = str(_servermap[server_id], "utf8")
        server = chat.get_server(server_id)
        if server is None:
            dead_ids.append(server_id)
            continue
        for channel in server.channels:
            if channel.name == channame:
                await chat.send_message(channel, *args, **kwargs)
                break
        else:
            dead_ids.append(server_id)
    for server_id in dead_ids:
        print("deleting "+server_id)
        del _servermap[server_id]
