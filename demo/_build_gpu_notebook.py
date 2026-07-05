"""Generate demo/notebook_gpu.ipynb — a real 10-run PyTorch/CUDA sweep."""
import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
nb = nbf.v4.new_notebook()
md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
cells = []

cells.append(md(
    "# Groundhog — GPU sweep (PyTorch on CUDA)\n"
    "A **real** 10-run hyperparameter sweep: a small CNN on FashionMNIST, trained "
    "on the GPU, with a wide hyperparameter space so Groundhog derives clear "
    "insights (which knob actually moves accuracy) and tracks realistic "
    "**GPU-hours** from wall-clock. Every run records config, metrics, dataset, "
    "artifacts (checkpoint + logs), and cost."
))

cells.append(code(
    "import os, sys, json, time, urllib.request\n"
    "ROOT = os.path.abspath(os.path.join(os.getcwd(), '..')) if os.path.basename(os.getcwd())=='demo' else os.getcwd()\n"
    "if os.path.basename(os.getcwd()) != 'demo':\n"
    "    # allow running from repo root too\n"
    "    ROOT = os.getcwd()\n"
    "sys.path.insert(0, os.path.join(ROOT, 'sdk')); sys.path.insert(0, ROOT)\n"
    "import groundhog\n"
    "from demo.train_torch import train_and_evaluate, DATASET_INFO\n"
    "import torch\n"
    "print('CUDA available:', torch.cuda.is_available(), '|', (torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'))\n"
    "\n"
    "BACKEND = os.getenv('GROUNDHOG_API_URL', 'http://localhost:8000')\n"
    "SIG = ['lr','batch_size','optimizer','weight_decay','dropout','conv_channels','hidden_dim','activation','epochs']\n"
    "CACHE = os.path.join(ROOT, 'demo', '.gpu_project.json')\n"
    "\n"
    "def _http(method, path, payload=None):\n"
    "    data = json.dumps(payload).encode() if payload is not None else None\n"
    "    req = urllib.request.Request(BACKEND.rstrip('/')+path, data=data, method=method, headers={'Content-Type':'application/json'})\n"
    "    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read().decode())\n"
    "\n"
    "def ensure_project():\n"
    "    if os.path.exists(CACHE):\n"
    "        pid = json.load(open(CACHE))['project_id']\n"
    "        try: _http('GET', f'/api/projects/{pid}'); return pid\n"
    "        except Exception: pass\n"
    "    pid = _http('POST','/api/projects',{'name':'FashionMNIST CNN Sweep','significant_keys':SIG})['project_id']\n"
    "    json.dump({'project_id':pid}, open(CACHE,'w'))\n"
    "    print('created project', pid); return pid\n"
    "\n"
    "project_id = ensure_project()\n"
    "# optional: attach W&B creds from env so runs mirror out to W&B\n"
    "if os.getenv('WANDB_PROJECT') and os.getenv('WANDB_API_KEY'):\n"
    "    _http('POST', f'/api/projects/{project_id}/wandb', {'entity':os.getenv('WANDB_ENTITY'),'project':os.getenv('WANDB_PROJECT'),'api_key':os.getenv('WANDB_API_KEY')})\n"
    "    print('W&B attached')\n"
    "groundhog.init(project_id=project_id, base_url=BACKEND, experiment='fmnist_cnn_sweep')\n"
    "print('project:', project_id)"
))

cells.append(md("### Dataset (real, versioned input)"))
cells.append(code("DATASET_INFO"))

cells.append(md("### The sweep — 10 configs across a wide hyperparameter space\n"
                "Spans learning rate (5 orders of magnitude of effect), optimizer, capacity, "
                "dropout, and weight decay — so parameter-sensitivity has a clear signal."))
cells.append(code(
    "BASE = dict(batch_size=128, weight_decay=0.0, dropout=0.0, conv_channels=32, hidden_dim=128, activation='relu', epochs=2, seed=0)\n"
    "SWEEP = [\n"
    "    {**BASE, 'lr':1e-3, 'optimizer':'adam'},\n"
    "    {**BASE, 'lr':3e-3, 'optimizer':'adam'},\n"
    "    {**BASE, 'lr':3e-4, 'optimizer':'adam'},\n"
    "    {**BASE, 'lr':1e-2, 'optimizer':'adam'},\n"
    "    {**BASE, 'lr':3e-2, 'optimizer':'adam'},\n"
    "    {**BASE, 'lr':1e-3, 'optimizer':'adam', 'dropout':0.25},\n"
    "    {**BASE, 'lr':1e-3, 'optimizer':'adam', 'conv_channels':48, 'hidden_dim':192},\n"
    "    {**BASE, 'lr':1e-3, 'optimizer':'adam', 'weight_decay':5e-4},\n"
    "    {**BASE, 'lr':5e-3, 'optimizer':'sgd'},\n"
    "    {**BASE, 'lr':1e-1, 'optimizer':'sgd'},\n"
    "]\n"
    "len(SWEEP)"
))

