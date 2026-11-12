# boxctl: timeout=700
# boxctl: timeout=600
# plan session: build the claim finder (sure_cpp, from research/sure-trick-table-20261112) into ~/work/plan/bin. Light:
# one compile, one check line. Touches nothing else.
set -uo pipefail
P=$HOME/work/plan; mkdir -p "$P/bin" "$P/surebuild"
cd "$P/surebuild"
[ -d .git ] || git init -q .
git remote get-url origin >/dev/null 2>&1 || git remote add origin "$(git -C "$P/src" remote get-url origin)"
export GIT_SSH_COMMAND="$(git -C "$P/src" config core.sshCommand 2>/dev/null || echo ssh)"
git fetch -q --depth 1 origin research/sure-trick-table-20261112 && git show FETCH_HEAD:experiments/sure_tricks/sure.cpp > "$P/bin/sure.cpp" && git log -1 --format='source %h %s' FETCH_HEAD | cut -c1-100
which g++ && g++ --version | head -1
g++ -O2 -march=native -std=c++17 -o "$P/bin/sure_cpp" "$P/bin/sure.cpp" && ls -la "$P/bin/sure_cpp"
echo "N3 4 0 1fff 0 0 0 0 0 0" | "$P/bin/sure_cpp" --keep | cut -c1-200 || true
nproc; uptime
