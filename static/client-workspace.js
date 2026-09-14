const editorialTheme=document.createElement('link');editorialTheme.rel='stylesheet';editorialTheme.href='/static/editorial-theme.css?v=sidebar-signout-2';document.head.appendChild(editorialTheme);
function openClientMoodboardLightbox(image){
  document.querySelector('.moodboard-lightbox')?.remove();
  const modal=document.createElement('div');
  modal.className='moodboard-lightbox';
  modal.setAttribute('role','dialog');
  modal.setAttribute('aria-modal','true');
  modal.setAttribute('aria-label',image.alt||'Moodboard image preview');
  modal.innerHTML=`<div class="moodboard-lightbox-panel"><button type="button" class="moodboard-lightbox-close" aria-label="Close image preview">×</button><img src="${esc(image.currentSrc||image.src)}" alt="${esc(image.alt||'Moodboard image preview')}"></div>`;
  const close=()=>{modal.remove();document.body.classList.remove('moodboard-lightbox-open');document.removeEventListener('keydown',onKey)};
  const onKey=event=>{if(event.key==='Escape')close()};
  modal.addEventListener('click',event=>{if(event.target===modal||event.target.closest('.moodboard-lightbox-close'))close()});
  document.body.appendChild(modal);
  document.body.classList.add('moodboard-lightbox-open');
  document.addEventListener('keydown',onKey);
  modal.querySelector('.moodboard-lightbox-close').focus();
}
document.addEventListener('click',event=>{const image=event.target.closest('.client-moodboard-tiles img');if(!image)return;event.preventDefault();openClientMoodboardLightbox(image)});
const clientInquiryCardStyleEarly=document.createElement('style');clientInquiryCardStyleEarly.textContent='.gallery-card.gallery-featured{background:#211e21!important}.gallery-card.gallery-featured>img{inset:0 0 0 auto!important;width:43%!important;height:100%!important;object-position:center!important;filter:saturate(.82) contrast(1.02)!important}.gallery-card.gallery-featured>.gallery-shade{background:linear-gradient(90deg,#211e21 0 51%,#211e21ee 58%,#211e2130 80%,transparent 100%)!important}.gallery-card.gallery-featured>.gallery-content{right:48%!important;bottom:32px!important}.gallery-card.gallery-featured>.gallery-content h2{max-width:560px!important}.gallery-card.gallery-featured>.gallery-content .gallery-cta{position:static!important;margin-top:20px!important}.gallery-card.gallery-featured>.circle-action{background:#211e2199!important}@media(max-width:900px){.gallery-card.gallery-featured>img{width:42%!important}.gallery-card.gallery-featured>.gallery-content{right:46%!important;bottom:22px!important}.gallery-card.gallery-featured>.gallery-content h2{font-size:clamp(34px,7vw,48px)!important}}@media(max-width:620px){.gallery-card.gallery-featured>img{width:100%!important;opacity:.48}.gallery-card.gallery-featured>.gallery-shade{background:linear-gradient(110deg,#211e21ee,#211e2188)!important}.gallery-card.gallery-featured>.gallery-content{right:22px!important}}';document.head.appendChild(clientInquiryCardStyleEarly);
const conversationTheme=document.createElement('link');conversationTheme.rel='stylesheet';conversationTheme.href='/static/client-conversation.css?v=1';document.head.appendChild(conversationTheme);
const clientInquiryCardRefinement=document.createElement('style');clientInquiryCardRefinement.textContent='.gallery-card.gallery-featured>.gallery-content .gallery-cta{display:none!important}.gallery-card.gallery-featured>img{top:18px!important;right:18px!important;bottom:18px!important;left:auto!important;width:calc(43% - 18px)!important;height:calc(100% - 36px)!important;border-radius:12px!important;object-position:center 12%!important}.gallery-card.gallery-featured>.circle-action:after{content:"View details";position:absolute;right:0;top:calc(100% + 8px);padding:5px 7px;border-radius:6px;background:#211e21e8;color:#fff;font:700 10px Inter,system-ui,sans-serif;letter-spacing:.03em;opacity:0;pointer-events:none;transform:translateY(-3px);transition:.16s;white-space:nowrap}.gallery-card.gallery-featured>.circle-action:hover:after,.gallery-card.gallery-featured>.circle-action:focus-visible:after{opacity:1;transform:translateY(0)}@media(max-width:620px){.gallery-card.gallery-featured>img{top:0!important;right:0!important;bottom:0!important;width:100%!important;height:100%!important;border-radius:0!important;object-position:center 18%!important}}';document.head.appendChild(clientInquiryCardRefinement);
const clientInquiryCardImageFit=document.createElement('style');clientInquiryCardImageFit.textContent='.gallery-card:not(.gallery-featured)>img{object-fit:contain!important;object-position:center!important;background:#211e21}.gallery-card:not(.gallery-featured) .gallery-shade{background:linear-gradient(180deg,#15131624 0%,#1513161a 38%,#151316dc 100%)}@media(max-width:620px){.gallery-card:not(.gallery-featured)>img{object-fit:cover!important;object-position:center 18%!important}}';document.head.appendChild(clientInquiryCardImageFit);
const clientUser=JSON.parse(sessionStorage.getItem('shotcraftUser')||'{}');
const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
async function hydrateClientSession(){const response=await fetch('/api/auth/me',{cache:'no-store'}),user=await response.json();if(!response.ok||user.user_type!=='client'){sessionStorage.removeItem('shotcraftUser');location.replace('/auth?mode=login');throw Error('Please sign in to continue.')}Object.assign(clientUser,user);sessionStorage.setItem('shotcraftUser',JSON.stringify(clientUser));document.getElementById('clientName').textContent=clientUser.name;document.getElementById('clientEmail').textContent=clientUser.email;const avatar=document.querySelector('.identity .profile-orb');if(avatar&&clientUser.profile_image)avatar.outerHTML=`<span class="profile-orb profile-orb-image"><img src="${esc(clientUser.profile_image)}" alt=""></span>`}
async function signOut(){try{await fetch('/api/auth/logout',{method:'POST'})}finally{sessionStorage.removeItem('shotcraftUser');location.replace('/auth?mode=login')}}
const app=document.getElementById('app');
function formatScheduleTextForClient(value){
  return String(value||'')
    .replace(/Requested date:\s*(\d{4}-\d{2}-\d{2})/g,(_,date)=>`Requested date: ${formatDate(date)}`)
    .replace(/Your shoot is confirmed for\s+(\d{4}-\d{2}-\d{2})[ T](\d{1,2}:\d{2})(?=\s+at\b)/g,(_,date,time)=>`Your shoot is confirmed for ${formatDate(`${date}T${time}`)}`)
    .replace(/(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})/g,(_,start,end)=>`${formatTimeOfDay(start)} – ${formatTimeOfDay(end)}`);
}
function formatClientMessageTimes(){
  app.querySelectorAll('.message p').forEach(node=>{
    if(node.dataset.scheduleFormat)return;
    node.textContent=formatScheduleTextForClient(node.textContent);
    node.dataset.scheduleFormat='true';
  });
}
new MutationObserver(formatClientMessageTimes).observe(app,{childList:true,subtree:true});
new MutationObserver(()=>{const form=document.getElementById('clientProfileForm');if(!form)return;enhanceClientProfileForm();form.onsubmit=saveClientProfileWithSuccess}).observe(app,{childList:true,subtree:true});
let timelineRequest=0;
const timelineMarkup=items=>`<section class="shared-timeline"><div class="eyebrow">Shoot journey</div><div class="timeline-track">${(items||[]).map(item=>`<div class="timeline-item ${item.completed?'complete':''}"><span class="timeline-dot">${item.completed?'✓':''}</span><div><b>${esc(item.label)}</b>${item.timestamp?`<small>${esc(new Date(item.timestamp.replace(' ','T')+'Z').toLocaleString([], {dateStyle:'medium',timeStyle:'short'}))}</small>`:'<small>Upcoming</small>'}</div></div>`).join('')}</div></section>`;
async function refreshTimeline(){const id=app.dataset.timelineId;if(!id||app.querySelector('.inquiry-review-loading'))return;const request=++timelineRequest;try{const response=await fetch(`/api/inquiries/${id}/timeline`,{cache:'no-store'}),data=await response.json();if(request!==timelineRequest||app.dataset.timelineId!==id||app.querySelector('.inquiry-review-loading'))return;const existing=document.querySelector('.shared-timeline');if(existing)existing.outerHTML=timelineMarkup(data.timeline);else {const legacy=document.querySelector('.steps,.detail-progress');if(legacy)legacy.outerHTML=timelineMarkup(data.timeline);else app.insertAdjacentHTML('beforeend',timelineMarkup(data.timeline))}if(['details','plan'].includes(current.view))ensureClientTimelineFullWidth()}catch(_){} }
new MutationObserver(()=>{const form=document.getElementById('inquiryForm');if(!form||document.getElementById('deliverableCount'))return;const wardrobe=document.getElementById('wardrobe')?.closest('.field');if(!wardrobe)return;wardrobe.insertAdjacentHTML('beforebegin','<div class="field"><label>Number of final photos</label><input id="deliverableCount" type="number" min="1" max="100" value="10" required><small class="muted">Edited images you expect to receive</small></div>')}).observe(app,{childList:true,subtree:true});
let shoots=[],filter='all',current={view:'shoots',id:null},cityImages={};
document.getElementById('clientName').textContent=clientUser.name||'Client workspace';
document.getElementById('clientEmail').textContent=clientUser.email||'';
document.querySelector('.sidebar')?.insertAdjacentHTML('beforeend','<button class="sign-out" type="button">Sign out</button>');
document.querySelector('.sign-out')?.addEventListener('click',signOut);
document.querySelector('.brand').innerHTML='<span class="brand-mark logo-image"><img src="/static/brand/shotcraft-mark.png" alt=""></span><span class="brand-copy"><b>ShotCraft</b><small>Creative workspace</small></span>';
document.querySelector('.identity').insertAdjacentHTML('afterbegin','<span class="profile-orb" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm7 8a7 7 0 0 0-14 0"/></svg></span>');
document.querySelector('.nav').innerHTML='<div class="nav-label">Workspace</div><button data-view="shoots"><span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M4 11 12 4l8 7v9h-5v-6H9v6H4Z"/></svg></span><span>Overview</span></button><button data-view="shoots" class="gallery-nav"><span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M4 6.5h16v11H4zM8 10h8M8 14h5"/></svg></span><span>Inquiries</span><span class="nav-dot"></span></button><button data-view="notifications" class="notifications-nav"><span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/></svg></span><span>Notifications</span><span class="notification-badge" hidden>0</span></button><button type="button"><span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M4 5h16v12H9l-5 3V5Z"/></svg></span><span>Messages</span></button><button type="button"><span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm7 8a7 7 0 0 0-14 0"/></svg></span><span>Profile</span></button><div class="nav-label nav-create-label">Create</div><button class="create" data-view="create"><span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg></span><span>New inquiry</span><span class="nav-arrow">→</span></button>';
const parsed=value=>{try{return typeof value==='string'?JSON.parse(value):value}catch{return null}};
(()=>{const nav=document.querySelector('.nav'),messages=[...nav?.querySelectorAll('button')||[]].find(button=>button.textContent.includes('Messages')),profile=[...nav?.querySelectorAll('button')||[]].find(button=>button.textContent.includes('Profile'));messages?.insertAdjacentHTML('beforebegin','<div class="nav-label nav-communication-label">Communication</div>');profile?.insertAdjacentHTML('beforebegin','<div class="nav-label nav-account-label">Account</div>')})();
const payload=record=>parsed(record.payload)||{};
// Shoot dates are intentionally stored as wall-clock values (without a UTC
// suffix). Parse them as local calendar values so a date never moves because a
// browser treats `YYYY-MM-DD` as midnight UTC.
const wallClockDate=value=>{const text=String(value||''),match=text.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?$/);return match?new Date(Number(match[1]),Number(match[2])-1,Number(match[3]),Number(match[4]||0),Number(match[5]||0),Number(match[6]||0)):new Date(text)};
const wallClockDateKey=value=>{const date=value instanceof Date?value:wallClockDate(value),pad=part=>String(part).padStart(2,'0');return Number.isNaN(date.valueOf())?'':`${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}`};
const formatTimeOfDay=value=>{const match=String(value||'').match(/^(\d{1,2}):(\d{2})$/);if(!match)return String(value||'');const date=new Date(2000,0,1,Number(match[1]),Number(match[2]));return date.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit',hour12:true})};
const formatAvailabilityWindow=value=>String(value||'').replace(/(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})/,(_,start,end)=>`${formatTimeOfDay(start)} – ${formatTimeOfDay(end)}`);
const formatDate=value=>{if(!value)return'Flexible date';const date=wallClockDate(value),hasTime=String(value).includes('T')||/^\d{4}-\d{2}-\d{2}\s/.test(String(value));return Number.isNaN(date.valueOf())?value:date.toLocaleString(undefined,{dateStyle:'medium',...(hasTime?{timeStyle:'short',hour12:true}:{})})};
function statusInfo(record){if(record.status==='CANCELLED')return['SHOOT CANCELLED','needs'];if(record.cancellation_status==='PENDING')return['CANCELLATION REQUESTED','needs'];if(record.status==='SCHEDULED')return['SHOOT SCHEDULED','scheduled'];if(record.status==='CLIENT_CONFIRMED')return['CONFIRMED','ready'];if(record.status==='CLIENT_CHANGE_REQUESTED')return['CHANGE REQUESTED','needs'];if(record.production_approved)return['PLAN READY','ready'];if(record.status==='NEEDS_INFORMATION')return['NEEDS YOUR INPUT','needs'];if(record.status==='READY_FOR_REVIEW')return['WITH PHOTOGRAPHER','ready'];return['IN REVIEW','']}
function clientActionFor(record){
  if(record.status==='CANCELLED'||record.status==='CLIENT_CHANGE_REQUESTED'||record.cancellation_status==='PENDING')return null;
  if(record.schedule_request?.status==='PENDING_CLIENT'&&['PENDING','AWAITING_CLIENT'].includes(record.change_request?.status))return{label:'Choose a revised time',description:'Your photographer sent conflict-free options for your review.',view:'plan'};
  if(record.status==='NEEDS_INFORMATION')return{label:'Answer follow-up',description:'Your photographer needs a few more details.',view:'followup'};
  if(record.production_approved&&!['CLIENT_CONFIRMED','SCHEDULED'].includes(record.status))return{label:'Review plan and choose a time',description:'Your shoot plan is ready for your decision.',view:'plan'};
  return null;
}
function isClientActionNeeded(record){return Boolean(clientActionFor(record))}
function title(record){const p=payload(record),analysis=parsed(record.analysis)||{},originalRequest=String(p.message||'').split(/\n\s*Client follow-up answers:|\n{2,}/i)[0].trim();return analysis.concept_name||p.shoot_type||originalRequest.split(/[.!?]/)[0]?.slice(0,64)||'Your shoot'}
function setNav(view){document.querySelectorAll('.nav button').forEach(button=>button.classList.toggle('active',(view==='create'&&button.dataset.view==='create')||(view!=='create'&&button.dataset.view==='shoots')))}
function go(view,id=null,push=true){current={view,id:id?Number(id):null};if(push){const query=new URLSearchParams();if(view!=='shoots')query.set('view',view);if(id)query.set('id',id);history.pushState(current,'','/client'+(query.size?'?'+query:''))}render()}
function nextAction(record){if(record.status==='SCHEDULED')return`<div class="next schedule"><b>Your shoot is scheduled</b>${esc(formatDate(record.call_time))} · ${esc(record.meeting_location||'Meeting location pending')}</div>`;if(record.status==='NEEDS_INFORMATION')return'<div class="next"><b>A few details are needed</b>Answer the follow-up questions to keep planning moving.</div>';if(record.production_approved)return'<div class="next"><b>Your shoot plan is ready</b>Review the plan, then confirm it or request a change.</div>';if(record.status==='CLIENT_CONFIRMED')return'<div class="next"><b>Your confirmation is with the photographer</b>They’ll add the final schedule shortly.</div>';return'<div class="next"><b>With your photographer</b>Creative planning is in progress.</div>'}
function card(record,index=0){const p=payload(record),status=statusInfo(record),city=(p.message||'').match(/Seattle|Delhi|New Delhi/i)?.[0]?.toLowerCase().replace('new delhi','delhi'),gallery=cityImages[city]?.gallery||[],image=gallery.length?gallery[index%gallery.length]:null;return`<article class="card shoot-row ${index===0?'featured':''}" ${image?`style="--tile-image:url('${image}')"`:''}><div class="shoot-visual">${image?`<img src="${image}" alt="${esc(city||'shoot')}" loading="lazy">`:''}<div class="shoot-overlay"></div><div class="shoot-date"><div class="eyebrow">${esc(formatDate(p.shoot_date))}</div><span class="status ${status[1]}">${status[0]}</span></div><h2 class="shoot-title">${esc(title(record))}</h2></div><div class="shoot-copy"><div class="meta"><span>${esc(p.message?.slice(0,150)||'')}</span></div>${nextAction(record)}</div><div class="actions shoot-actions">${record.status==='NEEDS_INFORMATION'?`<button class="primary" data-followup="${record.id}">Answer questions →</button>`:''}<button class="link" data-detail="${record.id}">View details →</button></div></article>`}
function shootsView(){setNav('shoots');const counts={action:shoots.filter(x=>x.status==='NEEDS_INFORMATION'||x.production_approved&&!['CLIENT_CONFIRMED','SCHEDULED'].includes(x.status)).length,scheduled:shoots.filter(x=>x.status==='SCHEDULED').length};const filtered=shoots.filter(record=>filter==='all'||filter==='action'&&(record.status==='NEEDS_INFORMATION'||record.production_approved&&!['CLIENT_CONFIRMED','SCHEDULED'].includes(record.status))||filter==='planning'&&['READY_FOR_REVIEW','NEW','CLIENT_CONFIRMED'].includes(record.status)||filter==='scheduled'&&record.status==='SCHEDULED');app.innerHTML=`<div class="head"><div><div class="eyebrow">Client workspace</div><h1>My shoots</h1><p class="lede">Every shoot, plan, and photographer update in one calm place.</p></div><button class="primary" data-view="create">New inquiry →</button></div><div class="summary"><span class="summary-item">${counts.action} action${counts.action===1?'':'s'} needed</span><span class="summary-item">${counts.scheduled} upcoming shoot${counts.scheduled===1?'':'s'}</span></div><div class="filters"><button class="filter ${filter==='all'?'active':''}" data-filter="all">All shoots</button><button class="filter ${filter==='action'?'active':''}" data-filter="action">Needs action</button><button class="filter ${filter==='planning'?'active':''}" data-filter="planning">In planning</button><button class="filter ${filter==='scheduled'?'active':''}" data-filter="scheduled">Scheduled</button></div><div class="shoot-list">${filtered.map((record,index)=>card(record,index)).join('')||'<div class="card empty">No shoots in this view yet.</div>'}</div>`;bind()}
async function detail(id){setNav('shoots');const record=await getRecord(id),p=payload(record),status=statusInfo(record);let heading='Your inquiry is being reviewed.',lead='Your photographer is organizing the creative direction.',state='In review',stateDetail='We’ll keep you updated here.';if(record.status==='SCHEDULED'){heading='Your shoot is scheduled.';lead='Your photographer has confirmed the final shoot details.';state='Shoot scheduled';stateDetail=`${formatDate(record.call_time)} · ${record.meeting_location||'Meeting location pending'}`}else if(record.status==='CLIENT_CONFIRMED'){heading='You’re confirmed.';lead='Your photographer will send the final schedule.';state='Shoot confirmed';stateDetail='Watch for scheduling updates.'}else if(record.status==='NEEDS_INFORMATION'){heading='One more detail from you.';lead='A few answers will help your photographer plan the right shoot.';state='Details needed';stateDetail='Answer the follow-up questions to move this forward.'}else if(record.production_approved){heading='Your shoot plan is ready.';lead='The photographer approved the shoot plan for your session.';state='Shoot plan ready';stateDetail='Review the plan, then confirm it or request a change.'}app.innerHTML=`<button class="link" data-view="shoots">← Back to My shoots</button><div class="detail-head"><div class="eyebrow">Shoot details · #${record.id}</div><h1>${heading}</h1><p class="lede">${lead}</p></div><section class="card"><div class="state"><div class="check">✓</div><div><strong>${state}</strong><p>${esc(stateDetail)}</p></div></div><div class="steps"><div class="step done"><b>01 · Inquiry</b>Details captured</div><div class="step ${record.status!=='NEW'?'done':''}"><b>02 · Planning</b>Creative review</div><div class="step ${record.production_approved||record.status==='SCHEDULED'?'done':''}"><b>03 · Confirm</b>Plan and schedule</div></div><div class="actions">${record.status==='NEEDS_INFORMATION'?`<button class="primary" data-followup="${id}">Answer questions →</button>`:''}${record.production_approved?`<button class="primary" data-plan="${id}">Review shoot plan →</button>`:''}${record.production_approved&&!['CLIENT_CONFIRMED','SCHEDULED'].includes(record.status)?`<button class="secondary" data-confirm="${id}">Confirm this plan</button><button class="secondary" data-change="${id}">Request a change</button>`:''}</div></section><section class="card"><div class="eyebrow">Your inquiry</div><h2 class="shoot-title">${esc(title(record))}</h2><p class="muted">${esc(p.message||'')}</p></section>`;bind()}
async function followup(id){setNav('shoots');const record=await getRecord(id),p=payload(record),analysis=parsed(record.analysis)||{},questions=analysis.questions||[],location=record.meeting_location||p.location||'Location to be confirmed',date=record.call_time||p.shoot_date,request=String(p.message||'').split(/\n\s*Client follow-up answers:/i)[0].trim().slice(0,220);app.innerHTML=`<button class="link" data-detail="${id}">← Back to shoot details</button><div class="detail-head followup-head"><div class="eyebrow">Shoot follow-up · Inquiry #${record.id}</div><h1>A few details for your shoot.</h1><p class="lede">Your answers help your photographer make the plan more specific.</p></div><section class="followup-project-context"><div><div class="eyebrow">You’re answering for</div><h2>${esc(title(record))}</h2>${request?`<p><strong>Your request:</strong> ${esc(request)}</p>`:''}<div class="followup-context-facts"><span><small>Date</small><b>${esc(formatDate(date))}</b></span><span><small>Location</small><b>${esc(location)}</b></span><span><small>Photographer</small><b>${esc(p.photographer_email||'Your ShotCraft photographer')}</b></span></div></div><button class="secondary" data-detail="${id}">View project details →</button></section><section class="card followup-questions"><div class="eyebrow">Details needed</div><h2>Help shape the direction.</h2>${questions.length?`<ol>${questions.map(q=>`<li>${esc(q)}</li>`).join('')}</ol>`:'<p class="muted">Add any detail that will help your photographer prepare the shoot.</p>'}<form id="followupForm"><div class="field"><label for="answers">Your answers</label><textarea id="answers" required placeholder="Answer the questions above with as much detail as you can…"></textarea></div><div class="actions"><button class="primary" id="sendAnswers">Send answers →</button><span id="replyStatus" class="muted"></span></div></form></section>`;bind();document.getElementById('followupForm').onsubmit=event=>reply(event,id)}
async function reply(event,id){event.preventDefault();const button=document.getElementById('sendAnswers'),status=document.getElementById('replyStatus');button.disabled=true;status.textContent='Sending your answers…';try{const response=await fetch(`/api/inquiries/${id}/reply`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answers:document.getElementById('answers').value})});if(!response.ok)throw Error();status.textContent='Answers received. Updating your shoot…';for(let attempt=0;attempt<20;attempt++){await new Promise(resolve=>setTimeout(resolve,1500));const record=await fetch(`/api/inquiries/${id}`).then(r=>r.json());if(record.status!=='NEW'){await refresh();detail(id);return}}await refresh();detail(id)}catch{status.textContent='Could not send your answers. Please try again.';button.disabled=false}}
async function plan(id){setNav('shoots');const record=await getRecord(id),pack=parsed(record.production_pack);if(!pack){detail(id);return}app.innerHTML=`<button class="link" data-detail="${id}">← Back to shoot details</button><div class="detail-head"><div class="eyebrow">Approved shoot plan</div><h1>${esc(displayShootPlanTitle(pack.title))}</h1><p class="lede">Everything your photographer prepared for the session.</p></div><section class="card"><div class="eyebrow">Call sheet</div><div class="call-sheet">${Object.entries(pack.call_sheet||{}).map(([k,v])=>`<div><small>${esc(k)}</small><b>${esc(v)}</b></div>`).join('')}</div></section><div class="plan-grid">${section('Location plan',pack.location_plan)}${section('Shot list',pack.shot_list)}${section('Lighting plan',pack.lighting_plan)}${section('Wardrobe checklist',pack.wardrobe_checklist)}${section('Weather note',[pack.weather_note])}${section('Backup plan',[pack.backup_plan])}</div>`;bind()}
const section=(title,values)=>`<section class="card"><div class="eyebrow">${title}</div><ul>${(values||[]).map(v=>`<li>${esc(v)}</li>`).join('')}</ul></section>`;
function create(){setNav('create');app.innerHTML=`<div class="head"><div><div class="eyebrow">New inquiry</div><h1>Tell us what you’re imagining.</h1><p class="lede">Start with the essentials. Your account details are already included.</p></div></div><section class="card"><form id="inquiryForm"><div class="form-grid"><div class="field"><label>Your name</label><input value="${esc(clientUser.name)}" readonly></div><div class="field"><label>Email address</label><input value="${esc(clientUser.email)}" readonly></div><div class="field"><label>Preferred shoot date</label><input id="date" type="date"></div><div class="field"><label>How long should the shoot be?</label><select id="duration"><option value="30">30 minutes</option><option value="60" selected>1 hour</option><option value="120">2 hours</option><option value="240">Half day (4 hours)</option><option value="480">Full day (8 hours)</option><option value="1440">Full day (up to 24 hours)</option></select></div><div class="field"><label>Estimated budget</label><input id="budget" type="number" min="0" step="50" placeholder="500"></div><div class="field"><label>Who is the shoot for?</label><select id="subject"><option value="woman">A woman</option><option value="man">A man</option><option value="non-binary person">A non-binary person</option><option value="group">A group</option><option value="no person / product or location">No person</option></select></div><div class="field"><label>Number of people</label><input id="count" type="number" min="1" max="10" value="1"></div><div class="field full"><label>When are you available?</label><textarea id="availability" placeholder="Add up to five windows, one per line.&#10;e.g. Tue Sep 15, 4:00–7:00 PM&#10;Thu Sep 17, 10:00 AM–2:00 PM"></textarea><small class="muted">Your photographer will use these preferences when proposing exact times.</small></div><div class="field full"><label>Wardrobe details</label><input id="wardrobe" placeholder="e.g. navy polo, black jeans, black boots"></div><div class="field"><label for="photographer">Choose a photographer</label><select id="photographer" required disabled><option value="">Loading available photographers…</option></select><small class="muted" id="photographerHelp">Choose who should receive this inquiry.</small></div><div class="field full"><label>What are you picturing?</label><textarea id="message" required placeholder="Describe the mood, location, purpose, wardrobe, or anything else that matters…"></textarea></div></div><div class="actions"><button class="primary" id="sendInquiry">Send my inquiry →</button><span id="formStatus" class="muted"></span></div></form></section>`;bind();document.getElementById('inquiryForm').onsubmit=submitInquiry;populatePhotographers()}
async function populatePhotographers(){const select=document.getElementById('photographer'),help=document.getElementById('photographerHelp'),submit=document.getElementById('sendInquiry');if(!select)return;try{const response=await fetch('/api/photographers',{cache:'no-store'});if(!response.ok)throw Error();const photographers=await response.json();if(!photographers.length){select.innerHTML='<option value="">No photographers are available yet</option>';help.textContent='Ask a photographer to create a ShotCraft workspace first.';if(submit)submit.disabled=true;return}select.innerHTML=`<option value="" selected disabled>Select a photographer…</option>${photographers.map(person=>`<option value="${esc(person.email)}">${esc(person.name)} · ${esc(person.email)}</option>`).join('')}`;select.disabled=false;help.textContent=`${photographers.length} photographer${photographers.length===1?'':'s'} available to receive your inquiry.`}catch{select.innerHTML='<option value="">Could not load photographers</option>';help.textContent='Refresh the page and try again.';if(submit)submit.disabled=true}}
async function submitInquiry(event){event.preventDefault();const button=document.getElementById('sendInquiry'),status=document.getElementById('formStatus'),availability=String(document.getElementById('availability').value||'').split(/\n+/).map(value=>value.trim()).filter(Boolean).slice(0,5);button.disabled=true;status.textContent='Sending your inquiry…';try{const response=await fetch('/api/inquiries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_name:clientUser.name,client_email:clientUser.email,contact_email:clientUser.email,message:document.getElementById('message').value,budget:Number(document.getElementById('budget').value)||null,shoot_date:document.getElementById('date').value||null,duration_minutes:Number(document.getElementById('duration').value)||60,availability_windows:availability,reference_images:[],photographer_email:document.getElementById('photographer').value,subject_presentation:document.getElementById('subject').value,subject_count:Number(document.getElementById('count').value)||1,wardrobe_details:document.getElementById('wardrobe').value||null,deliverable_count:Number(document.getElementById('deliverableCount').value)||null})});if(!response.ok)throw Error();const created=await response.json();current={view:'details',id:Number(created.id)};history.pushState(current,'',`/client?view=details&id=${created.id}`);app.innerHTML='<div class="loading">Reviewing your inquiry and preparing any follow-up questions…</div>';for(let attempt=0;attempt<40;attempt++){await new Promise(resolve=>setTimeout(resolve,1500));const record=await getRecord(created.id);if(record.status!=='NEW'){await refresh();galleryDetail(created.id);return}}await refresh();galleryDetail(created.id)}catch{status.textContent='We couldn’t send that just yet. Please try again.';button.disabled=false}}
async function decision(id,endpoint,note=''){const response=await fetch(`/api/inquiries/${id}/${endpoint}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({note})});if(response.ok){await refresh();current={view:'details',id:Number(id)};galleryDetail(id)}}
function bind(){document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>go(b.dataset.view));document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;shootsView()});document.querySelectorAll('[data-detail]').forEach(b=>b.onclick=()=>go('details',b.dataset.detail));document.querySelectorAll('[data-followup]').forEach(b=>b.onclick=()=>go('followup',b.dataset.followup));document.querySelectorAll('[data-plan]').forEach(b=>b.onclick=()=>go('plan',b.dataset.plan));document.querySelectorAll('[data-confirm]').forEach(b=>b.onclick=()=>decision(b.dataset.confirm,'client-confirm'));document.querySelectorAll('[data-change]').forEach(b=>b.onclick=()=>{const note=prompt('What would you like to change?');if(note!==null)decision(b.dataset.change,'client-change-request',note)})}
async function getRecord(id){const record=await fetch(`/api/inquiries/${id}`,{cache:'no-store'}).then(r=>r.json()),index=shoots.findIndex(x=>x.id==id);if(index>=0)shoots[index]=record;return record}
async function refresh(){const response=await fetch('/api/inquiries?client_email='+encodeURIComponent(clientUser.email||''),{cache:'no-store'});const data=await response.json();if(response.status===401){sessionStorage.removeItem('shotcraftUser');location.replace('/auth?mode=login');throw Error('Your session has expired. Please sign in again.')}if(!response.ok||!Array.isArray(data))throw Error(data?.detail||'Could not load your shoots.');const dateValue=record=>{const p=payload(record),value=record.call_time||p.shoot_date,timestamp=value?wallClockDate(value).valueOf():NaN;return Number.isFinite(timestamp)?timestamp:Number.MAX_SAFE_INTEGER};shoots=data.sort((a,b)=>dateValue(a)-dateValue(b)||b.id-a.id)}
function galleryCard(record,index=0){const p=payload(record),status=statusInfo(record),city=(p.message||'').match(/Seattle|Delhi|New Delhi/i)?.[0]?.toLowerCase().replace('new delhi','delhi'),gallery=cityImages[city]?.gallery||[],mood=parsed(record.moodboard),moodTiles=mood?.generated?.tiles||[],moodImage=moodTiles[2]?.image_url||moodTiles.find(tile=>tile?.image_url)?.image_url,image=moodImage||gallery[index%Math.max(gallery.length,1)]||null,location=record.meeting_location||p.location||(city==='delhi'?'Delhi, India':city==='seattle'?'Seattle, Washington':'Location to be confirmed');return`<article class="gallery-card ${index===0?'gallery-featured':''} ${image?'gallery-has-image':'gallery-no-image'}">${image?`<img src="${image}" alt="${esc(location)} creative reference" loading="lazy">`:''}<div class="gallery-shade"></div><button class="circle-action" data-detail="${record.id}" aria-label="View ${esc(title(record))}">→</button><div class="gallery-content"><h2>${esc(title(record))}</h2><div class="gallery-meta"><span>▣ ${esc(formatDate(record.call_time||p.shoot_date))}</span><span>⌖ ${esc(location)}</span></div><span class="status ${status[1]}">${status[0]}</span>${index===0?`<button class="primary gallery-cta" data-detail="${record.id}">View shoot details →</button>`:`<button class="link gallery-link" data-detail="${record.id}">View details →</button>`}</div></article>`}
function clientInquiryTime(record){const value=record.call_time||payload(record).shoot_date,timestamp=value?wallClockDate(value).valueOf():NaN;return Number.isFinite(timestamp)?timestamp:Number.MAX_SAFE_INTEGER}
function compareClientShootTime(a,b){return clientInquiryTime(a)-clientInquiryTime(b)||b.id-a.id}
function galleryView(){
  setNav('shoots');
  document.querySelectorAll('.nav button').forEach(button=>button.classList.remove('active'));
  document.querySelector('.gallery-nav')?.classList.add('active');
  const needsAction=shoots.filter(isClientActionNeeded).sort(compareClientShootTime),
    cancelled=shoots.filter(record=>record.status==='CANCELLED').sort(compareClientShootTime),
    scheduled=shoots.filter(record=>record.status==='SCHEDULED'&&!needsAction.includes(record)).sort(compareClientShootTime),
    inProgress=shoots.filter(record=>!needsAction.includes(record)&&!scheduled.includes(record)&&!cancelled.includes(record)).sort(compareClientShootTime),
    sections=[
      ['Needs action','Shoots waiting for your answers, plan review, or time selection.',needsAction],
      ['In progress','Creative direction, moodboards, and shoot planning in motion.',inProgress],
      ['Scheduled','Confirmed sessions ordered by shoot date and time.',scheduled],
      ['Cancelled','Cancelled shoots retained for your records.',cancelled],
    ];
  app.innerHTML=`<div class="head projects-head"><div><div class="eyebrow">Client workspace</div><h1>My shoots</h1><p class="lede">Every shoot organized by its current stage.</p></div><button class="primary" data-view="create">New inquiry →</button></div><div class="project-sections">${sections.map(([name,description,records])=>`<section class="project-section"><div class="section-head"><div><div class="eyebrow">${records.length} shoot${records.length===1?'':'s'}</div><h2 class="section-title">${name}</h2><p class="muted">${description}</p></div></div>${records.length?`<div class="gallery-grid project-section-grid">${records.map((record,index)=>galleryCard(record,index+1)).join('')}</div>`:'<div class="project-section-empty">Nothing in this section right now.</div>'}</section>`).join('')}</div>`;
  bind();
}
async function galleryDetail(id){setNav('shoots');document.querySelectorAll('.nav button').forEach(button=>button.classList.remove('active'));document.querySelector('.gallery-nav')?.classList.add('active');const record=await getRecord(id),p=payload(record),status=statusInfo(record),city=(p.message||'').match(/Seattle|Delhi|New Delhi/i)?.[0]?.toLowerCase().replace('new delhi','delhi'),gallery=cityImages[city]?.gallery||[],location=record.meeting_location||(city==='delhi'?'Delhi, India':city==='seattle'?'Seattle, Washington':'Location being planned'),date=record.call_time||p.shoot_date,scheduled=record.status==='SCHEDULED',planning=record.status!=='NEW',confirmed=record.production_approved||['CLIENT_CONFIRMED','SCHEDULED'].includes(record.status);let actions='';if(record.status==='NEEDS_INFORMATION')actions=`<button class="primary" data-followup="${id}">Answer questions →</button>`;else if(record.production_approved)actions=`<button class="primary" data-plan="${id}">Review shoot plan →</button>`;else actions='<button class="secondary" type="button">Message photographer</button>';app.innerHTML=`<div class="detail-gallery"><div class="detail-top"><div><button class="link detail-crumb" data-view="shoots">Inquiries</button><span> / ${esc(title(record))}</span><h1>${esc(title(record))}</h1></div><button class="circle-action detail-back" data-view="shoots" aria-label="Back to inquiries">←</button></div><div class="detail-strip">${gallery.slice(0,5).map((image,index)=>`<img src="${image}" alt="${esc(location)} reference ${index+1}">`).join('')||'<div class="detail-placeholder">Creative references are being prepared.</div>'}</div><div class="detail-progress"><div class="done"><i>✓</i><b>Inquiry</b><span>${esc(formatDate(p.shoot_date))}</span></div><div class="${planning?'done current':''}"><i>2</i><b>Creative review</b><span>${planning?'In progress':'Pending'}</span></div><div class="${confirmed?'done':''}"><i>3</i><b>${scheduled?'Scheduled':'Confirmation'}</b><span>${scheduled?esc(formatDate(record.call_time)):'Pending'}</span></div></div><section class="detail-sheet"><div class="detail-facts"><div><span>▣ Date</span><b>${esc(formatDate(date))}</b></div><div><span>◷ Time</span><b>${record.call_time?esc(wallClockDate(record.call_time).toLocaleTimeString([],{hour:'numeric',minute:'2-digit'})):'To be confirmed'}</b></div><div><span>⌖ Location</span><b>${esc(location)}</b></div><div><span>♙ Photographer</span><b>${esc(p.photographer_email||'Your ShotCraft photographer')}</b></div></div><div class="detail-next"><p>${scheduled?'Your shoot is confirmed. Review the plan, location, and final details before the session.':record.production_approved?'Your photographer has prepared the creative plan. Review it and confirm when you are ready.':'Your photographer is shaping the creative direction. Updates will appear here.'}</p><div class="actions">${actions}<button class="secondary" type="button">Message photographer</button></div></div></section></div>`;bind()}
function displayShootPlanTitle(value){return String(value||'Shoot plan').replace(/\s*[·—]\s*(?:shoot )?production (?:pack|plan)\s*$/i,' · Shoot Plan').replace(/^\s*(?:shoot )?production (?:pack|plan)\s*$/i,'Shoot Plan')}
function planBlock(titleText,value,icon){const values=Array.isArray(value)?value:[value];return`<section class="plan-block"><div class="plan-icon">${icon}</div><h3>${esc(titleText)}</h3><ul>${values.filter(Boolean).map(item=>`<li>${esc(typeof item==='object'?JSON.stringify(item):item)}</li>`).join('')||'<li>Details will be added by your photographer.</li>'}</ul></section>`}
async function cinematicPlan(id){setNav('shoots');document.querySelectorAll('.nav button').forEach(button=>button.classList.remove('active'));document.querySelector('.gallery-nav')?.classList.add('active');const record=await getRecord(id),p=payload(record),pack=parsed(record.production_pack);if(!pack){galleryDetail(id);return}const mood=parsed(record.moodboard),gallery=(mood?.generated?.tiles||[]).map(tile=>tile.image_url).filter(Boolean),confirmed=['CLIENT_CONFIRMED','SCHEDULED'].includes(record.status),scheduled=record.status==='SCHEDULED',call=pack.call_sheet||{};app.innerHTML=`<div class="plan-page"><div class="detail-top"><div><button class="link detail-crumb" data-detail="${id}">Inquiries / ${esc(title(record))}</button><span> / Shoot plan</span><h1>${esc(displayShootPlanTitle(pack.title||title(record)))}</h1><p class="lede">The creative direction and practical details for your session.</p></div><button class="circle-action detail-back" data-detail="${id}" aria-label="Back to inquiry">←</button></div><div class="plan-visuals">${gallery.slice(0,5).map((image,index)=>`<img src="${esc(image)}" alt="Moodboard reference ${index+1}">`).join('')||'<div class="detail-placeholder">Moodboard references are being prepared.</div>'}</div><section class="plan-call-sheet"><div><div class="eyebrow">Call sheet</div><h2>${scheduled?'Your shoot is scheduled':confirmed?'Plan confirmed':'Ready for your review'}</h2><div class="call-grid">${Object.entries(call).slice(0,6).map(([key,value])=>`<div><span>${esc(key.replaceAll('_',' '))}</span><b>${esc(value)}</b></div>`).join('')}<div><span>Meeting location</span><b>${esc(record.meeting_location||'To be confirmed')}</b></div></div></div><div class="plan-decision"><p>${scheduled?'Everything is confirmed. Keep this plan handy on shoot day.':confirmed?'Your photographer has your confirmation and will finalize the schedule.':'Review the creative and logistical details, then confirm or request an adjustment.'}</p>${confirmed?'<div class="confirmed-banner">✓ Plan confirmed</div>':`<button class="primary" data-confirm="${id}">Confirm shoot plan →</button><button class="secondary" data-change="${id}">Request a change</button>`}<button class="secondary" type="button">Message photographer</button></div></section><div class="plan-card-grid">${planBlock('Location plan',pack.location_plan,'⌖')}${planBlock('Shot list',pack.shot_list,'◉')}${planBlock('Lighting plan',pack.lighting_plan,'☼')}${planBlock('Wardrobe checklist',pack.wardrobe_checklist,'◇')}</div><section class="weather-panel"><div><div class="eyebrow">Weather and contingencies</div><h2>Stay ready for the conditions.</h2></div><div class="weather-copy"><p><b>Recommendation:</b> ${esc(pack.weather_note||'Recheck the forecast three hours before call time.')}</p><p><b>Backup plan:</b> ${esc(pack.backup_plan||'Your photographer will confirm an alternate covered location if needed.')}</p></div></section></div>`;bind()}
function render(){if(current.view==='shoots')galleryView();else if(current.view==='create')create();else if(current.view==='details')galleryDetail(current.id);else if(current.view==='followup')followup(current.id);else if(current.view==='plan')cinematicPlan(current.id)}
window.onpopstate=event=>{current=event.state||{view:'shoots',id:null};render()};
async function init(){try{await hydrateClientSession();try{cityImages=await fetch('/static/city-images.json?v=2',{cache:'no-store'}).then(r=>r.json())}catch{cityImages={}}await refresh();const params=new URLSearchParams(location.search),view=params.get('view')||'overview',id=params.get('id');current={view,id:id?Number(id):null};render()}catch(error){if(location.pathname==='/auth')return;app.innerHTML=`<div class="card empty"><h2>We couldn’t load your workspace.</h2><p>${esc(error.message||'Please refresh and try again.')}</p><button class="primary" onclick="location.reload()">Try again</button></div>`}}
const renderGalleryDetailWithTimeline=galleryDetail;galleryDetail=async id=>{app.dataset.timelineId=String(id);await renderGalleryDetailWithTimeline(id);refreshTimeline()};
const renderCinematicPlanWithTimeline=cinematicPlan;cinematicPlan=async id=>{app.dataset.timelineId=String(id);await renderCinematicPlanWithTimeline(id);refreshTimeline()};
init();setInterval(async()=>{if(['create','followup','details','plan','messages','profile','edit-shoot'].includes(current.view))return;await refresh();render()},10000);setInterval(()=>{const view=new URLSearchParams(location.search).get('view');if(view==='details'||view==='plan'){app.dataset.timelineId=new URLSearchParams(location.search).get('id')||'';refreshTimeline()}},2000);
async function showMessages(id){const record=await getRecord(id),p=payload(record),status=statusInfo(record);setNav('shoots');const response=await fetch(`/api/inquiries/${id}/messages`,{cache:'no-store'}),messages=response.ok?await response.json():[],photographer=messages.find(message=>message.sender_role==='photographer')?.sender_name||p.photographer_email||'Your photographer';app.innerHTML=`<div class="conversation-page"><button class="link conversation-back" data-detail="${id}">← Back to shoot details</button><header class="conversation-hero"><div class="eyebrow">Shoot conversation</div><h1>${esc(title(record))}</h1><p class="lede">A dedicated thread for questions, changes, and final shoot details.</p></header><section class="card conversation"><header class="conversation-topbar"><div class="conversation-person"><span class="conversation-avatar" aria-hidden="true">${esc(photographer.charAt(0).toUpperCase())}</span><div><b>${esc(photographer)}</b><small>Your photographer</small></div></div><span class="status ${status[1]}">${status[0]}</span></header><div class="conversation-list" id="conversationList" role="log" aria-live="polite">${messages.map(message=>`<article class="message ${message.sender_role==='client'?'mine':''}"><small>${esc(message.sender_name)} · ${esc(formatDate(message.created_at))}</small><p>${esc(message.body)}</p></article>`).join('')||'<div class="conversation-empty"><span>✦</span><p>Start the conversation with your photographer.</p></div>'}</div><form id="messageForm" class="message-compose"><label class="sr-only" for="messageBody">Message your photographer</label><textarea id="messageBody" required maxlength="4000" placeholder="Write a message…"></textarea><div class="message-compose-footer"><span class="message-hint">Messages are shared with your photographer.</span><div class="actions"><span id="messageStatus" class="muted" aria-live="polite"></span><button class="primary">Send message <span aria-hidden="true">→</span></button></div></div></form></section></div>`;bind();document.getElementById('messageForm').onsubmit=event=>sendInquiryMessage(event,id,'client',clientUser.name||'Client',showMessages);requestAnimationFrame(()=>{const list=document.getElementById('conversationList');if(list)list.scrollTop=list.scrollHeight})}
async function sendInquiryMessage(event,id,role,name,done){event.preventDefault();const button=event.currentTarget.querySelector('button'),status=document.getElementById('messageStatus'),body=document.getElementById('messageBody').value.trim();if(!body)return;button.disabled=true;status.textContent='Sending…';try{const response=await fetch(`/api/inquiries/${id}/messages`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({body,sender_role:role,sender_name:name})}),raw=await response.text();let data={};try{data=raw?JSON.parse(raw):{}}catch{data={detail:'The server could not send this message. Please try again.'}}if(!response.ok)throw Error(data.detail||'Could not send your message.');await done(id)}catch(error){status.textContent=error.message;button.disabled=false}}
const renderClientWorkspace=render;render=()=>{if(current.view==='messages')return showMessages(current.id);return renderClientWorkspace()};
document.addEventListener('click',event=>{const button=event.target.closest('button');if(!button||button.dataset.message||button.textContent.trim()!=='Message photographer')return;event.preventDefault();if(current.id)go('messages',current.id)});
document.querySelectorAll('.nav button').forEach(button=>{if(button.textContent.includes('Messages'))button.onclick=()=>{const id=current.id||shoots[0]?.id;if(id)go('messages',id)}});
function updateClientMessageNotices(){const total=shoots.filter(record=>!isClientActionNeeded(record)).reduce((sum,record)=>sum+Number(record.unread_messages||0),0),messagesButton=[...document.querySelectorAll('.nav button')].find(button=>button.textContent.includes('Messages'));if(messagesButton){let badge=messagesButton.querySelector('.unread-message-badge');if(total){if(!badge){badge=document.createElement('span');badge.className='unread-message-badge';messagesButton.appendChild(badge)}badge.textContent=total>99?'99+':total;messagesButton.title=`${total} unread message${total===1?'':'s'}`}else{badge?.remove();messagesButton.removeAttribute('title')}}document.querySelector('.gallery-nav .nav-dot')?.classList.toggle('has-unread',!!total)}
function decorateClientUnread(){document.querySelectorAll('[data-detail]').forEach(button=>{const record=shoots.find(item=>item.id==button.dataset.detail),count=record&&isClientActionNeeded(record)?0:Number(record?.unread_messages||0),card=button.closest('.gallery-card,.shoot-row');if(!count||!card||card.querySelector('.inquiry-unread'))return;card.insertAdjacentHTML('afterbegin',`<span class="inquiry-unread">${count} new message${count===1?'':'s'}</span>`)});updateClientMessageNotices()}
const renderClientGalleryWithNotices=galleryView;galleryView=()=>{renderClientGalleryWithNotices();decorateClientUnread()};
const openClientMessageThread=showMessages;showMessages=async id=>{await fetch(`/api/inquiries/${id}/messages?reader_role=client`,{cache:'no-store'});await refresh();await openClientMessageThread(id);updateClientMessageNotices()};
setTimeout(async()=>{await refresh();updateClientMessageNotices()},0);
let clientMessageNoticeRefresh=false;
async function refreshClientMessageNotices(){
  if(clientMessageNoticeRefresh||document.hidden)return;
  clientMessageNoticeRefresh=true;
  try{
    await refresh();
    updateClientMessageNotices();
  }catch(_){/* Keep the current workspace usable during a transient refresh failure. */}
  finally{clientMessageNoticeRefresh=false}
}
// Keep the navigation badge current when a photographer writes, without replacing
// the page or interrupting a form the client may be editing.
setInterval(refreshClientMessageNotices,5000);
const clientMessagesNav=[...document.querySelectorAll('.nav button')].find(button=>button.textContent.includes('Messages'));if(clientMessagesNav){clientMessagesNav.dataset.view='messages';clientMessagesNav.onclick=()=>go('messages')}
const setClientWorkspaceNav=setNav;setNav=view=>{setClientWorkspaceNav(view);if(view==='messages'){document.querySelectorAll('.nav button').forEach(button=>button.classList.remove('active'));clientMessagesNav?.classList.add('active')}};
async function clientMessageInbox(){
  setNav('messages');
  app.innerHTML='<div class="loading">Loading conversations…</div>';
  try{
    await refresh();
    if(current.view!=='messages'||current.id)return;
    const conversations=shoots.filter(record=>!isClientActionNeeded(record)&&Number(record.message_count||0)>0).sort((a,b)=>String(b.latest_message?.created_at||'').localeCompare(String(a.latest_message?.created_at||'')));
    app.innerHTML=`<div class="head"><div><div class="eyebrow">Your conversations</div><h1>Messages</h1><p class="lede">All of your shoot conversations, with the important details close by.</p></div></div><div class="conversation-inbox">${conversations.map(record=>{const p=payload(record),status=statusInfo(record),when=record.call_time?formatDate(record.call_time):p.shoot_date?`Preferred date · ${formatDate(p.shoot_date)}`:'Date to be confirmed',location=record.meeting_location||'Location being planned',unread=Number(record.unread_messages||0);return`<article class="card conversation-preview rich-conversation"><div class="conversation-main"><div class="conversation-heading"><div><div class="eyebrow">Shoot conversation</div><h2>${esc(title(record))}</h2></div><span class="status ${status[1]}">${status[0]}</span></div><p class="conversation-title">Your photographer · ${esc(p.photographer_email||'ShotCraft Studio')}</p><div class="conversation-context"><span>▣ ${esc(when)}</span><span>⌖ ${esc(location)}</span></div></div><div class="conversation-action">${unread?`<span class="inquiry-unread inline-unread">${unread} new</span>`:''}<button class="primary" data-client-message="${record.id}">Open conversation →</button></div></article>`}).join('')||'<div class="card muted">No conversations have been started yet.</div>'}</div>`;
    bind();
    updateClientMessageNotices();
  }catch(error){
    if(current.view==='messages'&&!current.id)app.innerHTML=`<div class="card muted">We couldn’t load your conversations. Please try again.</div>`;
  }
}
document.addEventListener('click',event=>{const button=event.target.closest('[data-client-message]');if(!button)return;event.preventDefault();go('messages',button.dataset.clientMessage)});
const renderClientWorkspaceWithMessageInbox=render;render=()=>{if(current.view==='messages')return current.id?showMessages(current.id):clientMessageInbox();return renderClientWorkspaceWithMessageInbox()};
// The original availability-booking view was replaced by schedule recommendations.

/* Shared scheduling calendar: recommendations are preferences, never confirmations. */
const clientCalendarNav=document.querySelector('.nav button[data-view="messages"]');
if(clientCalendarNav)clientCalendarNav.insertAdjacentHTML('afterend','<button data-view="calendar"><span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M5 5h14v15H5zM8 3v4M16 3v4M5 9h14"/></svg></span><span>Shoot calendar</span></button>');
function calendarDate(value){const date=wallClockDate(value);return Number.isNaN(date.valueOf())?'—':date.toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric'})}
function calendarTime(value){const date=wallClockDate(value);return Number.isNaN(date.valueOf())?'':date.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit',hour12:true})}
async function clientScheduleOptions(id){setNav('calendar');const record=await getRecord(id),p=payload(record);let response=await fetch(`/api/inquiries/${id}/schedule-recommendations`,{cache:'no-store'}),request=response.ok?await response.json():null;if(!request?.suggestions?.length){app.innerHTML=`<button class="link" data-plan="${id}">← Back to shoot plan</button><div class="detail-head"><div class="eyebrow">Smart scheduling</div><h1>Choose a preferred time.</h1><p class="lede">We’ll prioritize your requested date and avoid your photographer’s confirmed shoots.</p></div><section class="card schedule-intro"><div><b>Preferred date</b><span>${esc(formatDate(p.shoot_date))}</span></div><button class="primary" data-generate-slots="${id}">Find recommended times →</button><p class="muted" id="slotStatus"></p></section>`;bind();return}const status=request.status==='PENDING_PHOTOGRAPHER'?'Your preferred time is with the photographer for final confirmation.':request.status==='CONFIRMED'?'Your shoot time is confirmed.':'Choose one time for your photographer to confirm.';app.innerHTML=`<button class="link" data-plan="${id}">← Back to shoot plan</button><div class="detail-head"><div class="eyebrow">Smart scheduling</div><h1>Pick your preferred time.</h1><p class="lede">${esc(status)}</p></div><section class="schedule-options">${request.suggestions.map((slot,index)=>`<article class="card schedule-option ${request.selected_starts_at===slot.starts_at?'selected':''}"><span class="schedule-option-number">0${index+1}</span><div><h2>${esc(calendarDate(slot.starts_at))}</h2><p>${esc(calendarTime(slot.starts_at))} – ${esc(calendarTime(slot.ends_at))}</p><small>${esc(slot.location)} · ${esc(slot.rationale)}</small></div>${request.status==='PENDING_CLIENT'?`<button class="primary" data-select-slot="${id}" data-start="${esc(slot.starts_at)}" data-end="${esc(slot.ends_at)}" data-location="${esc(slot.location)}">Choose this time →</button>`:request.selected_starts_at===slot.starts_at?'<span class="status ready">PREFERRED TIME</span>':''}</article>`).join('')}</section>${request.status==='PENDING_CLIENT'?`<button class="secondary" data-generate-slots="${id}">Refresh recommendations</button>`:''}<p class="muted" id="slotStatus"></p>`;bind()}
async function clientCalendar(){setNav('calendar');const response=await fetch('/api/calendar?client_email='+encodeURIComponent(clientUser.email||''),{cache:'no-store'}),data=response.ok?await response.json():{entries:[]},entries=data.entries||[];const start=new Date();start.setHours(0,0,0,0);const days=Array.from({length:14},(_,index)=>{const day=new Date(start);day.setDate(day.getDate()+index);return day});app.innerHTML=`<div class="head"><div><div class="eyebrow">Your shoot calendar</div><h1>Dates worth looking forward to.</h1><p class="lede">Scheduled shoots and your pending time preferences, all in one calm view.</p></div></div><section class="calendar-board"><div class="calendar-board-head"><b>${esc(start.toLocaleDateString(undefined,{month:'long',year:'numeric'}))}</b><span>${entries.filter(item=>item.kind==='scheduled').length} confirmed shoot${entries.filter(item=>item.kind==='scheduled').length===1?'':'s'}</span></div><div class="calendar-week">${days.map(day=>{const key=wallClockDateKey(day),events=entries.filter(item=>String(item.starts_at).slice(0,10)===key);return`<article class="calendar-day ${events.length?'has-event':''}"><div><small>${esc(day.toLocaleDateString(undefined,{weekday:'short'}))}</small><b>${day.getDate()}</b></div>${events.map(item=>`<button class="calendar-event ${item.kind}" data-calendar-inquiry="${item.inquiry_id}">${esc(calendarTime(item.starts_at))}<span>${esc(item.kind==='scheduled'?'Shoot confirmed':'Awaiting confirmation')}</span></button>`).join('')}</article>`}).join('')}</div></section><section class="calendar-agenda"><div class="eyebrow">Upcoming shoots</div>${entries.map(item=>`<article class="card calendar-agenda-item"><div><b>${esc(calendarDate(item.starts_at))} · ${esc(calendarTime(item.starts_at))}</b><span>${esc(item.location||'Location to be confirmed')}</span></div><span class="status ${item.kind==='scheduled'?'scheduled':'ready'}">${item.kind==='scheduled'?'CONFIRMED':'PENDING'}</span></article>`).join('')||'<div class="card muted">No confirmed shoots yet. When your plan is ready, choose a preferred time and we’ll coordinate the booking.</div>'}</section>`;bind()}
async function generateScheduleOptions(id){const status=document.getElementById('slotStatus'),button=document.querySelector('[data-generate-slots]');button.disabled=true;status.textContent='Analyzing the photographer’s calendar…';try{const response=await fetch(`/api/inquiries/${id}/schedule-recommendations`,{method:'POST'}),raw=await response.text();let data={};try{data=raw?JSON.parse(raw):{}}catch{data={detail:'Scheduling could not be completed. Please try again.'}}if(!response.ok)throw Error(data.detail||'Could not find times right now.');await refresh();clientScheduleOptions(id)}catch(error){status.textContent=error.message;button.disabled=false}}
async function selectScheduleOption(button){const status=document.getElementById('slotStatus');button.disabled=true;status.textContent='Sending your preferred time to the photographer…';try{const response=await fetch(`/api/inquiries/${button.dataset.selectSlot}/schedule-selection`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({starts_at:button.dataset.start,ends_at:button.dataset.end,location:button.dataset.location})}),data=await response.json();if(!response.ok)throw Error(data.detail||'Could not save your time preference.');await refresh();clientScheduleOptions(button.dataset.selectSlot)}catch(error){status.textContent=error.message;button.disabled=false}}
document.addEventListener('click',event=>{const button=event.target.closest('[data-generate-slots],[data-select-slot],[data-calendar-inquiry]');if(!button)return;event.preventDefault();if(button.dataset.generateSlots)generateScheduleOptions(button.dataset.generateSlots);else if(button.dataset.selectSlot)selectScheduleOption(button);else go('details',button.dataset.calendarInquiry)});
const clientPlanWithScheduling=cinematicPlan;cinematicPlan=async id=>{await clientPlanWithScheduling(id);const record=await getRecord(id);if(record.status!=='CLIENT_CONFIRMED')return;const decision=app.querySelector('.plan-decision');if(decision&&!decision.querySelector('[data-smart-schedule]'))decision.insertAdjacentHTML('beforeend',`<button class="primary" data-smart-schedule="${id}">Choose a preferred time →</button>`)};
document.addEventListener('click',event=>{const button=event.target.closest('[data-smart-schedule]');if(!button)return;event.preventDefault();go('schedule-options',button.dataset.smartSchedule)});
const renderClientWorkspaceWithCalendar=render;render=()=>{if(current.view==='calendar')return clientCalendar();if(current.view==='schedule-options')return clientScheduleOptions(current.id);return renderClientWorkspaceWithCalendar()};

// Client-facing creative direction: use the photographer's completed
// moodboard first, then make city imagery a useful temporary fallback.
const clientCreativePreviewStyle=document.createElement('style');
clientCreativePreviewStyle.textContent='.detail-strip.client-creative-preview{position:relative;display:grid;grid-template-columns:1.45fr repeat(3,1fr);gap:4px;overflow:hidden;background:#211f25}.client-creative-preview>img{display:block!important;width:100%!important;height:100%!important;min-height:276px!important;object-fit:cover!important}.client-creative-preview>img:first-of-type{grid-row:span 2}.client-creative-preview .creative-preview-label{position:absolute;left:18px;top:17px;z-index:1;display:inline-flex;align-items:center;gap:7px;padding:7px 10px;border:1px solid #ffffff35;border-radius:999px;background:#18161ad1;color:#fff;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.client-creative-preview .creative-preview-label i{width:7px;height:7px;border-radius:50%;background:#a7e4bc}.detail-strip.client-creative-preview.is-city-fallback:after{content:"Location inspiration";position:absolute;left:18px;bottom:17px;padding:7px 10px;border-radius:999px;background:#18161ad1;color:#fff;font-size:11px;font-weight:750}.detail-strip.client-creative-pending{display:grid;place-items:center;min-height:284px;padding:26px;overflow:hidden;background:radial-gradient(circle at 18% 18%,#3b334d 0,transparent 35%),radial-gradient(circle at 88% 76%,#544035 0,transparent 38%),#211f25}.creative-pending-grid{position:absolute;inset:20px;display:grid;grid-template-columns:1.4fr repeat(3,1fr);gap:5px;opacity:.38}.creative-pending-grid span{border:1px solid #ffffff1c;background:linear-gradient(120deg,#ffffff12,#ffffff04)}.creative-pending-grid span:first-child{grid-row:span 2}.creative-pending-copy{position:relative;z-index:1;max-width:330px;color:#f8f4f0;text-align:center}.creative-pending-copy i{display:grid;place-items:center;width:30px;height:30px;margin:0 auto 12px;border:2px solid #ffffff38;border-top-color:#c2b1ff;border-radius:50%;animation:workspace-spin .8s linear infinite}.creative-pending-copy b,.creative-pending-copy span{display:block}.creative-pending-copy b{font:600 22px Georgia,serif}.creative-pending-copy span{margin-top:5px;color:#c9c2cd;font-size:13px}@media(max-width:700px){.detail-strip.client-creative-preview{grid-template-columns:1.4fr 1fr 1fr}.client-creative-preview>img{min-height:165px!important}.client-creative-preview>img:nth-of-type(n+4){display:none!important}.detail-strip.client-creative-pending{min-height:210px}}';
document.head.appendChild(clientCreativePreviewStyle);

const moodboardImageUrls=record=>{
  const mood=parsed(record.moodboard)||{};
  return (mood.generated?.tiles||mood.tiles||[])
    .map(tile=>typeof tile==='string'?tile:tile?.image_url)
    .filter(Boolean)
    .slice(0,4);
};
const creativePreviewMarkup=(images,kind='moodboard')=>kind==='city'
  ? `<span class="creative-preview-label"><i></i>Location context</span><img src="${esc(images[1]||images[0])}" alt="Location context"><div class="location-context-note"><b>Your shoot location</b><span>Temporary preview—your creative direction is being prepared.</span></div>`
  : `<span class="creative-preview-label"><i></i>Creative direction</span>${images.map((image,index)=>`<img src="${esc(image)}" alt="Creative direction reference ${index+1}">`).join('')}`;
const creativePendingMarkup=()=>'<div class="creative-pending-copy"><i aria-hidden="true"></i><b>Shaping your creative direction</b><span>Your photographer’s visual references will appear here shortly. You can keep using your workspace while we prepare them.</span></div>';
const galleryDetailWithCreativePreview=galleryDetail;
galleryDetail=async id=>{
  await galleryDetailWithCreativePreview(id);
  if(current.view!=='details'||Number(current.id)!==Number(id))return;
  const strip=app.querySelector('.detail-strip');
  if(!strip)return;
  const record=await getRecord(id);
  const moodboardImages=moodboardImageUrls(record);
  if(moodboardImages.length){
    strip.className='detail-strip client-creative-preview';
    strip.innerHTML=creativePreviewMarkup(moodboardImages);
    return;
  }
  const existingImages=Array.from(strip.querySelectorAll('img')).map(image=>image.src).filter(Boolean);
  if(existingImages.length){
    strip.className='detail-strip client-creative-preview is-city-fallback';
    strip.innerHTML=creativePreviewMarkup(existingImages.slice(0,4),'city');
    return;
  }
  strip.className='detail-strip client-creative-pending';
  strip.innerHTML=creativePendingMarkup();
  const place=record.meeting_location||payload(record).location;
  if(!place)return;
  try{
    const response=await fetch(`/api/city-images?city=${encodeURIComponent(place)}`,{cache:'no-store'});
    const city=await response.json();
    if(!response.ok||!city.gallery?.length||current.view!=='details'||Number(current.id)!==Number(id)||!strip.isConnected)return;
    strip.className='detail-strip client-creative-preview is-city-fallback';
    strip.innerHTML=creativePreviewMarkup(city.gallery.slice(0,4),'city');
  }catch(_){/* The polished preparing state remains if city imagery is unavailable. */}
};
const setClientNavWithCalendar=setNav;setNav=view=>{setClientNavWithCalendar(view);if(['calendar','schedule-options'].includes(view)){document.querySelectorAll('.nav button').forEach(button=>button.classList.remove('active'));document.querySelector('.nav button[data-view="calendar"]')?.classList.add('active')}};

/* A confirmed schedule always wins over the earlier date-only production-pack draft. */
const clientPlanWithConfirmedCallTime=cinematicPlan;cinematicPlan=async id=>{await clientPlanWithConfirmedCallTime(id);const record=await getRecord(id);if(record.status!=='SCHEDULED'||!record.call_time)return;const callTime=wallClockDate(record.call_time),grid=app.querySelector('.call-grid');if(!grid||Number.isNaN(callTime.valueOf()))return;const dateField=[...grid.children].find(field=>field.querySelector('span')?.textContent.trim().toLowerCase()==='date');if(dateField){const value=dateField.querySelector('b');if(value)value.textContent=callTime.toLocaleDateString(undefined,{year:'numeric',month:'long',day:'numeric'})}if(![...grid.children].some(field=>field.querySelector('span')?.textContent.trim().toLowerCase()==='time'))grid.insertAdjacentHTML('beforeend',`<div><span>Time</span><b>${esc(callTime.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'}))}</b></div>`)};

async function confirmPreShootReadiness(id){const button=document.querySelector('[data-pre-shoot-ready]'),status=document.getElementById('preShootStatus');if(button)button.disabled=true;if(status)status.textContent='Saving your check-in…';try{const response=await fetch(`/api/inquiries/${id}/pre-shoot-checkin`,{method:'POST'}),data=await response.json();if(!response.ok)throw Error(data.detail||'Could not save your check-in.');await refresh();cinematicPlan(id)}catch(error){if(status)status.textContent=error.message;if(button)button.disabled=false}}
let preShootMessageId=null;const messagesWithPreShootHelp=showMessages;showMessages=async id=>{await messagesWithPreShootHelp(id);if(Number(id)!==preShootMessageId)return;const input=document.getElementById('messageBody');if(input){input.value='Hi, I have a question about getting ready for our shoot. Could you please help me with the details?';input.focus()}preShootMessageId=null};
document.addEventListener('click',event=>{const button=event.target.closest('[data-pre-shoot-ready],[data-pre-shoot-help]');if(!button)return;event.preventDefault();if(button.dataset.preShootReady)return confirmPreShootReadiness(button.dataset.preShootReady);preShootMessageId=Number(button.dataset.preShootHelp);go('messages',button.dataset.preShootHelp)});
const clientPlanWithPreShootReadiness=cinematicPlan;cinematicPlan=async id=>{await clientPlanWithPreShootReadiness(id);const record=await getRecord(id),pack=parsed(record.production_pack);if(record.status!=='SCHEDULED'||!pack||app.querySelector('.pre-shoot-checkin'))return;const checklist=[...(pack.wardrobe_checklist||[]).slice(0,2),record.meeting_location?`Plan to arrive at ${record.meeting_location}.`:'Confirm the meeting location with your photographer.'];const ready=record.pre_shoot_checkin?.status==='READY',panel=`<section class="card pre-shoot-checkin ${ready?'is-ready':''}"><div><div class="eyebrow">AI pre-shoot check-in</div><h2>${ready?'You’re ready for shoot day.':'A quick check before shoot day.'}</h2><p>${ready?'Your photographer can see that you reviewed the essentials.':'ShotCraft pulled the practical essentials from your approved plan.'}</p><ul>${checklist.map(item=>`<li>${esc(item)}</li>`).join('')}</ul></div><div class="pre-shoot-actions">${ready?'<div class="confirmed-banner">✓ Ready confirmed</div>':`<button class="primary" data-pre-shoot-ready="${id}">I’m ready →</button><button class="secondary" data-pre-shoot-help="${id}">I have a question</button>`}<span class="muted" id="preShootStatus"></span></div></section>`;app.querySelector('.weather-panel')?.insertAdjacentHTML('afterend',panel)};
const clientOverviewNav=[...document.querySelectorAll('.nav button')].find(button=>button.textContent.includes('Overview'));
const clientInquiriesNav=[...document.querySelectorAll('.nav button')].find(button=>button.textContent.includes('Inquiries'));
if(clientOverviewNav)clientOverviewNav.dataset.view='overview';
if(clientInquiriesNav)clientInquiriesNav.dataset.view='inquiries';
const renderClientWorkspaceWithDedicatedNav=render;
render=()=>{if(current.view==='overview')return clientOverview();if(current.view==='inquiries'||current.view==='shoots')return galleryView();if(current.view==='messages'){const inquiryId=Number(new URLSearchParams(location.search).get('id'));return inquiryId?showMessages(inquiryId):clientMessageInbox()}return renderClientWorkspaceWithDedicatedNav()};
const setClientNavWithDedicatedNav=setNav;
setNav=view=>{setClientNavWithDedicatedNav(view);document.querySelectorAll('.nav button').forEach(button=>button.classList.remove('active'));if(view==='overview')clientOverviewNav?.classList.add('active');else if(view==='inquiries'||view==='shoots')clientInquiriesNav?.classList.add('active');else if(view==='messages')clientMessagesNav?.classList.add('active');else if(['calendar','schedule-options'].includes(view))document.querySelector('.nav button[data-view="calendar"]')?.classList.add('active');else if(view==='create')document.querySelector('.nav button[data-view="create"]')?.classList.add('active')};
go=(view,id=null,push=true)=>{if(view==='shoots')view='inquiries';current={view,id:id?Number(id):null};if(push){const query=new URLSearchParams();query.set('view',view);if(id)query.set('id',id);history.pushState(current,'',`/client?${query}`)}render()};
if(clientInquiriesNav){const label=clientInquiriesNav.querySelector('.nav-icon + span');if(label)label.textContent='My Inquiries'};
clientInquiriesNav?.querySelector('.nav-dot')?.remove();
setNav=view=>{const activeView=view==='shoots'?current.view:view;document.querySelectorAll('.nav button').forEach(button=>button.classList.remove('active'));const button=activeView==='overview'?clientOverviewNav:activeView==='messages'?clientMessagesNav:['calendar','schedule-options'].includes(activeView)?document.querySelector('.nav button[data-view="calendar"]'):activeView==='create'?document.querySelector('.nav button[data-view="create"]'):clientInquiriesNav;button?.classList.add('active')};
function clientOverview(){setNav('overview');const scheduled=shoots.filter(record=>record.status==='SCHEDULED').sort((a,b)=>String(a.call_time||'').localeCompare(String(b.call_time||'')));const next=scheduled[0]||shoots[0]||null,needsAction=shoots.filter(record=>record.status==='NEEDS_INFORMATION'||record.production_approved&&!['CLIENT_CONFIRMED','SCHEDULED'].includes(record.status)),unread=shoots.reduce((total,record)=>total+Number(record.unread_messages||0),0),p=next?payload(next):{},when=next?(next.call_time?formatDate(next.call_time):p.shoot_date?`Preferred date · ${formatDate(p.shoot_date)}`:'Date to be confirmed'):'No shoots scheduled yet',location=next?.meeting_location||'Location to be confirmed',status=next?statusInfo(next):null;app.innerHTML=`<div class="client-overview"><header class="overview-head"><div><div class="eyebrow">Client workspace</div><h1>Welcome back, ${esc(clientUser.name?.split(' ')[0]||'there')}.</h1><p>Everything important for your shoots, in one calm place.</p></div><button class="primary" data-view="create">New inquiry →</button></header>${next?`<section class="overview-next"><div class="overview-next-copy"><div class="eyebrow">${next.status==='SCHEDULED'?'Next up':'In progress'}</div><h2>${esc(title(next))}</h2><span class="status ${status[1]}">${status[0]}</span><div class="overview-facts"><div><small>WHEN</small><b>${esc(when)}</b></div><div><small>WHERE</small><b>${esc(location)}</b></div></div><div class="actions"><button class="primary" data-detail="${next.id}">View shoot details →</button>${unread?`<button class="secondary" data-view="messages">Open messages</button>`:''}</div></div><div class="overview-journey"><div><i>✓</i><span>Inquiry received</span></div><div><i>✓</i><span>Creative direction</span></div><div><i>${next.production_approved?'✓':'3'}</i><span>Shoot plan</span></div><div class="${next.status==='SCHEDULED'?'done':''}"><i>${next.status==='SCHEDULED'?'✓':'4'}</i><span>Scheduled</span></div></div></section>`:`<section class="overview-empty"><div><div class="eyebrow">Your next shoot</div><h2>Start with a simple idea.</h2><p>Tell us the mood, purpose, and timing. ShotCraft will guide the rest.</p></div><button class="primary" data-view="create">Start an inquiry →</button></section>`}<section class="overview-summary"><article class="overview-stat"><small>ACTION NEEDED</small><b>${needsAction.length}</b><p>${needsAction.length?'A shoot is ready for your input.':'You’re all caught up.'}</p></article><article class="overview-stat"><small>UPCOMING SHOOTS</small><b>${scheduled.length}</b><p>${scheduled.length?'Your confirmed sessions are on your calendar.':'Confirm a plan to schedule your first shoot.'}</p></article><article class="overview-stat"><small>MESSAGES</small><b>${unread}</b><p>${unread?'A photographer update is waiting for you.':'No unread messages.'}</p></article></section><section class="overview-list-head"><div><div class="eyebrow">Your work</div><h2>Recent inquiries</h2></div><button class="link" data-view="inquiries">View all inquiries →</button></section><section class="overview-recent">${shoots.slice(0,3).map(record=>{const itemStatus=statusInfo(record),itemPayload=payload(record);return`<button class="overview-recent-row" data-detail="${record.id}"><span class="overview-recent-status ${itemStatus[1]}">${itemStatus[0]}</span><span><b>${esc(title(record))}</b><small>${esc(record.call_time?formatDate(record.call_time):itemPayload.shoot_date?formatDate(itemPayload.shoot_date):'Date to be confirmed')}</small></span><span class="overview-row-arrow">→</span></button>`}).join('')||'<div class="card empty">No inquiries yet. Start one whenever an idea strikes.</div>'}</section></div>`;bind();updateClientMessageNotices()}
function clientOverviewNextShoot(record){const p=payload(record),city=(p.message||'').match(/Seattle|Delhi|New Delhi/i)?.[0]?.toLowerCase().replace('new delhi','delhi'),gallery=cityImages[city]?.gallery||[],mood=parsed(record.moodboard),moodTiles=mood?.generated?.tiles||[],moodImage=moodTiles[2]?.image_url||moodTiles.find(tile=>tile?.image_url)?.image_url,image=moodImage||gallery[0]||null,location=record.meeting_location||p.location||(city==='delhi'?'Delhi, India':city==='seattle'?'Seattle, Washington':'Location to be confirmed'),duration=Number(p.duration_minutes||0);return`<section class="overview-priority card overview-next-shoot client-overview-next-shoot"><div class="overview-next-main"><div class="eyebrow">Coming up next</div><div class="overview-next-heading"><div><h2>${esc(title(record))}</h2><p class="overview-next-client">Your confirmed shoot</p></div></div><div class="overview-next-details"><div><small>Date & time</small><b>${esc(formatDate(record.call_time))}</b></div><div><small>Location</small><b>${esc(location)}</b></div><div><small>Session</small><b>${esc(duration?`${duration} minutes`:'Duration pending')}</b></div></div><div class="overview-next-action-copy"><span>✓ Booking confirmed</span><button class="primary" data-detail="${record.id}">View shoot details</button></div></div><div class="overview-next-visual">${image?`<img src="${esc(image)}" alt="${esc(title(record))} creative reference" loading="lazy">`:''}<span class="overview-next-status">UP NEXT</span></div></section>`}
const clientOverviewWithDateSort=clientOverview;
clientOverview=()=>{
  const originalShoots=shoots;
  const dateValue=record=>{
    const value=record.call_time||payload(record).shoot_date;
    const timestamp=value?wallClockDate(value).valueOf():NaN;
    return Number.isFinite(timestamp)?timestamp:Number.MAX_SAFE_INTEGER;
  };
  // A cancelled shoot stays in My Inquiries, but cannot be the overview's
  // active hero or inflate its action count.
  const activeShoots=shoots.filter(record=>record.status!=='CANCELLED');
  const scheduled=activeShoots.filter(record=>record.status==='SCHEDULED')
    .sort((a,b)=>dateValue(a)-dateValue(b)||b.id-a.id);
  shoots=[...activeShoots].sort((a,b)=>dateValue(a)-dateValue(b));
  try{
    clientOverviewWithDateSort();
    const hero=app.querySelector('.overview-next');
    const heading=app.querySelector('.overview-list-head');
    const list=app.querySelector('.overview-recent');
    if(hero&&scheduled[0])hero.outerHTML=clientOverviewNextShoot(scheduled[0]);
    if(heading){
      const eyebrow=heading.querySelector('.eyebrow'),title=heading.querySelector('h2'),link=heading.querySelector('[data-view="inquiries"]');
      if(eyebrow)eyebrow.textContent='Coming up';
      if(title)title.textContent='My scheduled shoots';
      if(link)link.textContent='View all shoots →';
    }
    if(list){
      list.className='overview-projects client-scheduled-projects';
      list.innerHTML=scheduled.slice(0,2).map((record,index)=>galleryCard(record,index+1)).join('')||'<div class="card empty">No scheduled shoots yet.</div>';
    }
    bind();
    decorateClientUnread();
  }finally{shoots=originalShoots}
};

/* Photographer-authored scheduling options. The client can only choose a saved
   option, so the selection is deterministic and never parsed from a message. */
async function clientScheduleOptions(id){
  setNav('calendar');
  const requestResponse=await fetch(`/api/inquiries/${id}/schedule-recommendations`,{cache:'no-store'}),request=requestResponse.ok?await requestResponse.json():null;
  if(!request?.suggestions?.length){
    app.innerHTML=`<button class="link" data-plan="${id}">← Back to shoot plan</button><div class="detail-head"><div class="eyebrow">Scheduling</div><h1>Your photographer is preparing times.</h1><p class="lede">You’ll be able to select one exact option as soon as your photographer sends it.</p></div><section class="card"><div class="notice"><b>Awaiting time options</b><br>No booking is being held yet. We’ll show only times proposed by your photographer.</div></section>`;
    bind();return;
  }
  const status=request.status==='PENDING_PHOTOGRAPHER'?'Your selected time is with your photographer for final confirmation.':request.status==='CONFIRMED'?'Your shoot time is confirmed.':'Choose one time for your photographer to confirm.';
  app.innerHTML=`<button class="link" data-plan="${id}">← Back to shoot plan</button><div class="detail-head"><div class="eyebrow">Scheduling</div><h1>Choose your preferred time.</h1><p class="lede">${esc(status)}</p></div><section class="schedule-options">${request.suggestions.map((slot,index)=>`<article class="card schedule-option ${request.selected_starts_at===slot.starts_at?'selected':''}"><span class="schedule-option-number">0${index+1}</span><div><h2>${esc(calendarDate(slot.starts_at))}</h2><p>${esc(calendarTime(slot.starts_at))} – ${esc(calendarTime(slot.ends_at))}</p><small>${esc(slot.location)}</small></div>${request.status==='PENDING_CLIENT'?`<button class="primary" data-select-slot="${id}" data-start="${esc(slot.starts_at)}" data-end="${esc(slot.ends_at)}" data-location="${esc(slot.location)}">Choose this time →</button>`:request.selected_starts_at===slot.starts_at?'<span class="status ready">YOUR SELECTION</span>':''}</article>`).join('')}</section><p class="muted" id="slotStatus"></p>`;
  bind();
}

/* Overview metrics are shortcuts, not passive counters. */
const overviewShortcutStyles=document.createElement('style');
overviewShortcutStyles.textContent='.overview-stat-link{position:relative;cursor:pointer;transition:border-color .18s ease,box-shadow .18s ease,transform .18s ease}.overview-stat-link:hover,.overview-stat-link:focus-visible{border-color:#aa97df;box-shadow:0 12px 26px #3f266712;outline:0;transform:translateY(-2px)}.overview-stat-cta{display:flex;align-items:center;gap:6px;margin-top:15px;color:#6f55c9;font-size:12px;font-weight:800}.overview-actions{margin:14px 0 24px;padding:22px;border:1px solid #d9cfef;border-radius:16px;background:linear-gradient(125deg,#f6f2ff,#fff)}.overview-actions-head{display:flex;align-items:end;justify-content:space-between;gap:18px;margin-bottom:14px}.overview-actions-head h2{margin:7px 0 0;font:500 28px/.98 Georgia,serif}.overview-action-list{display:grid;gap:10px}.overview-action-row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:18px;padding:16px 17px;border:1px solid #e1daeb;border-radius:12px;background:#fff}.overview-action-row b,.overview-action-row span{display:block}.overview-action-row span{margin-top:4px;color:#746d7c;font-size:13px}@media(max-width:760px){.overview-action-row{grid-template-columns:1fr}.overview-action-row .primary{justify-self:start}}';
document.head.appendChild(overviewShortcutStyles);
const clientOverviewWithShortcuts=clientOverview;
clientOverview=()=>{
  clientOverviewWithShortcuts();
  const actions=shoots.map(record=>({record,action:clientActionFor(record)})).filter(item=>item.action);
  const actionCount=actions.length;
  const actionStat=app.querySelector('.overview-stat');
  if(actionStat){
    const count=actionStat.querySelector('b'),copy=actionStat.querySelector('p');
    if(count)count.textContent=actionCount;
    if(copy)copy.textContent=actionCount?'A shoot is ready for your input.':'You’re all caught up.';
  }
  app.querySelector('.overview-head .primary')?.remove();
  app.querySelectorAll('.overview-journey div').forEach(step=>{
    if(step.querySelector('i')?.textContent.trim()==='✓')step.classList.add('done');
  });
  if(actions.length){
    const actionMarkup=`<section class="overview-actions" id="client-actions"><div class="overview-actions-head"><div><div class="eyebrow">Action needed</div><h2>${actions.length===1?'One shoot needs you.':`${actions.length} shoots need you.`}</h2></div></div><div class="overview-action-list">${actions.map(({record,action})=>`<article class="overview-action-row"><div><b>${esc(title(record))}</b><span>${esc(action.description)}</span></div><button class="primary" data-client-action="${record.id}" data-action-view="${action.view}">${esc(action.label)} →</button></article>`).join('')}</div></section>`;
    app.querySelector('.overview-summary')?.insertAdjacentHTML('beforebegin',actionMarkup);
    app.querySelectorAll('[data-client-action]').forEach(button=>button.onclick=()=>go(button.dataset.actionView,button.dataset.clientAction));
  }
  const openActions=()=>{
    if(actions.length===1){const {record,action}=actions[0];go(action.view,record.id);return}
    if(actions.length>1){app.querySelector('#client-actions')?.scrollIntoView({behavior:'smooth',block:'start'});return}
    go('inquiries');
  };
  const shortcuts=[
    {label:actionCount?'Review actions':'View inquiries',goTo:openActions},
    {label:'Open calendar',goTo:()=>go('calendar')},
    {label:'Open messages',goTo:()=>go('messages')},
  ];
  app.querySelectorAll('.overview-stat').forEach((stat,index)=>{
    const shortcut=shortcuts[index];
    if(!shortcut)return;
    stat.classList.add('overview-stat-link');
    stat.setAttribute('role','button');
    stat.tabIndex=0;
    stat.setAttribute('aria-label',shortcut.label);
    stat.insertAdjacentHTML('beforeend',`<span class="overview-stat-cta">${shortcut.label} <span aria-hidden="true">→</span></span>`);
    stat.onclick=shortcut.goTo;
    stat.onkeydown=event=>{
      if(event.key==='Enter'||event.key===' '){event.preventDefault();shortcut.goTo()}
    };
  });
};

/* Optional, AI-generated inspiration lives on the overview rather than competing
   with the client's active shoot. The response is kept only for this page visit. */
const shootIdeaTheme=document.createElement('link');
shootIdeaTheme.rel='stylesheet';
shootIdeaTheme.href='/static/client-ideas.css?v=1';
document.head.appendChild(shootIdeaTheme);
let shootIdeas=null,shootIdeasLoading=false,selectedShootIdea='';
function renderShootIdeas(){
  const existing=app.querySelector('.shoot-ideas');
  if(!existing)return;
  if(shootIdeasLoading){
    existing.innerHTML='<div class="shoot-ideas-head"><div><div class="eyebrow">Creative spark</div><h2>Ideas for your next shoot</h2></div></div><p class="shoot-ideas-loading">ShotCraft is finding a few directions that build on your work…</p>';
    return;
  }
  if(!shootIdeas?.length){
    existing.innerHTML='<div class="shoot-ideas-head"><div><div class="eyebrow">Creative spark</div><h2>Ideas for your next shoot</h2></div><button class="link" data-refresh-shoot-ideas>Try again →</button></div><p class="shoot-ideas-loading">Ideas are temporarily unavailable. Your existing shoots are unchanged.</p>';
    return;
  }
  existing.innerHTML=`<div class="shoot-ideas-head"><div><div class="eyebrow">Creative spark</div><h2>Ideas for your next shoot</h2><p>Optional directions, generated from the shoots you’ve already planned.</p></div><button class="link" data-refresh-shoot-ideas>Refresh ideas →</button></div><div class="shoot-idea-grid">${shootIdeas.map((idea,index)=>`<article class="shoot-idea-card"><span class="shoot-idea-number">0${index+1}</span><h3>${esc(idea.title)}</h3><p>${esc(idea.description)}</p><button class="secondary" data-use-shoot-idea="${index}">Start with this idea →</button></article>`).join('')}</div>`;
}
async function loadShootIdeas(force=false){
  if(shootIdeasLoading||(!force&&shootIdeas))return;
  if(force)shootIdeas=null;
  shootIdeasLoading=true;renderShootIdeas();
  try{
    const response=await fetch('/api/client/shoot-ideas?client_email='+encodeURIComponent(clientUser.email||'')+(force?'&refresh=true':''),{cache:'no-store'});
    const data=await response.json();
    shootIdeas=response.ok&&Array.isArray(data.ideas)?data.ideas:null;
  }catch(_){shootIdeas=null}
  shootIdeasLoading=false;renderShootIdeas();
}
const clientOverviewWithIdeas=clientOverview;
clientOverview=()=>{
  clientOverviewWithIdeas();
  app.querySelector('.overview-summary')?.insertAdjacentHTML('afterend','<section class="shoot-ideas" aria-live="polite"></section>');
  renderShootIdeas();
  loadShootIdeas();
};
const clientCreateWithIdea=create;
create=()=>{
  clientCreateWithIdea();
  if(!selectedShootIdea)return;
  const message=document.getElementById('message');
  if(message){message.value=selectedShootIdea;message.focus()}
  selectedShootIdea='';
};
document.addEventListener('click',event=>{
  const ideaButton=event.target.closest('[data-use-shoot-idea]');
  if(ideaButton){
    const idea=shootIdeas?.[Number(ideaButton.dataset.useShootIdea)];
    if(!idea)return;
    event.preventDefault();selectedShootIdea=idea.prompt;go('create');return;
  }
  if(event.target.closest('[data-refresh-shoot-ideas]')){event.preventDefault();loadShootIdeas(true)}
});

/* Complete intake for the draft-to-review workflow. */
create=()=>{setNav('create');app.innerHTML=`<div class="head"><div><div class="eyebrow">New inquiry</div><h1>Plan your shoot in one go.</h1><p class="lede">Share the creative essentials and your availability. Your photographer will receive one complete draft to review.</p></div></div><section class="card"><form id="inquiryForm"><div class="form-grid"><div class="field"><label>Your name</label><input value="${esc(clientUser.name)}" readonly></div><div class="field"><label>Email address</label><input value="${esc(clientUser.email)}" readonly></div><div class="field"><label>Preferred shoot date</label><input id="date" type="date" required></div><div class="field"><label>Duration</label><select id="duration"><option value="30">30 minutes</option><option value="60">1 hour</option><option value="120" selected>2 hours</option><option value="240">Half day (4 hours)</option><option value="480">Full day (8 hours)</option></select></div><div class="field"><label>Location or city</label><input id="location" required placeholder="e.g. Chicago, IL or Studio Alpha"></div><div class="field"><label>Estimated budget</label><input id="budget" type="number" min="0" step="50" placeholder="$500" required></div><div class="field"><label>Final edited photos</label><input id="deliverableCount" type="number" min="1" max="100" value="10" required></div><div class="field"><label>Who is the shoot for?</label><select id="subject"><option value="woman">A woman</option><option value="man">A man</option><option value="non-binary person">A non-binary person</option><option value="group">A group</option><option value="no person / product or location">No person</option></select></div><div class="field full"><label>Style and creative direction</label><input id="style" required placeholder="e.g. cinematic editorial, relaxed street portrait, clean studio beauty"></div><div class="field full"><label>Preferred time</label><div class="form-grid"><div class="field"><label>From</label><input id="availabilityStart" type="time" required></div><div class="field"><label>Until</label><input id="availabilityEnd" type="time" required></div></div><small class="muted">On your preferred shoot date. Your photographer will use this window when proposing the final booking time.</small></div><div class="field"><label for="photographer">Choose a photographer</label><select id="photographer" required disabled><option value="">Loading available photographers…</option></select><small class="muted" id="photographerHelp">Choose who should receive this inquiry.</small></div><div class="field full"><label>What are you picturing?</label><textarea id="message" required placeholder="Share the purpose, mood, wardrobe, and anything that matters…">${esc(selectedShootIdea||'')}</textarea></div></div><div class="actions"><button class="primary" id="sendInquiry">Create my shoot brief →</button><span id="formStatus" class="muted"></span></div></form></section>`;bind();document.getElementById('inquiryForm').onsubmit=submitInquiry;populatePhotographers()};
submitInquiry=async event=>{event.preventDefault();const button=document.getElementById('sendInquiry'),status=document.getElementById('formStatus'),start=document.getElementById('availabilityStart').value,end=document.getElementById('availabilityEnd').value;if(!start||!end){status.textContent='Please provide a preferred start and end time.';return}if(end<=start){status.textContent='Your preferred end time must be after the start time.';return}const availability=[`${start}–${end}`];button.disabled=true;status.textContent='Creating your draft shoot plan…';try{const body={client_name:clientUser.name,client_email:clientUser.email,contact_email:clientUser.email,message:document.getElementById('message').value,budget:Number(document.getElementById('budget').value),shoot_date:document.getElementById('date').value,duration_minutes:Number(document.getElementById('duration').value),location:document.getElementById('location').value,style_direction:document.getElementById('style').value,availability_windows:availability,deliverable_count:Number(document.getElementById('deliverableCount').value),reference_images:[],photographer_email:document.getElementById('photographer').value,subject_presentation:document.getElementById('subject').value,subject_count:1};const response=await fetch('/api/inquiries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),created=await response.json();if(!response.ok)throw Error(created.detail||'Could not create the inquiry.');current={view:'details',id:Number(created.id)};history.pushState(current,'',`/client?view=details&id=${created.id}`);app.innerHTML='<div class="loading">ShotCraft is preparing your photographer’s review draft…</div>';for(let attempt=0;attempt<30;attempt++){await new Promise(resolve=>setTimeout(resolve,1500));const record=await getRecord(created.id);if(record.status!=='NEW'){await refresh();galleryDetail(created.id);return}}await refresh();galleryDetail(created.id)}catch(error){status.textContent=error.message||'We couldn’t create that just yet. Please try again.';button.disabled=false}};

/* Profile-backed photographer finder: city and specialties are saved at signup. */
populatePhotographers=async()=>{const select=document.getElementById('photographer'),help=document.getElementById('photographerHelp'),submit=document.getElementById('sendInquiry'),search=document.getElementById('photographerSearch'),city=document.getElementById('photographerCity');if(!select)return;try{const params=new URLSearchParams();if(search?.value.trim())params.set('search',search.value.trim());if(city?.value.trim())params.set('city',city.value.trim());const response=await fetch('/api/photographers?'+params,{cache:'no-store'});if(!response.ok)throw Error();const photographers=await response.json();if(!photographers.length){select.innerHTML='<option value="">No matching photographers yet</option>';help.textContent='Try a different city or search term.';if(submit)submit.disabled=true;return}select.innerHTML=`<option value="" selected disabled>Select a photographer…</option>${photographers.map(person=>`<option value="${esc(person.email)}">${esc(person.name)}${person.city?` · ${esc(person.city)}`:''}${person.specialties?` — ${esc(person.specialties)}`:''}</option>`).join('')}`;select.disabled=false;if(submit)submit.disabled=false;help.textContent=`${photographers.length} photographer${photographers.length===1?'':'s'} found. Search by name, city, or specialty.`}catch{select.innerHTML='<option value="">Could not load photographers</option>';help.textContent='Refresh the page and try again.';if(submit)submit.disabled=true}};
const createWithPhotographerFinder=create;
create=()=>{createWithPhotographerFinder();const chooser=document.getElementById('photographer');if(!chooser)return;const field=chooser.closest('.field');field.querySelector('label').textContent='Select a photographer';const budget=document.getElementById('budget');if(budget&&!budget.parentElement.classList.contains('currency-input')){budget.outerHTML=`<div class="currency-input"><span>$</span>${budget.outerHTML}`};field.insertAdjacentHTML('beforebegin',`<div class="field full photographer-finder"><label>Choose your photographer</label><div class="field"><label for="photographerCity">Photographer’s city <span>optional</span></label><input id="photographerCity" placeholder="e.g. Seattle"></div><small class="muted">Browse every photographer, or filter by city if you already know where you want to shoot.</small></div>`);const refreshDirectory=()=>populatePhotographers();document.getElementById('photographerCity').addEventListener('input',refreshDirectory);populatePhotographers()};

/* Match the studio calendar: a navigable month view preserves both history and
   future planning, rather than hiding the client's schedule in a two-week strip. */
const clientCalendarToday=new Date();
let clientCalendarMonthCursor=new Date(clientCalendarToday.getFullYear(),clientCalendarToday.getMonth(),1);
const clientCalendarDayKey=day=>`${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,'0')}-${String(day.getDate()).padStart(2,'0')}`;
const clientSameCalendarDay=(left,right)=>clientCalendarDayKey(left)===clientCalendarDayKey(right);
const compareClientCalendarEntries=(left,right)=>{
  const leftTime=wallClockDate(left.starts_at).valueOf(),rightTime=wallClockDate(right.starts_at).valueOf();
  if(Number.isNaN(leftTime))return Number.isNaN(rightTime)?0:1;
  if(Number.isNaN(rightTime))return-1;
  return leftTime-rightTime;
};
async function clientMonthlyCalendar(){
  setNav('calendar');
  const response=await fetch('/api/calendar?client_email='+encodeURIComponent(clientUser.email||''),{cache:'no-store'}),data=response.ok?await response.json():{entries:[]},entries=data.entries||[],records=Object.fromEntries(shoots.map(item=>[item.id,item]));
  const gridStart=new Date(clientCalendarMonthCursor);gridStart.setDate(1-gridStart.getDay());
  const days=Array.from({length:42},(_,index)=>{const day=new Date(gridStart);day.setDate(gridStart.getDate()+index);return day});
  const inMonth=item=>{const date=wallClockDate(item.starts_at);return !Number.isNaN(date.valueOf())&&date.getFullYear()===clientCalendarMonthCursor.getFullYear()&&date.getMonth()===clientCalendarMonthCursor.getMonth()};
  const monthEvents=entries.filter(inMonth);
  app.innerHTML=`<div class="head"><div><div class="eyebrow">Your shoot calendar</div><h1>Your shoots, in rhythm.</h1></div></div><section class="calendar-board calendar-month"><div class="calendar-board-head"><div class="calendar-month-nav"><button class="secondary calendar-month-button" data-client-calendar-month="-1" aria-label="Previous month">←</button><div><b>${esc(clientCalendarMonthCursor.toLocaleDateString(undefined,{month:'long',year:'numeric'}))}</b><span>${monthEvents.filter(item=>item.kind==='scheduled').length} confirmed shoot${monthEvents.filter(item=>item.kind==='scheduled').length===1?'':'s'}</span></div><button class="secondary calendar-month-button" data-client-calendar-today>Today</button><button class="secondary calendar-month-button" data-client-calendar-month="1" aria-label="Next month">→</button></div></div><div class="calendar-weekdays">${['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(day=>`<span>${day}</span>`).join('')}</div><div class="calendar-month-grid">${days.map(day=>{const key=clientCalendarDayKey(day),events=entries.filter(item=>String(item.starts_at).slice(0,10)===key).sort(compareClientCalendarEntries),outside=day.getMonth()!==clientCalendarMonthCursor.getMonth();return`<article class="calendar-day ${events.length?'has-event':''} ${outside?'outside-month':''} ${clientSameCalendarDay(day,clientCalendarToday)?'today':''}"><div><b>${day.getDate()}</b></div>${events.map(item=>{const record=records[item.inquiry_id]||{};return`<button class="calendar-event ${item.kind}" data-calendar-inquiry="${item.inquiry_id}">${esc(calendarTime(item.starts_at))}<span>${esc(title(record))} · ${esc(item.kind==='scheduled'?'Confirmed':'Pending')}</span></button>`}).join('')}</article>`}).join('')}</div></section>`;
  bind();
  document.querySelectorAll('[data-client-calendar-month]').forEach(button=>button.onclick=()=>{clientCalendarMonthCursor.setMonth(clientCalendarMonthCursor.getMonth()+Number(button.dataset.clientCalendarMonth));clientMonthlyCalendar()});
  document.querySelector('[data-client-calendar-today]')?.addEventListener('click',()=>{clientCalendarMonthCursor=new Date(clientCalendarToday.getFullYear(),clientCalendarToday.getMonth(),1);clientMonthlyCalendar()});
}
clientCalendar=clientMonthlyCalendar;
const clientMonthlyCalendarStyles=document.createElement('style');
clientMonthlyCalendarStyles.textContent='.calendar-month-nav{display:flex;align-items:center;gap:9px}.calendar-month-nav>div{display:grid;gap:2px;margin-right:4px}.calendar-month-nav b{font:inherit;font-weight:800}.calendar-month-nav span{color:#746f7a;font-size:12px}.calendar-month-button{min-width:36px;padding:7px 10px;font-size:12px}.calendar-weekdays,.calendar-month-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr))}.calendar-weekdays{border-bottom:1px solid #ded9e4;background:#faf8fd}.calendar-weekdays span{padding:10px 13px;color:#746f7a;font-size:11px;font-weight:800}.calendar-month-grid .calendar-day{min-height:126px}.calendar-month-grid .calendar-day:nth-child(7n){border-right:0}.calendar-day.outside-month{background:#fbfafc}.calendar-day.outside-month>div b{color:#aaa3af}.calendar-day.today>div b{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#7057c7;color:#fff;font-size:15px}.calendar-month .calendar-event{margin-top:7px;padding:6px 7px;font-size:10px}@media(max-width:760px){.calendar-month-nav{flex-wrap:wrap}.calendar-weekdays span{padding:8px 5px;text-align:center}.calendar-month-grid{grid-template-columns:repeat(7,minmax(104px,1fr));overflow:auto}.calendar-month{overflow-x:auto}.calendar-month-grid .calendar-day{min-height:105px;padding:8px}}';
document.head.appendChild(clientMonthlyCalendarStyles);
if(current.view==='calendar')clientMonthlyCalendar();
const clientCreateWithCurrencyPlaceholder=create;
create=()=>{clientCreateWithCurrencyPlaceholder();document.getElementById('budget')?.setAttribute('placeholder','500')};
const populatePhotographersWithProfiles=populatePhotographers;
populatePhotographers=async()=>{await populatePhotographersWithProfiles();const select=document.getElementById('photographer');if(!select)return;let preview=document.getElementById('photographerProfilePreview');if(!preview){preview=document.createElement('div');preview.id='photographerProfilePreview';preview.className='photographer-profile-preview';select.closest('.field')?.appendChild(preview)}const search=document.getElementById('photographerSearch'),city=document.getElementById('photographerCity'),params=new URLSearchParams();if(search?.value.trim())params.set('search',search.value.trim());if(city?.value.trim())params.set('city',city.value.trim());try{const response=await fetch('/api/photographers?'+params,{cache:'no-store'}),directory=response.ok?await response.json():[];const show=()=>{const person=directory.find(item=>item.email===select.value);preview.innerHTML=person?`<div class="eyebrow">Photographer profile</div><b>${esc(person.name)}</b>${person.city?`<span>${esc(person.city)}</span>`:''}${person.specialties?`<span>${esc(person.specialties)}</span>`:''}${person.bio?`<p>${esc(person.bio)}</p>`:''}`:''};select.onchange=show;show()}catch{preview.innerHTML=''}};
const populateWithoutDirectoryHelper=populatePhotographers;
populatePhotographers=async()=>{await populateWithoutDirectoryHelper();document.getElementById('photographerHelp')?.remove()};
document.addEventListener('change',event=>{if(event.target?.id!=='photographer'||!event.target.value)return;setTimeout(()=>{const preview=document.getElementById('photographerProfilePreview');if(preview&&!preview.querySelector('b+span'))preview.insertAdjacentHTML('beforeend','<span>City not added to profile</span>')},0)});
function clientProfile(){setNav('profile');app.innerHTML=`<div class="head"><div><div class="eyebrow">Your profile</div><h1>Keep your details current.</h1><p class="lede">Photographers use this information to understand who they’re planning with.</p></div></div><form class="card profile-form" id="clientProfileForm"><div class="field"><label for="profileName">Name</label><input id="profileName" value="${esc(clientUser.name||'')}" required maxlength="120"></div><div class="field"><label for="profileEmail">Email address</label><input id="profileEmail" value="${esc(clientUser.email||'')}" disabled></div><div class="field"><label for="profileCity">City</label><input id="profileCity" value="${esc(clientUser.city||'')}" placeholder="e.g. Seattle, WA" maxlength="120"></div><div class="field"><label for="profileBio">About you <span>optional</span></label><textarea id="profileBio" maxlength="500" placeholder="A little context about you or the kind of work you do.">${esc(clientUser.bio||'')}</textarea></div><div class="actions"><button class="primary">Save profile →</button><span class="muted" id="profileStatus"></span></div></form>`;document.getElementById('clientProfileForm').onsubmit=saveClientProfile}
async function saveClientProfile(event){event.preventDefault();const button=event.currentTarget.querySelector('button'),status=document.getElementById('profileStatus');button.disabled=true;status.textContent='Saving…';try{const response=await fetch('/api/auth/profile',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:document.getElementById('profileName').value,city:document.getElementById('profileCity').value,bio:document.getElementById('profileBio').value})}),data=await response.json();if(!response.ok)throw Error(data.detail||'Could not save your profile.');Object.assign(clientUser,data);sessionStorage.setItem('shotcraftUser',JSON.stringify(clientUser));document.getElementById('clientName').textContent=clientUser.name;updateClientSidebarAvatar(data.profile_image);showProfileSavedToast(()=>go('overview'))}catch(error){status.textContent=error.message;button.disabled=false}}
document.addEventListener('click',event=>{const button=event.target.closest('.nav button');if(button&&button.textContent.trim()==='Profile'){event.preventDefault();go('profile')}});
const renderClientWithProfile=render;render=()=>{if(current.view==='profile')return clientProfile();return renderClientWithProfile()};
const readProfileImage=file=>new Promise((resolve,reject)=>{if(!file)return resolve(null);if(!file.type.startsWith('image/'))return reject(Error('Choose an image file.'));if(file.size>2*1024*1024)return reject(Error('Profile pictures must be 2 MB or smaller.'));const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('Could not read that image.'));reader.readAsDataURL(file)});
clientProfile=()=>{setNav('profile');app.innerHTML=`<section class="profile-page client-profile-page"><header class="profile-page-head"><div><div class="eyebrow">Your profile</div><h1>Keep your profile current.</h1><p>Manage the details connected to your ShotCraft account.</p></div><span class="profile-state"><i>✓</i> Private to your workspace</span></header><form class="profile-layout" id="clientProfileForm"><aside class="profile-identity-card client-profile-card"><div class="profile-picture-field"><div class="profile-picture-preview">${clientUser.profile_image?`<img src="${esc(clientUser.profile_image)}" alt="Profile picture">`:'<span>◎</span>'}</div><div><span class="profile-card-kicker">Profile photo</span><h2>${esc(clientUser.name||'Your profile')}</h2><p>${esc(clientUser.city||'Add your city')}</p><input id="profileImage" type="file" accept="image/png,image/jpeg,image/webp"><small class="muted">PNG, JPEG, or WebP · 2 MB maximum</small></div></div></aside><div class="profile-details-card"><div class="profile-section-head"><div><span class="profile-card-kicker">Account details</span><h2>Personal information</h2></div><p>Name and email are managed by your account.</p></div><div class="profile-fields-grid"><div class="field"><label for="profileName">Name</label><input id="profileName" value="${esc(clientUser.name||'')}" readonly></div><div class="field"><label for="profileEmail">Email address</label><input id="profileEmail" value="${esc(clientUser.email||'')}" disabled></div><div class="field profile-field-wide"><label for="profileCity">Home city</label><input id="profileCity" value="${esc(clientUser.city||'')}" placeholder="e.g. Seattle, WA" maxlength="120"></div><div class="field profile-field-wide"><label for="profileBio">About you <span>optional</span></label><textarea id="profileBio" maxlength="500" placeholder="A little context about you or the kind of work you do.">${esc(clientUser.bio||'')}</textarea></div></div><footer class="profile-actions"><div><b>Ready to update?</b><span>Your changes will be used for future shoot planning.</span></div><span class="muted" id="profileStatus"></span><button class="primary">Save changes <span>→</span></button></footer></div></form></section>`;document.getElementById('clientProfileForm').onsubmit=saveClientProfile};
saveClientProfile=async event=>{event.preventDefault();const button=event.currentTarget.querySelector('button'),status=document.getElementById('profileStatus');button.disabled=true;status.textContent='Saving…';try{const image=await readProfileImage(document.getElementById('profileImage').files[0]);const response=await fetch('/api/auth/profile',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({city:document.getElementById('profileCity').value,bio:document.getElementById('profileBio').value,profile_image:image||clientUser.profile_image||null})}),data=await response.json();if(!response.ok)throw Error(data.detail||'Could not save your profile.');Object.assign(clientUser,data);sessionStorage.setItem('shotcraftUser',JSON.stringify(clientUser));updateClientSidebarAvatar(data.profile_image);showProfileSavedToast(()=>go('overview'))}catch(error){status.textContent=error.message;button.disabled=false}};
document.addEventListener('change',event=>{if(event.target?.id!=='profileImage')return;const file=event.target.files?.[0];if(!file)return;const reader=new FileReader();reader.onload=()=>{const preview=document.querySelector('.profile-picture-preview');if(preview)preview.innerHTML=`<img src="${esc(reader.result)}" alt="Profile picture preview">`};reader.readAsDataURL(file)});

// Profile is a full workspace view too: rebind the persistent sidebar after it renders.
const renderClientProfileWithNavigation=clientProfile;
clientProfile=()=>{renderClientProfileWithNavigation();bind()};

// The photographer chooser is intentionally self-contained: the helper copy was
// removed from the UI, so filtering must not rely on a missing helper element.
populatePhotographers=async()=>{
  const select=document.getElementById('photographer'),submit=document.getElementById('sendInquiry'),city=document.getElementById('photographerCity');
  if(!select)return;
  try{
    const params=new URLSearchParams();
    if(city?.value.trim())params.set('city',city.value.trim());
    const response=await fetch('/api/photographers?'+params,{cache:'no-store'});
    const photographers=await response.json();
    if(!response.ok||!Array.isArray(photographers))throw Error('Could not load photographers.');
    if(!photographers.length){select.innerHTML='<option value="">No matching photographers yet</option>';select.disabled=true;if(submit)submit.disabled=true;document.getElementById('photographerProfilePreview')?.replaceChildren();return}
    select.innerHTML=`<option value="" selected disabled>Select a photographer…</option>${photographers.map(person=>`<option value="${esc(person.email)}">${esc(person.name)}${person.city?` · ${esc(person.city)}`:''}${person.specialties?` — ${esc(person.specialties)}`:''}</option>`).join('')}`;
    select.disabled=false;if(submit)submit.disabled=false;
    const preview=document.getElementById('photographerProfilePreview');
    select.onchange=()=>{const person=photographers.find(item=>item.email===select.value);if(preview)preview.innerHTML=person?`<div class="eyebrow">Photographer profile</div><b>${esc(person.name)}</b>${person.city?`<span>${esc(person.city)}</span>`:''}${person.specialties?`<span>${esc(person.specialties)}</span>`:''}${person.bio?`<p>${esc(person.bio)}</p>`:''}`:''};
  }catch(error){select.innerHTML='<option value="">Could not load photographers</option>';select.disabled=true;if(submit)submit.disabled=true;document.getElementById('photographerProfilePreview')?.replaceChildren()}
};

/* Time options arrive with the shared shoot plan, then the client approves
   the plan and selects one exact option in the same decision flow. */
const bookingPolicySummary='Cancel 48+ hours before the shoot for no fee. Cancellations 24–48 hours before may incur a 25% fee; cancellations under 24 hours may incur a 50% fee.';
const bookingPolicyStyle=document.createElement('style');bookingPolicyStyle.textContent='.booking-policy{margin:14px 0;padding:15px 16px;border:1px solid #ded6eb;border-radius:13px;background:#f8f5fc}.booking-policy b,.booking-policy span{display:block}.booking-policy span{margin:5px 0 12px;color:#6f6875;font-size:12px;line-height:1.45}.booking-policy label{display:flex;align-items:flex-start;gap:9px;font-size:12px;font-weight:750;cursor:pointer}.booking-policy input{margin-top:3px;accent-color:#7057c7}';document.head.appendChild(bookingPolicyStyle);
const clientPlanWithSharedTimeOptions=cinematicPlan;
cinematicPlan=async id=>{
  await clientPlanWithSharedTimeOptions(id);
  const record=await getRecord(id),decision=app.querySelector('.plan-decision');
  if(!decision||!record.production_approved||['CLIENT_CONFIRMED','SCHEDULED','CANCELLED'].includes(record.status))return;
  const response=await fetch(`/api/inquiries/${id}/schedule-recommendations`,{cache:'no-store'}),request=response.ok?await response.json():null;
  if(!request?.suggestions?.length)return;
  const confirm=decision.querySelector('[data-confirm]');
  if(confirm){confirm.textContent='Approve plan & choose a time →';confirm.dataset.confirmAndChoose=id;confirm.removeAttribute('data-confirm')}
  decision.querySelector('.shared-time-summary')?.remove();
  if(!decision.querySelector('.booking-policy'))decision.insertAdjacentHTML('afterbegin',`<section class="booking-policy"><b>Cancellation policy</b><span>${esc(bookingPolicySummary)}</span><label><input type="checkbox" data-policy-accept="${id}"> I understand and accept the cancellation policy.</label></section>`);
};
document.addEventListener('click',async event=>{const button=event.target.closest('[data-confirm-and-choose]');if(!button)return;event.preventDefault();const accepted=app.querySelector(`[data-policy-accept="${button.dataset.confirmAndChoose}"]`);if(!accepted?.checked){button.textContent='Accept the cancellation policy first';return}button.disabled=true;try{const response=await fetch(`/api/inquiries/${button.dataset.confirmAndChoose}/client-confirm`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cancellation_policy_accepted:true})}),data=await response.json();if(!response.ok||data.error)throw Error(data.detail||data.error||'Could not approve this plan.');await refresh();go('schedule-options',button.dataset.confirmAndChoose)}catch(error){button.disabled=false;button.textContent=error.message}});
// The older calendar renderer is not present in every workspace build. Keep
// this cosmetic enhancement optional so it cannot prevent later view code from
// loading (including the Create Inquiry view).
if(typeof calendar==='function'){
  const renderClientCalendarWithoutSubtitle=calendar;
  calendar=async()=>{await renderClientCalendarWithoutSubtitle();app.querySelector('.head .lede')?.remove()};
}
function enhanceClientProfileForm(){const form=document.getElementById('clientProfileForm'),input=document.getElementById('profileImage'),bio=document.getElementById('profileBio');if(!form||!input||input.dataset.enhanced)return;input.dataset.enhanced='true';input.classList.add('profile-file-input');const upload=document.createElement('div');upload.className='profile-upload-row';upload.innerHTML=`<label class="profile-upload-button" for="profileImage">Change photo</label><span class="profile-upload-name">No file selected</span>`;input.after(upload);const name=upload.querySelector('.profile-upload-name');input.addEventListener('change',()=>{const file=input.files?.[0];name.textContent=file?file.name:'No file selected';name.classList.toggle('selected',Boolean(file))});if(bio){const field=bio.closest('.field');field?.classList.add('bio-field');const meta=document.createElement('div');meta.className='bio-meta';meta.innerHTML='<span>A short introduction helps people know what to expect.</span><span class="bio-count"></span>';bio.after(meta);const count=meta.querySelector('.bio-count'),update=()=>count.textContent=`${bio.value.length} / ${bio.maxLength}`;bio.addEventListener('input',update);update()}}
const renderClientProfileWithModernControls=clientProfile;
clientProfile=()=>{renderClientProfileWithModernControls();enhanceClientProfileForm()};
if(current.view==='profile')clientProfile();
function showProfileSavedToast(done){document.querySelector('.profile-save-toast')?.remove();const toast=document.createElement('div'),message=document.createElement('span');toast.className='profile-save-toast';toast.setAttribute('role','status');toast.innerHTML='<i>✓</i>';toast.appendChild(message);document.body.appendChild(toast);let remaining=3;const update=()=>message.textContent=`Profile saved successfully. Taking you to Overview in ${remaining}…`;update();const countdown=setInterval(()=>{remaining-=1;if(remaining>0)update()},1000);setTimeout(()=>{clearInterval(countdown);toast.remove();done()},3000)}
function updateClientSidebarAvatar(image){if(!image)return;const avatar=document.querySelector('.identity .profile-orb');if(avatar)avatar.outerHTML=`<span class="profile-orb profile-orb-image"><img src="${esc(image)}" alt=""></span>`}
saveClientProfile=async event=>{event.preventDefault();const button=event.currentTarget.querySelector('button'),status=document.getElementById('profileStatus');button.disabled=true;status.textContent='Saving…';try{const image=await readProfileImage(document.getElementById('profileImage').files[0]);const response=await fetch('/api/auth/profile',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({city:document.getElementById('profileCity').value,bio:document.getElementById('profileBio').value,profile_image:image||clientUser.profile_image||null})}),data=await response.json();if(!response.ok)throw Error(data.detail||'Could not save your profile.');Object.assign(clientUser,data);sessionStorage.setItem('shotcraftUser',JSON.stringify(clientUser));updateClientSidebarAvatar(data.profile_image);showProfileSavedToast(()=>go('overview'))}catch(error){status.textContent=error.message;button.disabled=false}}
const saveClientProfileWithSuccess=saveClientProfile;
{const form=document.getElementById('clientProfileForm');if(form)form.onsubmit=saveClientProfileWithSuccess}
const shootCities=['Seattle','Chicago','New York','Los Angeles','Austin'];
const clientCreateStyle=document.createElement('style');clientCreateStyle.textContent='.city-picker{position:relative}.city-picker input{padding-right:40px}.city-picker:after{content:"⌄";position:absolute;right:15px;bottom:43px;color:var(--muted);pointer-events:none}.city-suggestions{position:absolute;z-index:5;top:71px;left:0;right:0;margin:0;padding:6px;background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:0 14px 30px #211e2122;list-style:none}.city-suggestion{display:flex;width:100%;padding:10px 12px;border:0;border-radius:8px;background:transparent;color:var(--ink);font:inherit;text-align:left;cursor:pointer}.city-suggestion:hover,.city-suggestion:focus{background:#eeeaf9;color:#5b43b1;outline:0}.time-window-picker{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-top:3px}.time-window{min-height:74px;padding:11px 12px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--ink);text-align:left;font:inherit;cursor:pointer;transition:.16s}.time-window:hover{border-color:#7057c7}.time-window b,.time-window span{display:block}.time-window b{font-size:12px}.time-window span{margin-top:3px;color:var(--muted);font-size:11px}.time-window.active{border-color:#7057c7;background:#eeeaf9;box-shadow:0 0 0 1px #7057c7}.time-window.active b{color:#5b43b1}.budget-input{position:relative}.budget-input span{position:absolute;z-index:1;left:15px;top:12px;color:var(--muted);font-weight:700}.budget-input input{padding-left:30px}@media(max-width:700px){.time-window-picker{grid-template-columns:1fr 1fr}}';document.head.appendChild(clientCreateStyle);
create=()=>{setNav('create');app.innerHTML=`<div class="head"><div><div class="eyebrow">New inquiry</div><h1>Plan your shoot in one go.</h1><p class="lede">Share the creative essentials and your availability. Your photographer will receive one complete draft to review.</p></div></div><section class="card"><form id="inquiryForm"><div class="form-grid"><div class="field"><label>Your name</label><input value="${esc(clientUser.name)}" readonly></div><div class="field"><label>Email address</label><input value="${esc(clientUser.email)}" readonly></div><div class="field"><label>Preferred shoot date</label><input id="date" type="date" required></div><div class="field"><label>Duration</label><select id="duration"><option value="30">30 minutes</option><option value="60">1 hour</option><option value="120" selected>2 hours</option><option value="240">Half day (4 hours)</option><option value="480">Full day (8 hours)</option></select></div><div class="field"><label>Estimated budget</label><div class="budget-input"><span>$</span><input id="budget" type="text" inputmode="decimal" autocomplete="off" placeholder="500" required></div></div><div class="field"><label>Final edited photos</label><input id="deliverableCount" type="number" min="1" max="100" value="10" required></div><div class="field"><label>Who is the shoot for?</label><select id="subject"><option value="woman">A woman</option><option value="man">A man</option><option value="non-binary person">A non-binary person</option><option value="group">A group</option><option value="no person / product or location">No person</option></select></div><div class="field full"><label>Style and creative direction</label><input id="style" required placeholder="e.g. cinematic editorial, relaxed street portrait, clean studio beauty"></div><div class="field full"><label>Preferred time window</label><div class="time-window-picker" role="radiogroup" aria-label="Preferred time window">${[['Morning','08:00','11:00'],['Midday','11:00','14:00'],['Afternoon','14:00','17:00'],['Golden hour','17:00','20:00']].map(([label,start,end])=>`<button type="button" class="time-window" data-time-window data-start="${start}" data-end="${end}"><b>${label}</b><span>${start}–${end}</span></button>`).join('')}</div><input id="availabilityStart" type="hidden" required><input id="availabilityEnd" type="hidden" required><small class="muted">Choose the window that best suits you. Your photographer will confirm the final time.</small></div><div class="field full city-picker"><label for="shootCity">Shoot city</label><input id="shootCity" required autocomplete="off" aria-autocomplete="list" aria-expanded="false" placeholder="Start typing a city"><ul id="shootCitySuggestions" class="city-suggestions" role="listbox" hidden></ul><small class="muted">Recommended cities: Seattle, Chicago, New York, Los Angeles, and Austin.</small></div><div class="field"><label for="photographer">Select a photographer</label><select id="photographer" required disabled><option value="">Choose a shoot city first…</option></select><small class="muted" id="photographerHelp">Choose one of the recommended cities to see available photographers.</small></div><div class="field full"><label>What are you picturing?</label><textarea id="message" required placeholder="Share the purpose, mood, wardrobe, and anything that matters…">${esc(selectedShootIdea||'')}</textarea></div></div><div class="actions"><button class="primary" id="sendInquiry">Create my shoot brief →</button><span id="formStatus" class="muted"></span></div></form></section>`;bind();document.getElementById('inquiryForm').onsubmit=submitInquiry;document.querySelectorAll('[data-time-window]').forEach(button=>button.onclick=()=>{document.querySelectorAll('[data-time-window]').forEach(item=>item.classList.toggle('active',item===button));document.getElementById('availabilityStart').value=button.dataset.start;document.getElementById('availabilityEnd').value=button.dataset.end});const cityInput=document.getElementById('shootCity'),suggestions=document.getElementById('shootCitySuggestions'),chooseCity=city=>{cityInput.value=city;suggestions.hidden=true;cityInput.setAttribute('aria-expanded','false');populatePhotographers()};const showSuggestions=()=>{const query=cityInput.value.trim().toLowerCase(),matches=shootCities.filter(city=>city.toLowerCase().includes(query));suggestions.innerHTML=matches.map(city=>`<li><button type="button" class="city-suggestion" role="option" data-city="${city}">${city}</button></li>`).join('');suggestions.hidden=!matches.length;cityInput.setAttribute('aria-expanded',String(Boolean(matches.length)));suggestions.querySelectorAll('[data-city]').forEach(button=>button.onclick=()=>chooseCity(button.dataset.city))};cityInput.addEventListener('input',()=>{showSuggestions();populatePhotographers()});cityInput.addEventListener('focus',showSuggestions);cityInput.addEventListener('blur',()=>setTimeout(()=>{suggestions.hidden=true;cityInput.setAttribute('aria-expanded','false')},150))};
populatePhotographers=async()=>{const select=document.getElementById('photographer'),help=document.getElementById('photographerHelp'),submit=document.getElementById('sendInquiry'),input=document.getElementById('shootCity')?.value.trim(),city=shootCities.find(item=>item.toLowerCase()===input?.toLowerCase());if(!select)return;if(!city){select.innerHTML='<option value="">Choose a recommended city first…</option>';select.disabled=true;if(help)help.textContent=input?'Select a city from the recommendations.':'Choose a recommended city to see available photographers.';return}try{const response=await fetch('/api/photographers?city='+encodeURIComponent(city),{cache:'no-store'}),photographers=await response.json();if(!response.ok||!photographers.length){select.innerHTML='<option value="">No photographers found for this city</option>';select.disabled=true;help.textContent='Try another recommended city.';return}select.innerHTML=`<option value="" selected disabled>Select a photographer…</option>${photographers.map(person=>`<option value="${esc(person.email)}">${esc(person.name)}${person.specialties?` — ${esc(person.specialties)}`:''}</option>`).join('')}`;select.disabled=false;if(submit)submit.disabled=false;help.textContent=`${photographers.length} photographer${photographers.length===1?'':'s'} available in ${city}.`}catch{select.innerHTML='<option value="">Could not load photographers</option>';select.disabled=true;help.textContent='Refresh and try again.'}};
submitInquiry=async event=>{event.preventDefault();const button=document.getElementById('sendInquiry'),status=document.getElementById('formStatus'),start=document.getElementById('availabilityStart').value,end=document.getElementById('availabilityEnd').value,budget=Number(String(document.getElementById('budget').value).replace(/[^0-9.]/g,''));if(!start||!end){status.textContent='Choose your preferred time window.';return}button.disabled=true;status.textContent='Creating your draft shoot plan…';try{const city=document.getElementById('shootCity').value,body={client_name:clientUser.name,client_email:clientUser.email,contact_email:clientUser.email,message:document.getElementById('message').value,budget:Number.isFinite(budget)?budget:null,shoot_date:document.getElementById('date').value,duration_minutes:Number(document.getElementById('duration').value),location:city,style_direction:document.getElementById('style').value,availability_windows:[`${start}–${end}`],deliverable_count:Number(document.getElementById('deliverableCount').value),reference_images:[],photographer_email:document.getElementById('photographer').value,subject_presentation:document.getElementById('subject').value,subject_count:1};const response=await fetch('/api/inquiries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),created=await response.json();if(!response.ok)throw Error(created.detail||'Could not create the inquiry.');current={view:'details',id:Number(created.id)};history.pushState(current,'',`/client?view=details&id=${created.id}`);app.innerHTML='<div class="loading">ShotCraft is preparing your photographer’s review draft…</div>';for(let attempt=0;attempt<30;attempt++){await new Promise(resolve=>setTimeout(resolve,1500));const record=await getRecord(created.id);if(record.status!=='NEW'){await refresh();galleryDetail(created.id);return}}await refresh();galleryDetail(created.id)}catch(error){status.textContent=error.message||'We couldn’t create that just yet. Please try again.';button.disabled=false}};
// This file has a few historical view wrappers. Ensure a direct visit to the
// Create route always uses the final form above, after every wrapper is loaded.
if(new URLSearchParams(location.search).get('view')==='create')create();

// The sidebar persists while the main content is replaced. Use one delegated
// handler so later render enhancements cannot override navigation buttons.
const bindClientNavWithoutDirectHandlers=bind;
bind=()=>{
  bindClientNavWithoutDirectHandlers();
  document.querySelectorAll('.nav button[data-view]').forEach(button=>{button.onclick=null});
};
document.querySelectorAll('.nav button[data-view]').forEach(button=>{button.onclick=null});
document.querySelector('.nav')?.addEventListener('click',event=>{
  const button=event.target.closest('button[data-view]');
  if(!button)return;
  event.preventDefault();
  go(button.dataset.view);
});

/* Needs you — a single source of truth for unresolved client decisions. */
const clientNeedsNav=document.createElement('button');
clientNeedsNav.type='button';clientNeedsNav.dataset.view='needs-you';clientNeedsNav.className='client-needs-nav';
clientNeedsNav.innerHTML='<span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M12 3a9 9 0 1 0 9 9M12 7v5l3 2"/></svg></span><span>Needs you</span><span class="nav-count client-needs-count"></span>';
document.querySelector('.gallery-nav,.notifications-nav')?.before(clientNeedsNav);
clientNeedsNav.insertAdjacentHTML('beforebegin','<div class="nav-label nav-decisions-label">Decisions</div>');
(()=>{const nav=document.querySelector('.nav'),communication=nav?.querySelector('.nav-communication-label'),messages=[...nav?.querySelectorAll('button')||[]].find(button=>button.textContent.includes('Messages')),notifications=nav?.querySelector('.notifications-nav');if(communication&&messages)communication.after(messages);if(messages&&notifications)messages.after(notifications)})();
(()=>{const nav=document.querySelector('.nav');if(!nav)return;const nodes=[nav.querySelector('.nav-label:not(.nav-communication-label):not(.nav-decisions-label):not(.nav-account-label):not(.nav-create-label)'),nav.querySelector('button[data-view="overview"]'),nav.querySelector('.gallery-nav'),nav.querySelector('button[data-view="calendar"]'),nav.querySelector('.nav-communication-label'),[...nav.querySelectorAll('button')].find(button=>button.textContent.includes('Messages')),nav.querySelector('.notifications-nav'),nav.querySelector('.nav-decisions-label'),clientNeedsNav,nav.querySelector('.nav-account-label'),[...nav.querySelectorAll('button')].find(button=>button.textContent.includes('Profile')),nav.querySelector('.nav-create-label'),nav.querySelector('button[data-view="create"]')].filter(Boolean);nav.append(...nodes)})();
function clientDecisionItems(){return shoots.map(record=>{const action=clientActionFor(record);return action?{record,action}:null}).filter(Boolean)}
function updateClientNeedsCount(){const badge=document.querySelector('.client-needs-count'),count=clientDecisionItems().length;if(badge){badge.textContent=count||'';badge.hidden=!count}}
function clientNeedsYouView(){
  document.querySelectorAll('.nav button').forEach(button=>button.classList.toggle('active',button.dataset.view==='needs-you'));
  const items=clientDecisionItems();
  app.innerHTML=`<section class="needs-page"><header class="needs-head"><div><div class="eyebrow">Human decisions</div><h1>Needs you</h1><p>Only the choices and details that ShotCraft cannot complete without you.</p></div><span class="needs-count">${items.length} ${items.length===1?'open item':'open items'}</span></header><div class="needs-list">${items.length?items.map(({record,action},index)=>`<article class="needs-card"><span class="needs-number">${String(index+1).padStart(2,'0')}</span><div><div class="eyebrow">${esc(title(record))}</div><h2>${esc(action.label)}</h2><p>${esc(action.description)}</p></div><button class="primary" data-client-action="${record.id}" data-action-view="${action.view}">${esc(action.label)} →</button></article>`).join(''):'<article class="needs-empty"><span>✓</span><div><h2>Nothing needs your decision.</h2><p>ShotCraft will keep working and bring you back only when your input is required.</p></div></article>'}</div></section>`;
  app.querySelectorAll('[data-client-action]').forEach(button=>button.onclick=()=>go(button.dataset.actionView,button.dataset.clientAction));
}
const refreshWithClientNeeds=refresh;refresh=async()=>{await refreshWithClientNeeds();updateClientNeedsCount()};
updateClientNeedsCount();

// Client notification center: durable read state comes from the API while this
// small cache keeps the bell and open page responsive between polls.
let clientNotifications=[];
let notificationFilter='unread';
let notificationsInitialized=false;
function updateNotificationBadge(){
  const unread=clientNotifications.filter(item=>!item.resolved_at&&!item.read_at).length;
  const badge=document.querySelector('.notification-badge');
  if(!badge)return;
  badge.textContent=unread>99?'99+':String(unread);
  badge.hidden=!unread;
  document.querySelector('.notifications-nav')?.classList.toggle('has-unread',Boolean(unread));
}
function notificationTime(value){
  const date=new Date(String(value||'').replace(' ','T')+'Z');
  if(Number.isNaN(date.valueOf()))return '';
  const seconds=Math.max(0,(Date.now()-date.valueOf())/1000);
  if(seconds<60)return 'Just now';
  if(seconds<3600)return `${Math.floor(seconds/60)}m ago`;
  if(seconds<86400)return `${Math.floor(seconds/3600)}h ago`;
  if(seconds<604800)return `${Math.floor(seconds/86400)}d ago`;
  return date.toLocaleDateString([],{month:'short',day:'numeric'});
}
function notificationIcon(type){return ({FOLLOWUP_REQUESTED:'?',FOLLOWUP_COMPLETE:'✓',PLAN_READY:'✦',SCHEDULE_OPTIONS:'◷',TIME_CHANGE_REQUESTED:'◷',SHOOT_CONFIRMED:'✓',SHOOT_CANCELLED:'×',CANCELLATION_DECLINED:'↩'})[type]||'•'}
function showClientNotificationToast(item){
  document.querySelector('.client-notification-toast')?.remove();
  const toast=document.createElement('button');
  toast.type='button';toast.className='client-notification-toast';
  toast.innerHTML=`<i>${notificationIcon(item.notification_type)}</i><span><small>New notification</small><strong>${esc(item.title)}</strong><em>${esc(item.body)}</em></span>`;
  toast.onclick=()=>openClientNotification(item.id);
  document.body.appendChild(toast);
  setTimeout(()=>toast.remove(),6500);
}
async function refreshClientNotifications(showToast=false){
  try{
    const oldUnread=new Set(clientNotifications.filter(item=>!item.resolved_at&&!item.read_at).map(item=>item.id));
    const response=await fetch('/api/notifications',{cache:'no-store'}),data=await response.json();
    if(!response.ok)return;
    clientNotifications=data.notifications||[];
    updateNotificationBadge();
    if(showToast&&notificationsInitialized){
      const newest=clientNotifications.find(item=>!item.resolved_at&&!item.read_at&&!oldUnread.has(item.id));
      if(newest)showClientNotificationToast(newest);
    }
    notificationsInitialized=true;
    if(current.view==='notifications')notificationsView();
  }catch(_){/* Notifications should never prevent the workspace from loading. */}
}
function notificationsView(){
  document.querySelectorAll('.nav button').forEach(button=>button.classList.remove('active'));
  document.querySelector('.notifications-nav')?.classList.add('active');
  const unread=clientNotifications.filter(item=>!item.resolved_at&&!item.read_at).length;
  const visible=notificationFilter==='unread'?clientNotifications.filter(item=>!item.resolved_at&&!item.read_at):clientNotifications;
  app.innerHTML=`<section class="notifications-page"><header class="notifications-head"><div><div class="eyebrow">Your updates</div><h1>Notifications</h1><p>Everything that needs your attention, in one place.</p></div>${unread?'<button class="secondary" id="markAllNotificationsRead">Mark all as read</button>':''}</header><div class="notification-tabs" role="tablist"><button class="${notificationFilter==='unread'?'active':''}" data-notification-filter="unread">Unread <span>${unread}</span></button><button class="${notificationFilter==='all'?'active':''}" data-notification-filter="all">All <span>${clientNotifications.length}</span></button></div><div class="notification-list">${visible.length?visible.map(item=>`<button class="notification-row ${item.read_at?'is-read':'is-unread'}" data-notification-id="${item.id}"><span class="notification-type-icon">${notificationIcon(item.notification_type)}</span><span class="notification-copy"><span class="notification-title-line"><strong>${esc(item.title)}</strong>${item.action_required&&!item.resolved_at?'<b>Needs action</b>':''}</span><span>${esc(item.body)}</span><small>${notificationTime(item.created_at)}</small></span><i aria-hidden="true">→</i></button>`).join(''):`<div class="notification-empty"><span>✓</span><h2>${notificationFilter==='unread'?'You’re all caught up.':'No notifications yet.'}</h2><p>${notificationFilter==='unread'?'New updates and requests will appear here.':'We’ll let you know when something changes with a shoot.'}</p></div>`}</div></section>`;
  document.querySelectorAll('[data-notification-filter]').forEach(button=>button.onclick=()=>{notificationFilter=button.dataset.notificationFilter;notificationsView()});
  document.querySelectorAll('[data-notification-id]').forEach(button=>button.onclick=()=>openClientNotification(Number(button.dataset.notificationId)));
  const markAll=document.getElementById('markAllNotificationsRead');if(markAll)markAll.onclick=markAllClientNotificationsRead;
}
async function openClientNotification(id){
  const item=clientNotifications.find(notification=>notification.id===Number(id));if(!item)return;
  if(!item.read_at){
    item.read_at=new Date().toISOString();updateNotificationBadge();
    await fetch(`/api/notifications/${item.id}/read`,{method:'POST'});
  }
  go(item.target_view,item.inquiry_id);
}
async function markAllClientNotificationsRead(){
  clientNotifications.forEach(item=>{if(!item.read_at)item.read_at=new Date().toISOString()});
  updateNotificationBadge();notificationsView();
  await fetch('/api/notifications/read-all',{method:'POST'});
}
const renderWithNotificationCenter=render;
render=()=>current.view==='notifications'?notificationsView():renderWithNotificationCenter();
refreshClientNotifications(false);
setInterval(()=>refreshClientNotifications(true),10000);

// Cancelled shoots are read-only: no date/time change action should be exposed.
const finalPlanWithCancellationGuard=cinematicPlan;
cinematicPlan=async id=>{await finalPlanWithCancellationGuard(id);const record=await getRecord(id);if(record.status!=='CANCELLED')return;app.querySelectorAll('[data-edit-shoot],[data-smart-schedule],[data-availability],[data-confirm-and-choose],[data-approve-plan-time]').forEach(button=>button.remove())};

async function submitCancellationRequest(event,id){event.preventDefault();const form=event.currentTarget,button=form.querySelector('.primary'),status=form.querySelector('.cancel-status');button.disabled=true;status.textContent='Sending request…';try{const response=await fetch(`/api/inquiries/${id}/cancellation-request`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason:form.elements.reason.value,note:form.elements.note.value})}),data=await response.json();if(!response.ok)throw Error(data.detail||'Could not send the cancellation request.');form.closest('.cancel-modal').remove();await refresh();cinematicPlan(id)}catch(error){status.textContent=error.message;button.disabled=false}}
function openCancellationModal(id){const record=shoots.find(item=>Number(item.id)===Number(id)),p=payload(record||{}),amount=Number(p.budget||0),hours=record?.call_time?(wallClockDate(record.call_time)-new Date())/36e5:null,percent=hours==null||hours>=48?0:hours>=24?25:50,fee=amount*percent/100,refund=Math.max(amount-fee,0),modal=document.createElement('div');modal.className='cancel-modal';modal.innerHTML=`<form class="cancel-dialog"><button type="button" class="cancel-close" aria-label="Close">×</button><div class="eyebrow">Cancellation request</div><h2>Request to cancel this shoot?</h2><p>Your booking stays active until your photographer reviews this request.</p><div class="cancel-policy-preview"><b>Policy estimate</b><span>${esc(bookingPolicySummary)}</span><strong>Suggested fee: $${fee.toFixed(2)} · Estimated refund: $${refund.toFixed(2)}</strong><small>No payment is processed through ShotCraft.</small></div><label>Reason<select name="reason" required><option value="">Choose a reason</option><option>Plans changed</option><option>Scheduling conflict</option><option>Budget changed</option><option>No longer need the shoot</option><option>Other</option></select></label><label>Optional note<textarea name="note" maxlength="1200" placeholder="Anything your photographer should know…"></textarea></label><div class="cancel-actions"><button type="button" class="secondary cancel-back">Keep my booking</button><button class="primary">Send cancellation request →</button></div><span class="muted cancel-status"></span></form>`;const close=()=>modal.remove();modal.onclick=event=>{if(event.target===modal||event.target.closest('.cancel-close,.cancel-back'))close()};modal.querySelector('form').onsubmit=event=>submitCancellationRequest(event,id);document.body.append(modal);modal.querySelector('select').focus()}
document.addEventListener('click',event=>{const button=event.target.closest('[data-cancel-shoot]');if(button){event.preventDefault();openCancellationModal(button.dataset.cancelShoot)}});
const openCancellationModalWithTransparentFee=openCancellationModal;
openCancellationModal=id=>{
  openCancellationModalWithTransparentFee(id);
  const record=shoots.find(item=>Number(item.id)===Number(id)),p=payload(record||{}),amount=Number(p.budget||0),hours=record?.call_time?(wallClockDate(record.call_time)-new Date())/36e5:null,percent=hours==null||hours>=48?0:hours>=24?25:50,fee=amount*percent/100,refund=Math.max(amount-fee,0),tier=hours==null?'No confirmed shoot time is available, so no fee is suggested.':hours>=48?'The request is at least 48 hours before the shoot, so the no-fee tier applies.':hours>=24?'The request is 24–48 hours before the shoot, so the 25% tier applies.':'The request is less than 24 hours before the shoot, so the 50% tier applies.',notice=hours==null?'Notice unavailable':`${Math.max(hours,0).toFixed(hours<10?1:0)} hours before the shoot`,preview=document.querySelector('.cancel-modal .cancel-policy-preview');
  if(!preview)return;
  preview.innerHTML=`<b>Cancellation fee: ${percent}%</b><span><strong>Booking amount:</strong> $${amount.toFixed(2)}</span><span><strong>Why:</strong> ${esc(tier)} (${esc(notice)})</span><span><strong>Calculation:</strong> $${amount.toFixed(2)} × ${percent}% = $${fee.toFixed(2)}</span><strong>Estimated refund: $${refund.toFixed(2)}</strong><small>Your photographer will review the request and can apply the policy fee, waive it, or choose a custom fee.</small>`;
};
const clientPlanWithCancellation=cinematicPlan;
cinematicPlan=async id=>{await clientPlanWithCancellation(id);const record=await getRecord(id),decision=app.querySelector('.plan-decision');if(!decision)return;if(record.status==='CANCELLED'){decision.querySelectorAll('button,.confirmed-banner').forEach(item=>item.remove());decision.querySelector('p').textContent='This shoot has been cancelled. The conversation remains available for any follow-up.';decision.insertAdjacentHTML('beforeend','<div class="cancel-pending">Shoot cancelled</div>');return}if(!['CLIENT_CONFIRMED','SCHEDULED'].includes(record.status))return;if(record.cancellation_status==='PENDING'){decision.insertAdjacentHTML('beforeend','<div class="cancel-pending">Cancellation requested · Your booking remains active while the photographer reviews it.</div>')}else if(!record.cancellation_status||record.cancellation_status==='DECLINED'){decision.insertAdjacentHTML('beforeend',`<button class="cancel-request-button" data-cancel-shoot="${id}">Request cancellation</button>`)}};

// Legacy render enhancers can append schedule controls after the plan renders.
// Keep cancelled plans read-only regardless of which renderer runs last.
async function enforceCancelledPlanReadOnly(){
  const params=new URLSearchParams(location.search);
  if(params.get('view')!=='plan')return;
  const id=params.get('id');
  const record=shoots.find(item=>item.id==id)||await getRecord(id);
  if(record?.status!=='CANCELLED')return;
  app.querySelectorAll('button,[data-edit-shoot]').forEach(button=>{
    if(button.dataset.editShoot||/edit shoot date or time/i.test(button.textContent))button.remove();
  });
}
new MutationObserver(()=>enforceCancelledPlanReadOnly()).observe(app,{childList:true,subtree:true});
setTimeout(enforceCancelledPlanReadOnly,0);

// Native datetime controls retain their browser editing format; every rendered
// client-facing schedule label uses a clear 12-hour clock.
const galleryDetailWithAmPmClock=galleryDetail;
galleryDetail=async id=>{
  await galleryDetailWithAmPmClock(id);
  const record=await getRecord(id);
  if(!record.call_time)return;
  const time=[...app.querySelectorAll('.detail-facts>div')].find(item=>item.querySelector('span')?.textContent.includes('Time'))?.querySelector('b');
  if(time)time.textContent=wallClockDate(record.call_time).toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit',hour12:true});
};
const cinematicPlanWithAmPmClock=cinematicPlan;
cinematicPlan=async id=>{
  await cinematicPlanWithAmPmClock(id);
  const record=await getRecord(id);
  if(!record.call_time)return;
  const field=[...app.querySelectorAll('.call-grid>div')].find(item=>item.querySelector('span')?.textContent.trim().toLowerCase()==='time');
  if(field?.querySelector('b'))field.querySelector('b').textContent=wallClockDate(record.call_time).toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit',hour12:true});
};

/* Client schedule-change flow: requests never overwrite a confirmed booking. */
function editShoot(id){
  getRecord(id).then(record=>{
    const p=payload(record),date=String(record.call_time||p.shoot_date||'').slice(0,10),windows=p.availability_windows||[];
    setNav('shoots');
    app.innerHTML=`<div class="shoot-edit-page"><button class="link" data-detail="${id}">← Back to shoot details</button><header class="shoot-edit-head"><div class="eyebrow">Schedule change</div><h1>Find a better time.</h1><p>Choose a preferred date and one or more windows. Your current booking stays in place until your photographer sends new options for you to approve.</p></header><section class="shoot-edit-card"><div class="shoot-edit-current"><span>Current booking</span><b>${esc(record.call_time?formatDate(record.call_time):formatDate(p.shoot_date))}</b></div><form id="shootChangeForm"><div class="field"><label for="changeShootDate">Preferred date</label><input id="changeShootDate" type="date" value="${esc(date)}" required></div><div class="field"><label>Times that work for you</label><div class="change-time-windows">${[['Early morning','06:00','09:00'],['Morning','09:00','12:00'],['Afternoon','12:00','17:00'],['Evening','17:00','23:00']].map(([label,start,end])=>{const value=`${start}–${end}`;return`<button type="button" class="change-time-window ${windows.includes(value)?'active':''}" data-change-window="${value}"><b>${label}</b><span>${value}</span></button>`}).join('')}</div><small class="muted">Select every window that works. Your photographer will reply with available times.</small></div><div class="field"><label for="changeShootNote">Anything else to note? <span>Optional</span></label><textarea id="changeShootNote" maxlength="1200" placeholder="For example: I’m flexible later in the afternoon."></textarea></div><div class="actions"><button class="primary" type="submit">Send change request →</button><button class="secondary" type="button" data-detail="${id}">Cancel</button><span class="muted" id="shootChangeStatus"></span></div></form></section></div>`;
    document.querySelectorAll('[data-change-window]').forEach(button=>{button.querySelector('span').textContent=formatAvailabilityWindow(button.dataset.changeWindow);button.onclick=()=>button.classList.toggle('active')});
    document.getElementById('shootChangeForm').onsubmit=event=>submitShootChange(event,id);
  });
}
async function submitShootChange(event,id){
  event.preventDefault();
  const button=event.currentTarget.querySelector('.primary'),status=document.getElementById('shootChangeStatus'),windows=[...document.querySelectorAll('[data-change-window].active')].map(item=>item.dataset.changeWindow);
  if(!windows.length){status.textContent='Select at least one time window.';return}
  button.disabled=true;status.textContent='Sending your request…';
  try{
    const response=await fetch(`/api/inquiries/${id}/schedule-change-request`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({shoot_date:document.getElementById('changeShootDate').value,availability_windows:windows,note:document.getElementById('changeShootNote').value.trim()||null})}),data=await response.json();
    if(!response.ok)throw Error(data.detail||'Could not send the change request.');
    await refresh();await refreshClientNotifications(false);current={view:'details',id:Number(id)};history.pushState(current,'',`/client?view=details&id=${id}`);galleryDetail(id);setTimeout(()=>{document.querySelector('.shoot-change-toast')?.remove();const toast=document.createElement('div');toast.className='shoot-change-toast';toast.textContent='Change request sent. Your photographer will review it.';document.body.append(toast);setTimeout(()=>toast.remove(),4200)},50);
  }catch(error){status.textContent=error.message;button.disabled=false}
}
const renderClientWithShootEdit=render;
render=()=>current.view==='edit-shoot'?editShoot(current.id):renderClientWithShootEdit();
const galleryDetailWithShootEdit=galleryDetail;
galleryDetail=async id=>{await galleryDetailWithShootEdit(id);const actions=app.querySelector('.detail-next .actions'),record=await getRecord(id);if(['CLIENT_CONFIRMED','SCHEDULED'].includes(record.status)&&actions&&!actions.querySelector('[data-edit-shoot]'))actions.insertAdjacentHTML('beforeend',`<button class="secondary" data-edit-shoot="${id}">Request a time change →</button>`)};
const cinematicPlanWithShootEdit=cinematicPlan;
cinematicPlan=async id=>{await cinematicPlanWithShootEdit(id);const actions=app.querySelector('.plan-decision'),record=await getRecord(id);if(['CLIENT_CONFIRMED','SCHEDULED'].includes(record.status)&&actions&&!actions.querySelector('[data-edit-shoot]'))actions.insertAdjacentHTML('beforeend',`<button class="secondary" data-edit-shoot="${id}">Request a time change →</button>`)};
document.addEventListener('click',event=>{const button=event.target.closest('[data-edit-shoot]');if(!button)return;event.preventDefault();current={view:'edit-shoot',id:Number(button.dataset.editShoot)};history.pushState(current,'',`/client?view=edit-shoot&id=${button.dataset.editShoot}`);editShoot(current.id)});
const shootChangeStyle=document.createElement('style');shootChangeStyle.textContent='.shoot-edit-page{max-width:840px;margin:0 auto}.shoot-edit-head{margin:28px 0}.shoot-edit-head h1{margin:8px 0;font:500 clamp(42px,5vw,64px)/.98 Georgia;letter-spacing:-.055em}.shoot-edit-head p{max-width:620px;color:var(--muted);font-size:16px}.shoot-edit-card{padding:28px;border:1px solid var(--line);border-radius:18px;background:var(--card);box-shadow:0 20px 50px #392e530c}.shoot-edit-current{display:flex;justify-content:space-between;gap:16px;margin-bottom:22px;padding:15px 17px;border-radius:12px;background:#f1edf8}.shoot-edit-current span{color:var(--muted);font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.08em}.change-time-windows{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.change-time-window{min-height:80px;padding:12px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--ink);text-align:left;font:inherit;cursor:pointer}.change-time-window b,.change-time-window span{display:block}.change-time-window span{margin-top:5px;color:var(--muted);font-size:12px}.change-time-window.active{border-color:var(--accent);background:#f0ecfa;box-shadow:0 0 0 1px var(--accent)}.shoot-change-toast{position:fixed;z-index:100;right:24px;bottom:24px;padding:14px 18px;border:1px solid #9acaae;border-radius:13px;background:#e5f4ea;color:#225e3d;box-shadow:0 18px 46px #173d281f;font-weight:750}@media(max-width:700px){.change-time-windows{grid-template-columns:1fr 1fr}.shoot-edit-card{padding:20px}}';document.head.append(shootChangeStyle);

