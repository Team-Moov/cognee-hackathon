"""
test_day1.py — Day 1 Verification

Verifies that Cognee connects to Groq successfully.
Run this before anything else.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load env before local imports
load_dotenv()

import cognee

async def main():
    print("Testing Cognee + Groq Connection...")

    # Configure Cognee manually for test
    cognee.config.llm_config = {
        "provider": os.getenv("LLM_PROVIDER", "groq"),
        "model": os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile"),
        "api_key": os.getenv("GROQ_API_KEY", ""),
    }
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "<YOUR_GROQ_API_KEY>":
        print("ERROR: Please set a valid Groq API key in .env")
        sys.exit(1)
        
    try:
        print("\n--- 1. Testing cognee.add & cognify ---")
        dataset = "test_dataset"
        await cognee.add("Groundhog is a memory layer for ML experiments.", dataset_name=dataset)
        await cognee.cognify(dataset_name=dataset)
        print("SUCCESS: Data added and cognified.")
        
        print("\n--- 2. Testing cognee.search (Recall) ---")
        from cognee import SearchType
        results = await cognee.search(
            query_text="What is Groundhog?", 
            query_type=SearchType.GRAPH_COMPLETION,
            datasets=[dataset]
        )
        print(f"SUCCESS: Search returned {len(results)} result(s).")
        for i, r in enumerate(results[:1]):
            print(f"Top result: {str(r)[:100]}...")
            
    except Exception as e:
        print(f"\nERROR: Connection test failed: {e}")
        sys.exit(1)
        
    print("\nDay 1 Verification Complete! Groq connection is working.")

if __name__ == "__main__":
    asyncio.run(main())
