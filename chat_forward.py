# chat_forward.py: Read EQ chat, filter, and format messages for Discord

import asyncio
import chat
import eqlog
import re
import spam
import time
import discord


async def init():
    asyncio.ensure_future(_ooc_loop())

_OOC_RE = re.compile(r"([^ ]*) says out of character, '(.*)'")
_TELL_RE = re.compile(r"([^ ]*) tells you, '(.*)'")
_KILL_RE = re.compile(r"(Thou hast been expelled by the gods!)")

async def _ooc_loop():
    with eqlog.tap() as lt:
        while True:
            line = await lt.next_line()
            m = _TELL_RE.match(line)
            if m:
                msgtext = chat.quote(m.group(2))
                fmtmsg = "\\[%s\\] **TELL** `%s`: %s" % (time.strftime("%l:%M %p").strip(), m.group(1), msgtext)
                await spam.send(fmtmsg)
                continue
            m = _OOC_RE.match(line)
            if m:
                msgtext = chat.quote(m.group(2))
                fmtmsg = "\\[%s\\] **OOC** `%s`: %s" % (time.strftime("%l:%M %p").strip(), m.group(1), msgtext)
                await spam.send(fmtmsg)
                continue
            m = _KILL_RE.match(line)
            if m:
                fmtmsg = "\\[%s\\] **GM** *%s*" % (time.strftime("%l:%M %p").strip(), m.group(1))
                await spam.send(fmtmsg)
                continue