// Final route wrapper: the file contains several legacy render enhancers, so
// place the timeline after all of them have finished rendering.
function ensureClientTimelineFullWidth(){
  if(!['details','plan'].includes(current.view))return;
  const timeline=app.querySelector('.shared-timeline');
  const page=app.querySelector('.detail-gallery,.plan-page');
  if(!timeline||!page)return;
  timeline.classList.add('client-timeline-full-width');
  const anchor=page.querySelector('.detail-sheet,.plan-call-sheet');
  if(!page.contains(timeline))anchor?.before(timeline);
  if(!page.contains(timeline))page.append(timeline);
}
const finalGalleryDetailForTimeline=galleryDetail;
galleryDetail=async id=>{await finalGalleryDetailForTimeline(id);await refreshTimeline();ensureClientTimelineFullWidth()};
const finalCinematicPlanForTimeline=cinematicPlan;
cinematicPlan=async id=>{await finalCinematicPlanForTimeline(id);await refreshTimeline();ensureClientTimelineFullWidth()};

// Keep the client journey as a full-width section on both client-facing pages.
function placeClientTimeline(){
  const timeline=app.querySelector('.shared-timeline');
  const page=app.querySelector('.detail-gallery,.plan-page');
  if(!timeline||!page)return;
  timeline.classList.add('client-timeline-full-width');
  const anchor=page.querySelector('.detail-sheet,.plan-call-sheet');
  if(anchor&&!page.contains(timeline))anchor.before(timeline);
  else if(!page.contains(timeline))page.append(timeline);
}
const clientGalleryDetailWithFullWidthTimeline=galleryDetail;
galleryDetail=async id=>{await clientGalleryDetailWithFullWidthTimeline(id);await refreshTimeline();placeClientTimeline()};
const clientCinematicPlanWithFullWidthTimeline=cinematicPlan;
cinematicPlan=async id=>{await clientCinematicPlanWithFullWidthTimeline(id);await refreshTimeline();placeClientTimeline()};

