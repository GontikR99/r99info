# leaderboard.py: PvP tracking functionality

import asyncio
import eqlog
import chat
import sqlite3
import re
import os
import os.path
import datetime
import discord
import spam
import time
import isodate
from misc import inicap, trimiso
import logging

_PVP_CATEGORY = "PvP Tracker"

_DB_FILENAME = os.path.join(os.environ["HOME"], "r99infoleaderboard.db")
_DB = None

_logger = logging.getLogger("pvp")


@chat.command("!today", _PVP_CATEGORY)
async def _todays_kills(msg):
    """Show the kills over the past day"""
    llimit = datetime.datetime.now() - datetime.timedelta(days=1)
    kills = _query("WHERE timestamp > ? ORDER BY timestamp", (llimit.isoformat(),))
    text = []
    for kill in kills:
        line = "\\[%s\\] `%s` <%s> killed `%s` <%s> in %s" % (
            trimiso(kill.timestamp)[kill.timestamp.find("T")+1:],
            inicap(kill.winner), kill.winner_guild,
            inicap(kill.loser), kill.loser_guild,
            kill.zone)
        value = _kill_value(kill)[2]
        if value > 0:
            line = line + " *(%d pt)*" % value
        text.append(line)
    killcount = _count("WHERE timestamp > ?", (llimit.isoformat(),))
    if killcount > len(kills):
        text.append("")
        text.append("*and %d more*" % (len(kills) - killcount))
    for i in range(0, len(text), 10):
        ul = min(len(text), i + 10)
        chat.fade(await chat.send_info(msg.channel, "Today's kills", "\n".join(text[i:ul])))


@chat.command("!top", _PVP_CATEGORY)
async def _top(msg):
    """Show the top ranked players and their scores."""
    rgroups = []
    ckey = None
    cgroup = None
    cursor = _DB.cursor()
    try:
        cursor.execute("SELECT player, score FROM scores WHERE score > 2 ORDER BY score DESC LIMIT 1000")
        rows = cursor.fetchall()
        prev_score = -1
        for row in rows:
            player = row[0]
            score = row[1]
            if score != prev_score:
                if ckey is not None:
                    rgroups.append((ckey, cgroup))
                cgroup = []
                ckey = "%d points (rank #%d)" % (score, _get_rank(player))
                prev_score = score
            cgroup.append(player)
        if ckey:
            rgroups.append((ckey, cgroup))
        for key, group in rgroups:
            group.sort()
            lines = []
            for i in range(0, len(group), 4):
                ul = min(len(group), i+4)
                lines.append("  ".join("`%s`" % inicap(player) for player in group[i:ul]))
            for i in range(0, len(lines), 10):
                ul = min(len(lines), i+10)
                chat.fade(await chat.send_info(msg.channel, key, "\n".join(lines[i:ul])))
    finally:
        cursor.close()

_NAME_RE = re.compile("[a-zA-Z]+")


@chat.command("!stats", _PVP_CATEGORY)
async def _stats_cmd(msg: discord.Message):
    """Get kills/deaths for a player"""
    parts = msg.content.strip().split(maxsplit=1)
    if len(parts) != 2:
        chat.fade(await chat.send_error(msg.channel, "`stats`", "Usage: !stats character || !stats <guild>"))
        return
    if parts[1].strip().startswith("<"):
        return await _guild_stats(msg, parts[1].strip())
    name = parts[1].lower()
    if len(name) < 3 or len(name) > 45 or not _NAME_RE.match(name):
        chat.fade(await chat.send_error(msg.channel, "`stats`", chat.quote("%r is not a valid name" % name)))
        return

    e = discord.Embed()
    e.color = 0x007f00
    e.title = "`stats %s`" % name
    wins = _query("WHERE winner==? ORDER BY timestamp DESC limit 10", (name,))
    if wins:
        e.add_field(name="Killed", value="\n".join(
            ["[%s] `%s` <%s> in %s *(%d pt)*" % (
                trimiso(win.timestamp), inicap(win.loser), win.loser_guild, win.zone, _kill_value(win)[2]) for win in wins]),
            inline=True)
    losses = _query("WHERE loser==? ORDER BY timestamp DESC limit 10", (name,))
    if losses:
        e.add_field(name="Died to", value="\n".join(
            ["[%s] `%s` <%s> in %s *(%d pt)*" % (
                trimiso(loss.timestamp), inicap(loss.winner), loss.winner_guild, loss.zone, -_kill_value(loss)[2]) for loss in losses]),
            inline=True)
    e.add_field(name="Stats", value="Kills: %d\nDeaths: %d\nStreak: %d\nScore: %d\nRank: %d" % _stats(name), inline=False)
    chat.fade(await chat.send_message(msg.channel, embed=e))


