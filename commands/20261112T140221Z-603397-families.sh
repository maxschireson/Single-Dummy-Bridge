# boxctl: timeout=200
#!/bin/bash
P=$HOME/work/p41; PY=$HOME/work/venv/bin/python
nice -n 19 $PY - <<'PYEOF'
import numpy as np, gzip, os, hashlib
P = os.path.expanduser('~/work/p41')
with np.load(f'{P}/data/gen7_v41_train.npz') as z:
    fam = sorted(set(z['family'].tolist()))
text = '\n'.join(fam) + '\n'
os.makedirs(f'{P}/lists', exist_ok=True)
with gzip.open(f'{P}/lists/v41_training_families.txt.gz', 'wt') as f:
    f.write(text)
print(len(fam), 'families', hashlib.sha256(text.encode()).hexdigest())
PYEOF
W=$HOME/work/p41lists; rm -rf $W; mkdir -p $W && cd $W && git init -q
git config core.sshCommand "ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
git config user.name "p41 box (azure5)"; git config user.email "boxctl-azure5@invalid"
cp $P/lists/v41_training_families.txt.gz .
printf '%s\n' "# The deal families policy v4.1 was trained on" "" "\`v41_training_families.txt.gz\`: one family hash a line, sorted; every deal of the training set \`gen7_v41_train.npz\` (boards fetched up to 03:59 UTC on 12 November 2026; see \`training/policy-v4.1-20261112/\` on \`transfer/gen7-policy-v4.1-20261112\`). A net trained on that set (v4.1 and the five-epoch and 768-wide nets of the same run) must not be scored on these deals." > README.md
git add -A && git commit -q -m "The deal families policy v4.1 was trained on" && git push -q -f git@github.com:maxschireson/Single-Dummy-Bridge.git HEAD:refs/heads/transfer/gen7-policy-v4.1-families-20261112 2>&1 | grep -v "^remote:" | tail -2
ls -la; uptime | cut -c1-70