// Answers are complete once the API accepts them. Keep the client out of the
// intermediary review screen while the photographer's workflow continues.
function showFollowupSubmittedToast(){
  document.querySelector('.followup-success-toast')?.remove();
  const toast=document.createElement('div');
  toast.className='followup-success-toast';
  toast.setAttribute('role','status');
  toast.innerHTML='<i>✓</i><div><strong>Answers received</strong><span>ShotCraft is checking whether any other details are needed.</span></div>';
  document.body.appendChild(toast);
  setTimeout(()=>toast.remove(),5000);
}

reply=async(event,id)=>{
  event.preventDefault();
  const button=document.getElementById('sendAnswers');
  const status=document.getElementById('replyStatus');
  if(!button||button.disabled)return;
  button.disabled=true;
  status.textContent='Sending your answers…';
  try{
    const response=await fetch(`/api/inquiries/${id}/reply`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({answers:document.getElementById('answers').value})
    });
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw Error(data.detail||'Could not send your answers. Please try again.');
    await refresh();
    current={view:'details',id:Number(id)};
    history.pushState(current,'',`/client?view=details&id=${id}`);
    await galleryDetail(id);
    await refreshClientNotifications(false);
    showFollowupSubmittedToast();
  }catch(error){
    status.textContent=error.message||'Could not send your answers. Please try again.';
    button.disabled=false;
  }
};

