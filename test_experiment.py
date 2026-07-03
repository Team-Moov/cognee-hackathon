import cognee
import asyncio
from cognee.tasks.storage import add_data_points
from schema import Experiment

from cognee import SearchType

async def run():
    # Forget everything to test isolated insertion
    await cognee.forget(everything=True)

    exp = Experiment(
        name="lr-sweep-01",
        description="Testing learning rates for the vision model fine-tune"
    )

    await add_data_points([exp])

    results = await cognee.search("lr-sweep-01", query_type=SearchType.GRAPH_COMPLETION)
    print("\n--- SEARCH RESULTS ---")
    print(results)

if __name__ == '__main__':
    asyncio.run(run())
