const {chromium}=require('/tmp/w/node_modules/playwright-core');
const fs=require('fs');
const [,, shard, nsh, fps, total]=process.argv.map(Number);
(async()=>{
 const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome',args:['--no-sandbox']});
 const pg=await b.newPage({viewport:{width:540,height:960},deviceScaleFactor:2});
 await pg.goto('file:///home/user/idk/exzmoto-ad/index.html');await pg.waitForTimeout(800);
 for(let f=shard;f<total;f+=nsh){await pg.evaluate(t=>render(t),f/fps);
  await pg.screenshot({path:`/tmp/w/frames/f${String(f).padStart(4,'0')}.jpg`,type:'jpeg',quality:92});}
 await b.close();})();