// Final Create-layer behavior: this must come after the legacy wrappers above,
// which otherwise replace the time-card click handler with a single-select one.
const createWithFinalMultiTimeSelection=create;
create=()=>{
  createWithFinalMultiTimeSelection();
  const picker=document.querySelector('.time-window-picker');
  if(!picker)return;
  picker.setAttribute('aria-multiselectable','true');
  document.getElementById('timeWindowHelp')?.remove();
  picker.insertAdjacentHTML('afterend','<small class="muted" id="timeWindowHelp">Select one or more windows that work for you.</small>');
  picker.querySelectorAll('[data-time-window]').forEach(button=>{
    button.setAttribute('aria-pressed',String(button.classList.contains('active')));
    button.onclick=()=>{
      button.classList.toggle('active');
      button.setAttribute('aria-pressed',String(button.classList.contains('active')));
      const count=picker.querySelectorAll('.time-window.active').length;
      document.getElementById('timeWindowHelp').textContent=count?`${count} preferred time window${count===1?'':'s'} selected.`:'Select one or more windows that work for you.';
    };
  });
  document.getElementById('inquiryForm').onsubmit=submitInquiry;
};
submitInquiry=async event=>{
  event.preventDefault();
  const button=document.getElementById('sendInquiry'),status=document.getElementById('formStatus'),windows=Array.from(document.querySelectorAll('.time-window.active')).map(item=>`${item.dataset.start}–${item.dataset.end}`),budget=Number(String(document.getElementById('budget').value).replace(/[^0-9.]/g,'')),city=cityOptionFor(document.getElementById('shootCity')?.value);
  if(!windows.length){status.textContent='Select at least one preferred time window.';return}
  if(!city){status.textContent='Select a city from the recommendations.';return}
  button.disabled=true;status.textContent='Creating your draft shoot plan…';
  try{
    const body={client_name:clientUser.name,client_email:clientUser.email,contact_email:clientUser.email,message:document.getElementById('message').value,budget:Number.isFinite(budget)?budget:null,shoot_date:document.getElementById('date').value,duration_minutes:Number(document.getElementById('duration').value),location:city.label,style_direction:document.getElementById('style').value,availability_windows:windows,deliverable_count:Number(document.getElementById('deliverableCount').value),reference_images:[],photographer_email:document.getElementById('photographer').value,subject_presentation:document.getElementById('subject').value,subject_count:1};
    const response=await fetch('/api/inquiries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),created=await response.json();
    if(!response.ok)throw Error(created.detail||'Could not create the inquiry.');
    current={view:'details',id:Number(created.id)};history.pushState(current,'',`/client?view=details&id=${created.id}`);app.innerHTML='<div class="loading">ShotCraft is preparing your photographer’s review draft…</div>';
    for(let attempt=0;attempt<30;attempt++){await new Promise(resolve=>setTimeout(resolve,1500));const record=await getRecord(created.id);if(record.status!=='NEW'){await refresh();galleryDetail(created.id);return}}
    await refresh();galleryDetail(created.id);
  }catch(error){status.textContent=error.message||'We couldn’t create that just yet. Please try again.';button.disabled=false}
};
if(new URLSearchParams(location.search).get('view')==='create')create();
// Final review layout: make the decision sequence full-width and linear.
function arrangeClientPlanDecision(){
  const sheet=app.querySelector('.plan-call-sheet'),decision=sheet?.querySelector('.plan-decision'),schedule=decision?.querySelector('.inline-schedule');
  if(!sheet||!decision||!schedule||sheet.classList.contains('plan-review-flow'))return;
  sheet.classList.add('plan-review-flow');
  sheet.firstElementChild?.classList.add('plan-review-summary');
  decision.classList.add('plan-review-actions');
  const policy=decision.querySelector('.booking-policy'),approve=schedule.querySelector('[data-approve-plan-time]');
  if(policy&&approve)schedule.querySelector('.inline-schedule-footer')?.before(policy);
  const secondary=document.createElement('div');secondary.className='plan-review-secondary';
  [...decision.children].filter(item=>item!==schedule&&item!==policy&&item.matches('button')).forEach(button=>secondary.appendChild(button));
  decision.querySelector(':scope > p')?.remove();
  if(secondary.children.length)decision.appendChild(secondary);
}
const cinematicPlanWithModernDecisionFlow=cinematicPlan;
cinematicPlan=async id=>{await cinematicPlanWithModernDecisionFlow(id);arrangeClientPlanDecision()};
new MutationObserver(()=>{if(current.view==='plan')arrangeClientPlanDecision()}).observe(app,{childList:true,subtree:true});

// Keep notification routing as the final render wrapper after all legacy view enhancements.
const finalRenderWithNotificationCenter=render;
render=()=>current.view==='notifications'?notificationsView():finalRenderWithNotificationCenter();

// A cancelled plan is a reference record, not another booking decision.
const planBeforeCancelledArchive=cinematicPlan;
cinematicPlan=async id=>{
  await planBeforeCancelledArchive(id);
  if(current.view!=='plan'||Number(current.id)!==Number(id))return;
  const record=await getRecord(id);
  if(record.status!=='CANCELLED')return;
  const page=app.querySelector('.plan-page'),sheet=page?.querySelector('.plan-call-sheet'),decision=sheet?.querySelector('.plan-decision');
  if(!page||!decision)return;
  page.classList.add('cancelled-plan');
  page.querySelector('.detail-top .lede').textContent='A record of the creative plan for this cancelled shoot.';
  const heading=sheet.querySelector('h2');if(heading)heading.textContent='Shoot cancelled';
  decision.querySelectorAll('.booking-policy,.inline-schedule,.confirmed-banner,.cancel-pending,.plan-review-secondary,button,[data-policy-accept]').forEach(element=>element.remove());
  const fee=Number(record.cancellation_fee||0),refund=Number(record.cancellation_refund||0);
  decision.innerHTML=`<div class="cancelled-plan-summary"><span class="eyebrow">Booking closed</span><p>This shoot has been cancelled. The original plan remains here for reference.</p><div><span>Cancellation fee <b>$${fee.toFixed(2)}</b></span><span>Estimated refund <b>$${refund.toFixed(2)}</b></span></div></div>`;
  page.querySelector('.weather-panel')?.remove();
};

// Availability can be a set of windows, not a single preference. Persist each
// selected range on the inquiry so the photographer can schedule within it.
const createWithMultiSelectTimeWindows=create;
create=()=>{
  createWithMultiSelectTimeWindows();
  const picker=document.querySelector('.time-window-picker');
  if(!picker)return;
  picker.setAttribute('aria-multiselectable','true');
  picker.insertAdjacentHTML('afterend','<small class="muted" id="timeWindowHelp">Select one or more windows that work for you.</small>');
  picker.querySelectorAll('[data-time-window]').forEach(button=>{
    button.setAttribute('aria-pressed','false');
    button.onclick=()=>{
      const active=!button.classList.contains('active');
      button.classList.toggle('active',active);
      button.setAttribute('aria-pressed',String(active));
      const count=picker.querySelectorAll('.time-window.active').length;
      document.getElementById('timeWindowHelp').textContent=count?`${count} preferred time window${count===1?'':'s'} selected.`:'Select one or more windows that work for you.';
    };
  });
  document.getElementById('inquiryForm').onsubmit=submitInquiry;
};
submitInquiry=async event=>{
  event.preventDefault();
  const button=document.getElementById('sendInquiry'),status=document.getElementById('formStatus'),windows=Array.from(document.querySelectorAll('.time-window.active')).map(item=>`${item.dataset.start}–${item.dataset.end}`),budget=Number(String(document.getElementById('budget').value).replace(/[^0-9.]/g,'')),city=cityOptionFor(document.getElementById('shootCity')?.value);
  if(!windows.length){status.textContent='Select at least one preferred time window.';return}
  if(!city){status.textContent='Select a city from the recommendations.';return}
  button.disabled=true;status.textContent='Creating your draft shoot plan…';
  try{
    const body={client_name:clientUser.name,client_email:clientUser.email,contact_email:clientUser.email,message:document.getElementById('message').value,budget:Number.isFinite(budget)?budget:null,shoot_date:document.getElementById('date').value,duration_minutes:Number(document.getElementById('duration').value),location:city.label,style_direction:document.getElementById('style').value,availability_windows:windows,deliverable_count:Number(document.getElementById('deliverableCount').value),reference_images:[],photographer_email:document.getElementById('photographer').value,subject_presentation:document.getElementById('subject').value,subject_count:1};
    const response=await fetch('/api/inquiries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),created=await response.json();
    if(!response.ok)throw Error(created.detail||'Could not create the inquiry.');
    current={view:'details',id:Number(created.id)};history.pushState(current,'',`/client?view=details&id=${created.id}`);app.innerHTML='<div class="loading">ShotCraft is preparing your photographer’s review draft…</div>';
    for(let attempt=0;attempt<30;attempt++){await new Promise(resolve=>setTimeout(resolve,1500));const record=await getRecord(created.id);if(record.status!=='NEW'){await refresh();galleryDetail(created.id);return}}
    await refresh();galleryDetail(created.id);
  }catch(error){status.textContent=error.message||'We couldn’t create that just yet. Please try again.';button.disabled=false}
};
if(new URLSearchParams(location.search).get('view')==='create')create();

// Offer a full-day availability range while keeping each choice compact and
// unambiguous for the photographer's scheduling workflow.
const expandedTimeWindowStyle=document.createElement('style');
expandedTimeWindowStyle.textContent='.time-window-picker{grid-template-columns:repeat(3,minmax(0,1fr))}@media(max-width:700px){.time-window-picker{grid-template-columns:1fr 1fr}}';
document.head.appendChild(expandedTimeWindowStyle);
const createWithExpandedTimeWindows=create;
create=()=>{
  createWithExpandedTimeWindows();
  const picker=document.querySelector('.time-window-picker');
  if(!picker)return;
  const windows=[['Early morning','06:00','09:00'],['Morning','09:00','12:00'],['Midday','12:00','15:00'],['Afternoon','15:00','18:00'],['Evening','18:00','20:00'],['Night','20:00','23:00']];
  picker.innerHTML=windows.map(([label,start,end])=>`<button type="button" class="time-window" data-time-window data-start="${start}" data-end="${end}"><b>${label}</b><span>${formatTimeOfDay(start)} – ${formatTimeOfDay(end)}</span></button>`).join('');
  picker.querySelectorAll('[data-time-window]').forEach(button=>button.onclick=()=>{picker.querySelectorAll('[data-time-window]').forEach(item=>item.classList.toggle('active',item===button));document.getElementById('availabilityStart').value=button.dataset.start;document.getElementById('availabilityEnd').value=button.dataset.end});
};
if(new URLSearchParams(location.search).get('view')==='create')create();
const clientInquiryCardStyle=document.createElement('style');clientInquiryCardStyle.textContent='.gallery-card.gallery-featured.gallery-has-image{background:#201d20}.gallery-card.gallery-featured.gallery-has-image>img{inset:0 0 0 auto;width:43%;height:100%;object-position:center;filter:saturate(.82) contrast(1.02)}.gallery-card.gallery-featured.gallery-has-image .gallery-shade{background:linear-gradient(90deg,#211e21 0 51%,#211e21ee 58%,#211e2130 80%,transparent 100%)}.gallery-card.gallery-featured.gallery-has-image .gallery-content{right:48%;bottom:32px}.gallery-card.gallery-featured.gallery-has-image .gallery-content h2{max-width:560px}.gallery-card.gallery-featured.gallery-has-image .gallery-cta{position:static;margin-top:20px}.gallery-card.gallery-featured.gallery-has-image .circle-action{background:#211e2199}@media(max-width:900px){.gallery-card.gallery-featured.gallery-has-image>img{width:42%}.gallery-card.gallery-featured.gallery-has-image .gallery-content{right:46%;bottom:22px}.gallery-card.gallery-featured.gallery-has-image .gallery-content h2{font-size:clamp(34px,7vw,48px)}}@media(max-width:620px){.gallery-card.gallery-featured.gallery-has-image>img{width:100%;opacity:.48}.gallery-card.gallery-featured.gallery-has-image .gallery-shade{background:linear-gradient(110deg,#211e21ee,#211e2188)}.gallery-card.gallery-featured.gallery-has-image .gallery-content{right:22px}}';document.head.appendChild(clientInquiryCardStyle);

// Census Places directory: all 50 states and DC, with a small popular set when
// the picker opens. The search remains local and is capped to eight results.
let usCityDirectory=[];
const popularCityLabels=['Seattle, WA','Chicago, IL','New York, NY','Los Angeles, CA','Austin, TX'];
const cityPickerStyle=document.createElement('style');
cityPickerStyle.textContent='.city-picker:after{display:none}.city-combobox{position:relative}.city-trigger{position:absolute;right:10px;top:50%;display:grid;place-items:center;width:34px;height:34px;transform:translateY(-50%);border:0;border-radius:9px;background:transparent;color:#615b68;cursor:pointer}.city-trigger:hover{background:#eeeaf9;color:#5b43b1}.city-trigger svg{width:17px;height:17px}.city-suggestions{top:calc(100% - 28px);max-height:296px;overflow:auto}.city-suggestion{align-items:center;justify-content:space-between}.city-suggestion small{color:#807987;font-size:11px;font-weight:700}';
document.head.appendChild(cityPickerStyle);
const normaliseCity=value=>String(value||'').trim().toLowerCase();
const cityOptionFor=value=>usCityDirectory.find(city=>normaliseCity(city.label)===normaliseCity(value)||normaliseCity(city.name)===normaliseCity(value));
const createWithCityDirectory=create;
create=()=>{
  createWithCityDirectory();
  const picker=document.querySelector('.city-picker');
  if(!picker)return;
  picker.innerHTML='<label for="shootCity">Shoot city</label><div class="city-combobox"><input id="shootCity" required autocomplete="off" aria-autocomplete="list" aria-expanded="false" placeholder="Search a U.S. city"><button class="city-trigger" id="shootCityTrigger" type="button" aria-label="Show recommended cities" aria-expanded="false"><svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m5 7 5 5 5-5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></button></div><ul id="shootCitySuggestions" class="city-suggestions" role="listbox" hidden></ul><small class="muted">Start typing to search U.S. cities. Select a recommendation to find photographers.</small>';
  const input=document.getElementById('shootCity'),list=document.getElementById('shootCitySuggestions'),trigger=document.getElementById('shootCityTrigger');
  const choose=city=>{input.value=city.label;list.hidden=true;input.setAttribute('aria-expanded','false');trigger.setAttribute('aria-expanded','false');populatePhotographers()};
  const show=()=>{
    const query=normaliseCity(input.value);
    const pool=query?usCityDirectory.filter(city=>normaliseCity(city.name).includes(query)||normaliseCity(city.label).includes(query)):usCityDirectory.filter(city=>popularCityLabels.includes(city.label));
    const matches=pool.slice(0,8);
    list.innerHTML=matches.map(city=>`<li><button type="button" class="city-suggestion" role="option" data-city-label="${esc(city.label)}"><span>${esc(city.name)}</span><small>${esc(city.state)}</small></button></li>`).join('');
    list.hidden=!matches.length;
    input.setAttribute('aria-expanded',String(Boolean(matches.length)));
    trigger.setAttribute('aria-expanded',String(Boolean(matches.length)));
    list.querySelectorAll('[data-city-label]').forEach(button=>button.onclick=()=>{const city=cityOptionFor(button.dataset.cityLabel);if(city)choose(city)});
  };
  input.addEventListener('input',()=>{show();populatePhotographers()});
  input.addEventListener('focus',show);
  input.addEventListener('blur',()=>setTimeout(()=>{list.hidden=true;input.setAttribute('aria-expanded','false');trigger.setAttribute('aria-expanded','false')},150));
  trigger.onclick=()=>{if(list.hidden){input.focus();show()}else{list.hidden=true;input.setAttribute('aria-expanded','false');trigger.setAttribute('aria-expanded','false')}};
};
populatePhotographers=async()=>{
  const select=document.getElementById('photographer'),help=document.getElementById('photographerHelp'),submit=document.getElementById('sendInquiry'),city=cityOptionFor(document.getElementById('shootCity')?.value);
  if(!select)return;
  if(!city){select.innerHTML='<option value="">Select a recommended city first…</option>';select.disabled=true;if(help)help.textContent='Select a city from the recommendations to see available photographers.';return}
  try{const response=await fetch('/api/photographers?city='+encodeURIComponent(city.name),{cache:'no-store'}),photographers=await response.json();if(!response.ok||!photographers.length){select.innerHTML='<option value="">No photographers found for this city</option>';select.disabled=true;help.textContent='Try another U.S. city.';return}select.innerHTML=`<option value="" selected disabled>Select a photographer…</option>${photographers.map(person=>`<option value="${esc(person.email)}">${esc(person.name)}${person.specialties?` — ${esc(person.specialties)}`:''}</option>`).join('')}`;select.disabled=false;if(submit)submit.disabled=false;help.textContent=`${photographers.length} photographer${photographers.length===1?'':'s'} available in ${city.label}.`}catch{select.innerHTML='<option value="">Could not load photographers</option>';select.disabled=true;help.textContent='Refresh and try again.'}
};
const submitInquiryWithCityDirectory=submitInquiry;
submitInquiry=async event=>{const city=cityOptionFor(document.getElementById('shootCity')?.value);if(city)document.getElementById('shootCity').value=city.name;return submitInquiryWithCityDirectory(event)};
fetch('/static/us-cities.json?v=2024',{cache:'no-store'}).then(response=>response.ok?response.json():[]).then(cities=>{usCityDirectory=Array.isArray(cities)?cities:[];if(new URLSearchParams(location.search).get('view')==='create')create()}).catch(()=>{usCityDirectory=shootCities.map(name=>({name,state:'',label:name}));if(new URLSearchParams(location.search).get('view')==='create')create()});
if(new URLSearchParams(location.search).get('view')==='create')create();

// Keep this final: previous wrappers establish the visual cards, while this
// handler deliberately leaves already-selected cards selected.
// Keep pending time choices in the production-plan action panel, immediately
// above Message photographer, instead of navigating away to a separate screen.
const inlineScheduleStyle=document.createElement('style');
inlineScheduleStyle.textContent='.inline-schedule{display:grid;gap:9px;margin:16px 0;padding:15px;border:1px solid #e3dff0;border-radius:14px;background:#fbfaff}.inline-schedule header{display:grid;gap:3px}.inline-schedule header b{font-size:13px}.inline-schedule header span{color:#746f7a;font-size:12px;line-height:1.4}.inline-schedule-options{display:grid;gap:7px}.inline-schedule-option{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;width:100%;padding:11px 12px;border:1px solid #ded9e4;border-radius:10px;background:#fff;color:#25212a;text-align:left;font:inherit;cursor:pointer}.inline-schedule-option:hover{border-color:#7057c7;background:#f5f2fd}.inline-schedule-option b,.inline-schedule-option small{display:block}.inline-schedule-option b{font-size:12px}.inline-schedule-option small{margin-top:2px;color:#746f7a;font-size:11px}.inline-schedule-option i{color:#7057c7;font-style:normal;font-size:16px}.inline-schedule-status{margin:0;color:#746f7a;font-size:12px}';
document.head.appendChild(inlineScheduleStyle);
const inlineScheduleSelectionStyle=document.createElement('style');
inlineScheduleSelectionStyle.textContent='.inline-schedule-option.selected{border-color:#7057c7;background:#eeeaf9;box-shadow:0 0 0 1px #7057c7}.inline-schedule-option.selected i{font-size:0}.inline-schedule-option.selected i:after{content:"✓";font-size:16px;font-weight:800}';
document.head.appendChild(inlineScheduleSelectionStyle);
const cinematicPlanWithInlineSchedule=cinematicPlan;
cinematicPlan=async id=>{
  await cinematicPlanWithInlineSchedule(id);
  const record=await getRecord(id);
  const pendingReschedule=record.status==='SCHEDULED'&&record.schedule_request?.status==='PENDING_CLIENT'&&['PENDING','AWAITING_CLIENT'].includes(record.change_request?.status);
  if(!record.production_approved||record.status==='CLIENT_CHANGE_REQUESTED'||(record.status==='SCHEDULED'&&!pendingReschedule))return;
  const response=await fetch(`/api/inquiries/${id}/schedule-recommendations`,{cache:'no-store'}),request=response.ok?await response.json():null;
  if(!request?.suggestions?.length||request.status!=='PENDING_CLIENT')return;
  const decision=app.querySelector('.plan-decision');
  if(!decision||decision.querySelector('.inline-schedule'))return;
  decision.querySelector('[data-smart-schedule]')?.remove();
  decision.querySelector('.shared-time-summary')?.remove();
  decision.querySelector('[data-confirm-and-choose]')?.remove();
  decision.querySelector('[data-confirm]')?.remove();
  if(pendingReschedule){decision.querySelector('[data-edit-shoot]')?.remove();decision.querySelector('.confirmed-banner')?.remove()}
  const panel=`<section class="inline-schedule ${pendingReschedule?'is-reschedule':''}"><header>${pendingReschedule?'<span class="inline-schedule-kicker">New times are ready</span>':''}<b>${pendingReschedule?'Choose a revised time':'Choose your preferred time'}</b><span>${pendingReschedule?'Your photographer reviewed the request and sent conflict-free options. Your current booking remains active until you confirm one.':'Select one of the photographer’s available options, then approve your plan.'}</span></header>${pendingReschedule?'<div class="current-booking-note"><i>✓</i><span><b>Current booking protected</b><small>Nothing changes until you confirm a replacement.</small></span></div>':''}<div class="inline-schedule-options">${request.suggestions.map((slot,index)=>`<button type="button" class="inline-schedule-option" aria-pressed="false" data-inline-time-choice data-start="${esc(slot.starts_at)}" data-end="${esc(slot.ends_at)}" data-location="${esc(slot.location)}">${pendingReschedule?`<span class="inline-option-number">Option ${String(index+1).padStart(2,'0')}</span>`:''}<span><b>${esc(calendarDate(slot.starts_at))}</b><small>${esc(calendarTime(slot.starts_at))} – ${esc(calendarTime(slot.ends_at))}${slot.location?` · ${esc(slot.location)}`:''}</small></span><i>→</i></button>`).join('')}</div><div class="inline-schedule-footer"><button type="button" class="primary" data-approve-plan-time="${id}" ${pendingReschedule?'disabled':''}>${pendingReschedule?'Confirm revised time →':'Approve plan & selected time →'}</button>${pendingReschedule?`<button type="button" class="secondary" data-edit-shoot="${id}">None of these work</button>`:''}<p class="inline-schedule-status" id="inlineScheduleStatus">Choose a time to continue.</p></div></section>`;
  const message=decision.querySelector('button.secondary[type="button"]');
  if(message)message.insertAdjacentHTML('beforebegin',panel);else decision.insertAdjacentHTML('beforeend',panel);
};
document.addEventListener('click',async event=>{
  const choice=event.target.closest('[data-inline-time-choice]');
  if(choice){
    event.preventDefault();
    const panel=choice.closest('.inline-schedule');
    panel.querySelectorAll('[data-inline-time-choice]').forEach(option=>{const selected=option===choice;option.classList.toggle('selected',selected);option.setAttribute('aria-pressed',String(selected))});
    panel.dataset.start=choice.dataset.start;panel.dataset.end=choice.dataset.end;panel.dataset.location=choice.dataset.location;
    panel.querySelector('[data-approve-plan-time]').disabled=false;
    panel.querySelector('#inlineScheduleStatus').textContent=panel.classList.contains('is-reschedule')?'Ready to confirm. Your current booking remains active until then.':'Time selected. Approve the plan when you’re ready.';
    return;
  }
  const button=event.target.closest('[data-approve-plan-time]');
  if(!button)return;
  event.preventDefault();
  const panel=button.closest('.inline-schedule'),status=panel.querySelector('#inlineScheduleStatus');
  if(!panel.dataset.start){status.textContent='Choose one of the proposed times first.';return}
  const policy=app.querySelector(`[data-policy-accept="${button.dataset.approvePlanTime}"]`);
  if(policy&&!policy.checked){status.textContent='Accept the cancellation policy before booking.';policy.focus();return}
  button.disabled=true;status.textContent=panel.classList.contains('is-reschedule')?'Confirming your revised time…':'Approving your plan and time…';
  try{
    const record=await getRecord(button.dataset.approvePlanTime);
    if(!['CLIENT_CONFIRMED','SCHEDULED'].includes(record.status)){
      const approval=await fetch(`/api/inquiries/${button.dataset.approvePlanTime}/client-confirm`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cancellation_policy_accepted:true})}),approvalData=await approval.json();
      if(!approval.ok||approvalData.error)throw Error(approvalData.detail||approvalData.error||'Could not approve the shoot plan.');
    }
    const response=await fetch(`/api/inquiries/${button.dataset.approvePlanTime}/schedule-selection`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({starts_at:panel.dataset.start,ends_at:panel.dataset.end,location:panel.dataset.location})}),data=await response.json();
    if(!response.ok)throw Error(data.detail||'Could not save your time preference.');
    await refresh();
    cinematicPlan(button.dataset.approvePlanTime);
  }catch(error){status.textContent=error.message;button.disabled=false}
});