cells.append(md("### Run the sweep\n"
                "Each run: Pre-flight Guard → train on GPU → record the full picture "
                "(config, metrics, dataset, checkpoint artifact, **GPU-hours**)."))
cells.append(code(
    "EXPERIMENT = 'fmnist_cnn_sweep'\n"
    "total_gpu_hours = 0.0\n"
    "for i, cfg in enumerate(SWEEP, 1):\n"
    "    if groundhog.check(cfg, experiment=EXPERIMENT).get('already_tried'):\n"
    "        print(f'[{i:2d}/10] already tried lr={cfg[\"lr\"]} {cfg[\"optimizer\"]} — skipping'); continue\n"
    "    out = os.path.join('outputs', EXPERIMENT, f'run_{i:02d}')\n"
    "    m = train_and_evaluate(cfg, out_dir=out)\n"
    "    total_gpu_hours += m['gpu_hours']\n"
    "    groundhog.remember(config=cfg, metrics=m, experiment=EXPERIMENT, dataset=DATASET_INFO,\n"
    "                       output_dir=out, gpu_hours=m['gpu_hours'], wall_clock_seconds=m['wall_clock_seconds'],\n"
    "                       hypothesis=f\"cfg #{i}: lr={cfg['lr']} opt={cfg['optimizer']}\",\n"
    "                       rationale=f\"sweep run {i}: val_acc={m['val_accuracy']} in {m['wall_clock_seconds']}s on {m['device']}\")\n"
    "    print(f\"[{i:2d}/10] lr={cfg['lr']:<6} {cfg['optimizer']:<4} -> val_acc={m['val_accuracy']:.4f} \"\n"
    "          f\"loss={m['val_loss']:.3f} | {m['wall_clock_seconds']:.1f}s | {m['gpu_hours']*3600:.1f} gpu-sec\")\n"
    "print(f'\\nTotal GPU-hours across sweep: {total_gpu_hours:.5f} h ({total_gpu_hours*3600:.0f} GPU-seconds)')"
))

cells.append(md("### Ask the memory"))
cells.append(code(
    "print(groundhog.query('Which learning rate and optimizer gave the best val_accuracy on FashionMNIST, and which hyperparameter mattered most?'))"
))

cells.append(md("### Derived insights — clear signal from 10 runs"))
cells.append(code(
    "ins = json.load(urllib.request.urlopen(f'{BACKEND}/api/insights?project_id={project_id}', timeout=60))\n"
    "print('n_runs:', ins['n_runs'], '| completed:', ins['n_completed'])\n"
    "print('summary:', ins['summary'])\n"
    "print('\\nparameter sensitivity (most -> least impactful):')\n"
    "for s in ins['parameter_sensitivity']:\n"
    "    print(f\"  {s['parameter']:<14} impact={s['sensitivity']:<8} best={s['best_value']}  ({s['metric']})\")"
))

cells.append(md("### Cost summary (GPU-hours tracked per run)"))
cells.append(code(
    "runs = json.load(urllib.request.urlopen(f'{BACKEND}/api/runs/?project_id={project_id}', timeout=30))['runs']\n"
    "tot = sum((r.get('gpu_hours') or 0) for r in runs)\n"
    "print(f'{len(runs)} runs, total {tot:.5f} GPU-hours ({tot*3600:.0f} GPU-seconds)')\n"
    "for r in sorted(runs, key=lambda r: -(r.get('metrics',{}).get('val_accuracy') or 0))[:3]:\n"
    "    print(f\"  best: val_acc={r['metrics'].get('val_accuracy')} lr={r['config'].get('lr')} {r['config'].get('optimizer')} gpu_h={r.get('gpu_hours')}\")"
))

cells.append(md("Open **http://localhost:5173**, select **FashionMNIST CNN Sweep**, and see the runs, "
                "the metric-over-runs chart, parameter sensitivity, and GPU-hour cost."))

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}
out = os.path.join(HERE, "notebook_gpu.ipynb")
nbf.write(nb, out)
print("wrote", out)
