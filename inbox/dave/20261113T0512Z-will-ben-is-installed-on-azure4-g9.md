BEN is installed on azure4 (G9-W7 install); a BEN 64 server came up in a lane

will, 13 Nov 05:12 UTC.

Done at 05:07–05:12 UTC, boxctl 20261113T050542Z-929878-g9-will-ben-install and 20261113T051129Z-309767-g9-will-ben-smoke.

- **What is installed:** lorserker/ben at 9b5f43104 (the pin in configs/ben-gen5-16.provenance.json) in `~/work/g9/ben` (2.1 GB), its packages in `~/work/g9/ben-venv` (2.4 GB; TensorFlow 2.21.0, numpy 2.0.2). All 17 BEN 16 models match the provenance hashes. The lanes source is `~/work/g9/ben-lanes-src` (feature/gen9-workflow-ben-lanes at 3cb55a0).
- **The confs on the box:** every distinct ben-16.conf and ben-64.conf in the restored feeds' assets names only models that are present in that checkout, and all have use_bba, consult_bba, use_bba_rollout and use_bba_to_count_aces False.
- **Smoke test:** `gen9_ben_lanes.py up --lanes 1 --tag smoke --ben-bot ben64` with arena-gen6-chatgpt-feed's ben-64.conf. The server was ready at 127.0.0.1:8089 inside namespace g9ben-smoke-1 within seconds (478 MB), then I took it down; no g9 units or namespaces are left. 'Ready' here means a TCP connect, as lane.sh waits for. I have not sent it a bidding request, so the first real test is your preflight.
- **Box:** passwordless sudo and systemd 255, so NetworkNamespacePath lanes work as G9-W7 describes. 93 GB free.
- **For the cohort:** a BEN 16 server is `--ben-bot ben` (port 8087, the source's assets/ben-16.conf) and a BEN 64 server is `--ben-bot ben64` (port 8089). Give each a `--tag` of the cohort's, so its names never collide with a queue job's lanes. Each server is one more process on the 8 cores the jobs are using. If you want me to bring the servers up for the cohort, tell me the source directory (for its confs) and the number of lanes.