// The timeline was already live, but the action panel was not. Poll the single
// open inquiry and rerender only when a plan/status change actually arrives.
let clientDetailStatusPoll=null;
const galleryDetailWithLivePlanUpdates=galleryDetail;
galleryDetail=async id=>{
  if(clientDetailStatusPoll){clearInterval(clientDetailStatusPoll);clientDetailStatusPoll=null}
  await galleryDetailWithLivePlanUpdates(id);
  const signature=record=>{
    const mood=parsed(record.moodboard)||{},tiles=mood.generated?.tiles||mood.tiles||[],schedule=record.schedule_request||{};
    return [record.status,Boolean(record.production_approved),Boolean(record.production_pack),mood.status||'',tiles.filter(tile=>tile?.image_url||typeof tile==='string').length,schedule.status||''].join('|');
  };
  try{app.dataset.detailStatusSignature=signature(await getRecord(id))}catch{return}
  clientDetailStatusPoll=setInterval(async()=>{
    if(current.view!=='details'||Number(current.id)!==Number(id)){clearInterval(clientDetailStatusPoll);clientDetailStatusPoll=null;return}
    try{
      const latest=await getRecord(id);
      if(signature(latest)===app.dataset.detailStatusSignature)return;
      clearInterval(clientDetailStatusPoll);clientDetailStatusPoll=null;
      await refresh();
      galleryDetail(id);
    }catch{/* keep the visible project stable if a transient request fails */}
  },1000);
};

