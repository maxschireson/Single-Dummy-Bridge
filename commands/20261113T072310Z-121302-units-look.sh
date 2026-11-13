# boxctl: timeout=30
date -u +%T; for u in arena-ben@1 arena-ben-publish@1 ben-server@1; do echo "== $u"; systemctl cat $u 2>/dev/null | grep -v "^#" | grep -E "WorkingDirectory|ExecStart|EnvironmentFile|Environment=" | cut -c1-230; done; cat $HOME/work/lanes/1.env | cut -c1-200; ls $HOME/work | tr '\n' ' '
