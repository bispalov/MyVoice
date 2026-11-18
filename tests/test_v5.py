#!/usr/bin/env python3
"""Тесты «Мій голос» v5: размер плиток (4 варианта, число в ряд не зависит от увеличенного шрифта, шрифт от ширины плитки),
онлайн-поиск слова на экране «Писать». Запуск как test_v1.py. Интернет подменяется (page.route)."""
import json, sys
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
Object.defineProperty(window,'speechSynthesis',{value:{speak:u=>{setTimeout(()=>{u.onend&&u.onend()},5)},cancel(){},getVoices:()=>[],speaking:false,pending:false,paused:false,onvoiceschanged:null}});
"""
def page(b, st, lang='uk', w=360, hgt=640):
    c = b.new_context(viewport={'width': w, 'height': hgt}, service_workers='block')
    c.add_init_script(INIT + f"if(!localStorage.getItem('mv.settings'))localStorage.setItem('mv.settings',JSON.stringify({json.dumps(st)}));if(!localStorage.getItem('mv.lang'))localStorage.setItem('mv.lang','{lang}');")
    pg = c.new_page(); pg.set_default_timeout(5000)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(350)
    return c, pg, errs
COLS = "getComputedStyle(document.querySelector('#main .grid:last-of-type')).gridTemplateColumns.split(' ').length"
LBL = "parseFloat(getComputedStyle(document.querySelector('#main .tile>span:not(.em)')).fontSize)"
EM = "parseFloat(getComputedStyle(document.querySelector('#main .tile .em')).fontSize)"
OVER = "[...document.querySelectorAll('#main .tile')].filter(t=>t.scrollWidth>t.clientWidth+1||[...t.children].some(s=>s.scrollWidth>s.clientWidth+1)).length"

with sync_playwright() as p:
    b = p.chromium.launch()

    # 1. Число плиток в ряд: одинаково на телефонах, в т. ч. при увеличенном шрифте (277 и 313 px)
    want = {'s': {277: 3, 313: 3, 360: 4, 412: 4}, 'm': {277: 2, 313: 2, 360: 2, 412: 2}, 'l': {277: 2, 313: 2, 360: 2, 412: 2}, 'xl': {277: 1, 313: 1, 360: 1, 412: 1}}
    fonts = {}
    for sz in ['s', 'm', 'l', 'xl']:
        for w in [277, 313, 360, 412, 800]:
            for lv, lang in [('L1', 'uk'), ('L2', 'ru'), ('L5', 'en'), ('L5', 'uk')]:
                c, pg, errs = page(b, {'profile': 'words', 'size': sz, 'level': lv}, lang, w, 700)
                n = pg.evaluate(COLS)
                if w in want[sz]:
                    check(f'cols {sz} {w} {lv} {lang}', n == want[sz][w], n)
                else:
                    check(f'tablet more cols {sz} {lv} {lang}', n >= want[sz][412], n)
                check(f'no overflow {sz} {w} {lv} {lang}', pg.evaluate(OVER) == 0)
                check(f'no page hscroll {sz} {w} {lv}', pg.evaluate("document.documentElement.scrollWidth<=innerWidth+1"))
                if lv == 'L2' and w in (277, 360):
                    fonts[(sz, w)] = (pg.evaluate(LBL), pg.evaluate(EM), pg.evaluate("document.querySelector('#main .tile').getBoundingClientRect().height"))
                check(f'no errors {sz} {w} {lv}', not errs, errs)
                c.close()
    # шрифт и значок растут вместе с плиткой
    for w in (277, 360):
        f = [fonts[(sz, w)] for sz in ['s', 'm', 'l', 'xl']]
        check(f'label font grows {w}', f[0][0] < f[1][0] < f[2][0] <= f[3][0], f)
        check(f'emoji grows {w}', f[0][1] < f[1][1] < f[2][1] <= f[3][1], f)
        check(f'large taller than normal {w}', f[2][2] > f[1][2], f)
        check(f'small label readable {w}', f[0][0] >= 12, f)

    # 2. Настройка: четыре варианта, «Маленький» сохраняется после перезапуска
    for lang, lab in [('uk', 'Маленький'), ('ru', 'Маленький'), ('en', 'Small')]:
        c, pg, errs = page(b, {'profile': 'words'}, lang)
        pg.click('#settingsBtn'); pg.click('#sett .sg[data-g=home] .sgh')
        opts = pg.eval_on_selector_all('#setSize option', 'e=>e.map(x=>x.value+":"+x.textContent)')
        check(f'4 sizes {lang}', [o.split(':')[0] for o in opts] == ['s', 'm', 'l', 'xl'] and opts[0].split(':', 1)[1].startswith(lab), opts)
        pg.select_option('#setSize', 's'); pg.wait_for_timeout(100)
        check(f'applied at once {lang}', pg.evaluate("document.documentElement.dataset.size") == 's')
        pg.click('#closeSettBtn'); pg.reload(); pg.wait_for_timeout(350)
        check(f'small kept after reload {lang}', pg.evaluate("settings.size") == 's' and pg.evaluate(COLS) == 4)
        c.close()

    # 3. Онлайн-поиск на «Писать»
    calls = []
    def wiki(route):
        calls.append(route.request.url)
        if 'prefixsearch' in route.request.url:
            route.fulfill(status=200, content_type='application/json', body=json.dumps({'query': {'prefixsearch': [{'title': 'мнемоніка'}, {'title': 'мнемонічний'}]}}))
        else:
            route.fulfill(status=200, content_type='application/json', body=json.dumps({'query': {'search': [], 'searchinfo': {}}}))
    c, pg, errs = page(b, {'profile': 'words', 'tyFirst': False})
    pg.route('**/*.wiktionary.org/**', wiki)
    pg.click('#typeBtn')
    for ch in ['М', 'Н', 'Е']:
        pg.click(f'.tykb .letters .lt:text-is("{ch}")')
    check('no globe when online off', pg.locator('#tySug .tyglobe').count() == 0)
    pg.evaluate("settings.wordOnline=true;saveSettings();tyRefresh()")
    check('globe at end of row', pg.locator('#tySug .tyglobe').count() == 1 and pg.evaluate("document.querySelector('#tySug').lastElementChild.classList.contains('tyglobe')"))
    n_local = pg.locator('#tySug .tyw').count()
    check('one slot given to globe', n_local == pg.evaluate('tySugN()') - 1 or n_local < pg.evaluate('tySugN()'), n_local)
    head_h = pg.evaluate("$('.tyhead').getBoundingClientRect().height")
    pg.click('#tySug .tyglobe'); pg.wait_for_timeout(400)
    res = pg.eval_on_selector_all('#tySug .tyw', 'e=>e.map(x=>x.textContent)')
    check('online results', res == ['🌐 мнемоніка', '🌐 мнемонічний'], res)
    check('request sent to uk wiktionary', any('uk.wiktionary.org' in u and 'pssearch=%D0%BC%D0%BD%D0%B5' in u for u in calls), calls[:2])
    check('row height unchanged', abs(pg.evaluate("$('.tyhead').getBoundingClientRect().height") - head_h) < 1)
    check('keyboard not moved', pg.evaluate("$('.tykb').getBoundingClientRect().top") > 0)
    pg.click('#tySug .tyw >> nth=0')
    check('online word inserted', pg.evaluate('tyText') == 'Мнемоніка ', pg.evaluate('tyText'))
    check('online word learned', 'мнемоніка' in pg.evaluate("JSON.parse(localStorage.getItem('mv.learn.uk')||'[]')"))
    check('back to local suggestions', pg.locator('#tySug .tyglobe').count() == 0 and not pg.evaluate("$('#tySug').classList.contains('onl')"))
    # следующий раз — без интернета, из словаря на телефоне
    pg.click('#tyAct .tyb.cl')
    for ch in ['М', 'Н', 'Е', 'М']:
        pg.click(f'.tykb .letters .lt:text-is("{ch}")')
    loc = pg.eval_on_selector_all('#tySug .tyw', 'e=>e.map(x=>x.textContent)')
    check('learned word suggested offline', 'мнемоніка' in loc, loc)
    # ✕ — назад; новая буква сбрасывает результаты
    pg.click('#tySug .tyglobe'); pg.wait_for_timeout(300)
    pg.click('#tySug .tyglobe:text-is("✕")')
    check('close online results', pg.locator('#tySug .tyglobe:text-is("🌐")').count() == 1)
    pg.click('#tySug .tyglobe'); pg.wait_for_timeout(300)
    pg.click('.tykb .letters .lt:text-is("О")')
    check('typing resets online results', not pg.evaluate("$('#tySug').classList.contains('onl')"))
    # ошибка сети
    pg.unroute('**/*.wiktionary.org/**')
    pg.route('**/*.wiktionary.org/**', lambda r: r.abort())
    pg.click('#tySug .tyglobe'); pg.wait_for_timeout(500)
    info = pg.inner_text('#tySug')
    check('network error shown', pg.locator('#tySug .tyinfo').count() == 1 and len(info) > 5, info)
    check('no globe for 1 letter', (pg.click('#tyAct .tyb.cl'), pg.click('.tykb .letters .lt:text-is("М")'), pg.locator('#tySug .tyglobe').count())[2] == 0)
    check('no errors online', not errs, errs)
    c.close()

    # 4. Вёрстка онлайн-результатов на узком экране
    for (w, hgt) in [(277, 492), (360, 640)]:
        c, pg, errs = page(b, {'profile': 'words', 'tyFirst': False, 'wordOnline': True}, 'ru', w, hgt)
        pg.route('**/*.wiktionary.org/**', lambda r: r.fulfill(status=200, content_type='application/json', body=json.dumps({'query': {'prefixsearch': [{'title': x} for x in ['вода', 'водопровод', 'водитель', 'водоворот', 'водолаз', 'водоём']], 'search': []}})))
        pg.click('#typeBtn'); pg.click('.tykb .letters .lt:text-is("В")'); pg.click('.tykb .letters .lt:text-is("О")')
        pg.click('#tySug .tyglobe'); pg.wait_for_timeout(300)
        check(f'results scroll sideways {w}', pg.evaluate("$('#tySug').scrollWidth>$('#tySug').clientWidth"))
        check(f'no page hscroll {w}', pg.evaluate("document.documentElement.scrollWidth<=innerWidth+1"))
        check(f'globe close fits {w}', pg.evaluate("(()=>{const r=document.querySelector('#tySug .tyglobe').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth})()"))
        pg.screenshot(path=f'/tmp/onl_{w}.png')
        c.close()
    b.close()
print(f'OK {OK}  FAIL {FAIL}')
sys.exit(1 if FAIL else 0)