// This is intentionally the last detail-page wrapper: earlier compatibility
// layers define the base detail view and live-status polling.
const finalGalleryDetailWithCreativePreview=galleryDetail;
const clientCreativePreviewRefinement=document.createElement('style');
clientCreativePreviewRefinement.textContent='.detail-strip.client-creative-preview.is-city-fallback:after{display:none}';
document.head.appendChild(clientCreativePreviewRefinement);
const clientMoodboardCardStyle=document.createElement('style');
clientMoodboardCardStyle.textContent='.client-moodboard-card{margin:10px 0 34px;padding:20px;border:1px solid #ded9e4;border-radius:16px;background:#fff;box-shadow:0 16px 42px #392e5308}.client-moodboard-card h2{margin:5px 0 14px;font:500 29px/1.05 Georgia,serif;letter-spacing:-.025em}.client-moodboard-tiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.client-moodboard-tiles figure{min-width:0;margin:0}.client-moodboard-tiles img{display:block;width:100%;aspect-ratio:1;object-fit:cover;border-radius:10px;background:#211f25}.client-moodboard-tiles figcaption{padding-top:7px;color:#746f7a;font-size:12px;line-height:1.35}@media(max-width:700px){.client-moodboard-card{padding:16px}.client-moodboard-tiles{grid-template-columns:repeat(2,minmax(0,1fr))}.client-moodboard-card h2{font-size:25px}}';
document.head.appendChild(clientMoodboardCardStyle);
const clientMoodboardMarkup=record=>{
  const mood=parsed(record.moodboard)||{};
  const tiles=(mood.generated?.tiles||mood.tiles||[])
    .map((tile,index)=>typeof tile==='string'?{image_url:tile,title:`Creative reference ${index+1}`} : tile)
    .filter(tile=>tile?.image_url)
    .slice(0,4);
  if(!tiles.length)return '';
  const titleText=mood.moodboard?.title||mood.generated?.title||mood.title||'Creative direction';
  return `<div class="eyebrow">Rendered moodboard</div><h2>${esc(titleText)}</h2><div class="client-moodboard-tiles">${tiles.map((tile,index)=>`<figure><img src="${esc(tile.image_url)}" alt="${esc(tile.title||`Creative reference ${index+1}`)}"><figcaption>${esc(tile.title||`Creative reference ${index+1}`)}</figcaption></figure>`).join('')}</div>`;
};
galleryDetail=async id=>{
  await finalGalleryDetailWithCreativePreview(id);
  if(current.view!=='details'||Number(current.id)!==Number(id))return;
  const strip=app.querySelector('.detail-strip');
  if(!strip)return;
  const record=await getRecord(id);
  if(current.view!=='details'||Number(current.id)!==Number(id))return;
  if(record.status==='NEEDS_INFORMATION'){
    strip.className='client-creative-awaiting-details';
    strip.innerHTML=`<div class="eyebrow">Next step</div><h2>Help us shape your shoot</h2><p>Your photographer has a few questions before the creative plan can be prepared.</p><a class="primary" href="/client?view=followup&id=${Number(id)}">Answer follow-up questions →</a>`;
    return;
  }
  const moodboardImages=moodboardImageUrls(record);
  if(moodboardImages.length){
    strip.className='client-moodboard-card';
    strip.innerHTML=clientMoodboardMarkup(record);
    return;
  }
  const existingImages=Array.from(strip.querySelectorAll('img')).map(image=>image.src).filter(Boolean);
  if(existingImages.length){
    strip.className='detail-strip client-creative-preview is-city-fallback';
    strip.innerHTML=creativePreviewMarkup(existingImages.slice(0,4),'city');
    return;
  }
  strip.className='detail-strip client-creative-pending';
  strip.innerHTML=creativePendingMarkup();
  const place=record.meeting_location||payload(record).location;
  if(!place)return;
  try{
    const response=await fetch(`/api/city-images?city=${encodeURIComponent(place)}`,{cache:'no-store'});
    const city=await response.json();
    if(!response.ok||!city.gallery?.length||current.view!=='details'||Number(current.id)!==Number(id)||!strip.isConnected)return;
    strip.className='detail-strip client-creative-preview is-city-fallback';
    strip.innerHTML=creativePreviewMarkup(city.gallery.slice(0,4),'city');
  }catch(_){/* Keep the designed preparing state when city imagery is unavailable. */}
};

