#!/usr/bin/env python3
"""Тесты «Мій голос» v3: «потянуть вниз — перезагрузить» отключено (overscroll-behavior),
прокрутка и жесты приложения не сломаны. Запуск как test_v1.py.
Сам жест Chrome «потянуть вниз» в headless Chromium не воспроизводится — проверяются стили и то, что прокрутка и нажатия работают."""
import sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765/MyVoice/'
URL = BASE + 'index.html'
OK = FAIL = 0
def check(n, c, x=''):
    global OK, FAIL
    if c: OK += 1
    else: FAIL += 1; print('FAIL:', n, x)

INIT = """
if(!localStorage.getItem('mv.tour.seen'))localStorage.setItem('mv.tour.seen',JSON.stringify({home:1,tiles:1,hear:1,show:1,abc:1,type:1}));
window.__spoken=[];
Object.defineProperty(window,'speechSynthesis',{value:{speak:u=>{window.__spoken.push(u.text);setTimeout(()=>{u.onend&&u.onend()},5)},cancel(){},getVoices:()=>[],speaking:false,pending:false,paused:false,onvoiceschanged:null}});
"""
def page(b, w=360, hgt=640, st="{profile:'words',tyFirst:false}", touch=False, extra=''):
    c = b.new_context(viewport={'width': w, 'height': hgt}, service_workers='block', has_touch=touch, is_mobile=touch)
    c.add_init_script(INIT + f"if(!localStorage.getItem('mv.settings'))localStorage.setItem('mv.settings',JSON.stringify({st}));if(!localStorage.getItem('mv.lang'))localStorage.setItem('mv.lang','uk');" + extra)
    pg = c.new_page(); pg.set_default_timeout(5000)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(400)
    return c, pg, errs
OB = lambda pg, sel: pg.evaluate(f"(()=>{{const e=document.querySelector({sel!r});return e?getComputedStyle(e).overscrollBehaviorY+'/'+getComputedStyle(e).overscrollBehaviorX:null}})()")