async def _guild_stats(msg: discord.Message, arg: str):
    if not (arg.startswith("<") and arg.endswith(">")):
        chat.fade(await chat.send_error(msg.channel, "`stats`", "Usage: !stats character || !stats <guild>"))
        return
    gname = arg[1:-1]
    e = discord.Embed()
    e.color = 0x007f00
    e.title = "`stats <%s>`" % gname
    wins = _query("WHERE lower(winner_guild)==? ORDER BY timestamp DESC limit 10", (gname.lower(),))
    wincount = _count("WHERE lower(winner_guild)==? ORDER BY timestamp DESC limit 10", (gname.lower(),))
    if wins:
        e.add_field(name="Killed", value="\n".join(
            ["[%s] `%s` <%s> killed `%s` <%s> in %s" % (trimiso(win.timestamp),
                                                        inicap(win.winner), win.winner_guild,
                                                        inicap(win.loser), win.loser_guild,
                                                        win.zone) for win in wins]),
            inline=False)

    losses = _query("WHERE lower(loser_guild)==? ORDER BY timestamp DESC limit 10", (gname.lower(),))
    losscount = _count("WHERE lower(loser_guild)==? ORDER BY timestamp DESC limit 10", (gname.lower(),))
    if losses:
        e.add_field(name="Died to", value="\n".join(
            ["[%s] `%s` <%s> killed `%s` <%s> in %s" % (trimiso(loss.timestamp),
                                                        inicap(loss.winner), loss.winner_guild,
                                                        inicap(loss.loser), loss.loser_guild,
                                                        loss.zone) for loss in losses]),
            inline=True)
    e.add_field(name="Stats", value="Kills: %d\nDeaths: %d" % (wincount, losscount), inline=False)
    chat.fade(await chat.send_message(msg.channel, embed=e))


async def init():
    """Initialize the leaderboard"""
    _open_db()
    # if datetime.datetime.now() - _oldest_score() > datetime.timedelta(days=33):
    #     _rebuild_scores()
    asyncio.ensure_future(_pvp_loop())


def _open_db():
    """Open the database and set up the tables"""
    global _DB
    _DB = sqlite3.connect(_DB_FILENAME)
    _DB.execute("""CREATE TABLE IF NOT EXISTS kills(
    timestamp CHAR(50) NOT NULL,
    winner CHAR(50) NOT NULL,
    winner_guild CHAR(50) NOT NULL,
    loser CHAR(50) NOT NULL,
    loser_guild CHAR(50) NOT NULL,
    zone CHAR(50) NOT NULL 
    )""")
    _DB.execute("""CREATE INDEX IF NOT EXISTS kills_by_timestamp ON kills(timestamp)""")
    _DB.execute("""CREATE INDEX IF NOT EXISTS kills_by_winner ON kills(winner, timestamp)""")
    _DB.execute("""CREATE INDEX IF NOT EXISTS kills_by_winner_guild ON kills(winner_guild, timestamp)""")
    _DB.execute("""CREATE INDEX IF NOT EXISTS kills_by_loser ON kills(loser, timestamp)""")
    _DB.execute("""CREATE INDEX IF NOT EXISTS kills_by_loser_guild ON kills(loser_guild, timestamp)""")

    _DB.execute("""CREATE TABLE IF NOT EXISTS scores(
    player CHAR(50) NOT NULL PRIMARY KEY,
    score INT NOT NULL)""")
    _DB.execute("""CREATE INDEX IF NOT EXISTS rank ON scores(score)""")

    _DB.execute("""CREATE TABLE IF NOT EXISTS score_history(
    timestamp CHAR(50) NOT NULL,
    player CHAR(50) NOT NULL,
    score INT NOT NULL)""")
    _DB.execute("""CREATE INDEX IF NOT EXISTS score_history_by_timestamp ON score_history(timestamp, player)""")
    _DB.commit()


