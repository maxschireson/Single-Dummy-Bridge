#!/usr/bin/env bash
# Runs the lines of a job file one after another, each through run.sh:  chain.sh JOBS.txt
# A line is: NAME PAIR SEED FIRST DEALS WORKERS [options]. Lines starting with # are skipped. A failed job does not
# stop the chain. Every job resumes, so the unit may be restarted at any time.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
while read -r line; do
  case "$line" in ''|\#*) continue ;; esac
  # shellcheck disable=SC2086
  bash "$HERE/run.sh" $line || echo "$(date -u +%FT%TZ) job failed: $line" >> "$HOME/work/loop/runs.log"
done < "$1"
