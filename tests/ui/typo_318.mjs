// 318: panel core against eight-role real export reference; --old must fail.
import fs from 'node:fs';
import vm from 'node:vm';
const [page, dir, plant] = process.argv.slice(2);
const blocks=[...fs.readFileSync(page,'utf8').matchAll(/<script(?: id="core")?>\n([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const c={atob:s=>Buffer.from(s,'base64').toString('binary'),Math,Float32Array,Float64Array,Uint8Array,Int32Array,Object,JSON,Date,TYPO_318_OLD:plant==='--old'};
c.window=c;c.globalThis=c;vm.createContext(c);vm.runInContext(blocks[0],c);vm.runInContext(blocks[1],c);
const TC=c.TC, ref=JSON.parse(fs.readFileSync(dir+'/reference.json'));
TC.loadJson(JSON.parse(fs.readFileSync(dir+'/fixture.json')));
let count=0,bad=[];const groups=new Set();
for(const sc of TC.T.scenes){
  const raw=ref[sc.pack+':'+sc.screen]; if(!raw) throw Error('missing reference '+sc.id);
  const m=TC.applyTypo(sc);
  for(const [kind,nodes] of Object.entries(m)){
    if(!['texts','nums','stat'].includes(kind))continue;
    for(const t of nodes){
      const carried=TC.T.groups.some(g=>TC.changed(g.id) && (g.carry||[]).includes(t.group));
      if(!t.group || (!TC.changed(t.group) && !carried))continue;
      const r=raw.find(q=>q.page===t.page && q.name===t.name && (kind==='texts'?q.type===3:kind==='nums'?q.type===4:q.type!==3 && q.type!==4)); if(!r)throw Error('no raw element '+sc.id+'/'+t.name);
      count++;groups.add(t.group);
      const dst=kind==='stat'?t.cur:t.dst;
      if(JSON.stringify(dst)!==JSON.stringify(r.dst))bad.push([sc.id,t.name,'dst',dst,r.dst]);
      if(kind==='texts' && !t.pix8 && t.font!==r.font)bad.push([sc.id,t.name,'font',t.font,r.font]);
      if(kind==='texts' && !!t.pix8!==!!r.pix8)bad.push([sc.id,t.name,'pix8',t.pix8,r.pix8]);
    }
  }
}
const required=['phone_stats','st_shop_stars','shop_stats','save_slots','brief_btn','tut_text','tut_board','hud_nums','hud_small','hud_busted','st_ticket'];
for(const g of required) if(!groups.has(g))bad.push(['missing role coverage',g]);
if(ref._robContinue){
  TC.loadJson(JSON.parse(fs.readFileSync(dir+'/../ui_typo.json')));
  const t=TC.applyTypo(TC.T.scenes.find(s=>s.id==='brief')).texts.find(t=>t.name==='Continue');
  for(const k of ['font','pix8','dst']) if(JSON.stringify(t[k])!==JSON.stringify(ref._robContinue[k]))bad.push(['explicit Rob Continue',k,t[k],ref._robContinue[k]]);
}
if(count===0)bad.push(['zero coverage']);
console.log(JSON.stringify(bad.slice(0,12)));
console.log(`${bad.length?'FAIL':'PASS'} panel/export parity: ${count} elements, ${groups.size} groups, ${bad.length} differences`);
process.exit(bad.length?1:0);
