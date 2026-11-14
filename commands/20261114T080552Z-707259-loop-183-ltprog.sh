# boxctl: timeout=60
# boxctl: timeout=60
W=$HOME/work/loop
echo "records $(ls $W/pub/usbc/*.json.gz | wc -l) | lt2 $(ls $W/pub/usbc-lt/*.lt2.json.gz 2>/dev/null | wc -l) | units $(systemctl is-active loop-usbc loop-usbc25 loop-usbclt 2>/dev/null | tr '\n' ' ')"; tail -n 2 $W/usbc25.log 2>/dev/null | cut -c1-140
