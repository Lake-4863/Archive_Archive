from __future__ import annotations

import asyncio

from briefing_bots.digest_bot import main as digest_main
from briefing_bots.qa_bot import main as qa_main


async def main() -> None:
    await asyncio.gather(qa_main(), digest_main(), return_exceptions=False)


if __name__ == "__main__":
    asyncio.run(main())
