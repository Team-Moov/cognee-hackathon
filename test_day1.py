"""
test_day1.py — Day 1 Verification

Verifies that Cognee connects to Gemini successfully.
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
    print("Testing Cognee + Gemini Connection...")
    
    # Configure Cognee manually for test
    cognee.config.llm_config = {
        "provider": os.getenv("LLM_PROVIDER", "gemini"),
        "model": os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash"),
        "api_key": os.getenv("LLM_API_KEY", ""),
    }
    cognee.config.vector_db_config = {
        "embedding_provider": os.getenv("EMBEDDING_PROVIDER", "gemini"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "gemini/gemini-embedding-001"),
        "embedding_api_key": os.getenv("EMBEDDING_API_KEY", ""),
        "embedding_dimensions": int(os.getenv("EMBEDDING_DIMENSIONS", "768")),
    }
    
    if not os.getenv("LLM_API_KEY") or os.getenv("LLM_API_KEY") == "<YOUR_GOOGLE_API_KEY>":
        print("ERROR: Please set a valid Google API key in .env")
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
        
    print("\nDay 1 Verification Complete! Gemini connection is working.")

if __name__ == "__main__":
    asyncio.run(main())
