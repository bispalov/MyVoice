#!/usr/bin/env python3
"""Тесты «Мій голос» v11: 🔄 формы слова на «Писать» и 🖨 печать (таблица «По буквам», экстренная карточка).
Запуск как test_v1.py. Требуется pdftotext (poppler) — для проверки, что лист помещается на одну страницу A4."""
import json, sys, os, subprocess, tempfile
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765/MyVoice/'
URL = BASE + 'index.html'
OK = FAIL = 0
def check(n, c, x=''):
    global OK, FAIL
    if c: OK += 1
    else: FAIL += 1; print('FAIL:', n, x)

INIT = ("localStorage.setItem('mv.tour.seen',JSON.stringify({home:1,tiles:1,show:1,abc:1,type:1,pb:1}));"
        "Object.defineProperty(window,'speechSynthesis',{value:{speak:u=>{window.__said=(window.__said||[]).concat(u.text)},cancel(){},getVoices:()=>[],speaking:false,pending:false,paused:false}});"
        "window.print=()=>{window.__pr=(window.__pr||0)+1;window.__prHtml=(document.getElementById('printArea')||{}).innerHTML||''};")
CARD = {'name': 'Олена Коваль', 'main': '', 'dx': 'Інсульт, афазія', 'meds': 'Аспірин 100 мг', 'allergy': 'Пеніцилін', 'notes': 'Носить окуляри', 'sos': True}
def page(b, st, lang='uk', w=360, hgt=640):
    c = b.new_context(viewport={'width': w, 'height': hgt}, service_workers='block')
    c.add_init_script(INIT + f"localStorage.setItem('mv.settings',JSON.stringify({json.dumps(st)}));localStorage.setItem('mv.lang','{lang}');")
    pg = c.new_page(); pg.set_default_timeout(5000)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(350)
    return c, pg, errs
def lex(pg):
    pg.evaluate("loadBundledLex(lang)"); pg.wait_for_function("!!getLex()", timeout=8000)
def forms(pg, text):
    return pg.evaluate("(t)=>{const w=t.split(' ');const x=w.pop();return wordForms(x,w.pop()||'',24)}", text)

