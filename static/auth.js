let mode='login';
const $=id=>document.getElementById(id);
function setMode(next){mode=next;const signup=mode==='signup';document.body.classList.toggle('signup-mode',signup);document.body.classList.toggle('login-mode',!signup);$('loginTab').classList.toggle('active',!signup);$('signupTab').classList.toggle('active',signup);$('loginTab').setAttribute('aria-selected',String(!signup));$('signupTab').setAttribute('aria-selected',String(signup));$('heading').textContent=signup?'Create your workspace.':'Welcome back.';$('sub').textContent=signup?'Set up a profile so the right people can find you.':'Sign in to continue planning remarkable shoots.';$('name').required=signup;$('city').required=signup;$('password').autocomplete=signup?'new-password':'current-password';$('submit').innerHTML=signup?'Create account <span>→</span>':'Sign in <span>→</span>';togglePhotographerProfile();history.replaceState(null,'','/auth?mode='+mode)}
$('loginTab').onclick=()=>setMode('login');$('signupTab').onclick=()=>setMode('signup');setMode(new URLSearchParams(location.search).get('mode')==='signup'?'signup':'login');
function togglePhotographerProfile(){const photographer=document.querySelector('input[name=role]:checked').value==='photographer';$('photographerProfile').hidden=mode!=='signup'||!photographer;$('specialties').required=mode==='signup'&&photographer}
document.querySelectorAll('input[name=role]').forEach(input=>input.onchange=togglePhotographerProfile);
const cityInput=$('city'),citySuggestions=$('citySuggestions');
let cityDirectory=[],activeCityIndex=-1,selectedCity='';
const featuredCityLabels=new Set(['Seattle, WA','Chicago, IL','New York, NY','Los Angeles, CA','Austin, TX']);
const citySearch=value=>String(value||'').trim().toLowerCase();
function closeCitySuggestions(){citySuggestions.hidden=true;cityInput.setAttribute('aria-expanded','false');cityInput.removeAttribute('aria-activedescendant');activeCityIndex=-1}
function chooseCity(city){if(!city)return;cityInput.value=city.label;selectedCity=city.label;cityInput.setCustomValidity('');closeCitySuggestions()}
function renderCitySuggestions(){
  const query=citySearch(cityInput.value);
  citySuggestions.replaceChildren();
  activeCityIndex=-1;
  if(!query||!cityDirectory.length){closeCitySuggestions();return}
  const rank=city=>{const name=citySearch(city.name);return (featuredCityLabels.has(city.label)?0:10)+(name===query?0:name.startsWith(query)?1:2)};
  const matches=cityDirectory.filter(city=>citySearch(city.label).includes(query)).sort((a,b)=>rank(a)-rank(b)).slice(0,8);
  matches.forEach((city,index)=>{
    const item=document.createElement('li');
    item.id=`city-option-${index}`;
    item.setAttribute('role','option');
    item.setAttribute('aria-selected','false');
    item.textContent=city.label;
    item.addEventListener('pointerdown',event=>event.preventDefault());
    item.addEventListener('click',()=>chooseCity(city));
    citySuggestions.append(item);
  });
  citySuggestions.hidden=!matches.length;
  cityInput.setAttribute('aria-expanded',String(Boolean(matches.length)));
}
function highlightCity(index){
  const options=[...citySuggestions.children];
  if(!options.length)return;
  activeCityIndex=(index+options.length)%options.length;
  options.forEach((option,i)=>option.setAttribute('aria-selected',String(i===activeCityIndex)));
  cityInput.setAttribute('aria-activedescendant',options[activeCityIndex].id);
  options[activeCityIndex].scrollIntoView({block:'nearest'});
}
cityInput.addEventListener('input',()=>{selectedCity='';cityInput.setCustomValidity('');renderCitySuggestions()});
cityInput.addEventListener('focus',renderCitySuggestions);
cityInput.addEventListener('blur',closeCitySuggestions);
cityInput.addEventListener('keydown',event=>{
  if(event.key==='Escape'){closeCitySuggestions();return}
  if(event.key==='ArrowDown'||event.key==='ArrowUp'){
    if(citySuggestions.hidden)renderCitySuggestions();
    if(!citySuggestions.hidden){event.preventDefault();highlightCity(activeCityIndex<0?(event.key==='ArrowDown'?0:citySuggestions.children.length-1):activeCityIndex+(event.key==='ArrowDown'?1:-1))}
  }
  if(event.key==='Enter'&&!citySuggestions.hidden&&activeCityIndex>=0){event.preventDefault();chooseCity(cityDirectory.find(city=>city.label===citySuggestions.children[activeCityIndex].textContent))}
});
fetch('/static/us-cities.json?v=2024').then(response=>response.ok?response.json():[]).then(cities=>{cityDirectory=Array.isArray(cities)?cities:[]}).catch(()=>{});
$('form').onsubmit=async event=>{event.preventDefault();if(mode==='signup'&&cityDirectory.length&&!selectedCity){const exact=cityDirectory.find(city=>citySearch(city.label)===citySearch(cityInput.value));if(exact)chooseCity(exact);else{cityInput.setCustomValidity('Choose a city from the suggestions.');cityInput.reportValidity();cityInput.focus();return}}$('submit').disabled=true;$('status').textContent='One moment…';const selectedRole=document.querySelector('input[name=role]:checked').value,body={name:$('name').value||null,email:$('email').value,password:$('password').value,...(mode==='signup'?{user_type:selectedRole,city:$('city').value,bio:$('bio').value||null,specialties:$('specialties').value||null}:{})};try{const response=await fetch('/api/auth/'+mode,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),data=await response.json();if(!response.ok||data.error)throw Error(data.detail||data.error||'We could not continue.');sessionStorage.setItem('shotcraftUser',JSON.stringify(data));location.href=data.user_type==='photographer'?'/photographer':'/client'}catch(error){$('status').textContent=error.message;$('submit').disabled=false}};
