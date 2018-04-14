# friends.py: Manage friends list, repeatedly list friends, report on changes.

import asyncio
import chat
import eqcmd
import re
import misc
import dbm
import discord
import os
import os.path
import pickle
import logging
import spam
import who
import time
import datetime
import shelve

_LOG = logging.getLogger("friends")
_WATCHES = dbm.open(os.path.join(os.environ["HOME"], "r99infowatches.db"), "c")
_ONLINE_STATES = shelve.open(os.path.join(os.environ["HOME"], "r99infoonline.db"), "c", 2)
_SYNCED = False

_WATCH_MAX = 100

_NAME_RE = re.compile("[a-zA-Z]+")


@chat.command("!watch", who.CHAR_CATEGORY)
async def _watch_cmd(msg):
    """Request notification when a player is online/offline."""
    global _SYNCED
    parts = msg.content.strip().split()
    if len(parts) != 2:
        chat.fade(await chat.send_error(msg.channel, "`watch`", "Usage: `!watch <name>`"))
        return
    name = parts[1]
    if len(name) < 3 or len(name) > 45 or not _NAME_RE.match(name):
        chat.fade(await chat.send_error(msg.channel, "`watch`", chat.quote("%r is not a valid name" % name)))
        return

    name = name.lower()
    if name in _WATCHES:
        watchers = pickle.loads(_WATCHES[name])
    else:
        if len([k for k in _WATCHES.keys()]) >= _WATCH_MAX:
            chat.fade(await chat.send_error(msg.channel, "`watch`",
                                            "%s, too many watches.  Get rid of some (try !listwatch)" %
                                            msg.author.mention))
            return
        watchers = set([])
        _SYNCED = False

    if msg.author in watchers:
        chat.fade(await chat.send_error(msg.channel, "`watch`",
                                        "%s, You're already watching `%s`" % (msg.author.mention, name)))
        return

    watchers.add(msg.author)
    _WATCHES[name] = pickle.dumps(watchers)
    chat.fade(await chat.send_info(msg.channel, "`watch`", "%s, watch added for `%s`" % (msg.author.mention, name)))


@chat.command("!unwatch", who.CHAR_CATEGORY)
async def _unwatch_cmd(msg):
    """Stop watching a player."""
    global _SYNCED
    parts = msg.content.strip().split()
    if len(parts) != 2:
        chat.fade(await chat.send_error(msg.channel, "`unwatch`", "Usage: `!unwatch <name>`"))
        return
    name = parts[1]
    if len(name) < 3 or len(name) > 45 or not _NAME_RE.match(name):
        chat.fade(await chat.send_error(msg.channel, "`unwatch`", chat.quote("%r is not a valid name" % name)))
        return

    name = name.lower()
    if name in _WATCHES:
        watchers = pickle.loads(_WATCHES[name])
    else:
        watchers = set([])

    if msg.author not in watchers:
        chat.fade(await chat.send_error(msg.channel,
                                        "`unwatch`", "%s, You're not watching `%s`" % (msg.author.mention, name)))
        return

    watchers.remove(msg.author)
    if len(watchers) != 0:
        _WATCHES[name] = pickle.dumps(watchers)
    else:
        del _WATCHES[name]
        _SYNCED = False
    chat.fade(await chat.send_info(msg.channel, "`unwatch`", "%s, watch removed for `%s`" % (msg.author.mention, name)))


@chat.command("!unfriend", who.CHAR_CATEGORY)
async def _unfriend_cmd(msg):
    """(admin) Remove a particular player from everyone's watch."""
    global _SYNCED

    if not msg.author.server_permissions.administrator:
        chat.fade(await chat.send_error(msg.channel, "`unfriend`", "You are not a server admin!"))
        return

    parts = msg.content.strip().split()
    if len(parts) != 2:
        chat.fade(await chat.send_error(msg.channel, "`unwatch", "Usage: `!unwatch <name>`"))
        return
    name = parts[1]
    if not _NAME_RE.match(name):
        chat.fade(await chat.send_error(msg.channel, "`unwatch`", chat.quote("%r is not a valid name" % name)))
        return

    name = name.lower()
    if name in _WATCHES:
        _SYNCED = False
        del _WATCHES[name]
        chat.fade(await chat.send_info(msg.channel,
                                       "`unwatch`", "%s, all watches removed for `%s`" % (msg.author.mention, name)))
    else:
        chat.fade(await chat.send_error(msg.channel, "`unwatch`", "%s, Nobody's watching `%s`" % (msg.author.mention, name)))


@chat.command("!listwatch", who.CHAR_CATEGORY)
async def _list_watch_cmd(msg):
    """List all players currently being watched"""
    names = [str(k, "utf8") for k in _WATCHES.keys()]
    names.sort()
    watch_text = []
    for name in names:
        watchers = pickle.loads(_WATCHES[name])
        watchers = ["%s#%s" % (user.name, user.discriminator) for user in watchers]
        watchers.sort()
        watch_text.append("`%s` by %s" % (name, ", ".join(watchers)))
    watch_text.append("")
    watch_text.append("*%d characters watched (%d max)*" % (len(names), _WATCH_MAX))
    for i in range(0, len(watch_text), 20):
        ul = min(len(watch_text), i+20)
        chat.fade(await chat.send_info(msg.channel, "Current watches", "\n".join(watch_text[i:ul])))


async def init():
    """Initialize the friends module."""
    asyncio.ensure_future(_friends_loop())
    asyncio.ensure_future(_sync_db())


