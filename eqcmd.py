# eqcmd.py: Basic routines for interfacing with EQ.

import asyncio
from asyncio.subprocess import create_subprocess_shell, PIPE
import eqlog
import os
import re
import shlex
import random


class CommandError(Exception):
    """A problem running a command"""
    pass


class NotReadyError(Exception):
    """EverQuest isn't ready to receive a command"""
    pass


async def _xdotool(display, text) -> [str]:
    """Interface with X via calls to xdotool."""
    cmd = "/usr/bin/xdotool "+text
    env = dict([(k, os.environ[k]) for k in os.environ])
    env["DISPLAY"] = display
    proc = await asyncio.create_subprocess_shell(cmd, stdout=PIPE, stderr=PIPE, env=env)
    stdout, stderr = await proc.communicate()
    rc = await proc.wait()
    if rc != 0:
        raise CommandError("Command send failed")
    return str(stdout, "utf8").splitlines()


_EQDISPLAY = None


async def _eqdisplay() -> str:
    """Figure out which X display EQ is running on."""
    return os.environ["DISPLAY"]
#    global _EQDISPLAY
#    if _EQDISPLAY is None:
#        for i in range(100):
#            try:
#                display = ":%d" % i
#                await _xdotool(display, "search --name EverQuest")
#                _EQDISPLAY = display
#                break
#            except CommandError:
#                pass
#        else:
#            raise CommandError("Couldn't find EverQuest display")
#    return _EQDISPLAY


async def _eqxdo(text):
    """Run xdotool against the display holding EverQuest"""
    return await _xdotool(await _eqdisplay(), text)


_WINDLOC_RE = re.compile(r"\s*Position: ([0-9]+),([0-9]+).*")
_GEOMETRY_RE = re.compile(r"\s*Geometry: ([0-9]+)x([0-9]+).*")


async def _geometry():
    """Get the EQ window location"""
    lines = await _eqxdo("search --name EverQuest getwindowgeometry")
    loc = None
    size = None
    for line in lines:
        m = _WINDLOC_RE.match(line)
        if m:
            loc = int(m.group(1)), int(m.group(2))
        m = _GEOMETRY_RE.match(line)
        if m:
            size = int(m.group(1)), int(m.group(2))
    if loc is None or size is None:
        raise CommandError("Couldn't find EverQuest window")
    return loc, size


async def _prepare():
    """Prepare EQ window to receive input"""
    loc, size = await _geometry()
    x = loc[0] + (size[0]//3 + random.randint(0, size[0]//3))
    y = loc[1] + (size[1]//3 + random.randint(0, size[1]//3))
    await _eqxdo("mousemove %d %d" % (x, y))
    await _eqxdo("click 1")
    await asyncio.sleep(0.2)
    await _eqxdo("search --name EverQuest windowmap windowraise windowfocus")
    await _eqxdo("click 1")


async def _press_raw(key_name):
    """Press a key in EQ"""
    await _eqxdo("key " + shlex.quote(key_name))
    await asyncio.sleep(0.2)


async def _press(key_name):
    """Press a key in EQ after preparing for input"""
    await _prepare()
    await _press_raw(key_name)


async def _type(text):
    """Type a line of text in EQ"""
    await _prepare()
    await _press_raw("Return")
    await _eqxdo("type --delay 20 "+shlex.quote(text))
    await _press_raw("Return")


async def _expect_io():
    """Wait until a line of text comes in from the EQ log."""
    try:
        with eqlog.tap() as t:
            await t.next_line()
    except asyncio.CancelledError:
        pass


_EQ_READY = False


async def _ping_watch():
    """Keep the _EQ_READY variable up to date.  Here, we decide EQ is up and running if
    we've seen at least 1 chat message (e.g. "You are out of food and drink.") sometime
    in the past minute."""
    global _EQ_READY
    while True:
        f = asyncio.ensure_future(_expect_io())
        try:
            await asyncio.wait_for(f, 60)
            _EQ_READY = True
        except asyncio.TimeoutError:
            _EQ_READY = False


def is_ready():
    """Determine if EQ is ready to receive commands"""
    return _EQ_READY


async def wait_for_ready():
    """Wait for EQ to be ready to receive commands"""
    while True:
        if is_ready():
            return
        else:
            await asyncio.sleep(1)

_is_init = False


async def init():
    """Prepare the EQ command subsytem"""
    global _is_init
    if _is_init:
        return
    _is_init = True
    await _eqdisplay()
    asyncio.ensure_future(_ping_watch())


class CommandTap(object):
    """A context object, extending the functionality of eqlog.LogTap,
    which also allows sending commands to EQ."""
    _LOCK = asyncio.Lock()

    def __init__(self):
        self._ltctx = None
        self._lt = None

    def __enter__(self):
        self._ltctx = eqlog.tap()
        self._lt = self._ltctx.__enter__()
        return self

    def __exit__(self, *args):
        try:
            self._ltctx.__exit__(*args)
        finally:
            CommandTap._LOCK.release()

    async def next_line(self):
        """Retrieve the next line"""
        return await self._lt.next_line()

    async def skip_until(self, text):
        """Wait until a line matching the specified regexp comes up"""
        while True:
            line = await self.next_line()
            if isinstance(text, str):
                if line == text:
                    return line
            else:
                m = text.match(line)
                if m:
                    return m

    async def send(self, text):
        """Send a command to EQ."""
        if not is_ready():
            raise NotReadyError("EQ is not currently ready to receive commands")
        await _type(text)

    async def press(self, key_name):
        """Press a key in the EQ window."""
        if not is_ready():
            raise NotReadyError("EQ is not currently ready to receive commands")
        await _press(key_name)


async def tap():
    """Call as 'with await eqcmd.tap() as t:' to get a CommandTap object to manipulate EQ with."""
    await CommandTap._LOCK.acquire()
    return CommandTap()
