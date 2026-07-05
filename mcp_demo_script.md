# Groundhog MCP Demo Script - Step-by-Step

This script is designed for you to copy-paste each prompt one by one to demonstrate the full power of the Groundhog MCP tools. We will use the project name **`mcp_demo_n`** for the demonstration.

---

### Step 1: Pre-flight Check (Check Config)
*Demonstrates how the agent checks if an experiment has already been run before wasting GPU time.*

**Copy and paste this:**
> "I want to start a new run for the project `mcp_demo_n`. Here is my config: `{"model": "ResNet50", "optimizer": "Adam", "learning_rate": 0.01, "batch_size": 64}`. Can you use your tools to check if we have already tried this configuration?"

*(Tool triggered: `mcp_groundhog_check_config`)*

---

### Step 2: Logging a Run (Remember)
*Demonstrates how the agent autonomously logs completed or failed runs with full context.*

**Copy and paste this:**
> "Okay, I just ran that configuration for `mcp_demo_n`. It completed successfully! Please remember this run into the database. Here is the data: 
> Config: `{"model": "ResNet50", "optimizer": "Adam", "learning_rate": 0.01, "batch_size": 64}`
> Metrics: `{"val_acc": 0.82, "val_loss": 0.45}`
> Rationale: 'Testing a higher learning rate with Adam to see if convergence speeds up.'
> Artifacts: `[{"type": "checkpoint", "path": "/models/mcp_demo_n/run_01_best.pt"}]`"

*(Tool triggered: `mcp_groundhog_remember`)*

---

### Step 3: Fetching History
*Demonstrates fetching a deterministic list of recent experiments.*

**Copy and paste this:**
> "Can you fetch the recent run history for the `mcp_demo_n` project so I can see what we've done recently?"

*(Tool triggered: `mcp_groundhog_history`)*

---

### Step 4: Surfacing Insights
*Demonstrates the system's ability to analyze parameter sensitivity and identify the best configuration.*

**Copy and paste this:**
> "Fetch the derived insights for `mcp_demo_n`. Tell me which hyperparameters are actually moving the needle and what the best configuration has been so far."

*(Tool triggered: `mcp_groundhog_insights`)*

---

### Step 5: Explaining & Finding (Deep Dive)
*Demonstrates explaining a specific run in plain English and locating its files without spelunking through folders.*

**Copy and paste this:**
> "Can you explain the best run from the `mcp_demo_n` history in plain English? And then use your tools to find the path to its best model checkpoint artifact."

*(Tools triggered: `mcp_groundhog_explain`, `mcp_groundhog_find`)*

---

### Step 6: The "What-If" Semantic Query
*Demonstrates the powerful graph-based memory by asking a complex, open-ended parameter question.*

**Copy and paste this:**
> "I'm thinking about changing the `learning_rate` to `0.5` for my next run in `mcp_demo_n`. Based on our experiment memory and similar results, can you query the database and tell me if this is a good idea or a bad idea?"

*(Tool triggered: `mcp_groundhog_query`)*
