"""Generate demo/notebook_demo.ipynb (lightweight, real multi-run demo)."""
import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
nb = nbf.v4.new_notebook()
md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
cells = []

cells.append(md(
    "# Groundhog — notebook demo\n"
    "A lightweight, **real** experiment loop: we train a small softmax classifier "
    "across a few configs and watch Groundhog memory fill up — Pre-flight Guard, "
    "semantic recall, and derived insights — all scoped to one project.\n\n"
    "Prereqs: the 3 services running (cognee :8010, backend :8000, frontend :5173)."
))

cells.append(code(
    "import os, sys\n"
    "sys.path.insert(0, os.path.dirname(os.getcwd()) if os.path.basename(os.getcwd())=='pages' else os.getcwd())\n"
    "# make sure repo root is importable so `demo` package + sdk resolve\n"
    "ROOT = os.path.abspath(os.path.join(os.getcwd(), '..'))\n"
    "sys.path.insert(0, ROOT)\n"
    "from demo._bootstrap import init, BACKEND\n"
    "from demo.train_lib import train_and_evaluate, DATASET_INFO\n"
    "import groundhog\n"
    "\n"
    "project_id = init(experiment='blobs3_notebook')\n"
    "print('connected to project:', project_id)"
))

cells.append(md("### Register the Groundhog notebook magics\n"
                 "`%groundhog_hypothesis` and `%groundhog_decision` write the *why* "
                 "straight into project memory."))
cells.append(code(
    "get_ipython().run_line_magic('load_ext', 'connectors.jupyter_magic')"
))

cells.append(md("### Dataset (proper, versioned input)"))
cells.append(code("DATASET_INFO"))

cells.append(md("### Hypothesis → memory"))
cells.append(code(
    "%groundhog_hypothesis A little weight decay should improve val_accuracy on blobs3 without hurting convergence."
))

cells.append(md("### Run a small weight-decay sweep\n"
                "`groundhog.run(...)` runs the Pre-flight Guard on enter and auto-logs "
                "metrics + wall-clock on exit. Re-running this cell should show the guard "
                "flag configs you already tried."))
cells.append(code(
    "EXPERIMENT = 'blobs3_notebook'\n"
    "for wd in (0.0, 1e-3, 1e-2):\n"
    "    cfg = {'model':'softmax','optimizer':'sgd','lr':0.1,'batch_size':32,'weight_decay':wd,'epochs':20}\n"
    "    with groundhog.run(config=cfg, experiment=EXPERIMENT) as r:\n"
    "        if r.already_tried:\n"
    "            print(f'wd={wd}: already tried -> {r.prior_metrics}; skipping'); r.skip()\n"
    "        else:\n"
    "            out = os.path.join('outputs', EXPERIMENT, f'wd_{wd}')\n"
    "            m = train_and_evaluate(cfg, out_dir=out)\n"
    "            r.log(**m)\n"
    "            print(f'wd={wd}: val_acc={m[\"val_accuracy\"]} val_loss={m[\"val_loss\"]}')"
))

cells.append(md("### Record a decision"))
cells.append(code(
    "%groundhog_decision Keeping weight_decay small (<=1e-3); 1e-2 underfits blobs3."
))

cells.append(md("### Ask the memory"))
cells.append(code(
    "print(groundhog.query('Across the notebook runs, which weight_decay gave the best val_accuracy and why?'))"
))

cells.append(md("### What the memory learned (derived insights)"))
cells.append(code(
    "import json, urllib.request\n"
    "url = f'{BACKEND}/api/insights?project_id={project_id}'\n"
    "ins = json.load(urllib.request.urlopen(url, timeout=60))\n"
    "print('summary:', ins.get('summary'))\n"
    "for s in ins.get('parameter_sensitivity', [])[:5]:\n"
    "    print(f\"  {s['parameter']}: impact={s['sensitivity']} best={s['best_value']}\")"
))

cells.append(md("Open the dashboard at **http://localhost:5173** and select this project — "
                "the runs, artifacts, and insights you just created are all there."))

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}
out = os.path.join(HERE, "notebook_demo.ipynb")
nbf.write(nb, out)
print("wrote", out)
