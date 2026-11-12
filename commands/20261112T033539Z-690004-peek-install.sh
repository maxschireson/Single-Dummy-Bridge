# boxctl: timeout=60
echo "ben-install: $(systemctl is-active ben-install)"; cat $HOME/work/ben-setup/install.log 2>/dev/null | cut -c1-230 | tail -30
