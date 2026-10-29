import fs from 'node:fs';
const [endpoint,url,widthText,out] = process.argv.slice(2),width=Number(widthText);
const ws=new WebSocket(endpoint);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject});
let seq=0;const pending=new Map();
ws.onmessage=e=>{const v=JSON.parse(e.data);if(pending.has(v.id)){const {resolve,reject,timer}=pending.get(v.id);clearTimeout(timer);pending.delete(v.id);v.error?reject(Error(JSON.stringify(v.error))):resolve(v.result)}};
const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const id=++seq,timer=setTimeout(()=>reject(Error('CDP timeout '+method)),20000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}))});
try{
 const {targetId}=await send('Target.createTarget',{url:'about:blank'});
 const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
 await send('Emulation.setDeviceMetricsOverride',{width,height:1080,deviceScaleFactor:1,mobile:width<768},sessionId);
 await send('Page.enable',{},sessionId);await send('Page.navigate',{url},sessionId);
 const expression=`new Promise((resolve,reject)=>{let n=0;const t=setInterval(()=>{if(document.body?.dataset.qa){clearInterval(t);resolve({qa:document.body.dataset.qa,width:innerWidth,scroll:document.documentElement.scrollWidth})}else if(++n>1500){clearInterval(t);reject(Error('QA timeout'))}},20)})`;
 const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true},sessionId);
 if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));
 const result=r.result.value;
 const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},sessionId);
 fs.writeFileSync(out,Buffer.from(shot.data,'base64'));console.log(JSON.stringify(result));
 await send('Target.closeTarget',{targetId});
}finally{ws.close()}
