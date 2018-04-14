#!/usr/bin/env python3.5

# relogger.py: automatically log into EverQuest

import conf
import cv2
import tempfile
import os
import subprocess
import time
import re
import shlex
import conf
import os.path
import logging

_LOGGER = logging.getLogger("relogger")


WAIT_DURATION = 60

EULA_BUTTON = cv2.imread("snips/eulabutton.png")
LOGO = cv2.imread("snips/logo.png")
LOGIN_BUTTON = cv2.imread("snips/login_button.png")
LOGIN_BUTTON2 = cv2.imread("snips/login_button2.png")
USERNAME_LABEL = cv2.imread("snips/username.png")
R99SERVER1 = cv2.imread("snips/r99server1.png")
R99SERVER2 = cv2.imread("snips/r99server2.png")
PLAYEQ_BUTTON = cv2.imread("snips/playeq.png")
PLAYEQ_BUTTON2 = cv2.imread("snips/playeq2.png")
ENTER_WORLD_BUTTON = cv2.imread("snips/enterworld.png")
ENTER_WORLD_BUTTON2 = cv2.imread("snips/enterworld2.png")
DONE_LOADING = cv2.imread("snips/doneloading.png")


def _w(arr):
    """Width of an array"""
    return arr.shape[1]


def _h(arr):
    """Height of an array"""
    return arr.shape[0]