def _oldest_score() -> datetime.datetime:
    """Determine the oldest existing score (i.e. when the scores table was last rebuilt)"""
    cursor = _DB.cursor()
    try:
        cursor.execute("SELECT timestamp FROM score_history ORDER BY timestamp LIMIT 1")
        rows = cursor.fetchall()
        if rows:
            return isodate.parse_datetime(rows[0][0])
        else:
            return datetime.datetime(2000, 1, 1)
    finally:
        cursor.close()


def _rebuild_scores():
    """Wipe out the scores table and rebuild."""
    _logger.info("Rebuilding scores tables")
    _DB.execute("""DELETE FROM scores""")
    _DB.execute("""DELETE FROM score_history""")
    _DB.commit()

    tsbreak = (datetime.datetime.now() - datetime.timedelta(days=60)).isoformat()
    while True:
        _logger.info("Rebuilding from beyond "+tsbreak)
        kills = _query("WHERE timestamp > ? ORDER BY timestamp LIMIT 200", (tsbreak,))
        if not kills:
            break
        for kill in kills:
            tsbreak = kill.timestamp
            _update_scores(kill)


class Kill(object):
    """A PvP kill"""
    __slots__ = ['timestamp', 'winner', 'winner_guild', 'loser', 'loser_guild', 'zone']

    def __init__(self, timestamp: str, winner: str, winner_guild: str, loser: str, loser_guild: str, zone: str):
        self.timestamp = timestamp
        self.winner = winner.lower()
        self.winner_guild = winner_guild
        self.loser = loser.lower()
        self.loser_guild = loser_guild
        self.zone = zone

    def __eq__(self, other):
        return isinstance(other, Kill) and \
            self.timestamp == other.timestamp and \
            self.winner == other.winner and \
            self.winner_guild == other.winner_guild and \
            self.loser == other.loser and \
            self.loser_guild == other.loser_guild and \
            self.zone == other.zone

    def __hash__(self):
        return self.timestamp.__hash__() ^ self.winner.__hash__() ^ self.winner_guild.__hash__() ^ \
            self.loser.__hash__() ^ self.loser_guild.__hash__() ^ self.zone.__hash__()

    def __repr__(self):
        return "Kill(%r, %r, %r, %r, %r, %r)" % (self.timestamp,
                                                 self.winner, self.winner_guild,
                                                 self.loser, self.loser_guild,
                                                 self.zone)


def _insert(kill: Kill):
    """Add a kill to the database"""
    _DB.execute("INSERT INTO kills(timestamp, winner, winner_guild, loser, loser_guild, zone) VALUES (?,?,?,?,?,?)",
                (kill.timestamp, kill.winner, kill.winner_guild, kill.loser, kill.loser_guild, kill.zone))
    _DB.commit()


def _count(clause: str, *args) -> int:
    """Execute a count query against the kills table with a specified set of clauses"""
    cursor = _DB.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM kills "+clause, *args)
        r = cursor.fetchone()
        return r[0]
    finally:
        cursor.close()


def _query(clause: str, *args) -> [Kill]:
    """Execute a query against the kills table with a specified set of clauses"""
    cursor = _DB.cursor()
    try:
        cursor.execute("SELECT timestamp, winner, winner_guild, loser, loser_guild, zone FROM kills "+clause, *args)
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append(Kill(row[0], row[1], row[2], row[3], row[4], row[5]))
        return results
    finally:
        cursor.close()


def _stats(charname):
    charname = charname.lower()
    wins = _count("WHERE winner==?", (charname,))
    losses = _count("WHERE loser==?", (charname,))
    recent_losses = _query("WHERE loser==? ORDER BY timestamp DESC LIMIT 1", (charname,))
    if len(recent_losses) != 0:
        streak = _count("WHERE winner==? AND timestamp > ?", (charname, recent_losses[0].timestamp))
    else:
        streak = wins
    return wins, losses, streak, _get_score(charname, datetime.datetime.now().isoformat()), _get_rank(charname)


