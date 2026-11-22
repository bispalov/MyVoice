#!/usr/bin/env python3
"""Тесты «Мій голос» v13: звук нажатия кнопок (⚙️ → «Управление и нажатия», рядом с вибрацией).
Щелчок считается подменой AudioContext.prototype.createOscillator / createGain. Запуск как test_v1.py."""
import json, sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765/MyVoice/'
URL = BASE + 'index.html'
OK = FAIL = 0
def check(n, c, x=''):
    global OK, FAIL
    if c: OK += 1
    else: FAIL += 1; print('FAIL:', n, x)

INIT = ("localStorage.setItem('mv.tour.seen',JSON.stringify({home:1,tiles:1,show:1,abc:1,type:1,pb:1}));"
        "Object.defineProperty(window,'speechSynthesis',{value:{speak:u=>{},cancel(){},getVoices:()=>[],speaking:false,pending:false,paused:false}});"
        "window.__osc=0;window.__f=[];window.__g=[];window.__vib=0;"
        "try{Object.defineProperty(navigator,'vibrate',{value:()=>{window.__vib++;return true},configurable:true})}catch(e){}"
        "(()=>{const AC=window.AudioContext;if(!AC)return;const oc=AC.prototype.createOscillator,gc=AC.prototype.createGain;"
        "AC.prototype.createOscillator=function(){window.__osc++;const o=oc.call(this);const sv=o.frequency.setValueAtTime.bind(o.frequency),er=o.frequency.exponentialRampToValueAtTime.bind(o.frequency);"
        "o.frequency.setValueAtTime=(v,t)=>{window.__f.push(v);return sv(v,t)};o.frequency.exponentialRampToValueAtTime=(v,t)=>{window.__f.push(v);return er(v,t)};return o};"
        "AC.prototype.createGain=function(){const g=gc.call(this);const sv=g.gain.setValueAtTime.bind(g.gain);g.gain.setValueAtTime=(v,t)=>{window.__g.push(v);return sv(v,t)};return g};})();")
def page(b, st, lang='uk', w=360, hgt=640):
    c = b.new_context(viewport={'width': w, 'height': hgt}, service_workers='block')
    c.add_init_script(INIT + f"if(!sessionStorage.getItem('x')){{sessionStorage.setItem('x',1);localStorage.setItem('mv.settings',JSON.stringify({json.dumps(st)}));localStorage.setItem('mv.lang','{lang}');}}")
    pg = c.new_page(); pg.set_default_timeout(6000)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(350)
    return c, pg, errs
osc = lambda pg: pg.evaluate('window.__osc')
BASE_ST = {'profile': 'words', 'quick': False}

