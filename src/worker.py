"""Worker entrypoint: registers all workflows and starts polling."""

import asyncio

from mistralai import workflows

from src.workflows.sc_clean import ScCleanWorkflow


async def main() -> None:
    await workflows.run_worker([ScCleanWorkflow])


if __name__ == "__main__":
    asyncio.run(main())
