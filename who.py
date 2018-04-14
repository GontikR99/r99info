# who.py: Support for sending /who all commands to EQ

import re
import eqcmd
import misc
import chat

CHAR_CATEGORY="Character presence"


@chat.command("!who", CHAR_CATEGORY)
async def _who_cmd(msg):
    """Run a /who all <somebody>"""
    cmdparts = msg.content.strip().split(maxsplit=1)
    whofilter = ""
    if len(cmdparts) > 1:
        whofilter = cmdparts[1]
    please_wait = await chat.send_warning(msg.channel, "`who %s`" % chat.quote(whofilter),
                                          "Please wait while I work on that, "+msg.author.mention)
    wa = await who_all(whofilter)
    if wa is None:
        await chat.send_error(msg.channel, "`who %s`" % chat.quote(whofilter), "Failed to execute /who command")
        if please_wait is not None:
            await chat.delete_message(please_wait)
    else:
        chat.fade(await chat.send_info(msg.channel, "`who %s`" % chat.quote(whofilter),
                             "\n".join([we.fmt() for we in wa[0]]+
                                       ["", "*%s player%s found*" % (wa[1], "" if wa[1]=="1" else "s")])))
        if please_wait is not None:
            await chat.delete_message(please_wait)


class WhoEntry(object):
    """An immutable object holding /who information about a single player"""
    __slots__ = ["classlevel", "name", "race", "zone", "guild"]

    def __init__(self, classlevel, name, race, zone, guild):
        self.classlevel = classlevel
        self.name = name
        self.race = race
        self.zone = zone
        self.guild = guild

    def __eq__(self, other):
        return isinstance(other, WhoEntry) and \
            other is not None and \
            self.name == other.name and \
            self.zone == other.zone

    def __hash__(self):
        return self.name.__hash__() ^ self.zone.__hash__()

    def __repr__(self):
        return "WhoEntry(%r, %r, %r, %r, %r)" % (self.classlevel, self.name, self.race, self.zone, self.guild)

    def __str__(self):
        return self.__repr__()

    def fmt(self):
        parts = []
        parts.append("[%s] `%s`" % (self.classlevel, self.name.upper()[0]+self.name.lower()[1:]))
        if self.race is not None:
            parts.append(" (%s)" % self.race)
        if self.guild is not None:
            parts.append(" <%s>" % self.guild)
        if self.zone is not None:
            parts.append(" ZONE: %s " % self.zone)
        return "".join(parts)


_WHO_RE = re.compile(r"[^\[]*\[([^\]]*)] ([A-Za-z]+)(?:\s*\(([^)]*)\))?(?:\s*<([^>]+)>)?\s*(?:ZONE: ?([^ ]*))?")


def parse_who(line: str) -> WhoEntry:
    """Parse a /who entry"""
    m = _WHO_RE.match(line)
    if m:
        if m.group(1) == "PvP":
            return None
        classlevel = m.group(1) if m.group(1) != "" else None
        name = m.group(2).lower()
        race = m.group(3) if m.group(3) != "" else None
        guild = m.group(4) if m.group(4) != "" else None
        zone = m.group(5) if m.group(5) != "" else None
        return WhoEntry(classlevel, name, race, zone, guild)


_END_WHO = [
    (re.compile("There (?:is|are) ([0-9]+) players? in EverQuest[.]"), lambda m:m.group(1)),
    (re.compile("There are no players in EverQuest that match those who filters."), lambda m:"0"),
    (re.compile("Your who request was cut short[.][.]too many players[.]"), lambda m: "more than 20"),
    (re.compile("You have no friends, but you can add some with: /friends <name>"), lambda m: "0")
]


async def who_all(text: str):
    """Perform a /who all, and return a set of WhoEntry"""
    with await eqcmd.tap() as ct:
        return await _who_body(ct, text)


@misc.timeout(10)
async def _who_body(ct: eqcmd.CommandTap, text: str):
    who = []
    await ct.send("/who all " + text)
    while True:
        line = await ct.next_line()
        p = parse_who(line)
        if p:
            who.append(p)
        for filt in _END_WHO:
            m = filt[0].match(line)
            if m:
                return who, filt[1](m)

