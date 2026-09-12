/* Loaded after the workspace bundle so schedule editing remains the final view layer. */
const finalClientRenderWithShootEdit=render;
render=()=>current.view==='edit-shoot'?editShoot(current.id):finalClientRenderWithShootEdit();

async function showRevisedTimeAction(id){
  const response=await fetch(`/api/inquiries/${id}/schedule-recommendations`,{cache:'no-store'}),request=response.ok?await response.json():null;
  if(request?.status!=='PENDING_CLIENT'||!request.suggestions?.length)return false;
  const actions=app.querySelector('.detail-next .actions');
  if(actions&&!actions.querySelector('[data-revised-times]'))actions.insertAdjacentHTML('afterbegin',`<button class="primary" data-revised-times="${id}">Review revised times →</button>`);
  return true;
}

const finalClientDetailWithShootEdit=galleryDetail;
galleryDetail=async id=>{
  await finalClientDetailWithShootEdit(id);
  if(current.view==='details'&&Number(current.id)===Number(id))try{await showRevisedTimeAction(id)}catch(_){}
  const record=await getRecord(id);
  if(!['SCHEDULED','CLIENT_CONFIRMED'].includes(record.status))return;
  const actions=app.querySelector('.detail-next .actions');
  if(actions&&!actions.querySelector('[data-edit-shoot]'))actions.insertAdjacentHTML('beforeend',`<button class="secondary" data-edit-shoot="${id}">Edit shoot date or time</button>`);
};

const finalClientPlanWithShootEdit=cinematicPlan;
cinematicPlan=async id=>{
  await finalClientPlanWithShootEdit(id);
  const record=await getRecord(id);
  if(!['SCHEDULED','CLIENT_CONFIRMED'].includes(record.status))return;
  const actions=app.querySelector('.plan-decision');
  if(actions&&!actions.querySelector('[data-edit-shoot]'))actions.insertAdjacentHTML('beforeend',`<button class="secondary" data-edit-shoot="${id}">Edit shoot date or time</button>`);
};

// Surface photographer-proposed replacement times without requiring a manual refresh.
setInterval(async()=>{
  if(!['details','plan'].includes(current.view))return;
  if(current.view==='plan'&&app.querySelector('.inline-schedule'))return;
  try{
    const response=await fetch(`/api/inquiries/${current.id}/schedule-recommendations`,{cache:'no-store'}),request=response.ok?await response.json():null;
    if(request?.status!=='PENDING_CLIENT'||!request.suggestions?.length)return;
    if(current.view==='plan')cinematicPlan(current.id);
    else {
      await showRevisedTimeAction(current.id);
    }
  }catch(_){/* The normal page remains available if a transient refresh fails. */}
},5000);
document.addEventListener('click',event=>{const button=event.target.closest('[data-revised-times]');if(!button)return;event.preventDefault();go('plan',button.dataset.revisedTimes)});

// Make a photographer's revised times the most visible client action on Overview.
const clientOverviewWithRescheduleAction=clientOverview;
clientOverview=async()=>{
  clientOverviewWithRescheduleAction();
  try{
    const candidates=shoots.filter(record=>record.status==='SCHEDULED');
    const results=await Promise.all(candidates.map(async record=>{
      const response=await fetch(`/api/inquiries/${record.id}/schedule-recommendations`,{cache:'no-store'});
      return response.ok?{record,request:await response.json()}:null;
    }));
    const pending=results.find(item=>item?.request?.status==='PENDING_CLIENT'&&item.request.suggestions?.length);
    if(!pending||current.view!=='overview')return;
    const tile=app.querySelector('.overview-summary .overview-stat:first-child');
    if(!tile)return;
    const first=pending.request.suggestions[0],time=`${calendarDate(first.starts_at)} · ${calendarTime(first.starts_at)}`;
    tile.innerHTML=`<small>ACTION NEEDED</small><b>New times</b><p>Your photographer proposed ${pending.request.suggestions.length} revised option${pending.request.suggestions.length===1?'':'s'} — starting ${esc(time)}.</p><button class="primary" data-revised-times="${pending.record.id}">Review times →</button>`;
    tile.classList.add('overview-time-action');
  }catch(_){/* Overview remains useful if the notification refresh is unavailable. */}
};
