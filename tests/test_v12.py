#!/usr/bin/env python3
"""Тесты «Мій голос» v12: «💾 Сохранить PDF» — таблица «По буквам» и экстренная карточка сохраняются в PDF
прямо из приложения (без окна печати). Запуск как test_v1.py. Нужны pdfinfo и pdftoppm (poppler)."""
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
        "Object.defineProperty(window,'speechSynthesis',{value:{speak:u=>{},cancel(){},getVoices:()=>[],speaking:false,pending:false,paused:false}});"
        "window.print=()=>{window.__pr=(window.__pr||0)+1};")
CARD = {'name': 'Олена Коваль', 'main': '', 'dx': 'Інсульт, афазія', 'meds': 'Аспірин 100 мг', 'allergy': 'Пеніцилін', 'notes': 'Носить окуляри', 'sos': True}
TMP = tempfile.mkdtemp()
def page(b, st, lang='uk', w=360, hgt=640):
    c = b.new_context(viewport={'width': w, 'height': hgt}, service_workers='block', accept_downloads=True)
    c.add_init_script(INIT + f"localStorage.setItem('mv.settings',JSON.stringify({json.dumps(st)}));localStorage.setItem('mv.lang','{lang}');")
    pg = c.new_page(); pg.set_default_timeout(8000)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(350)
    return c, pg, errs
def save(pg, sel, name):
    with pg.expect_download() as d: pg.click(sel)
    f = os.path.join(TMP, name); d.value.save_as(f)
    return d.value.suggested_filename, f
def info(f):
    out = subprocess.run(['pdfinfo', f], capture_output=True, text=True).stdout
    g = lambda k: ([x.split(':', 1)[1].strip() for x in out.splitlines() if x.startswith(k + ':')] or [''])[0]
    return g('Pages'), g('Page size')
def dark_share(f):
    # доля тёмных точек на странице: лист не пустой и не залит
    png = f + '.png'; subprocess.run(['pdftoppm', '-r', '20', '-png', '-singlefile', f, f], check=True)
    from PIL import Image
    im = Image.open(png).convert('L'); px = im.tobytes()
    return sum(1 for v in px if v < 128) / len(px)

ST = {'profile': 'words', 'theme': 'dark', 'card': CARD, 'sos': [{'n': 'Син', 't': '+380501112233'}]}
with sync_playwright() as p:
    b = p.chromium.launch()
    for l in ['uk', 'ru', 'en']:
        c, pg, errs = page(b, ST, l)
        pg.evaluate('pbOpen()')
        check(f'pb pdf button {l}', pg.locator('#pbPdf').count() == 1 and '💾' in pg.inner_text('#pbPdf'))
        check(f'pb print button kept {l}', pg.locator('#pbPrint').count() == 1 and '🖨' in pg.inner_text('#pbPrint'))
        name, f = save(pg, '#pbPdf', f'pb_{l}.pdf')
        check(f'pb pdf name {l}', name == f'MyVoice-letters-{l}.pdf', name)
        check(f'pb pdf header {l}', open(f, 'rb').read(5) == b'%PDF-')
        n, sz = info(f)
        check(f'pb pdf one A4 page {l}', n == '1' and 'A4' in sz, (n, sz))
        ds = dark_share(f); check(f'pb pdf has content {l}', 0.02 < ds < 0.4, ds)
        check(f'pb pdf toast {l}', name in pg.inner_text('#mvToast'))
        check(f'no print dialog {l}', not pg.evaluate('window.__pr'))
        pg.evaluate('pbOn=false;render();cardOpen()')
        check(f'card pdf button {l}', pg.locator('#cardPdf').count() == 1)
        name, f = save(pg, '#cardPdf', f'card_{l}.pdf')
        check(f'card pdf name {l}', name == 'MyVoice-card.pdf', name)
        n, sz = info(f); check(f'card pdf one A4 page {l}', n == '1' and 'A4' in sz, (n, sz))
        ds = dark_share(f); check(f'card pdf has content {l}', 0.01 < ds < 0.4, ds)
        check(f'no errors {l}', not errs, errs)
        c.close()
    # длинные поля карточки не ломают лист (половинки для кошелька обрезаются)
    long = dict(CARD, notes='Дуже довгий текст. ' * 60, meds='Ліки ' * 80)
    c, pg, errs = page(b, dict(ST, card=long), 'uk')
    pg.evaluate('cardOpen()'); name, f = save(pg, '#cardPdf', 'card_long.pdf')
    check('long card one page', info(f)[0] == '1')
    check('no errors long', not errs, errs)
    c.close()
    # кнопки в настройках; карточка — со значениями формы
    c, pg, errs = page(b, ST, 'uk')
    pg.click('#settingsBtn'); pg.click('#sett .sg[data-g=card] .sgh')
    check('settings card pdf button', pg.is_visible('#cardPdfBtn') and '💾' in pg.inner_text('#cardPdfBtn'))
    pg.fill('#setCardName', 'Нове імʼя')
    pg.evaluate("window.__fill=0;const o=pdfText;pdfText=function(x,t,...a){if(String(t).includes('Нове імʼя'))window.__fill++;return o(x,t,...a)};0")
    name, f = save(pg, '#cardPdfBtn', 'card_sett.pdf')
    check('settings card pdf uses form values', pg.evaluate('window.__fill') >= 1)
    pg.click('#sett .sg[data-g=type] .sgh')
    check('settings board pdf button', pg.is_visible('#pbPdfBtn') and '💾' in pg.inner_text('#pbPdfBtn'))
    name, f = save(pg, '#pbPdfBtn', 'pb_sett.pdf'); check('settings board pdf', name == 'MyVoice-letters-uk.pdf' and info(f)[0] == '1')
    check('no errors settings', not errs, errs)
    c.close()
    # справка и вёрстка кнопок
    c, pg, errs = page(b, ST, 'uk')
    for l in ['uk', 'ru', 'en']:
        txt = pg.evaluate(f"JSON.stringify(U.{l}.helpDoc.s)"); check(f'help pdf {l}', txt.count('💾') >= 2)
    c.close()
    for (w, hg) in [(360, 640), (313, 556), (277, 492)]:
        for l in ['uk', 'ru', 'en']:
            c, pg, errs = page(b, ST, l, w, hg)
            pg.evaluate('pbOpen()'); pg.evaluate("$('#pbPdf').scrollIntoView()")
            ok = pg.evaluate("""['#pbPrint','#pbPdf'].every(s=>{const e=$(s),r=e.getBoundingClientRect();
              const one=t=>{const rg=document.createRange();rg.selectNodeContents(e);return rg.getClientRects().length};
              return r.left>=0&&r.right<=innerWidth&&r.height>=44&&e.scrollWidth<=e.clientWidth+1&&one()<=2})""")
            check(f'pb buttons fit {l} {w}', ok)
            pg.evaluate('pbOn=false;render();cardOpen()')
            ok = pg.evaluate("[...document.querySelectorAll('#card .row button')].every(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight&&r.height>=48})")
            check(f'card buttons fit {l} {w}', ok)
            check(f'no errors layout {l} {w}', not errs, errs)
            c.close()
    b.close()
print(f'OK {OK}  FAIL {FAIL}')
sys.exit(1 if FAIL else 0)