async def _sync_db():
    """Periodically sync the database."""
    global _WATCHES, _ONLINE_STATES
    while True:
        _WATCHES.close()
        _WATCHES = dbm.open(os.path.join(os.environ["HOME"], "r99infowatches.db"), "c")
        _ONLINE_STATES.close()
        _ONLINE_STATES = shelve.open(os.path.join(os.environ["HOME"], "r99infoonline.db"), "c", 2)
        await asyncio.sleep(5)


class _OnlineState(object):
    """State of a character"""
    __slots__ = ['first_time', 'zone_time', 'zone']

    def __init__(self, first_time: datetime.datetime = None, zone_time: datetime.datetime = None, zone: str = None):
        self.first_time = first_time if first_time is not None else datetime.datetime.now()
        self.zone_time = zone_time
        self.zone = zone

    def with_zone(self, zone):
        return _OnlineState(self.first_time, datetime.datetime.now(), zone)


async def _friends_loop():
    global _ONLINE_STATES
    global _SYNCED
    while True:
        await asyncio.sleep(3)
        try:
            if not _SYNCED:
                await _sync_friends()
            o_friends = await _online_friends()
            if o_friends is None:
                raise eqcmd.CommandError("Failed to /who friends")
            players = set(_ONLINE_STATES.keys()).union(o_friends.keys())
            for player in players:
                old_state = None
                if player in _ONLINE_STATES:
                    old_state = _ONLINE_STATES[player]
                new_entry = None
                if player in o_friends:
                    new_entry = o_friends[player]
                new_state = _state_delta(player, old_state, new_entry)
                if new_state is None:
                    if player in _ONLINE_STATES:
                        del _ONLINE_STATES[player]
                else:
                    _ONLINE_STATES[player] = new_state

        except eqcmd.CommandError as e:
            _LOG.error(str(e))
            await asyncio.sleep(5)


def _state_delta(player: str, old_state: _OnlineState, new_entry: who.WhoEntry) -> _OnlineState:
    mentions = []

    if player in _WATCHES:
        for user in pickle.loads(_WATCHES[player]):
            mentions.append(user.mention)

    new_state = old_state
    label, outmsg = None, None
    if old_state is None:
        if new_entry is None:
            return old_state

        label = "IN"
        new_state = _OnlineState()
        if new_entry.zone is None:
            outmsg = "is online"
        else:
            new_state = new_state.with_zone(new_entry.zone)
            outmsg = "is online in %s" % new_entry.zone
    elif new_entry is None:
        new_state = None
        label = "CAMP"
        tdstr = str(datetime.datetime.now() - old_state.first_time)
        offset = tdstr.find(".")
        if offset >= 0:
            tdstr = tdstr[:offset]
        outmsg = "has camped after %s online" % tdstr
        if old_state.zone is not None:
            tdstr = str(datetime.datetime.now() - old_state.zone_time)
            offset = tdstr.find(".")
            if offset >= 0:
                tdstr = tdstr[:offset]
            outmsg += " (seen in %s %s ago)" % (old_state.zone, tdstr)
    elif new_entry.zone is not None:
        new_state = new_state.with_zone(new_entry.zone)

    if outmsg:
        fmtmsg = "\\[%s\\] **%s** `%s` %s \\[%s\\]" % (
            time.strftime("%l:%M %p").strip(), label, misc.inicap(player), outmsg, " ".join(mentions))
        asyncio.ensure_future(spam.send(fmtmsg))
    return new_state


async def _sync_friends():
    """Get the actual set of friends to match the expected set of friends"""
    global _SYNCED, _WATCHES
    expected = set([str(k, "utf8").lower() for k in _WATCHES.keys()])
    while True:
        actual = await _friends()
        if actual is None:
            raise eqcmd.CommandError("Failed to retrieve friends")
        if actual == expected:
            _SYNCED = True
            return
        for person in expected.symmetric_difference(actual):
            if person in _ONLINE_STATES:
                del _ONLINE_STATES[person]
            await _toggle_friend(person)


_END_FRIENDS = re.compile("You have no friends! Awww, how sad...|You have [0-9]+ friend\(s\)[.]")


async def _friends():
    """Query for our current set of friends."""
    with await eqcmd.tap() as et:
        return await _friends_body(et)


@misc.timeout(5)
async def _friends_body(et: eqcmd.CommandTap):
    friends = set()
    await et.send("/friends")
    await et.skip_until("List of Friends")
    await et.skip_until("-----------------")
    while True:
        line = await et.next_line()
        if _END_FRIENDS.match(line) is not None:
            break
        friends.add(line.lower())
    return friends


_NOW_FRIEND = re.compile(r"([a-z]+) is now your friend.")
_NOT_FRIEND = re.compile(r"([a-z]+) is no longer your friend.")


async def _toggle_friend(name: str) -> bool:
    """Toggle a player's status as a friend."""
    with await eqcmd.tap() as et:
        return await _toggle_friend_body(et, name)


@misc.timeout(5)
async def _toggle_friend_body(et: eqcmd.CommandTap, name: str) -> bool:
    await et.send("/friend " + name)
    while True:
        line = await et.next_line()
        if _NOW_FRIEND.match(line):
            return True
        elif _NOT_FRIEND.match(line):
            return False


async def _online_friends():
    wf = await who.who_all("friends")
    if wf is None:
        return None
    online = {}
    for we in wf[0]:
        if we.name in _WATCHES:
            online[we.name] = we
    return online
