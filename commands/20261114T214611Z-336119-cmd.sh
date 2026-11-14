# boxctl: timeout=60
W=$HOME/work/loop; cat $W/pub/train-r4c/stu_test.npz.sha256; $W/venv/bin/python -c "import numpy as np,sys; z=np.load(sys.argv[1]); k=list(z.keys()); print(len(z[k[0]]), "rows", k[:10]); d=z["deal"] if "deal" in z else None; print("deals", len(set(d.tolist())) if d is not None else "?")" $W/pub/train-r4c/stu_test.npz
