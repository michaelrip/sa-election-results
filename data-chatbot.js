/* Mzanzi Data Assistant: deterministic answers from published election results, no AI API. */
(()=>{'use strict';
const style=document.createElement('style');
style.textContent=`
#mz-chat-toggle{position:fixed;right:18px;bottom:20px;z-index:11000;border:1px solid #7acbb4;background:#087b59;color:white;border-radius:999px;padding:13px 18px;box-shadow:0 8px 28px #0008;font-weight:750;cursor:pointer}
#mz-chat{position:fixed;right:16px;bottom:82px;width:min(390px,calc(100vw - 32px));height:min(540px,calc(100dvh - 115px));z-index:11000;background:#10223b;border:1px solid #54718b;border-radius:16px;box-shadow:0 12px 45px #000a;display:none;flex-direction:column;overflow:hidden;color:#eef6ff;font:14px system-ui,sans-serif}
#mz-chat.open{display:flex}#mz-chat header{display:flex;align-items:center;justify-content:space-between;padding:13px 15px;background:#193a51;border:0}#mz-chat header button{padding:3px 10px;min-height:34px}
#mz-chat-log{overflow:auto;flex:1;padding:13px;display:flex;flex-direction:column;gap:10px} .mz-msg{padding:10px 12px;border-radius:12px;white-space:pre-wrap;line-height:1.5;max-width:94%;overflow-wrap:anywhere}.mz-msg.bot{background:#24415c;align-self:flex-start}.mz-msg.user{background:#086d54;align-self:flex-end}
#mz-chat-form{display:flex;gap:7px;padding:11px;border-top:1px solid #456078}#mz-chat-input{min-width:0;flex:1;font-size:14px}#mz-chat-send{padding:8px 12px}
#mz-chat-examples{padding:0 12px 9px;display:flex;gap:6px;flex-wrap:wrap}#mz-chat-examples button{font-size:11px;padding:5px 8px;min-height:30px}
`;document.head.appendChild(style);
const toggle=document.createElement('button');toggle.id='mz-chat-toggle';toggle.type='button';toggle.textContent='Ask Mzanzi Data';toggle.setAttribute('aria-controls','mz-chat');toggle.setAttribute('aria-expanded','false');
const panel=document.createElement('section');panel.id='mz-chat';panel.setAttribute('aria-label','Election data question assistant');panel.innerHTML='<header><strong>Ask Mzanzi Data</strong><button type="button" id="mz-chat-close" aria-label="Close chat">✕</button></header><div id="mz-chat-log" role="log" aria-live="polite"></div><div id="mz-chat-examples"></div><form id="mz-chat-form"><input id="mz-chat-input" aria-label="Ask about election data" maxlength="240" placeholder="Ask about votes, parties or wards…" required><button id="mz-chat-send" type="submit">Ask</button></form>';
document.body.append(toggle,panel);
const log=panel.querySelector('#mz-chat-log'),input=panel.querySelector('#mz-chat-input');
function say(message,who='bot'){const el=document.createElement('div');el.className='mz-msg '+who;el.textContent=message;log.appendChild(el);log.scrollTop=log.scrollHeight}
function open(on){panel.classList.toggle('open',on);toggle.setAttribute('aria-expanded',String(on));if(on)input.focus()}
toggle.addEventListener('click',()=>open(!panel.classList.contains('open')));panel.querySelector('#mz-chat-close').addEventListener('click',()=>open(false));document.addEventListener('keydown',e=>{if(e.key==='Escape'&&panel.classList.contains('open'))open(false)});
const examples=['Cape Town results','Who leads in Tshwane?','ANC votes in Johannesburg','Ward 1 in Cape Town','How many districts reported?'];
examples.forEach(q=>{const b=document.createElement('button');b.type='button';b.textContent=q;b.addEventListener('click',()=>ask(q));panel.querySelector('#mz-chat-examples').appendChild(b)});
let cache=null,loadedAt=0;
async function results(){if(cache&&Date.now()-loadedAt<120000)return cache;const response=await fetch('./results.json?chat='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error('Election data unavailable');const d=await response.json();if(!d||!d.metros)throw Error('Election data incomplete');cache=d;loadedAt=Date.now();return d}
const fmt=n=>Number(n).toLocaleString('en-ZA');
function answer(q,d){
 const t=q.toLowerCase().trim(), names=Object.keys(d.metros);
 const alias={'cape town':'Cape Town','capetown':'Cape Town','tshwane':'Tshwane','pretoria':'Tshwane','johannesburg':'Johannesburg','joburg':'Johannesburg','jozi':'Johannesburg','hermanus':'Hermanus','overstrand':'Hermanus'};
 let city=Object.entries(alias).find(([a])=>t.includes(a))?.[1];
 if(!city&&/\b(here|this metro|selected metro)\b/.test(t)){const selected=document.querySelector('#metro');if(selected&&names.includes(selected.value))city=selected.value}
 if(!city&&names.length===1)city=names[0];
 const stamp='Published snapshot: '+(d.updated_at||'time unavailable')+'. These are provisional, unofficial figures, not a final IEC declaration.';
 if(/\b(help|what can you|examples|how to)\b/.test(t))return 'Ask about a metro’s party vote shares, votes, reporting progress, or a numbered ward. Try: “DA share in Cape Town”, “Ward 5 in Tshwane”, or “Johannesburg results”.\n'+stamp;
 if(/2021|compare|previous election|change since/.test(t))return 'This assistant currently reads the latest results.json snapshot only. For verified 2021 comparisons, use the website’s comparison controls. I will not invent historical figures.';
 if(!city)return 'Please name a metro: '+names.join(', ')+'. For example: “Cape Town results” or “ANC votes in Tshwane”.';
 const m=d.metros[city];if(!m)return 'No published data for '+city+'.';
 const partyList=Array.isArray(m.parties)?m.parties:[];
 const wardMatch=t.match(/\bward\s*(?:number\s*)?(\d{1,3})\b/);
 let target=m,scope=city;
 if(wardMatch){const n=Number(wardMatch[1]);const wards=Array.isArray(m.wards)?m.wards:Object.values(m.wards||{});const w=wards.find(w=>Number(w.number)===n);if(!w)return 'Ward '+n+' is not in the published '+city+' data.\n'+stamp;target=w;scope=city+' Ward '+n}
 const parties=Array.isArray(target.parties)?target.parties:[];
 const sorted=[...parties].filter(p=>Number.isFinite(Number(p.votes))).sort((a,b)=>Number(b.votes)-Number(a.votes));
 const p=sorted.find(p=>{const name=String(p.name||'').toLowerCase();return name.length>1&&new RegExp('(^|[^a-z0-9])'+name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'(?=$|[^a-z0-9])','i').test(t)});
 const summary=scope+' — '+(target.status||target.reporting||'status not supplied')+'.\n';
 if(p)return summary+p.name+': '+fmt(p.votes)+' votes'+(Number.isFinite(Number(p.share))?' ('+Number(p.share).toFixed(1)+'%)':'')+'.\n'+stamp;
 if(/\b(turnout|registered voters|voter turnout)\b/.test(t))return 'The published snapshot does not provide a reliable registered-voter turnout measure for '+scope+'.\n'+stamp;
 if(/\b(report|counted|district|progress|complete|percentage counted)\b/.test(t)){
 if(wardMatch)return summary+'Reporting: '+(target.reporting||'not available')+'.\n'+stamp;
 const a=Number(m.districts_reported),b=Number(m.districts_total);return summary+(Number.isFinite(a)&&Number.isFinite(b)&&b>0?fmt(a)+' of '+fmt(b)+' districts reported ('+(a/b*100).toFixed(1)+'%).':'Reporting totals unavailable.')+'\n'+stamp}
 if(!sorted.length)return summary+'No party vote totals have been published for this area yet.\n'+stamp;
 const head=/\b(lead|leading|most votes|top party|first)\b/.test(t)?'Highest currently recorded vote total (not a declared winner):\n':'Current published party totals:\n';
 return summary+head+sorted.slice(0,(/\b(all|every|full)\b/.test(t)?15:5)).map(p=>p.name+': '+fmt(p.votes)+' votes'+(Number.isFinite(Number(p.share))?' ('+Number(p.share).toFixed(1)+'%)':'')).join('\n')+(Number.isFinite(Number(target.valid_votes))?'\nValid votes: '+fmt(target.valid_votes):'')+'.\n'+stamp;
}
async function ask(q){q=String(q||'').trim();if(!q)return;say(q,'user');input.value='';input.disabled=true;panel.querySelector('#mz-chat-send').disabled=true;try{say(answer(q,await results()))}catch(e){say('I cannot retrieve the published election data right now. Please try again shortly.')}finally{input.disabled=false;panel.querySelector('#mz-chat-send').disabled=false;input.focus()}}
panel.querySelector('#mz-chat-form').addEventListener('submit',e=>{e.preventDefault();ask(input.value)});
say('Hello! I answer questions using the published election results on this site. I am a free, rule-based data assistant, not a generative AI model. Figures may be provisional. Choose an example or ask a question.');
})();