#!/usr/bin/env python3
"""Тесты «Мій голос» v10: в тёмной теме нет текста на светлом фоне (аудит всех экранов и окон),
поля номера телефона оформлены как поле имени, кнопки экрана «Помощь» тёмные в тёмной теме. Запуск как test_v1.py."""
import sys, json
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765/MyVoice/'
URL = BASE + 'index.html'
OK = FAIL = 0
def check(n, c, x=''):
    global OK, FAIL
    if c: OK += 1
    else: FAIL += 1; print('FAIL:', n, x)
INIT="""localStorage.setItem('mv.tour.seen',JSON.stringify({home:1,tiles:1,show:1,type:1,pb:1}));localStorage.setItem('mv.lang','uk');
localStorage.setItem('mv.settings',JSON.stringify({profile:'words',theme:'dark',msg:'wa',sos:[{n:'Син',t:'+380501112233'},{n:'Дочка',t:'+380671112233'}],card:{name:'Олена',main:'',dx:'',meds:'',allergy:'',notes:'',sos:true,theme:'app'}}));
localStorage.setItem('mv.myph.uk',JSON.stringify(['Я вас люблю']));
Object.defineProperty(window,'speechSynthesis',{value:{speak:u=>{setTimeout(()=>u.onend&&u.onend(),5)},cancel(){},getVoices:()=>[],speaking:false,pending:false,paused:false}});"""
AUD="""(name=>{const p=s=>{const m=s.match(/[\\d.]+/g);return m?m.map(Number):[0,0,0,0]};
const L=c=>{const v=p(c).slice(0,3).map(x=>{x/=255;return x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4)});return 0.2126*v[0]+0.7152*v[1]+0.0722*v[2]};
const bgOf=e=>{for(let x=e;x;x=x.parentElement){const c=getComputedStyle(x).backgroundColor,a=p(c);if(!(a.length>=4&&a[3]<0.5)&&c!=='transparent')return c}return 'rgb(0,0,0)'};
const out=[];document.querySelectorAll('body *').forEach(e=>{
  if(!e.offsetParent&&getComputedStyle(e).position!=='fixed')return;const r=e.getBoundingClientRect();if(r.width<2||r.height<2)return;
  const own=[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())||['INPUT','TEXTAREA','SELECT'].includes(e.tagName);if(!own)return;
  if(e.closest('#card:not(.app)'))return;
  const bg=bgOf(e);const ba=p(bg);if(ba.length>=4&&ba[3]<0.5)return;if(L(bg)>0.35)out.push(name+': '+e.tagName+(e.id?'#'+e.id:'')+'.'+String(e.className).slice(0,30)+' bg='+bg+' text='+getComputedStyle(e).color+' «'+(e.value||e.textContent).trim().slice(0,25)+'»')});
return out})"""
res = []
with sync_playwright() as p:
    b=p.chromium.launch()
    errs=[]
    c=b.new_context(viewport={'width':360,'height':640},service_workers='block');pg=c.new_page();pg.set_default_timeout(5000);pg.add_init_script(INIT);pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(URL);pg.wait_for_timeout(500)
    A=lambda n:res.extend(pg.evaluate(AUD+f"('{n}')"))
    A('home')
    pg.click('#typeBtn');A('type');pg.evaluate("tyFL={pre:'п'};renderType()");A('type-list');pg.evaluate("tyFL=null;tyMy=true;renderType()");A('type-my')
    pg.evaluate("tyMy=false;tyOpts=true;renderType()");A('type-opts');pg.evaluate("tyOpts=false;settings.tySys=true;renderType()");A('type-sys');pg.evaluate("settings.tySys=false;renderType()")
    pg.evaluate("tyText='Я хочу пити';tySay()");pg.wait_for_timeout(100);A('said');pg.evaluate("closeOv()")
    pg.evaluate("pbOpen()");A('pb');pg.evaluate("PBS.lvl='ph';renderPb()");A('pb-ph')
    pg.evaluate("openHear()");A('mic')
    pg.click('#home');pg.click('#main .tile >> nth=0');pg.wait_for_timeout(100);A('tiles')
    pg.evaluate("document.querySelector('#main .tile').click()");pg.wait_for_timeout(100);A('ask')
    pg.evaluate("closeOv();path=[];render();ynOpen('yn')");A('yn');pg.evaluate("ynTab='pain';ynDraw()");A('yn-pain');pg.evaluate("ynClose();cardOpen()");A('card-app');pg.evaluate("cardClose()")
    pg.evaluate("$('#bar button[data-k=help]').click()");pg.wait_for_timeout(100);A('help-red');pg.evaluate("sos&&0");pg.evaluate("appBack()");pg.wait_for_timeout(100)
    pg.evaluate("$('#bar button[data-k=pain]').click()");pg.wait_for_timeout(100);A('pain');pg.click('#home')
    pg.click('#settingsBtn')
    for g in pg.evaluate("[...document.querySelectorAll('#sett .sg')].filter(x=>!x.hidden).map(x=>x.dataset.g)"):
        pg.click(f'#sett .sg[data-g={g}] .sgh');pg.wait_for_timeout(50);A('sett-'+g)
    pg.click('#closeSettBtn');pg.click('#helpBtn');pg.click('#help .hexp');A('help');pg.click('#help .helphead button')
    pg.click('#gear');pg.wait_for_timeout(200);A('editor');pg.evaluate("document.querySelectorAll('#ed button')[3]&&document.querySelectorAll('#ed .tile,#ed button.et')[0]&&document.querySelectorAll('#ed .tile,#ed button.et')[0].click()");pg.wait_for_timeout(100);A('editor2')
    pg.evaluate("$('#ed').style.display='none'");pg.evaluate("setupOpen()");A('setup1');pg.evaluate("setupDraw(2)");A('setup2');pg.evaluate("setupClose()")
    pg.evaluate("tourStart&&tourStart('home')") if pg.evaluate("typeof tourStart==='function'") else None
    check('dark theme: no text on light background', not res, res[:10])
    check('no errors audit', not errs, errs)
    c.close()

    # поля имени и номера одинаковые; кнопки «Помощь»
    for th in ['dark', 'light']:
        c = b.new_context(viewport={'width': 360, 'height': 640}, service_workers='block'); pg = c.new_page(); pg.set_default_timeout(5000)
        pg.add_init_script(INIT.replace("theme:'dark'", "theme:'" + th + "'"))
        pg.goto(URL); pg.wait_for_timeout(400)
        pg.click('#settingsBtn'); pg.click('#sett .sg[data-g=sos] .sgh')
        st = pg.evaluate("['#setSosN0','#setSosT0','#setSosN1','#setSosT1'].map(s=>{const c=getComputedStyle(document.querySelector(s));return [c.fontSize,c.backgroundColor,c.color,c.borderTopColor,document.querySelector(s).offsetHeight].join('|')})")
        check(f'phone field like name field {th}', len(set(st)) == 1, st)
        pg.click('#closeSettBtn')
        pg.evaluate("$('#bar button[data-k=help]').click()"); pg.wait_for_timeout(200)
        bgs = pg.evaluate("[...document.querySelectorAll('#ov.red .call,#ov.red .send')].map(e=>getComputedStyle(e).backgroundColor)")
        check(f'help buttons present {th}', len(bgs) == 4, bgs)
        dark = all(x in ('rgb(26, 7, 5)', 'rgb(14, 42, 27)') for x in bgs)
        white = all(x == 'rgb(255, 255, 255)' for x in bgs)
        check(f'help buttons {th}', dark if th == 'dark' else white, bgs)
        c.close()
    b.close()
print(f'OK {OK}  FAIL {FAIL}')
sys.exit(1 if FAIL else 0)
