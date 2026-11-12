# boxctl: timeout=60
python3 -c "import json,os; c=json.load(open(os.path.expanduser(\"~/.boxctl/config.json\"))); print({k:(v if k in (\"repo\",\"repo_url\",\"url\",\"remote\",\"branch_prefix\",\"box\") else type(v).__name__) for k,v in c.items()})"; ls ~/.boxctl; git -C ~/.boxctl/repo remote -v 2>/dev/null | head -2; ls ~/.ssh
