#!/usr/bin/env python3.5

import asyncio
import chat
import eqcmd
import eqlog
import logging
import chat_forward
import conf
import friends
import spam
import pvp
import os

_logger = logging.getLogger("botmain")


_SHOULD_DIE = False


async def _timer():
    global _SHOULD_DIE
    await asyncio.sleep(conf.RELOG_DURATION)
    _SHOULD_DIE = True


async def main():
    asyncio.ensure_future(_timer())

    _logger.info("Initializing eqlog")
    await eqlog.init(conf.EQ_DIR)

    _logger.info("Initializing eqcmd")
    await eqcmd.init()
    await eqcmd.wait_for_ready()

    _logger.info("Connecting to discord")
    await chat.init(conf.TOKEN)

    _logger.info("Installing modules")
    await spam.init()
    await chat_forward.init()
    await friends.init()
    await pvp.init()

    try:
        while eqcmd.is_ready() and not _SHOULD_DIE:
            await asyncio.sleep(1)
    except:
        _logger.error("Unexpected error", exc_info=True)
    finally:
        _logger.fatal("Dieing now", exc_info=True)
        os._exit(1)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s | %(name)s | %(msg)s")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
