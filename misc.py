import asyncio
import logging

_LOGGER = logging.getLogger("misc")


def timeout(duration):
    """Rewrite a coroutine to operate on a strict timeout"""
    def rewrite(fn):
        async def wrapper1(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except asyncio.CancelledError:
                pass

        async def wrapper2(*args, **kwargs):
            fut = asyncio.ensure_future(wrapper1(*args, **kwargs))
            try:
                return await asyncio.wait_for(fut, timeout=duration)
            except asyncio.TimeoutError:
                return None
        return wrapper2
    return rewrite


def trimiso(dt):
    if "." in dt:
        dt = dt[:dt.find(".")]
    dt = dt.replace("T", " ")
    return dt


def inicap(text):
    if len(text) == 0:
        return ""
    return text.upper()[0]+text.lower()[1:]
