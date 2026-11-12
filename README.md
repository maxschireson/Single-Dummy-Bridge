# BEN lanes on the Azure boxes (copies of the operator's box scripts, 12 November 2026)

For Gen 9 (will's question on the board, 07:54 UTC). These are the scripts that ran on azure2 and azure3; they are
copies for reading and reuse, not a source branch.

- `ben-install.boxctl.sh`: a boxctl command that installs the BEN server: `lorserker/ben` at `9b5f431` (the models come
  with that checkout and are checked against `configs/ben-gen5-16.provenance.json`), its own venv from
  `configs/ben-round5-runtime-requirements.txt`, then a server start and one bid request. On azure3 it took under two
  minutes (03:32:58 to 03:34:49 UTC). Sizes there: `~/work/ben` 2.9 GB, `~/work/ben-venv` 2.4 GB. A server holds about
  0.8 GB when it starts and 1.1 to 1.2 GB after four hours (BEN (64) profile).
- `lane.sh`: the Gen 7.0 lane tool (`units | plan | prepare LANE | up LANE | preflight LANE | records LANE | start LANE |
  status`). `cmd_units` writes the systemd templates: `benlane-netns@N` (a private network namespace with loopback up),
  `ben-server@N` (the server inside it, `NetworkNamespacePath=/run/netns/benlane-N`), `arena-ben@N` and
  `arena-ben-publish@N`. `cmd_up` starts the namespace and server and waits for the port. Each lane's server and client
  share a namespace, so every lane reaches its own server at the same `127.0.0.1:PORT` that the bot spec pins.
- `lane71f.sh`: the Gen 7.1 version now running on azure3 (deals v4.1 was not trained on, `--exclude-families`).
- `lane-recycle.boxctl.sh`: the memory supervisor. A lane's collector worker grows by about 24 MB a board; the
  supervisor restarts a lane the graceful way at 1.9 GB.

There is no box-to-box SSH or shared disk: each box holds only its GitHub deploy key. Build on azure4 with the install
command (it needs `~/work/sdb-gen7-arena` or another checkout for the provenance file; change `SRC` in it).
