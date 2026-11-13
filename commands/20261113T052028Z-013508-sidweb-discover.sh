# boxctl: timeout=600
# boxctl: timeout=600
# sidweb discovery (read-only): runtime, run manifests with 7s-32, network exposure. Prints no IPs or ids.
set -u
echo "== host"; hostname; python3 --version; nproc; free -g | head -2
echo "== ~/work"; ls ~/work 2>/dev/null
echo "== venv"
for v in ~/work/venv; do [ -x $v/bin/python ] && $v/bin/python -c "import sys,numpy;print('py',sys.version.split()[0],'numpy',numpy.__version__)"; $v/bin/python -c "import tensorflow as tf;print('tf',tf.__version__)" 2>&1 | tail -1; done
echo "== manifests"
for m in ~/work/runs/*/manifest.json ~/work/*/runs/*/manifest.json; do [ -f "$m" ] || continue
python3 - "$m" <<'PY'
import json,sys
m=json.load(open(sys.argv[1])); b=m.get('bots',{})
print(sys.argv[1], ' '.join(sorted(b)))
PY
done
echo "== 7s-32 spec (first found)"
python3 - <<'PY'
import json,glob,os
for p in sorted(glob.glob(os.path.expanduser('~/work/runs/*/manifest.json'))):
    m=json.load(open(p)); b=m.get('bots',{})
    if '7s-32' in b:
        s=b['7s-32']; print(p)
        print(json.dumps({k:v for k,v in s.items() if k!='gen7'},indent=1)[:6000])
        print('gen7 keys', sorted(s.get('gen7',{})))
        print('common_bidder', m.get('common_bidder'))
        break
PY
echo "== network"
python3 - <<'PY'
import json,urllib.request
req=urllib.request.Request('http://169.254.169.254/metadata/instance?api-version=2021-02-01',headers={'Metadata':'true'})
try:
    d=json.load(urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=5))
    c=d['compute']; print('vm',c.get('name'),c.get('vmSize'),c.get('location'))
    for nic in d['network']['interface']:
        for a in nic['ipv4']['ipAddress']: print('nic public ip present:',bool(a.get('publicIpAddress')))
except Exception as e: print('imds error',e)
PY
ss -ltn 2>/dev/null | awk 'NR>1{print "listen",$4}' | sort -u
sudo -n ufw status 2>&1 | head -3
echo "== azure cli"
if command -v az >/dev/null; then
  az account show --query state -o tsv 2>&1 | head -1
  az vm list -d -o json 2>/dev/null | python3 -c "
import json,sys
for v in json.load(sys.stdin): print('vm',v['name'],v['hardwareProfile']['vmSize'],'public' if v.get('publicIps') else 'no-public','dns' if v.get('fqdns') else 'no-dns')"
  az network nsg list -o json 2>/dev/null | python3 -c "
import json,sys
for n in json.load(sys.stdin):
    print('nsg',n['name'],'nics',len(n.get('networkInterfaces') or []),'subnets',len(n.get('subnets') or []))
    for r in sorted(n.get('securityRules',[]),key=lambda r:r['priority']):
        src=r.get('sourceAddressPrefix') or ','.join(r.get('sourceAddressPrefixes') or [])
        src=src if src in ('*','Internet','VirtualNetwork','AzureLoadBalancer') else 'restricted'
        print('  rule',r['priority'],r['direction'],r['access'],r.get('destinationPortRange') or r.get('destinationPortRanges'),'src',src)"
else echo "no az"; fi
