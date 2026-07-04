# Groundhog demo — notebook + pages

A small, **real** end-to-end exercise of Groundhog: it trains an actual
(numpy-only) softmax classifier across a few configs and shows the memory fill
up — Pre-flight Guard, semantic recall, derived insights, real artifacts, and
the W&B round-trip — all scoped to one isolated project.

Nothing here is faked: `train_lib.py` trains a multinomial logistic model with
minibatch SGD + L2 weight decay on a synthetic 3-class dataset, so metrics
genuinely respond to `lr` / `batch_size` / `weight_decay` / `epochs`, and each
run writes real output files (model weights, metrics.json, training log,
predictions) that Groundhog scans into Artifact nodes.

## Prereqs

The three services running (see repo README): cognee `:8010`, backend `:8000`,
frontend `:5173`. The demo talks to the backend at `http://localhost:8000`
(override with `GROUNDHOG_API_URL`).

## The shared project

`_bootstrap.py` creates one project (**"Blobs3 SGD Demo"**) and caches its
`project_id` in `demo/.demo_project.json`. The notebook and every page reuse
that same project, so all runs land in one isolated memory.

## Pages (run in order, from the repo root)

```bash
python demo/pages/01_first_sweep.py        # 4-point lr sweep: real runs + dataset + artifacts
python demo/pages/02_preflight_guard.py    # re-checks configs -> guard blocks repeats (noise-tolerant)
python demo/pages/03_query_and_insights.py # semantic query + derived insights
python demo/pages/04_wandb_roundtrip.py    # app->W&B mirror + W&B->app sync  (needs W&B creds)
```

## Notebook

```bash
jupyter notebook demo/notebook_demo.ipynb   # or: jupyter lab
```

Run the cells top to bottom. Re-run the sweep cell to watch the Pre-flight Guard
flag configs you already tried. Uses the `%groundhog_hypothesis` /
`%groundhog_decision` magics to write the *why* into memory.

## W&B round-trip

Set these before running page 4 (or before launching the notebook) — the
bootstrap attaches them to the project automatically:

```bash
export WANDB_ENTITY=your-wandb-username   # optional
export WANDB_PROJECT=groundhog-demo
export WANDB_API_KEY=...
```

Then app runs mirror out to W&B on every `remember()`, and
`04_wandb_roundtrip.py` also pulls W&B runs back into the project's memory.