def _get_score(player, timestamp):
    """Get the current score of a player"""
    cursor = _DB.cursor()
    try:
        cursor.execute("SELECT score FROM score_history "
                       "WHERE player = ? AND timestamp < ? "
                       "ORDER BY timestamp DESC LIMIT 1",
                       (player.lower(), timestamp))
        rows = cursor.fetchall()
        if rows:
            return rows[0][0]
        else:
            return 1
    finally:
        cursor.close()


def _get_rank(player):
    """Get the rank of a player"""
    cursor = _DB.cursor()
    try:
        cursor.execute("SELECT score FROM scores WHERE player = ?", (player.lower(),))
        rows = cursor.fetchall()
        if not rows:
            return 0
        ps = rows[0][0]
        cursor.execute("SELECT count(*) FROM scores WHERE score > ?", (ps,))
        rows = cursor.fetchall()
        return 1+rows[0][0]
    finally:
        cursor.close()


def _kill_value(kill: Kill):
    """Determine the value of a kill"""
    loser_score = _get_score(kill.loser, kill.timestamp)
    winner_score = _get_score(kill.winner, kill.timestamp)
    if kill.winner_guild == kill.loser_guild and kill.winner_guild != "":
        return winner_score, loser_score, 0
    recent_deaths = _query("WHERE loser = ? and timestamp < ? ORDER BY timestamp DESC LIMIT 1", (kill.loser, kill.timestamp))
    if recent_deaths and \
            (isodate.parse_datetime(kill.timestamp) - isodate.parse_datetime(recent_deaths[0].timestamp) < datetime.timedelta(minutes=10)):
        return winner_score, loser_score, 0
    if winner_score == 0 and loser_score == 0:
        value = 1
    elif loser_score == 0:
        value = 0
    elif winner_score > loser_score:
        value = 1
    else:
        value = max(1, (loser_score - winner_score + 3)//4)
    return winner_score, loser_score, value


def _update_scores(kill: Kill):
    """Update scores to reflect a win."""
    ws, ls, value = _kill_value(kill)
    ws = ws + value
    ls = max(0, ls - value)
    _DB.execute("INSERT OR REPLACE INTO scores (player, score) VALUES (?,?)", (kill.winner, ws))
    _DB.execute("INSERT INTO score_history (timestamp, player, score) VALUES (?,?,?)", (kill.timestamp, kill.winner, ws))
    _DB.execute("INSERT OR REPLACE INTO scores (player, score) VALUES (?,?)", (kill.loser, ls))
    _DB.execute("INSERT INTO score_history (timestamp, player, score) VALUES (?,?,?)", (kill.timestamp, kill.loser, ls))
    _DB.commit()
    return value


async def _announce(kill: Kill, value: int):
    """Announce a kill"""
    e = discord.Embed()
    e.color = 0xaaaa00
    e.description = "\\[%s\\] `%s` <%s> killed `%s` <%s> in %s\n*%d point%s*" % (
        time.strftime("%l:%M %p").strip(),
        inicap(kill.winner), kill.winner_guild,
        inicap(kill.loser), kill.loser_guild,
        kill.zone, value, "" if value == 1 else "s"
    )
    e.add_field(name="`%s`" % inicap(kill.winner),
                value="Kills: %d\nDeaths: %d\nStreak: %d\nScore: %d\nRank: %d" % _stats(kill.winner),
                inline=True)
    e.add_field(name="`%s`" % inicap(kill.loser),
                value="Kills: %d\nDeaths: %d\nStreak: %d\nScore: %d\nRank: %d" % _stats(kill.loser),
                inline=True)
    await spam.send(embed=e)


_PVP_RE = re.compile(r"\[PvP] ([A-Za-z]+) <([^>]*)> has been defeated by ([A-Za-z]+) <([^>]*)> in ([^!]+)!")


async def _on_kill(kill: Kill):
    value = _update_scores(kill)
    _insert(kill)
    asyncio.ensure_future(_announce(kill, value))


async def _pvp_loop():
    """Watch for kills and update the database"""
    with eqlog.tap() as lt:
        while True:
            m = _PVP_RE.match(await lt.next_line())
            if m:
                kill = Kill(datetime.datetime.now().isoformat(),
                            m.group(3), m.group(4),
                            m.group(1), m.group(2),
                            m.group(5))
                await _on_kill(kill)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s | %(name)s | %(msg)s")
    _open_db()
    _rebuild_scores()
    _DB.close()