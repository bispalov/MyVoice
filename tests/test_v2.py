#!/usr/bin/env python3
"""Тесты «Мій голос» v2: назначение (профиль), вопрос при первом запуске, «Сложность плиток».
Запуск как test_v1.py: сервер в корне сайта, затем python3 MyVoice/tests/test_v2.py"""
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
window.__spoken=[];
Object.defineProperty(window,'speechSynthesis',{value:{speak:u=>{window.__spoken.push(u.text)},cancel(){},getVoices:()=>[],speaking:false,pending:false,paused:false,onvoiceschanged:null}});
"""
def page(b, w=360, hgt=640, extra=''):
    c = b.new_context(viewport={'width': w, 'height': hgt}, service_workers='block')
    c.add_init_script(INIT + extra)
    pg = c.new_page(); pg.set_default_timeout(5000)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(400)
    return c, pg, errs
S = lambda pg: pg.evaluate("JSON.parse(localStorage.getItem('mv.settings')||'{}')")

with sync_playwright() as p:
    b = p.chromium.launch()

    # 1. Первый запуск: вопрос «для кого», три варианта, язык
    c, pg, errs = page(b, extra="if(!localStorage.getItem('mv.lang'))localStorage.setItem('mv.lang','uk');")
    check('setup shown', pg.locator('#setup .suopt').count() == 3)
    check('setup title uk', 'Для кого' in pg.inner_text('#setup h2'))
    check('no tour over setup', pg.locator('#tourBox').count() == 0)
    pg.click('#setup .sul:text-is("Русский")')
    check('setup title ru', pg.inner_text('#setup h2') == 'Для кого настраиваем приложение?' and pg.evaluate('lang') == 'ru')
    pg.click('#setup .sul:text-is("Українська")')
    # назад на первом шаге не закрывает
    pg.evaluate('appBack()')
    check('back keeps setup', pg.locator('#setup').count() == 1)
    # «Не может говорить, но думает и пишет»
    pg.click('#setup .suopt >> nth=0')
    check('hands step', pg.locator('#setup .suopt').count() == 4 and 'руки' in pg.inner_text('#setup h2'))
    st = S(pg)
    check('speak profile applied', st.get('profile') == 'speak' and st.get('start') == 'type' and st.get('level') == 'L5' and st.get('quick') is True, st)
    pg.evaluate('appBack()')
    check('back to step 1', pg.locator('#setup .suopt').count() == 3)
    pg.click('#setup .suopt >> nth=0'); pg.click('#setup .suopt >> nth=0')   # торкання
    check('setup closed', pg.locator('#setup').count() == 0)
    check('opens Type', pg.locator('#tyBox').count() == 1)
    check('selMode tap', S(pg).get('selMode') == 'tap')
    pg.reload(); pg.wait_for_timeout(400)
    check('no setup second time', pg.locator('#setup').count() == 0 and pg.locator('#tyBox').count() == 1)
    # плитки — полные фразы, фраза звучит сразу (без «…?»)
    pg.click('#home')
    check('L5 tiles', pg.evaluate('settings.level') == 'L5' and pg.locator('#main .tile').count() > 3)
    check('no errors speak', not errs, errs)
    c.close()

    # 2. «Нужны простые картинки» + сканирование
    c, pg, errs = page(b, extra="if(!localStorage.getItem('mv.lang'))localStorage.setItem('mv.lang','ru');")
    pg.click('#setup .suopt >> nth=2')
    pg.click('#setup .suopt >> nth=3')
    st = S(pg)
    check('pics profile', st.get('profile') == 'pics' and st.get('level') == 'L1' and st.get('quickBar') is False and st.get('size') == 'l', st)
    check('home tiles', pg.locator('.mvhome').count() == 1 and pg.evaluate("document.querySelector('#quick').hidden"))
    check('L1 no abc', pg.evaluate("document.body.classList.contains('no-abc')"))
    pg.wait_for_timeout(2600)
    check('scan started', st.get('selMode') == 'scan' and pg.locator('.scanrow').count() >= 1)
    check('no errors pics', not errs, errs)
    c.close()

    # 3. «Трудно подбирать слова» + задержка
    c, pg, errs = page(b, extra="if(!localStorage.getItem('mv.lang'))localStorage.setItem('mv.lang','en');")
    check('setup en', pg.inner_text('#setup h2') == 'Who are we setting the app up for?')
    pg.click('#setup .suopt >> nth=1'); pg.click('#setup .suopt >> nth=2')
    st = S(pg)
    check('words profile', st.get('profile') == 'words' and st.get('level') == 'L2' and st.get('start') == 'tiles' and st.get('selMode') == 'dwell', st)
    check('dwell on', pg.evaluate("document.body.classList.contains('dwell')"))
    c.close()

    # 4. Ярлык ?open=card при первом запуске: сначала вопрос
    c, pg, errs = page(b)
    pg.goto(URL + '?open=card'); pg.wait_for_timeout(300)
    check('setup before shortcut', pg.locator('#setup').count() == 1)
    c.close()

    # 5. Настройки: назначение, смена с подстановкой значений, сложность плиток
    for lang, lvl5, lab in [('uk', 'Повні фрази (до 5 частин)', 'Складність плиток'), ('ru', 'Полные фразы (до 5 частей)', 'Сложность плиток'), ('en', 'Full phrases (up to 5 parts)', 'Tile complexity')]:
        c, pg, errs = page(b, extra=f"if(!localStorage.getItem('mv.settings'))localStorage.setItem('mv.settings',JSON.stringify({{profile:'words'}}));localStorage.setItem('mv.lang','{lang}');")
        pg.on('dialog', lambda d: d.accept())
        pg.click('#settingsBtn')
        check(f'profile select {lang}', pg.locator('#setProfile option').count() == 3 and pg.input_value('#setProfile') == 'words')
        check(f'level label {lang}', pg.inner_text('label[data-i=s_level]') == lab)
        check(f'level names {lang}', lvl5 in pg.eval_on_selector_all('#setSeg option', 'e=>e.map(x=>x.textContent)'))
        check(f'pf note {lang}', len(pg.inner_text('#pfNote')) > 40)
        pg.select_option('#setProfile', 'speak')
        check(f'form filled {lang}', pg.input_value('#setSeg') == 'L5' and pg.input_value('#setStart') == 'type' and pg.is_checked('#setQuick'))
        pg.click('#closeSettBtn')
        st = S(pg)
        check(f'saved {lang}', st.get('profile') == 'speak' and st.get('level') == 'L5' and st.get('start') == 'type', st)
        c.close()
    c, pg, errs = page(b, extra="if(!localStorage.getItem('mv.settings'))localStorage.setItem('mv.settings',JSON.stringify({profile:'words'}));localStorage.setItem('mv.lang','uk');")
    pg.on('dialog', lambda d: d.dismiss())
    pg.click('#settingsBtn'); pg.select_option('#setProfile', 'pics'); pg.click('#closeSettBtn')
    st = S(pg)
    check('dismiss keeps values', st.get('profile') == 'pics' and st.get('level') == 'L2', st)
    # справка: пункт о назначении, «Сложность плиток»
    for lang in ['uk', 'ru', 'en']:
        n = pg.evaluate("HELP_KEYS.length")
        check(f'help len {lang}', pg.evaluate(f"U.{lang}.helpDoc.s.length") == n)
        i = pg.evaluate("HELP_KEYS.indexOf('profile')")
        check(f'help profile {lang}', i == 1 and pg.evaluate(f"U.{lang}.helpDoc.s[1][0]").startswith({'uk': 'Призначення', 'ru': 'Назначение', 'en': 'Purpose'}[lang]))
        lv = pg.evaluate(f"U.{lang}.helpDoc.s[HELP_KEYS.indexOf('level')][0]")
        check(f'help level {lang}', lv.startswith({'uk': 'Складність', 'ru': 'Сложность', 'en': 'Tile complexity'}[lang]), lv)
    check('no errors settings', not errs, errs)
    c.close()

    # 6. Вёрстка вопроса при первом запуске
    for (w, hgt) in [(360, 640), (313, 556), (277, 492), (800, 1280)]:
        for lang in ['uk', 'ru', 'en']:
            c, pg, errs = page(b, w, hgt, extra=f"localStorage.setItem('mv.lang','{lang}');")
            tag = f'{w}x{hgt} {lang}'
            fit = "[...document.querySelectorAll('#setup button')].every(e=>{const r=e.getBoundingClientRect();return r.left>=-1&&r.right<=innerWidth+1&&e.scrollWidth<=e.clientWidth+2})"
            check(f'step1 fits {tag}', pg.evaluate(fit) and pg.evaluate("document.documentElement.scrollWidth<=innerWidth+1"))
            pg.screenshot(path=f'/tmp/setup1_{w}_{lang}.png')
            pg.click('#setup .suopt >> nth=0')
            check(f'step2 fits {tag}', pg.evaluate(fit))
            back = pg.evaluate("(()=>{const r=document.querySelector('#setup .subk').getBoundingClientRect();return r.bottom<=innerHeight+1})()")
            check(f'back visible {tag}', back)
            pg.screenshot(path=f'/tmp/setup2_{w}_{lang}.png')
            check(f'no errors {tag}', not errs, errs)
            c.close()
    b.close()
print(f'OK {OK}  FAIL {FAIL}')
sys.exit(1 if FAIL else 0)