const createWithFinalAvailabilitySelection=create;
const clientInquiryCardFramingRefinement=document.createElement('style');
clientInquiryCardFramingRefinement.textContent='@media(min-width:901px){.gallery-grid{grid-auto-rows:370px}.gallery-card:not(.gallery-featured)>img{object-fit:contain!important;object-position:center!important;padding:8px;background:#211e21}.gallery-card:not(.gallery-featured) .gallery-shade{background:linear-gradient(180deg,#15131614 0%,#15131620 36%,#151316df 100%)}}';
document.head.appendChild(clientInquiryCardFramingRefinement);
const clientCreativePreviewFraming=document.createElement('style');
clientCreativePreviewFraming.textContent='@media(min-width:701px){.detail-strip.client-creative-preview{grid-template-columns:repeat(3,minmax(0,1fr))!important;grid-template-rows:1fr!important;min-height:330px}.client-creative-preview>img{grid-row:auto!important;min-height:330px!important;object-fit:contain!important;object-position:center!important;padding:4px;background:#211f25}.client-creative-preview>img:nth-of-type(n+4){display:none!important}}';
document.head.appendChild(clientCreativePreviewFraming);
const timeWindowNoteStyle=document.createElement('style');
timeWindowNoteStyle.textContent='.time-window-note{display:flex;align-items:center;gap:8px;margin-top:11px;color:#746f7a;font-size:12px;line-height:1.4}.time-window-note:before{content:"✓";display:grid;place-items:center;width:18px;height:18px;border-radius:50%;background:#eeeaf9;color:#5b43b1;font-size:11px;font-weight:800}.time-window-note.has-selection{color:#4f4574}.time-window-note.has-selection:before{background:#e2f2e8;color:#317856}';
document.head.appendChild(timeWindowNoteStyle);
create=()=>{
  createWithFinalAvailabilitySelection();
  const picker=document.querySelector('.time-window-picker');
  if(!picker)return;
  picker.setAttribute('aria-multiselectable','true');
  const field=picker.closest('.field');
  field?.querySelectorAll('.muted,#timeWindowHelp').forEach(note=>note.remove());
  field?.insertAdjacentHTML('beforeend','<div class="time-window-note" id="timeWindowHelp">Select every window that works for you — your photographer will use these to propose the final time.</div>');
  picker.querySelectorAll('[data-time-window]').forEach(button=>button.onclick=()=>{
    button.classList.toggle('active');
    button.setAttribute('aria-pressed',String(button.classList.contains('active')));
    const count=picker.querySelectorAll('.time-window.active').length;
    const note=document.getElementById('timeWindowHelp');
    note.textContent=count?`${count} preferred time window${count===1?'':'s'} selected — your photographer will use these to propose the final time.`:'Select every window that works for you — your photographer will use these to propose the final time.';
    note.classList.toggle('has-selection',Boolean(count));
  });
  document.getElementById('inquiryForm').onsubmit=submitInquiry;
};
function enhanceNewInquiryLayout(){
  const form=document.getElementById('inquiryForm');
  if(!form||form.dataset.composed)return;
  form.dataset.composed='true';
  const legacyGrid=form.querySelector('.form-grid');
  if(!legacyGrid)return;
  const fieldFor=id=>document.getElementById(id)?.closest('.field');
  const fields={date:fieldFor('date'),duration:fieldFor('duration'),budget:fieldFor('budget'),deliverables:fieldFor('deliverableCount'),subject:fieldFor('subject'),style:fieldFor('style'),time:document.querySelector('.time-window-picker')?.closest('.field'),city:fieldFor('shootCity'),photographer:fieldFor('photographer'),message:fieldFor('message')};
  fields.subject?.classList.add('full');
  fields.photographer?.classList.add('full');
  const group=(number,title,copy,className='')=>{const section=document.createElement('section');section.className=`inquiry-form-section ${className}`.trim();section.innerHTML=`<header><span>${number}</span><div><h2>${title}</h2><p>${copy}</p></div></header><div class="inquiry-section-fields"></div>`;return section};
  const basics=group('01','Shoot essentials','Start with the practical details that shape the session.','inquiry-basics');
  const creative=group('02','Creative direction','Describe the look, feeling, and purpose of the photographs.','inquiry-creative');
  const planning=group('03','Place and availability','Choose every time that works and who you would like to collaborate with.','inquiry-planning');
  [fields.date,fields.duration,fields.budget,fields.deliverables,fields.subject].filter(Boolean).forEach(field=>basics.querySelector('.inquiry-section-fields').appendChild(field));
  [fields.style,fields.message].filter(Boolean).forEach(field=>creative.querySelector('.inquiry-section-fields').appendChild(field));
  [fields.time,fields.city,fields.photographer].filter(Boolean).forEach(field=>planning.querySelector('.inquiry-section-fields').appendChild(field));
  legacyGrid.remove();
  const actions=form.querySelector('.actions');
  const flow=document.createElement('div');flow.className='inquiry-form-flow';flow.append(basics,creative,planning);
  const footer=document.createElement('footer');footer.className='inquiry-submit-footer';footer.innerHTML=`<div><span class="profile-card-kicker">Final step</span><h2>Send your shoot brief</h2><p>Your photographer will review these details before anything is scheduled.</p></div>`;
  if(actions)footer.appendChild(actions);
  const shell=document.createElement('div');shell.className='inquiry-create-shell';shell.append(flow,footer);form.appendChild(shell);
  form.closest('.card')?.classList.add('inquiry-create-card');
  app.querySelector('.head')?.classList.add('inquiry-create-head');
}
const createWithEditorialLayout=create;
create=()=>{createWithEditorialLayout();enhanceNewInquiryLayout()};
if(current.view==='create')create();
const needsYouRouteAfterLegacyEnhancements=render;
render=()=>current.view==='needs-you'?clientNeedsYouView():needsYouRouteAfterLegacyEnhancements();
clientNeedsNav.onclick=()=>go('needs-you');
const inquiryReviewMarkup=()=>`<section class="inquiry-review-loading" role="status" aria-live="polite"><div class="inquiry-review-visual" aria-hidden="true"><span class="review-orbit review-orbit-one"></span><span class="review-orbit review-orbit-two"></span><span class="review-spark">✦</span></div><div class="inquiry-review-copy"><div class="eyebrow">Inquiry received</div><h1>Reviewing your shoot.</h1><p>ShotCraft is reviewing your brief to see whether your photographer needs any more details.</p><div class="inquiry-review-progress"><span class="inquiry-review-spinner" aria-hidden="true"></span><span>Reviewing your details</span></div><small>You can keep this page open—we’ll move you forward automatically.</small></div></section>`;
submitInquiry=async event=>{
  event.preventDefault();
  const button=document.getElementById('sendInquiry'),status=document.getElementById('formStatus'),windows=Array.from(document.querySelectorAll('.time-window.active')).map(item=>`${item.dataset.start}–${item.dataset.end}`),budget=Number(String(document.getElementById('budget').value).replace(/[^0-9.]/g,'')),city=cityOptionFor(document.getElementById('shootCity')?.value);
  if(!windows.length){status.textContent='Select at least one preferred time window.';return}
  if(!city){status.textContent='Select a city from the recommendations.';return}
  button.disabled=true;status.textContent='Creating your draft shoot plan…';
  try{
    const body={client_name:clientUser.name,client_email:clientUser.email,contact_email:clientUser.email,message:document.getElementById('message').value,budget:Number.isFinite(budget)?budget:null,shoot_date:document.getElementById('date').value,duration_minutes:Number(document.getElementById('duration').value),location:city.label,style_direction:document.getElementById('style').value,availability_windows:windows,deliverable_count:Number(document.getElementById('deliverableCount').value),reference_images:[],photographer_email:document.getElementById('photographer').value,subject_presentation:document.getElementById('subject').value,subject_count:1};
    const response=await fetch('/api/inquiries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),created=await response.json();
    if(!response.ok)throw Error(created.detail||'Could not create the inquiry.');
    current={view:'details',id:Number(created.id)};history.pushState(current,'',`/client?view=details&id=${created.id}`);app.innerHTML=inquiryReviewMarkup();
    for(let attempt=0;attempt<30;attempt++){await new Promise(resolve=>setTimeout(resolve,1500));const record=await getRecord(created.id);if(record.status!=='NEW'){await refresh();galleryDetail(created.id);return}}
    await refresh();galleryDetail(created.id);
  }catch(error){status.textContent=error.message||'We couldn’t create that just yet. Please try again.';button.disabled=false}
};
if(new URLSearchParams(location.search).get('view')==='create')create();
// An earlier details render may finish after the user navigates elsewhere.
// Restore the selected route instead of letting that stale response take over.
const galleryDetailBeforeRouteGuard=galleryDetail;
galleryDetail=async id=>{
  await galleryDetailBeforeRouteGuard(id);
  if(current.view!=='details'||Number(current.id)!==Number(id))render();
};
const awaitingDetailsStyle=document.createElement('style');
awaitingDetailsStyle.textContent='.client-creative-awaiting-details{display:flex;flex-direction:column;align-items:flex-start;justify-content:center;gap:12px;min-height:220px;padding:32px;border:1px solid #d9d0e8;border-radius:18px;background:linear-gradient(120deg,#fff 0%,#f4efff 100%)}.client-creative-awaiting-details .eyebrow{color:#6c55bf}.client-creative-awaiting-details h2{margin:0;font:500 clamp(26px,3vw,38px)/1.1 Georgia,serif;color:#27212f}.client-creative-awaiting-details p{margin:0 0 6px;color:#5d5668}.client-creative-awaiting-details .primary{display:inline-flex;align-items:center;min-height:44px;padding:0 20px;border-radius:999px;background:#7057c7;color:#fff;text-decoration:none;font-weight:700}';
document.head.appendChild(awaitingDetailsStyle);