with sync_playwright() as p:
    b = p.chromium.launch()
    # по умолчанию выключено
    c, pg, errs = page(b, BASE_ST)
    check('default off', pg.evaluate('settings.tapSound') == 0)
    pg.click('#main .tile >> nth=0'); pg.wait_for_timeout(100)
    check('no click by default', osc(pg) == 0)
    # настройка: 3 варианта, образец, сохранение
    pg.evaluate("closeOv&&closeOv()") if pg.evaluate("typeof closeOv==='function'") else None
    pg.evaluate("$('#ov').style.display='none'")
    pg.click('#settingsBtn'); pg.click('#sett .sg[data-g=touch] .sgh')
    check('select visible', pg.is_visible('#setTapSound'))
    opts = pg.evaluate("[...$('#setTapSound').options].map(o=>o.value+':'+o.text)")
    check('three options uk', opts == ['0:вимкнено', '1:тихий', '2:гучний'], opts)
    check('select after vibration', pg.evaluate("$('#setVib').closest('label').compareDocumentPosition($('#setTapSound'))&Node.DOCUMENT_POSITION_FOLLOWING") > 0)
    check('note text', 'низьке' in pg.inner_text('#tapSoundNote'))
    n0 = osc(pg)
    pg.click('#sett .sg[data-g=main] .sgh'); pg.click('#sett .sg[data-g=touch] .sgh')
    check('settings buttons do not click', osc(pg) == n0)
    pg.select_option('#setTapSound', '2'); pg.wait_for_timeout(150)
    check('sample on choose', osc(pg) == n0 + 1, osc(pg))
    check('sample loud gain', pg.evaluate('window.__g.slice(-1)[0]') == 0.55, pg.evaluate('window.__g'))
    check('saved immediately', json.loads(pg.evaluate("localStorage.getItem('mv.settings')")).get('tapSound') == 2)
    pg.select_option('#setTapSound', '0'); pg.wait_for_timeout(100)
    check('no sample for off', osc(pg) == n0 + 1)
    pg.select_option('#setTapSound', '1'); pg.wait_for_timeout(100)
    check('sample quiet', osc(pg) == n0 + 2 and pg.evaluate('window.__g.slice(-1)[0]') == 0.18)
    pg.click('#sett .sg[data-g=main] .sgh')
    check('summary shows sound', '🔊' in pg.inner_text('#sett .sg[data-g=touch] .sgh'), pg.inner_text('#sett .sg[data-g=touch] .sgh'))
    pg.click('#closeSettBtn')
    pg.reload(); pg.wait_for_timeout(350)
    check('persists after reload', pg.evaluate('settings.tapSound') == 1)
    check('no errors settings', not errs, errs)
    c.close()

    # щелчок на плитке и кнопках
    c, pg, errs = page(b, dict(BASE_ST, tapSound=1))
    pg.click('#main .tile >> nth=0'); pg.wait_for_timeout(100)
    check('click on tile', osc(pg) == 1, osc(pg))
    f = pg.evaluate('window.__f'); check('low frequency', f and max(f) <= 700 and min(f) >= 300, f)
    check('quiet gain', pg.evaluate('window.__g[0]') == 0.18)
    pg.evaluate("$('#ov').style.display='none';render()")
    n = osc(pg); pg.click('#bar button[data-k=rep]') if pg.locator('#bar button[data-k=rep]').count() else pg.click('#bar button >> nth=3')
    check('click on bottom bar', osc(pg) == n + 1)
    n = osc(pg); pg.click('#typeBtn'); pg.wait_for_timeout(100)
    check('click on header button', osc(pg) == n + 1)
    n = osc(pg); pg.click('.tykb >> nth=0'); check('click on keyboard key', osc(pg) == n + 1)
    pg.evaluate("typeOn=false;path=[];render()")
    # окна, не .modal: «Да/Нет», карточка — щёлкают; настройки/справка — нет
    n = osc(pg); pg.evaluate("ynOpen()"); pg.click('.ynb >> nth=0'); check('click in yes/no screen', osc(pg) == n + 1)
    pg.evaluate("ynClose()")
    n = osc(pg); pg.click('#helpBtn'); pg.wait_for_timeout(100); m = osc(pg)
    pg.click('#help .hexp') if pg.locator('#help .hexp').count() else None
    check('help buttons do not click', osc(pg) == m, (n, m, osc(pg)))
    pg.evaluate("$('#help').style.display='none'")
    # распознавание: нет щелчка, вибрация есть
    pg.evaluate("settings.vib=true;rec={abort(){},stop(){}}"); n = osc(pg); v = pg.evaluate('window.__vib')
    pg.evaluate("render()"); pg.click('#main .tile >> nth=0')
    check('no click while recognition', osc(pg) == n)
    check('vibration while recognition', pg.evaluate('window.__vib') > v)
    pg.evaluate("rec=null;rec2={abort(){},stop(){}};$('#ov').style.display='none';render()"); n = osc(pg)
    pg.click('#main .tile >> nth=0'); check('no click while rec2', osc(pg) == n)
    pg.evaluate("rec2=null")
    check('no errors taps', not errs, errs)
    c.close()

    # отклонённые нажатия не щёлкают
    c, pg, errs = page(b, dict(BASE_ST, tapSound=2, guard=1500))
    pg.click('#main .tile >> nth=0'); pg.evaluate("$('#ov').style.display='none';render()")
    n = osc(pg); pg.evaluate("$('#main .tile').click();$('#main .tile').click()")
    check('fast repeat rejected — no click', osc(pg) == n, (n, osc(pg)))
    check('loud gain', pg.evaluate('window.__g[0]') == 0.55)
    c.close()
    c, pg, errs = page(b, dict(BASE_ST, tapSound=2, selMode='hold', holdSel=True))
    n = osc(pg); pg.evaluate("$('#main .tile').click()")
    check('hold mode short tap — no click', osc(pg) == n)
    pg.hover('#main .tile >> nth=0'); pg.mouse.down(); pg.wait_for_timeout(750); pg.mouse.up(); pg.wait_for_timeout(100)
    check('hold mode long press — click', osc(pg) == n + 1, (n, osc(pg)))
    check('no errors hold', not errs, errs)
    c.close()
    # нажатие задержкой: щелчок при срабатывании
    c, pg, errs = page(b, dict(BASE_ST, tapSound=1, selMode='dwell', dwellMs=800))
    r = pg.evaluate("(()=>{const r=$('#main .tile').getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]})()")
    n = osc(pg); pg.mouse.move(r[0], r[1]); pg.mouse.move(r[0] + 2, r[1] + 1); pg.wait_for_timeout(1200)
    check('dwell select — click', osc(pg) >= n + 1, (n, osc(pg)))
    check('no errors dwell', not errs, errs)
    c.close()

    # справка и тексты на трёх языках, вёрстка группы
    c, pg, errs = page(b, BASE_ST)
    for l, t in [('uk', 'Звук під час'), ('ru', 'Звук при нажатии'), ('en', 'Sound on button')]:
        check(f'label {l}', pg.evaluate(f"U.{l}.s_tapsound").startswith(t))
        check(f'help {l}', '🔊' in pg.evaluate(f"JSON.stringify(U.{l}.helpDoc.s)"))
    c.close()
    for (w, hg) in [(360, 640), (313, 556), (277, 492), (240, 427)]:
        for l in ['uk', 'ru', 'en']:
            c, pg, errs = page(b, dict(BASE_ST, theme='dark'), l, w, hg)
            pg.click('#settingsBtn'); pg.click('#sett .sg[data-g=touch] .sgh')
            pg.evaluate("$('#setTapSound').scrollIntoView({block:'center'})")
            ok = pg.evaluate("""(()=>{const m=$('#sett').getBoundingClientRect();return ['#setTapSound','#tapSoundNote'].every(s=>{const r=$(s).getBoundingClientRect();return r.left>=m.left-1&&r.right<=m.right+1&&r.height>0})
              &&$('#setTapSound').scrollWidth<=$('#setTapSound').clientWidth+30})()""")
            check(f'layout {l} {w}', ok)
            check(f'dark select {l} {w}', pg.evaluate("getComputedStyle($('#setTapSound')).backgroundColor")!='rgb(255, 255, 255)')
            check(f'no hscroll {l} {w}', pg.evaluate("$('#sett').scrollWidth<=$('#sett').clientWidth+1"))
            check(f'no errors {l} {w}', not errs, errs)
            c.close()
    b.close()
print(f'OK {OK}  FAIL {FAIL}')
sys.exit(1 if FAIL else 0)
