import cognee
import asyncio

async def main():
    # Create a clean slate for cognee -- reset data and system state
    await cognee.forget(everything=True)

    # Store content in memory (ingests, builds knowledge graph, enriches)
    text = "Cognee turns documents into AI memory."
    await cognee.remember(text)

    # Retrieve from memory
    results = await cognee.recall(
        query_text="What does Cognee do?"
    )

    # Print
    for result in results:
        print(result.text)

if __name__ == '__main__':
    asyncio.run(main())