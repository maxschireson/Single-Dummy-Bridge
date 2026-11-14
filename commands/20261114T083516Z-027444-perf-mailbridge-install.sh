# boxctl: timeout=300
# boxctl: timeout=300
# perf session: install mailbridge (ops/mailbridge, branch perf/stu-20261114). Tiny: one process,
# polls one mailbox each minute; nothing under ~/work is touched. See box/coordination.
set -euo pipefail
curl -fsSL https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/2bf10e5c495783590c327a62e79368c5e89db2ab/ops/mailbridge/install.sh -o /tmp/mailbridge-install.sh
bash /tmp/mailbridge-install.sh 2bf10e5c495783590c327a62e79368c5e89db2ab azure1
