"""
seed_demo_data.py — Groundhog Demo Data Seeder (Day 2 requirement)

Generates ~15 synthetic ML run documents with plausible variety, including
explicitly failed/aborted runs, and near-duplicate configs for the 
Pre-flight Guard demo. Calls remember_run for each, with a small delay
to respect Groq free-tier rate limits.
"""

import asyncio
import os
import random
import time
import logging
import sys
from dotenv import load_dotenv

# Load env before any local imports
load_dotenv()

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("seed")

import cognee
from memory import remember_run

# Plausible ML options
OPTIMIZERS = ["Adam", "AdamW", "SGD"]
LEARNING_RATES = [1e-3, 5e-4, 1e-4, 5e-5]
ARCHITECTURES = ["ResNet50", "ResNet101", "VisionTransformer-B", "MobileNetV3"]
DATASETS = ["ImageNet1K", "CIFAR-100", "CustomMedical-v1"]
STATUSES = ["completed", "completed", "completed", "completed", "aborted", "failed"] 

def _generate_synthetic_run(is_duplicate=False, parent_params=None):
    if is_duplicate and parent_params:
        params = parent_params.copy()
        # Change one tiny thing to make it a near-duplicate, or leave it identical
        if random.random() > 0.5:
            params["batch_size"] = random.choice([32, 64, 128])
    else:
        params = {
            "model": random.choice(ARCHITECTURES),
            "optimizer": random.choice(OPTIMIZERS),
            "learning_rate": random.choice(LEARNING_RATES),
            "batch_size": random.choice([16, 32, 64, 128]),
            "epochs": random.choice([10, 50, 100]),
            "weight_decay": round(random.uniform(1e-5, 1e-2), 5)
        }

    status = random.choice(STATUSES)
    
    # Generate realistic metrics based on status
    metrics = {}
    if status == "completed":
        metrics["val_accuracy"] = round(random.uniform(0.70, 0.95), 4)
        metrics["val_loss"] = round(random.uniform(0.1, 1.5), 4)
        metrics["train_loss"] = round(random.uniform(0.05, metrics["val_loss"]), 4)
        rationale = f"Run finished successfully. Reached {metrics['val_accuracy']*100:.1f}% accuracy, looks stable."
    elif status == "failed":
        metrics["val_loss"] = float('inf') 
        metrics["train_loss"] = 999.9
        rationale = "Loss exploded to NaN around epoch 3. Probably LR is too high or gradient clipping is needed."
    else: # aborted
        metrics["val_accuracy"] = round(random.uniform(0.20, 0.40), 4)
        metrics["val_loss"] = round(random.uniform(1.5, 3.0), 4)
        rationale = "Aborted early. Validation loss was plateuing early on, didn't seem promising to continue."

    if is_duplicate and status == "completed":
        rationale = "Trying this config again to check for variance. " + rationale

    return {
        "config_params": params,
        "result_metrics": metrics,
        "status": status,
        "rationale": rationale,
        "experiment_name": "VisionBaseline-Alpha",
        "experiment_description": "Establishing baselines for vision architectures before trying custom attention.",
        "owner": "Alice",
        "thread_name": f"{params['model']}-exploration",
        "hypothesis": f"Using {params['model']} with {params['optimizer']} will yield better convergence.",
        "dataset_name_label": random.choice(DATASETS),
        "dataset_version": "v1.2",
        "gpu_hours": round(random.uniform(0.5, 24.0), 1),
        "wall_clock_seconds": random.randint(1800, 86400),
        "git_commit": hex(random.randint(0x1000000, 0xFFFFFFF))[2:],
    }

async def run_seed():
    logger.info("Configuring Cognee with Groq API...")
    cognee.config.llm_config = {
        "provider": os.getenv("LLM_PROVIDER", "groq"),
        "model": os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile"),
        "api_key": os.getenv("GROQ_API_KEY", ""),
    }
    
    # Non-destructive initialization
    try:
        await cognee.prune.prune_system(metadata=False)
    except Exception:
        pass

    logger.info("Generating synthetic run data...")
    runs = []
    
    # Generate 3 distinct runs
    for _ in range(3):
        runs.append(_generate_synthetic_run())
        
    # Generate 2 near/exact duplicate runs for Pre-flight Guard testing
    for i in range(2):
        runs.append(_generate_synthetic_run(is_duplicate=True, parent_params=runs[i]["config_params"]))
        
    logger.info(f"Total runs to ingest: {len(runs)}")
    
    successful = 0
    # Process sequentially
    for i, run in enumerate(runs):
        logger.info(f"Ingesting run {i+1}/{len(runs)}...")
        try:
            result = await remember_run(run)
            logger.info(f"  -> Success. node_id={result['node_id'][:12]}")
            successful += 1
            
            if i < len(runs) - 1:
                logger.info("  Waiting 10 seconds for rate limits...")
                time.sleep(10)
                
        except Exception as e:
            logger.error(f"  -> Failed to ingest run: {e}")
            if "429" in str(e) or "quota" in str(e).lower():
                logger.info("  Rate limit hit. Sleeping 30s...")
                time.sleep(30)

    logger.info(f"Seeding complete! Successfully ingested {successful}/{len(runs)} runs.")
    logger.info("You can now test the API endpoints.")

if __name__ == "__main__":
    if not os.getenv("GROQ_API_KEY"):
        logger.error("GROQ_API_KEY not found in environment. Please set it in .env first.")
        sys.exit(1)
        
    asyncio.run(run_seed())
