from __future__ import annotations

import asyncio

from briefing_bots.digest_bot import main as digest_main
from briefing_bots.qa_bot import main as qa_main


async def _run(name: str, coro) -> None:
    try:
        await coro
    except Exception as e:
        print(f"[{name}] crashed: {type(e).__name__}: {e}")
        raise


async def main() -> None:
    results = await asyncio.gather(
        _run("qa", qa_main()),
        _run("digest", digest_main()),
        return_exceptions=True,
    )
    for name, result in zip(("qa", "digest"), results):
        if isinstance(result, Exception):
            print(f"[{name}] exited with error: {result}")


if __name__ == "__main__":
    asyncio.run(main())
