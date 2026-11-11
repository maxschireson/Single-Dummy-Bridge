'use strict';
window.ReplayCommon = (() => {
  const FEED = 'https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-feed/arena/replays/catalog.json';
  const labels = {'5RZ32':'Gen 5RZ (32)','5RZ192':'Gen 5RZ (192)','5R32':'Gen 5R (32)','5R192':'Gen 5R (192)','5':'Gen 5 (192)','5-32':'Gen 5 (32)',ben:'BEN (16)',P:'Gen 4p',Q:'Gen 4b',A:'Gen 3.5', B:'Gen 3', C:'Gen 2',4:'Gen 4','4p':'Gen 4p','4b':'Gen 4b',3:'Gen 3',2:'Gen 2',1:'Gen 1'};
  const $ = id => document.getElementById(id);
  const pairMembers = p => p.includes('~')?p.split('~'):[...p];
  const pairLabel = p => pairMembers(p).map(k=>labels[k]||k).join(' vs ');
  const signed = n => n==null?'—':n > 0 ? '+' + n : String(n);
  const date = epoch => new Date(epoch * 1000).toLocaleString();
  const el = (tag, text, cls) => {const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  async function get(url) {url=new URL(url,location.href);if(url.hostname==='raw.githubusercontent.com')url.searchParams.set('v',Math.floor(Date.now()/30000));const r=await fetch(url.href,{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const data=await r.json();if(data.schema==='bridge-replay-index-v1'&&Array.isArray(data.record_shards)){data.records=(await Promise.all(data.record_shards.map(p=>get(new URL(p,url).href)))).flat();}return data;}
  async function catalog() {
    const urls=['https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-gen6-medium-ben-feed/arena/replays/catalog.json','https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-gen5rz-ben-feed/arena/replays/catalog.json','https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-gen5rz-feed/arena/replays/catalog.json','https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-gen5r-feed/arena/replays/catalog.json','https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-gen5-codex-32-feed/arena/replays/catalog.json','https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-gen5-codex-feed/arena/replays/catalog.json','https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-primary-components-feed/arena/replays/catalog.json',new URL('catalog.json',location.href).href,'https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-recovery-feed/arena/replays/catalog.json'];
    if(location.hostname !== '127.0.0.1' && location.hostname !== 'localhost') urls.push(FEED,'https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-local-feed/arena/replays/catalog.json','https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/arena-components-feed/arena/replays/catalog.json');
    const results=await Promise.allSettled(urls.map(get)); const map=new Map();
    results.forEach((r,i)=>{if(r.status==='fulfilled'&&r.value.schema==='bridge-replay-catalog-v1')
      for(const c of r.value.cohorts){if(!/^[a-f0-9]{64}$/.test(c.id))continue;
        const entry={...c,indexURL:new URL(c.index_url,urls[i]).href};
        if(!map.has(c.id)||c.count>=map.get(c.id).count)map.set(c.id,entry);}});
    if(!map.size)throw Error('Play records are temporarily unavailable. Please retry.');
    return [...map.values()];
  }
  function formatCard(card) {return ({S:'♠',H:'♥',D:'♦',C:'♣'})[card[0]]+(card[1]==='T'?'10':card[1]);}
  return {$,pairMembers,pairLabel,signed,date,el,get,catalog,labels,formatCard};
})();