def _capture():
    """Grab a screenshot of EverQuest"""
    fixup()
    tf = tempfile.mktemp(".png")
    try:
        cp = subprocess.run(["/usr/bin/import","-window", "EverQuest", tf], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if cp.returncode != 0 or b"unavailable" in cp.stdout:
            raise StateError("Couldn't capture screenshot")
        return cv2.imread(tf)
    finally:
        os.unlink(tf)


def capture():
    for i in range(WAIT_DURATION):
        img = _capture()
        if len(img.shape) == 3 and img.shape[0] >= 600 and img.shape[1] >= 600 and img.dtype == EULA_BUTTON.dtype:
            return img
        time.sleep(1)
    else:
        raise StateError("Couldn't capture screenshot")


def start_eq():
    """Start EverQuest"""
    pd = os.getcwd()
    try:
        os.chdir(conf.EQ_DIR)
        return subprocess.Popen(["/usr/bin/wine", "./eqgame.exe", "patchme"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        os.chdir(pd)


class CommandError(Exception):
    pass


class StateError(Exception):
    pass


def xdo(cmd):
    cp = subprocess.run(["/usr/bin/xdotool"]+shlex.split(cmd), stdout=subprocess.PIPE)
    if cp.returncode != 0:
        raise CommandError("Failed run of xdotool")
    else:
        return str(cp.stdout, "utf8")


_WINDLOC_RE = re.compile(r"\s*Position: (-?[0-9]+),(-?[0-9]+).*")
_GEOMETRY_RE = re.compile(r"\s*Geometry: ([0-9]+)x([0-9]+).*")


def _geometry():
    """Get the EQ window location"""
    lines = xdo("search --name EverQuest getwindowgeometry").splitlines()
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
        raise CommandError("Couldn't find EverQuest window: %r" % lines)
    return loc, size


def geometry():
    for i in range(10):
        try:
            return _geometry()
        except:
            _LOGGER.debug("Failed to retrieve geometry", exc_info=True)
            time.sleep(1)
    else:
        raise CommandError("Couldn't find EverQuest window")


def click(x, y, button=1):
    """Click the mouse in the EQ window"""
    loc, size = geometry()
    xdo("mousemove %d %d click %d" % (x + loc[0], y + loc[1], button))


def clickslow(x,y, button=1):
    loc, size = geometry()
    xdo("mousemove %d %d mousedown %d" % (x + loc[0], y+loc[1], button))
    time.sleep(0.1)
    xdo("mouseup %d" % button)


def key(text, repeat=1):
    xdo("key --delay=75 --repeat=%d %s" %(repeat, shlex.quote(text)))


def type(text):
    xdo("type --delay=200 "+shlex.quote(text))


def fixup():
    loc, size = geometry()
    if loc[0] < 0 or loc[1] <0:
        xdo("search --name EverQuest windowmove 100 100")


def prepare():
    fixup()
    click(10, 10)
    xdo("search --name EverQuest windowmap windowraise windowfocus")
    time.sleep(0.2)


def find_in(haystack, needle):
    """Find the location of a snip within a screenshot"""
    if _w(needle) > _w(haystack) or _h(needle) > _h(haystack):
        return None, None

    res = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
    minval, maxval, minloc, maxloc = cv2.minMaxLoc(res)

    if maxval < 0.8:
        return None, None
    else:
        return (maxloc[0]+_w(needle)//2, maxloc[1]+_h(needle)//2)


def wait_for(*imgs):
    for i in range(WAIT_DURATION):
        prepare()
        for img in imgs:
            x, y = find_in(capture(), img)
            if x is not None:
                return x, y
        else:
            time.sleep(1)
            continue
        break
    else:
        raise StateError("Got into bad state")


def click_on(*imgs, slow=False):
    """Find a button matching the given image and click on it"""
    wait_for(*imgs)

    for i in range(WAIT_DURATION):
        prepare()
        for img in imgs:
            x, y = find_in(capture(), img)
            if x is not None:
                break
        else:
            break
        if slow:
            clickslow(x,y)
        else:
            click(x, y)
        time.sleep(1)
    else:
        raise StateError("Got into bad state")


def pass_logo_screen():
    """Click past the logo screen"""
    while True:
        prepare()
        x, y = find_in(capture(), LOGO)
        if x is None:
            break
        click(100, 100)
        time.sleep(1)


def enter_login():
    prepare()
    x, y = wait_for(USERNAME_LABEL)
    prepare()
    for i in range(10):
        clickslow(x, y+25)
        time.sleep(0.25)
    time.sleep(0.1)
    key("BackSpace", 16)
    key("Delete", 16)
    time.sleep(0.1)
    type(conf.ACCOUNT)
    time.sleep(0.1)
    key("Tab")
    time.sleep(0.1)
    type(conf.PASSWORD)
    time.sleep(0.1)
    key("Return")


def select_server():
    prepare()
    x, y = wait_for(R99SERVER1, R99SERVER2)
    click(x, y)
    wait_for(R99SERVER1)

    click_on(PLAYEQ_BUTTON, PLAYEQ_BUTTON2)


def launch_eq():
    _LOGGER.info("Starting EQ")
    p = start_eq()
    try:
        for i in range(WAIT_DURATION):
            try:
                prepare()
                capture()
                break
            except:
                _LOGGER.debug("EQ isn't yet started", exc_info=True)
                time.sleep(1)
        else:
            raise StateError("EQ never started")

        _LOGGER.info("Clicking EULA button")
        click_on(EULA_BUTTON)

        _LOGGER.info("Passing logo screen")
        pass_logo_screen()

        _LOGGER.info("Clicking login button")
        click_on(LOGIN_BUTTON, LOGIN_BUTTON2)

        _LOGGER.info("Entering username/password")
        enter_login()

        _LOGGER.info("Selecting server")
        select_server()

        _LOGGER.info("Waiting for character select")
        wait_for(ENTER_WORLD_BUTTON, ENTER_WORLD_BUTTON2)
        time.sleep(10)

        _LOGGER.info("Entering world")
        click_on(ENTER_WORLD_BUTTON, ENTER_WORLD_BUTTON2, slow=True)
        time.sleep(10)

        _LOGGER.info("Waiting for world to load")
        wait_for(DONE_LOADING)

        return p
    except:
        _LOGGER.fatal("Trouble, aborting login attempt", exc_info=True)
        raise


def launch_bot():
    _LOGGER.info("Starting bot")
    os.system("./botmain.py")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s | %(name)s | %(msg)s")

    while True:
        try:
            os.system("killall eqgame.exe")
            time.sleep(5)
            p = launch_eq()
            try:
                launch_bot()
            finally:
                p.kill()
        except:
            _LOGGER.error("Session ended, starting over in 10 seconds", exc_info=True)
            time.sleep(10)
            continue