with sync_playwright() as p:
    b = p.chromium.launch()
    # ---------- формы слова ----------
    CASES = {
        'uk': [('лікарня', ['лікарні', 'лікарню']), ('мама', ['маму', 'мамі', 'мамою']), ('вода', ['води', 'воду', 'водою'])],
        'ru': [('больница', ['больнице', 'больницу']), ('мама', ['маму', 'маме', 'мамой']), ('вода', ['воды', 'воду', 'водой'])],
        'en': [('walk', ['walks', 'walked', 'walking']), ('house', ['houses'])]}
    for l, cases in CASES.items():
        c, pg, errs = page(b, {'profile': 'words', 'tyFirst': False}, l)
        lex(pg)
        for w, need in cases:
            r = forms(pg, w)
            check(f'forms {l} {w}', all(x in r for x in need), r)
            check(f'forms {l} {w} not itself', w not in r, r)
        check(f'no errors forms {l}', not errs, errs)
        c.close()
    c, pg, errs = page(b, {'profile': 'words', 'tyFirst': False}, 'uk'); lex(pg)
    check('uk ctx у → лікарні first', forms(pg, 'у лікарня')[:1] == ['лікарні'], forms(pg, 'у лікарня'))
    check('uk ctx з → мамою first', forms(pg, 'з мама')[:1] == ['мамою'], forms(pg, 'з мама'))
    check('uk вода: no verb forms', not any(x in forms(pg, 'вода') for x in ['водить', 'водити']), forms(pg, 'вода'))
    check('uk лікарня: not лікар', not any(x.startswith('лікар') and not x.startswith('лікарн') for x in forms(pg, 'лікарня')), forms(pg, 'лікарня'))
    check('short word: no forms', forms(pg, 'я') == [] and forms(pg, 'на') == [])
    c.close()
    c, pg, errs = page(b, {'profile': 'words', 'tyFirst': False}, 'ru'); lex(pg)
    check('ru ctx в → больнице/больницу first', set(forms(pg, 'в больница')[:2]) == {'больнице', 'больницу'}, forms(pg, 'в больница'))
    check('ru ctx с → мамой first', forms(pg, 'с мама')[:1] == ['мамой'], forms(pg, 'с мама'))
    check('ru ctx ты → хочешь first', forms(pg, 'ты хочу')[:1] == ['хочешь'], forms(pg, 'ты хочу'))
    c.close()

    # интерфейс: кнопка в строке подсказок, панель, замена, «Вернуть», «Назад»
    c, pg, errs = page(b, {'profile': 'words', 'tyFirst': False}, 'uk')
    pg.evaluate("$('#typeBtn').click()"); lex(pg)
    pg.evaluate("tyText='Я у лікарн';tyRefresh()")
    check('no forms chip while word typed', pg.locator('#tyFormsBtn').count() == 0)
    pg.evaluate("tyText='Я у лікарня ';tyRefresh()")
    check('forms chip first in suggestions', pg.evaluate("$('#tySug .chip')&&$('#tySug .chip').id==='tyFormsBtn'"))
    check('forms chip label', '🔄' in pg.inner_text('#tyFormsBtn'))
    pg.click('#tyFormsBtn'); pg.wait_for_timeout(100)
    check('forms panel open', pg.locator('.tyforms').count() == 1 and pg.locator('.tykb').count() == 0)
    check('forms panel title', 'лікарня' in pg.inner_text('.tyforms .tyflp'))
    words = pg.evaluate("[...document.querySelectorAll('.tyforms .tyflw .wd')].map(b=>b.textContent.trim())")
    check('forms panel words', words[:1] == ['лікарні'], words)
    pg.click('.tyforms .tyflw .wd >> nth=0'); pg.wait_for_timeout(100)
    check('form replaces last word', pg.evaluate('tyText') == 'Я у лікарні ', pg.evaluate('tyText'))
    check('keyboard back after pick', pg.locator('.tykb').count() == 1 and pg.locator('.tyforms').count() == 0)
    check('undo shown', pg.locator('#tyAct .tyb.un').count() == 1)
    pg.click('#tyAct .tyb.un'); check('undo restores', pg.evaluate('tyText') == 'Я у лікарня ', pg.evaluate('tyText'))
    pg.evaluate("tyText='Лікарня ';tyRefresh()"); pg.click('#tyFormsBtn'); pg.click('.tyforms .tyflw .wd >> nth=0')
    check('capital kept', pg.evaluate('tyText').startswith('Лікарн') and pg.evaluate('tyText') != 'Лікарня ', pg.evaluate('tyText'))
    pg.evaluate("tyText='мама.';tyRefresh()")
    check('chip after punctuation', pg.locator('#tyFormsBtn').count() == 1)
    pg.click('#tyFormsBtn'); pg.click('.tyforms .tyflw .wd >> nth=0')
    check('punctuation kept', pg.evaluate('tyText').endswith('.') and pg.evaluate('tyText').startswith('мам'), pg.evaluate('tyText'))
    pg.evaluate("tyText='я хочу ';tyRefresh()"); pg.click('#tyFormsBtn')
    pg.evaluate("appBack()"); pg.wait_for_timeout(100)
    check('back closes forms panel', pg.locator('.tyforms').count() == 0 and pg.evaluate('typeOn'))
    pg.evaluate("tyText='я йй ';tyRefresh()")
    check('no chip for short word', pg.locator('#tyFormsBtn').count() == 0)
    pg.evaluate("tyText='я ззззз ';tyRefresh()"); pg.click('#tyFormsBtn')
    check('no forms note', pg.locator('.tyforms .note').count() == 1 and pg.locator('.tyforms .wd').count() == 0)
    pg.evaluate("tyFL=null;settings.tySys=true;renderType(true);tyText='лікарня ';tyRefresh()")
    check('no chip with phone keyboard', pg.locator('#tyFormsBtn').count() == 0)
    check('no errors forms ui', not errs, errs)
    c.close()
    # помещается: строка подсказок с кнопкой, панель форм
    for (w, hg) in [(360, 640), (313, 556), (277, 492)]:
        for l, txt in [('uk', 'Я у лікарня '), ('ru', 'Я в больница '), ('en', 'He walk ')]:
            c, pg, errs = page(b, {'profile': 'words', 'tyFirst': False, 'theme': 'dark'}, l, w, hg)
            pg.evaluate("$('#typeBtn').click()"); lex(pg)
            pg.evaluate(f"tyText={json.dumps(txt)};tyRefresh()")
            fit = pg.evaluate("(()=>{const r=$('#tyFormsBtn').getBoundingClientRect(),m=$('#main').getBoundingClientRect();return r.left>=m.left-1&&r.right<=m.right+1&&r.height>=40})()")
            check(f'forms chip fits {l} {w}', fit)
            pg.click('#tyFormsBtn'); pg.wait_for_timeout(100)
            vis = pg.evaluate("(()=>{const m=$('#main').getBoundingClientRect(),b=$('.tyforms .wd');if(!b)return false;const r=b.getBoundingClientRect();return r.top>=m.top&&r.bottom<=m.bottom})()")
            check(f'forms visible {l} {w}', vis)
            check(f'no hscroll {l} {w}', pg.evaluate("document.documentElement.scrollWidth<=innerWidth+1"))
            check(f'no errors layout {l} {w}', not errs, errs)
            c.close()

    # ---------- печать ----------
    tmp = tempfile.mkdtemp()
    def pdf_pages(pg, name):
        f = os.path.join(tmp, name); pg.pdf(path=f, format='A4', print_background=True)
        try:
            out = subprocess.run(['pdfinfo', f], capture_output=True, text=True).stdout
            n = int([x for x in out.splitlines() if x.startswith('Pages:')][0].split()[1])
            txt = subprocess.run(['pdftotext', f, '-'], capture_output=True, text=True).stdout
            return n, txt
        except Exception as e:
            return -1, str(e)
    for l in ['uk', 'ru', 'en']:
        c, pg, errs = page(b, {'profile': 'words', 'theme': 'dark', 'card': CARD, 'sos': [{'n': 'Син', 't': '+380501112233'}]}, l)
        pg.evaluate("pbOpen()"); pg.wait_for_timeout(100)
        check(f'pb print button {l}', pg.locator('#pbPrint').count() == 1)
        pg.click('#pbPrint'); pg.wait_for_timeout(150)
        check(f'print called {l}', pg.evaluate('window.__pr') == 1)
        html = pg.evaluate('window.__prHtml')
        letters = pg.evaluate("[...document.querySelectorAll('#printArea .prtab tr:not(.ctl):not(.dig) td')].map(t=>t.textContent).filter(Boolean)")
        need = pg.evaluate("PB_ROWS[lang].join('')")
        got = ''.join(x.lower().replace('’', "'") for x in letters)
        check(f'print board all letters once {l}', sorted(got) == sorted(need) and len(set(got)) == len(got), (got, need))
        check(f'print board yes/no {l}', pg.evaluate("document.querySelectorAll('#printArea .pryb').length") == 3)
        check(f'print board help steps {l}', pg.evaluate("document.querySelectorAll('#printArea .prhow li').length") == 5)
        check(f'print board digits {l}', '1 2 3 4 5 6 7 8 9 0' in html)
        check(f'print hides app {l}', pg.evaluate("(()=>{document.body.classList.contains('mvprint');return true})()"))
        pg.emulate_media(media='print')
        check(f'print media: app hidden {l}', pg.evaluate("getComputedStyle($('#main')).display==='none'||getComputedStyle($('#main').parentElement).display==='none'||!$('#main').offsetParent"))
        check(f'print media: area shown {l}', pg.evaluate("getComputedStyle($('#printArea')).display==='block'"))
        check(f'print black text {l}', pg.evaluate("getComputedStyle($('#printArea td')).color==='rgb(0, 0, 0)'"))
        pg.emulate_media(media='screen')
        n, txt = pdf_pages(pg, f'pb_{l}.pdf')
        check(f'board pdf one page {l}', n == 1, n)
        pg.evaluate("window.dispatchEvent(new Event('afterprint'))"); pg.wait_for_timeout(50)
        check(f'afterprint cleans {l}', pg.locator('#printArea').count() == 0 and not pg.evaluate("document.body.classList.contains('mvprint')"))
        # карточка
        pg.evaluate("pbOn=false;render();cardOpen()")
        check(f'card print button {l}', pg.locator('#cardPrint').count() == 1)
        pg.click('#cardPrint'); pg.wait_for_timeout(150)
        txt2 = pg.inner_text('#printArea') if pg.locator('#printArea').count() else ''
        for v in ['Олена Коваль', 'Інсульт, афазія', 'Аспірин 100 мг', 'Пеніцилін', '+380501112233', 'Носить окуляри']:
            check(f'card print has {v} {l}', v in pg.evaluate("$('#printArea .prbig').textContent"))
        check(f'wallet halves {l}', pg.evaluate("document.querySelectorAll('#printArea .prw').length") == 2)
        check(f'wallet back fields {l}', 'Пеніцилін' in pg.evaluate("$('#printArea .prw.back').textContent"))
        n, txt = pdf_pages(pg, f'card_{l}.pdf')
        check(f'card pdf one page {l}', n == 1, n)
        pg.evaluate("window.dispatchEvent(new Event('afterprint'))")
        check(f'no errors print {l}', not errs, errs)
        c.close()
    # кнопки в настройках
    c, pg, errs = page(b, {'profile': 'words', 'card': CARD}, 'uk')
    pg.click('#settingsBtn'); pg.click('#sett .sg[data-g=card] .sgh')
    check('settings card print button', pg.is_visible('#cardPrintBtn') and '🖨' in pg.inner_text('#cardPrintBtn'))
    pg.fill('#setCardName', 'Нове імʼя'); pg.click('#cardPrintBtn'); pg.wait_for_timeout(150)
    check('settings card print uses form values', 'Нове імʼя' in pg.evaluate('window.__prHtml'))
    pg.evaluate("window.dispatchEvent(new Event('afterprint'))")
    pg.click('#sett .sg[data-g=type] .sgh')
    check('settings board print button', pg.is_visible('#pbPrintBtn') and '🖨' in pg.inner_text('#pbPrintBtn'))
    pg.click('#pbPrintBtn'); pg.wait_for_timeout(150)
    check('settings board print', pg.evaluate("window.__pr") == 2 and 'prtab' in pg.evaluate('window.__prHtml'))
    check('no errors settings', not errs, errs)
    c.close()
    # справка
    c, pg, errs = page(b, {'profile': 'words'}, 'uk')
    for l in ['uk', 'ru', 'en']:
        txt = pg.evaluate(f"JSON.stringify(U.{l}.helpDoc.s)")
        check(f'help forms {l}', '🔄' in txt)
        check(f'help print {l}', txt.count('🖨') >= 2)
    c.close()
    # вёрстка кнопок печати
    for (w, hg) in [(360, 640), (277, 492)]:
        for l in ['uk', 'en']:
            c, pg, errs = page(b, {'profile': 'words', 'card': CARD, 'theme': 'dark'}, l, w, hg)
            pg.evaluate("pbOpen()"); pg.evaluate("$('#pbPrint').scrollIntoView()")
            r = pg.evaluate("(()=>{const r=$('#pbPrint').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.height>=44})()")
            check(f'pb print button fits {l} {w}', r)
            check(f'pb yes/no still visible {l} {w}', pg.evaluate("(()=>{$('#main').scrollTop=0;const r=$('#pbYes').getBoundingClientRect();return r.bottom<=$('#main').getBoundingClientRect().bottom})()"))
            pg.evaluate("pbOn=false;render();cardOpen()")
            r = pg.evaluate("[...document.querySelectorAll('#card .row button')].every(b=>{const r=b.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight&&r.height>=48})")
            check(f'card buttons fit {l} {w}', r)
            c.close()
    b.close()
print(f'OK {OK}  FAIL {FAIL}')
sys.exit(1 if FAIL else 0)
