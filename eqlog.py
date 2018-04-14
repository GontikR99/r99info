import asyncio
import io
import re
import os
import contextlib


class LogTap(object):
    _INSTANCE_COUNTER = 0
    _ACTIVE = set()

    def __init__(self):
        self._id = LogTap._INSTANCE_COUNTER
        LogTap._INSTANCE_COUNTER += 1
        self._queue = asyncio.Queue()
        LogTap._ACTIVE.add(self)

    def __hash__(self):
        return self._id

    def __eq__(self, other):
        return isinstance(other, LogTap) and self._id == other._id

    async def post_line(self, line):
        await self._queue.put(line)

    async def next_line(self):
        return await self._queue.get()

    def close(self):
        LogTap._ACTIVE.remove(self)


@contextlib.contextmanager
def tap() -> LogTap:
    """Return a LogTap object which can be used to receive log lines."""
    lt = LogTap()
    try:
        yield lt
    finally:
        lt.close()


async def _tail(filename: str, q: asyncio.Queue):
    """Watch a file, and pass all new lines to the specified queue"""
    try:
        with open(filename, "r") as infile:
            infile.seek(0, io.SEEK_END)
            infile.seek(max(0, -1+infile.tell()), io.SEEK_SET)
            textbuf = []
            # Await initial newline
            while True:
                buf = infile.read(1024)
                if len(buf) == 0:
                    await asyncio.sleep(0.05)
                    continue
                if "\n" in buf:
                    offset = buf.find("\n")
                    buf = buf[offset+1:]
                    for line in buf.splitlines(keepends=True):
                        if line[-1] == "\n":
                            await q.put(line[:-1])
                        else:
                            textbuf.append(line)
                    break

            # Send remaining to queue
            while True:
                buf = infile.read(1024)
                if len(buf) == 0:
                    await asyncio.sleep(0.05)
                    continue
                textbuf.append(buf)
                if "\n" in buf:
                    buf = "".join(textbuf)
                    textbuf.clear()
                    for line in buf.splitlines(keepends=True):
                        if line[-1] == "\n":
                            await q.put(line[:-1])
                        else:
                            textbuf.append(line)
    except asyncio.CancelledError:
        pass

_LOGFILE_RE = re.compile("eqlog_.*[.]txt")
_LOGLINE_RE = re.compile(r"^\[[^\]]*\] (.*)$")


async def _watch_logs(directory: str):
    """Watch all log files in a directory"""
    rq = asyncio.Queue()
    logdir = os.path.join(directory, "Logs")
    for filename in os.listdir(logdir):
        if _LOGFILE_RE.match(filename):
            asyncio.ensure_future(_tail(os.path.join(logdir, filename), rq))

    try:
        while True:
            line = await rq.get()
            m = _LOGLINE_RE.match(line)
            if m:
                active = [instance for instance in LogTap._ACTIVE]
                for instance in active:
                    await instance.post_line(m.group(1))
    except asyncio.CancelledError:
        pass

_is_init = False


async def init(directory: str):
    global _is_init
    if _is_init:
        return
    _is_init = True
    asyncio.ensure_future(_watch_logs(directory))
