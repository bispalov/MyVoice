#!/usr/bin/env python3
"""Тесты «Мій голос» v6: вид экстренной карточки — «всегда светлая» (по умолчанию) или «как тема приложения».
Запуск как test_v1.py."""
import json, sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765/MyVoice/'
URL = BASE + 'index.html'
OK = FAIL = 0
def check(n, c, x=''):
    global OK, FAIL
    if c: OK += 1
    else: FAIL += 1; print('FAIL:', n, x)

INIT = "if(!localStorage.getItem('mv.tour.seen'))localStorage.setItem('mv.tour.seen',JSON.stringify({home:1,tiles:1,show:1,abc:1,type:1}));"
CARD = {'name': 'Олена', 'main': '', 'dx': 'Афазія', 'meds': 'Аспірин', 'allergy': '', 'notes': '', 'sos': True}
def page(b, st, lang='uk', w=360, hgt=640):
    c = b.new_context(viewport={'width': w, 'height': hgt}, service_workers='block')
    c.add_init_script(INIT + f"if(!localStorage.getItem('mv.settings'))localStorage.setItem('mv.settings',JSON.stringify({json.dumps(st)}));if(!localStorage.getItem('mv.lang'))localStorage.setItem('mv.lang','{lang}');")
    pg = c.new_page(); pg.set_default_timeout(5000)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(350)
    return c, pg, errs
# яркость фона карточки и контраст текста (WCAG)
LUM = """(()=>{const p=s=>s.match(/[\\d.]+/g).slice(0,3).map(Number);
const L=c=>{const v=p(c).map(x=>{x/=255;return x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4)});return 0.2126*v[0]+0.7152*v[1]+0.0722*v[2]};
const k=document.querySelector('#card'),bg=getComputedStyle(k).backgroundColor;
const cr=(a,b)=>{const x=L(a),y=L(b);return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05)};
return {bg:L(bg),main:cr(getComputedStyle(document.querySelector('.cdmain')).color,bg),val:cr(getComputedStyle(document.querySelector('.cdv')).color,bg),
 head:cr(getComputedStyle(document.querySelector('.cdh')).color,bg),lab:cr(getComputedStyle(document.querySelector('.cdl')).color,bg)*1}})()"""

with sync_playwright() as p:
    b = p.chromium.launch()
    for theme in ['dark', 'light']:
        for ct, want_light in [(None, True), ('light', True), ('app', theme == 'light')]:
            card = dict(CARD); 
            if ct: card['theme'] = ct
            c, pg, errs = page(b, {'profile': 'words', 'theme': theme, 'card': card})
            pg.evaluate('cardOpen()')
            r = pg.evaluate(LUM)
            tag = f'{theme} card={ct or "default"}'
            check(f'background {tag}', (r['bg'] > 0.8) if want_light else (r['bg'] < 0.1), r)
            check(f'main text contrast {tag}', r['main'] >= 7, r)
            check(f'value contrast {tag}', r['val'] >= 7, r)
            check(f'header contrast {tag}', r['head'] >= 3, r)
            check(f'labels readable {tag}', r['lab'] >= 3, r)
            check(f'class {tag}', pg.evaluate("document.querySelector('#card').classList.contains('app')") == (ct == 'app'))
            pg.screenshot(path=f'/tmp/card_{theme}_{ct or "def"}.png')
            check(f'no errors {tag}', not errs, errs)
            c.close()

    # настройка: два варианта на трёх языках, по умолчанию «всегда светлая», сохраняется сразу
    for lang, first in [('uk', 'Завжди світла'), ('ru', 'Всегда светлая'), ('en', 'Always light')]:
        c, pg, errs = page(b, {'profile': 'words', 'theme': 'dark'}, lang)
        check(f'default light {lang}', pg.evaluate('settings.card.theme') == 'light')
        pg.click('#settingsBtn'); pg.click('#sett .sg[data-g=card] .sgh')
        opts = pg.eval_on_selector_all('#setCardTheme option', 'e=>e.map(x=>x.value+":"+x.textContent)')
        check(f'two options {lang}', [o.split(':')[0] for o in opts] == ['light', 'app'] and opts[0].split(':', 1)[1].startswith(first), opts)
        check(f'selected light {lang}', pg.input_value('#setCardTheme') == 'light')
        pg.select_option('#setCardTheme', 'app'); pg.wait_for_timeout(100)
        check(f'saved at once {lang}', json.loads(pg.evaluate("localStorage.getItem('mv.settings')"))['card']['theme'] == 'app')
        pg.click('#cardShowBtn')
        check(f'card from settings follows theme {lang}', pg.evaluate("document.querySelector('#card').classList.contains('app')"))
        pg.evaluate('cardClose()'); pg.click('#closeSettBtn')
        pg.reload(); pg.wait_for_timeout(300)
        check(f'kept after reload {lang}', pg.evaluate('settings.card.theme') == 'app')
        n = pg.evaluate("HELP_KEYS.length")
        txt = pg.evaluate(f"JSON.stringify(U.{lang}.helpDoc.s[HELP_KEYS.indexOf('card')])")
        check(f'help mentions {lang}', {'uk': 'Вигляд картки', 'ru': 'Вид карточки', 'en': 'Card look'}[lang] in txt)
        check(f'help len {lang}', all(pg.evaluate(f"U.{l}.helpDoc.s.length") == n for l in ['uk', 'ru', 'en']))
        check(f'no errors settings {lang}', not errs, errs)
        c.close()
    # вёрстка группы при 277 px
    c, pg, errs = page(b, {'profile': 'words'}, 'ru', 277, 492)
    pg.click('#settingsBtn'); pg.click('#sett .sg[data-g=card] .sgh')
    check('select fits 277', pg.evaluate("(()=>{const r=$('#setCardTheme').getBoundingClientRect();return r.right<=innerWidth+1})()"))
    check('summary fits 277', pg.evaluate("document.documentElement.scrollWidth<=innerWidth+1"))
    c.close()
    b.close()
print(f'OK {OK}  FAIL {FAIL}')
sys.exit(1 if FAIL else 0)
