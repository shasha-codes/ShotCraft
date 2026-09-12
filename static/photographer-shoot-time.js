/* Final timing layer for project, production, and project-card views. */
const shootWallClockDate=value=>{
  const text=String(value||''),match=text.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?$/);
  return match?new Date(Number(match[1]),Number(match[2])-1,Number(match[3]),Number(match[4]||0),Number(match[5]||0),Number(match[6]||0)):new Date(text);
};
const shootTimeLabel=record=>{
  if(!record.call_time)return'Time to be confirmed';
  const time=shootWallClockDate(record.call_time);
  return Number.isNaN(time.valueOf())?String(record.call_time):time.toLocaleTimeString([],{hour:'numeric',minute:'2-digit',hour12:true});
};

const galleryProjectWithShootTime=galleryProject;
galleryProject=(record,index)=>{
  const markup=galleryProjectWithShootTime(record,index),time=esc(shootTimeLabel(record));
  return markup.replace('</div><span class="status',`<span>◷ ${time}</span></div><span class="status`);
};

const projectWithShootTime=project;
project=async id=>{
  await projectWithShootTime(id);
  const record=await getRecord(id),meta=app.querySelector('.shoot-summary .summary-facts,.detail-grid .meta');
  if(!meta||meta.querySelector('.shoot-time-fact'))return;
  meta.insertAdjacentHTML('beforeend',`<div class="shoot-time-fact">Time<b>${esc(shootTimeLabel(record))}</b></div>`);
};

const productionWithShootTime=showProduction;
showProduction=async(id,push=true)=>{
  await productionWithShootTime(id,push);
  const record=await getRecord(id),sheet=app.querySelector('.call-sheet');
  if(!sheet||sheet.querySelector('.shoot-time-fact'))return;
  sheet.insertAdjacentHTML('beforeend',`<div class="shoot-time-fact"><small>time</small><b>${esc(shootTimeLabel(record))}</b></div>`);
};
