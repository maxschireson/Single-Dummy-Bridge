'use strict';
window.ReplayCommon = (() => {
  const FEED = 'https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-feed/arena/replays/catalog.json';
  const labels = {A:'Gen 3', B:'Gen 3-early', C:'Gen 2'};
  const $ = id => document.getElementById(id);
  const pairLabel = p => labels[p[0]] + ' vs ' + labels[p[1]];
  const signed = n => n > 0 ? '+' + n : String(n);
  const date = epoch => new Date(epoch * 1000).toLocaleString();
  const el = (tag, text, cls) => {const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  async function get(url) {const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);return r.json();}
  async function catalog() {
    const urls=[new URL('catalog.json',location.href).href];
    if(location.hostname !== '127.0.0.1' && location.hostname !== 'localhost') urls.push(FEED);
    const results=await Promise.allSettled(urls.map(get)); const map=new Map();
    results.forEach((r,i)=>{if(r.status==='fulfilled'&&r.value.schema==='bridge-replay-catalog-v1')
      for(const c of r.value.cohorts){if(!/^[a-f0-9]{64}$/.test(c.id))continue;
        const entry={...c,indexURL:new URL(c.index_url,urls[i]).href};
        if(!map.has(c.id)||c.count>=map.get(c.id).count)map.set(c.id,entry);}});
    if(!map.size)throw Error('Play records are temporarily unavailable. Please retry.');
    return [...map.values()];
  }
  function formatCard(card) {return ({S:'♠',H:'♥',D:'♦',C:'♣'})[card[0]]+(card[1]==='T'?'10':card[1]);}
  return {$,pairLabel,signed,date,el,get,catalog,labels,formatCard};
})();