with sync_playwright() as p:
    b = p.chromium.launch()

    # 1. Стили: корень — none, свои области — contain
    for (w, hgt) in [(360, 640), (277, 492)]:
        c, pg, errs = page(b, w, hgt)
        check(f'html none {w}', pg.evaluate("getComputedStyle(document.documentElement).overscrollBehaviorY") == 'none')
        check(f'body none {w}', pg.evaluate("getComputedStyle(document.body).overscrollBehaviorY") == 'none')
        check(f'html x unchanged {w}', pg.evaluate("getComputedStyle(document.documentElement).overscrollBehaviorX") == 'auto')
        for sel in ['#main', '#ov', '#quick']:
            check(f'{sel} contain {w}', OB(pg, sel) == 'contain/contain', OB(pg, sel))
        pg.click('#settingsBtn')
        check(f'.modal contain {w}', OB(pg, '#sett') == 'contain/contain')
        pg.click('#closeSettBtn')
        pg.click('#typeBtn')
        check(f'.tybox contain {w}', OB(pg, '.tybox') == 'contain/contain')
        pg.click('#tyMyBtn')
        check(f'.tymy contain {w}', OB(pg, '.tymy') == 'contain/contain')
        pg.evaluate("ynOpen('yn')")
        check(f'.ynbody contain {w}', OB(pg, '.ynbody') == 'contain/contain')
        pg.evaluate("ynClose();cardOpen()")
        check(f'.cdscroll contain {w}', OB(pg, '.cdscroll') == 'contain/contain')
        pg.evaluate("cardClose();setupOpen()")
        check(f'.suscroll contain {w}', OB(pg, '.suscroll') == 'contain/contain')
        pg.evaluate("setupClose()")
        # все элементы с собственной прокруткой на экранах — с contain
        bad = pg.evaluate("""[...document.querySelectorAll('*')].filter(e=>{const s=getComputedStyle(e);return e!==document.documentElement&&e!==document.body&&/(auto|scroll)/.test(s.overflowY+s.overflowX)&&s.overscrollBehaviorY!=='contain'}).map(e=>e.id||e.className)""")
        check(f'all scroll areas contain {w}', not bad, bad)
        check(f'no errors styles {w}', not errs, errs)
        c.close()

    # 2. Прокрутка работает: #main, окно настроек, справка, горизонтальная полоса реплик
    c, pg, errs = page(b, 360, 640)
    pg.mouse.move(180, 300); pg.mouse.wheel(0, 400); pg.wait_for_timeout(200)
    check('main scrolls', pg.evaluate("$('#main').scrollTop") > 0)
    pg.mouse.wheel(0, -2000); pg.wait_for_timeout(200)
    check('main back to top', pg.evaluate("$('#main').scrollTop") == 0 and pg.evaluate("document.scrollingElement.scrollTop") == 0)
    pg.click('#settingsBtn'); pg.click('#sett .sg[data-g=card] .sgh')
    pg.mouse.move(180, 300); pg.mouse.wheel(0, 500); pg.wait_for_timeout(200)
    check('settings scroll', pg.evaluate("$('#sett').scrollTop") > 0)
    pg.click('#closeSettBtn')
    pg.click('#helpBtn'); pg.click('#help .hexp')
    pg.mouse.move(180, 300); pg.mouse.wheel(0, 800); pg.wait_for_timeout(200)
    check('help scroll', pg.evaluate("$('#help').scrollTop") > 0)
    pg.click('#help .helphead button')
    q = pg.locator('#quick').bounding_box()
    pg.mouse.move(q['x'] + 100, q['y'] + q['height'] / 2); pg.mouse.wheel(300, 0); pg.wait_for_timeout(200)
    check('quick strip scrolls horizontally', pg.evaluate("$('#quick').scrollLeft") > 0)
    check('page not scrolled horizontally', pg.evaluate("document.scrollingElement.scrollLeft") == 0)
    # «Назад» Android (popstate) и обычные нажатия
    pg.click('#typeBtn'); pg.evaluate("history.back()"); pg.wait_for_timeout(300)
    check('android back leaves type', pg.locator('.mvhome').count() == 1)
    check('no errors scroll', not errs, errs)
    c.close()

    # 3. Касания (touch): прокрутка пальцем, нажатие задержкой, выбор удержанием, сканирование
    def touch(pg, x, y, ms=0, moves=()):
        cdp = pg.context.new_cdp_session(pg)
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
        for (dx, dy, wait) in moves:
            pg.wait_for_timeout(wait)
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x + dx, 'y': y + dy}]})
        pg.wait_for_timeout(ms)
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        pg.wait_for_timeout(150)
    def center(pg, sel):
        r = pg.locator(sel).bounding_box(); return r['x'] + r['width'] / 2, r['y'] + r['height'] / 2

    c, pg, errs = page(b, 360, 640, touch=True)
    x, y = center(pg, '#bar button[data-k=yes]')
    pg.evaluate('window.__spoken.length=0')
    touch(pg, x, y, 60)
    check('touch tap works (tap mode)', pg.evaluate('window.__spoken') == ['Так'], pg.evaluate('window.__spoken'))
    c.close()

    c, pg, errs = page(b, 360, 640, st="{profile:'words',tyFirst:false,selMode:'dwell',dwellMs:800}", touch=True)
    x, y = center(pg, '#bar button[data-k=yes]')
    touch(pg, x, y, 80)
    check('touch dwell: short tap ignored', pg.evaluate('window.__spoken') == [], pg.evaluate('window.__spoken'))
    touch(pg, x, y, 300, moves=[(4, 3, 300), (-3, -2, 250)])
    check('touch dwell fires despite tremor', pg.evaluate('window.__spoken') == ['Так'], pg.evaluate('window.__spoken'))
    pg.evaluate('closeOv();window.__spoken.length=0')
    tx, ty = center(pg, '#main .tile >> nth=0')
    touch(pg, tx, ty, 1100)
    check('touch dwell on tile', pg.evaluate("ov.style.display") == 'flex' or pg.evaluate('path.length') > 0)
    pg.evaluate('closeOv();path=[];render()')
    pg.evaluate("$('#typeBtn').click()")
    kx, ky = center(pg, '.tykb .letters .lt >> nth=0')
    touch(pg, kx, ky, 1000)
    check('touch dwell on key', len(pg.evaluate('tyText')) == 1, pg.evaluate('tyText'))
    check('no errors dwell', not errs, errs)
    c.close()

    c, pg, errs = page(b, 360, 640, st="{profile:'words',selMode:'hold',holdSel:true}", touch=True)
    x, y = center(pg, '#bar button[data-k=no]')
    touch(pg, x, y, 80)
    check('touch hold: short tap ignored', pg.evaluate('window.__spoken') == [])
    touch(pg, x, y, 700)
    check('touch hold fires', pg.evaluate('window.__spoken') == ['Ні'], pg.evaluate('window.__spoken'))
    c.close()

    c, pg, errs = page(b, 360, 640, st="{profile:'words',selMode:'scan',scanMs:1000,scanSound:false}", touch=True)
    pg.wait_for_timeout(1500)
    check('scan highlight', pg.locator('.scanrow').count() >= 1)
    touch(pg, 180, 400, 60)
    check('touch anywhere selects row', pg.locator('.scanhi').count() == 1 or pg.locator('.scanrow').count() == 0)
    check('no errors scan', not errs, errs)
    c.close()

    # прокрутка пальцем в #main при обычном касании
    c, pg, errs = page(b, 360, 640, touch=True)
    pg.evaluate("$('#main').append(Object.assign(document.createElement('div'),{style:'height:1500px'}))")
    touch(pg, 180, 450, 0, moves=[(0, -60, 30), (0, -150, 30), (0, -250, 30)])
    check('finger scrolls main', pg.evaluate("$('#main').scrollTop") > 0, pg.evaluate("$('#main').scrollTop"))
    check('page itself not scrolled', pg.evaluate("document.scrollingElement.scrollTop") == 0)
    c.close()

    # 4. Обучение по-прежнему открывается и закрывается
    c, pg, errs = page(b, 360, 640, extra="localStorage.setItem('mv.tour.seen',JSON.stringify({tiles:1,show:1,abc:1,type:1}));")
    pg.wait_for_timeout(900)
    check('tour offered', pg.locator('#tourBox').count() == 1)
    pg.click('#tourBox .go'); pg.wait_for_timeout(200)
    check('tour box contain', OB(pg, '#tourBox') == 'contain/contain')
    pg.evaluate('appBack()')
    check('tour closed by back', pg.locator('#tourBox').count() == 0)
    check('no errors tour', not errs, errs)
    c.close()
    b.close()
print(f'OK {OK}  FAIL {FAIL}')
sys.exit(1 if FAIL else 0)
