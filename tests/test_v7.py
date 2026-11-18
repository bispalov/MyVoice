#!/usr/bin/env python3
"""Тесты «Мій голос» v7: «Азбука» стала режимом «Писать» (слово по первой букве), на её месте —
«👁 По буквам с помощником». Запуск как test_v1.py."""
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
if(!localStorage.getItem('mv.tour.seen'))localStorage.setItem('mv.tour.seen',JSON.stringify({home:1,tiles:1,hear:1,show:1,abc:1,type:1,pb:1}));
window.__sp=[];
Object.defineProperty(window,'speechSynthesis',{value:{speak:u=>{window.__sp.push(u.text);setTimeout(()=>{u.onend&&u.onend()},5)},cancel(){},getVoices:()=>[],speaking:false,pending:false,paused:false,onvoiceschanged:null}});
"""
def page(b, st, lang='uk', w=360, hgt=640, extra=''):
    c = b.new_context(viewport={'width': w, 'height': hgt}, service_workers='block')
    c.add_init_script(INIT + f"if(!localStorage.getItem('mv.settings'))localStorage.setItem('mv.settings',JSON.stringify({json.dumps(st)}));if(!localStorage.getItem('mv.lang'))localStorage.setItem('mv.lang','{lang}');" + extra)
    pg = c.new_page(); pg.set_default_timeout(5000)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(350)
    return c, pg, errs
SP = lambda pg: pg.evaluate('window.__sp')
def letter(pg, ch): pg.click(f'.tykb .letters .lt:has-text("{ch}") >> nth=0')

with sync_playwright() as p:
    b = p.chromium.launch()

    # 1. Экрана «Азбука» нет; на месте её кнопки — «По буквам»; группа настроек «Азбука» скрыта
    for lang, lab in [('uk', 'По літерах'), ('ru', 'По буквам'), ('en', 'Letters')]:
        c, pg, errs = page(b, {'profile': 'words'}, lang)
        check(f'pb button label {lang}', pg.inner_text('#abcBtn .lbl') == lab and pg.inner_text('#abcBtn .ic') == '👁')
        pg.click('#abcBtn'); pg.wait_for_timeout(100)
        check(f'pb screen opens {lang}', pg.locator('#pbQ').count() == 1 and pg.evaluate('pbOn') and not pg.evaluate('!!abc'))
        pg.evaluate('abcOpen()')
        check(f'abcOpen -> Type {lang}', pg.locator('#tyBox').count() == 1)
        pg.click('#settingsBtn')
        check(f'abc settings group hidden {lang}', pg.evaluate("document.querySelector('#sett .sg[data-g=abc]').hidden"))
        if pg.evaluate("settOpen") != 'type': pg.click('#sett .sg[data-g=type] .sgh')
        check(f'tyFirst setting {lang}', pg.is_visible('#setTyFirst') and pg.is_checked('#setTyFirst'))
        pg.click('#closeSettBtn')
        txt = pg.evaluate(f"JSON.stringify(U.{lang}.helpDoc.s)")
        bad = [w for w in {'uk': ['«Абетка»', '«Абетку»', 'екрані «Абетка»'], 'ru': ['«Азбука»', '«Азбуку»', 'экране «Азбука»'], 'en': ['the ABC screen', 'ABC button', 'through 🎤 and ABC']}[lang] if w in txt.replace('немає', '').replace('нет', '') and not ('Окремого екрана «Абетка»' in txt and w == '«Абетка»') and not ('Отдельного экрана «Азбука»' in txt and w == '«Азбука»')]
        check(f'help no old ABC screen {lang}', not bad, bad)
        n = pg.evaluate('HELP_KEYS.length')
        check(f'help lengths {lang}', all(pg.evaluate(f'U.{l}.helpDoc.s.length') == n for l in ['uk', 'ru', 'en']) and pg.evaluate("HELP_KEYS.indexOf('pb')") == pg.evaluate("HELP_KEYS.indexOf('abc')") + 1)
        check(f'no errors {lang}', not errs, errs)
        c.close()
    # L1 — кнопки «По буквам» нет
    c, pg, errs = page(b, {'profile': 'pics', 'level': 'L1'})
    check('L1 no pb button', not pg.is_visible('#abcBtn'))
    c.close()

    # 2. Слово по первой букве
    c, pg, errs = page(b, {'profile': 'words'})
    pg.click('#typeBtn')
    check('first mode on for words profile', pg.evaluate('settings.tyFirst') and pg.locator('.tykb.first').count() == 1)
    check('placeholder first', 'першу літеру' in pg.inner_text('#tyBox'))
    check('letters show dots', pg.locator('.tykb .letters .lt .dots').count() >= 33)
    letter(pg, 'Я')
    check('letter opens word list', pg.locator('.tyfl .tyflw .wd').count() > 0 and pg.evaluate('tyText') == '')
    check('panel header visible', pg.evaluate("(()=>{const r=$('.tyflh').getBoundingClientRect(),m=$('#main').getBoundingClientRect(),h=$('.tyhead').getBoundingClientRect();return r.top>=h.bottom-1&&r.bottom<=m.bottom})()"))
    words = pg.eval_on_selector_all('.tyflw .wd', 'e=>e.map(x=>x.textContent)')
    check('words start with letter', all(w.lower().startswith('я') for w in words) and 'я' in words, words[:8])
    pg.click('.tyflw .wd:text-is("я")')
    check('word inserted capitalized', pg.evaluate('tyText') == 'Я ' and pg.locator('.tykb').count() == 1)
    letter(pg, 'Х')
    w2 = pg.eval_on_selector_all('.tyflw .wd', 'e=>e.map(x=>x.textContent)')
    check('next-word ranking (хочу first after я)', w2[:3].count('хочу') == 1, w2[:6])
    nx = pg.eval_on_selector_all('.tyfln .chip', 'e=>e.map(x=>x.textContent)')
    check('second-letter chips', 'ХО' in nx and all(x.startswith('Х') and len(x) == 2 for x in nx), nx)
    pg.click('.tyfln .chip:text-is("ХО")')
    w3 = pg.eval_on_selector_all('.tyflw .wd', 'e=>e.map(x=>x.textContent)')
    check('narrowed by second letter', all(w.startswith('хо') for w in w3) and len(w3) > 0, w3[:6])
    check('prefix shown', pg.inner_text('.tyflp') == 'ХО…')
    pg.click('.tyflh .tyb.cl')
    check('⌫ removes second letter', pg.inner_text('.tyflp') == 'Х…')
    pg.evaluate('appBack()')
    check('back closes list', pg.locator('.tyfl').count() == 0 and pg.locator('.tykb').count() == 1)
    letter(pg, 'Х'); pg.click('.tyflw .wd:text-is("хочу")')
    check('second word', pg.evaluate('tyText') == 'Я хочу ')
    # служебные слова
    pg.click('.tykb .fnk')
    check('function words panel', pg.locator('.tyfl .fnp .chip').count() > 10)
    pg.click('.tyfl .fnp .chip:text-is("до")')
    check('function word inserted', pg.evaluate('tyText') == 'Я хочу до ')
    check('learned word list', 'хочу' in pg.evaluate("JSON.parse(localStorage.getItem('mv.learn.uk')||'[]')"))
    # переключатель режима
    pg.click('#tyFirstBtn')
    check('toggle off -> spelling', not pg.evaluate('settings.tyFirst') and pg.locator('.tykb.first').count() == 0)
    letter(pg, 'Д')
    check('spelling types letter', pg.evaluate('tyText') == 'Я хочу до д')
    pg.click('#tyFirstBtn')
    letter(pg, 'О')
    check('started word continues', pg.inner_text('.tyflp') == 'ДО…')
    w4 = pg.eval_on_selector_all('.tyflw .wd', 'e=>e.map(x=>x.textContent)')
    pg.click('.tyflw .wd >> nth=0')
    t = pg.evaluate('tyText')
    check('word completes started word', t == 'Я хочу до ' + w4[0] + ' ' and w4[0].startswith('до'), (t, w4[:3]))
    # 123 без «…», запятая в 123
    pg.click('.tykb .fn')
    check('digits without dots', pg.locator('.tykb .lt .dots').count() == 0 and pg.locator('.tykb .lt:text-is(",")').count() >= 1)
    pg.click('.tykb .fn')
    check('no errors first', not errs, errs)
    c.close()

    # онлайн-поиск в списке (после двух букв)
    c, pg, errs = page(b, {'profile': 'words', 'wordOnline': True})
    pg.route('**/*.wiktionary.org/**', lambda r: r.fulfill(status=200, content_type='application/json', body=json.dumps({'query': {'prefixsearch': [{'title': 'мнемоніка'}], 'search': []}})))
    pg.click('#typeBtn'); letter(pg, 'М')
    check('no online for 1 letter', pg.locator('.tyfl button:has-text("🌐")').count() == 0)
    pg.click('.tyfln .chip:text-is("МН")')
    pg.click('.tyfl button:has-text("🌐")'); pg.wait_for_timeout(300)
    pg.click('.tyfl .wd:has-text("мнемоніка")')
    check('online word picked', pg.evaluate('tyText') == 'Мнемоніка ')
    check('no errors online', not errs, errs)
    c.close()

    # 3. Черновик прежней «Азбуки» переходит в «Писать»; запомненный экран «Азбука» открывает «Писать»
    c, pg, errs = page(b, {'profile': 'words', 'resume': True, 'resumeDef': 1}, extra="if(!localStorage.getItem('x')){localStorage.setItem('x',1);localStorage.setItem('mv.draft.uk',JSON.stringify({ty:'',abc:['Я','хочу']}));localStorage.setItem('mv.lastScr',JSON.stringify({v:'abc'}))}")
    check('abc draft migrated', pg.evaluate('tyText') == 'Я хочу ', pg.evaluate('tyText'))
    check('abc screen -> Type', pg.locator('#tyBox').count() == 1)
    pg.wait_for_timeout(1200)
    check('draft saved without abc', json.loads(pg.evaluate("localStorage.getItem('mv.draft.uk')")) == {'ty': 'Я хочу ', 'abc': []})
    c.close()

    # 4. По буквам с помощником
    for lang in ['uk', 'ru', 'en']:
        c, pg, errs = page(b, {'profile': 'words'}, lang)
        rows = pg.evaluate(f"PB_ROWS.{lang}.join('')")
        alpha = pg.evaluate(f"ALPHA_FULL.{lang}")
        check(f'rows cover alphabet {lang}', sorted(rows) == sorted(alpha), (sorted(set(alpha) - set(rows)), sorted(set(rows) - set(alpha))))
        check(f'rows unique {lang}', len(set(rows)) == len(rows))
        c.close()
    c, pg, errs = page(b, {'profile': 'words'})
    pg.click('#abcBtn'); pg.wait_for_timeout(100)
    check('quick bar hidden for helper', not pg.is_visible('#quick'))
    check('empty text: starts with phrases', pg.inner_text('#pbQ') == '📋 Готові фрази?')
    pg.click('#pbNo')
    check('then rows', pg.inner_text('#pbQ') == 'О А Н І И Т ?')
    check('asked aloud', SP(pg)[-1] == 'О, А, Н, І, И, Т?', SP(pg)[-1:])
    pg.click('#pbYes')
    check('row level', pg.inner_text('#pbQ') == 'О ?' and SP(pg)[-1] == 'О?')
    pg.click('#pbNo'); pg.click('#pbNo'); pg.click('#pbNo')
    check('letter І', pg.inner_text('#pbQ') == 'І ?')
    pg.click('#pbNo'); pg.click('#pbNo'); pg.click('#pbNo')
    check('row wraps', pg.inner_text('#pbQ') == 'О ?')
    for _ in range(6): pg.click('#pbNo')
    check('two rounds -> back to rows', pg.evaluate('PBS.lvl') == 'top' and pg.inner_text('#pbQ') == 'О А Н І И Т ?')
    # выбрать «Я»: строка 3 («Д У М П Я З»), буква 5
    pg.click('#pbNo'); pg.click('#pbNo')
    check('third row', pg.inner_text('#pbQ') == 'Д У М П Я З ?')
    pg.click('#pbYes'); [pg.click('#pbNo') for _ in range(4)]; pg.click('#pbYes')
    check('letter typed', pg.evaluate('tyText') == 'Я')
    check('words offered first', pg.evaluate("PBS.lvl==='top'") and pg.inner_text('#pbQ').startswith('«'))
    pg.click('#pbYes')
    check('word accepted', pg.evaluate('tyText').startswith('Я') and pg.evaluate('tyText').endswith(' ') and len(pg.evaluate('tyText')) > 2, pg.evaluate('tyText'))
    t1 = pg.evaluate('tyText')
    # «↩ Выше», прямое нажатие буквы, действия
    pg.click('.pbrow >> nth=1 >> .pbl >> nth=0')
    check('direct tap letter', pg.evaluate('tyText') == t1 + 'в')
    items = pg.evaluate("pbItems().map(x=>x.k)")
    check('act last', items[-1] == 'act')
    pg.evaluate("PBS.i=pbItems().length-1;renderPb()")
    pg.click('#pbYes')
    check('act level', pg.inner_text('#pbQ').startswith('␣'))
    pg.click('#pbNo')
    check('delete item', pg.inner_text('#pbQ').startswith('⌫'))
    pg.click('#pbYes')
    check('deleted letter', pg.evaluate('tyText') == t1)
    pg.evaluate("PBS.i=pbItems().length-1;renderPb()"); pg.click('#pbYes'); pg.click('.pbsub .tyb >> nth=0')
    check('up returns to top', pg.evaluate("PBS.lvl") == 'top')
    pg.evaluate("PBS.i=pbItems().length-1;renderPb()"); pg.click('#pbYes'); pg.click('#pbNo'); pg.click('#pbNo')
    check('say item', pg.inner_text('#pbQ').startswith('🔊'))
    pg.click('#pbYes'); pg.wait_for_timeout(100)
    check('phrase said', pg.locator('#ov .said').count() == 1 and pg.evaluate('tyText') == '')
    pg.click('#ov .ans.yes')
    check('back on pb after said', pg.evaluate('pbOn'))
    # голос выключается
    pg.click('.pbsub .tyb >> nth=1')
    n0 = len(SP(pg)); pg.click('#pbNo')
    check('voice off', not pg.evaluate('settings.pbVoice') and len(SP(pg)) == n0)
    # задержка и сканирование не мешают помощнику
    pg.evaluate("settings.selMode='scan';scanApply()"); pg.wait_for_timeout(2300)
    check('no scan on pb', pg.locator('.scanrow,.scanhi').count() == 0)
    q0 = pg.inner_text('#pbQ'); pg.click('#pbNo')
    check('helper taps work in scan mode', pg.inner_text('#pbQ') != q0)
    pg.evaluate("settings.selMode='dwell';scanApply()")
    q0 = pg.inner_text('#pbQ'); pg.click('#pbNo')
    check('helper taps work in dwell mode', pg.inner_text('#pbQ') != q0)
    pg.evaluate("settings.selMode='tap';scanApply()")
    # «Назад»: уровень выше, затем выход; запуск с последнего экрана
    pg.evaluate("PBS.i=1;renderPb()"); pg.click('#pbYes')
    pg.evaluate('appBack()')
    check('back -> rows', pg.evaluate("PBS.lvl") == 'top' and pg.evaluate('pbOn'))
    pg.reload(); pg.wait_for_timeout(400)
    check('resume on pb', pg.evaluate('pbOn') and pg.locator('#pbQ').count() == 1)
    pg.evaluate('appBack()')
    check('back leaves pb', not pg.evaluate('pbOn') and pg.locator('.mvhome').count() == 1)
    pg.goto(URL + '?open=pb'); pg.wait_for_timeout(300)
    check('shortcut ?open=pb', pg.evaluate('pbOn'))
    check('help ctx pb', (pg.click('#helpBtn'), pg.locator('#help details.hi[open]').count())[1] == 6)
    pg.click('#help .helphead button')
    check('no errors pb', not errs, errs)
    c.close()
    # готовые фразы на «По буквам»: «Мои фразы», темы плиток → фразы
    for lv in ['L2', 'L5']:
        c, pg, errs = page(b, {'profile': 'words', 'level': lv}, extra="if(!localStorage.getItem('mv.myph.uk'))localStorage.setItem('mv.myph.uk',JSON.stringify(['Я вас люблю']));")
        pg.click('#abcBtn'); pg.wait_for_timeout(100)
        check(f'phrases first when empty {lv}', pg.inner_text('#pbQ') == '📋 Готові фрази?' and SP(pg)[-1] == 'Готові фрази?', pg.inner_text('#pbQ'))
        pg.click('#pbYes')
        check(f'my phrases offered first {lv}', pg.inner_text('#pbQ') == '📃 Мої фрази?')
        check(f'list instead of letters {lv}', pg.locator('.pbboard .pbli').count() == pg.evaluate('tree.length') + 1 and pg.locator('.pbl').count() == 0)
        pg.click('#pbYes')
        check(f'my phrase asked {lv}', pg.inner_text('#pbQ') == 'Я вас люблю?')
        pg.click('#pbYes'); pg.wait_for_timeout(100)
        check(f'my phrase said {lv}', 'Я вас люблю' in SP(pg) and pg.locator('#ov .said').count() == 1)
        pg.click('#ov .ans.yes')
        check(f'back to top {lv}', pg.evaluate('PBS.lvl') == 'top')
        # тема → (подтема) → фраза
        pg.click('#pbYes'); pg.click('#pbNo')
        topic = pg.evaluate("tree[0]")
        check(f'first topic {lv}', pg.inner_text('#pbQ').endswith('…?') and pg.evaluate("t(tree[0].l)") in pg.inner_text('#pbQ'))
        pg.click('#pbYes')
        depth = 1
        while pg.evaluate("PBS.lvl") == 'ph' and pg.inner_text('#pbQ').endswith('…?') and depth < 6:
            pg.click('#pbYes'); depth += 1
        q = pg.inner_text('#pbQ')
        n0 = len(SP(pg))
        check(f'leaf phrase asked {lv}', pg.evaluate("PBS.lvl") == 'ph' and not q.endswith('…?'), q)
        pg.click('#pbYes'); pg.wait_for_timeout(150)
        check(f'tile phrase said {lv}', pg.locator('#ov .said').count() == 1 and len(SP(pg)) > n0, SP(pg)[-2:])
        check(f'pick recorded {lv}', pg.evaluate("Object.keys(JSON.parse(localStorage.getItem('mv.use')||'{}')).length") >= 1)
        pg.click('#ov .ans.yes')
        # «Выше» по уровням и прямое нажатие в списке
        pg.click('#pbYes'); pg.click('#pbNo'); pg.click('#pbYes')
        check(f'inside topic {lv}', len(pg.evaluate("PBS.stack")) == 1)
        pg.evaluate('appBack()')
        check(f'up to topics {lv}', pg.evaluate("PBS.lvl") == 'ph' and len(pg.evaluate("PBS.stack")) == 0 and pg.evaluate("PBS.i") == 1)
        pg.evaluate('appBack()')
        check(f'up to top on phrases item {lv}', pg.evaluate("PBS.lvl") == 'top' and pg.inner_text('#pbQ') == '📋 Готові фрази?')
        pg.click('#pbYes'); pg.click('.pbboard .pbli >> nth=2')
        check(f'direct tap topic {lv}', len(pg.evaluate("PBS.stack")) == 1 and pg.evaluate("PBS.stack[0].id") == pg.evaluate("tree[1].id"))
        check(f'no errors phrases {lv}', not errs, errs)
        c.close()
    # без «Моих фраз» — сразу темы; при начатом слове сначала слова
    c, pg, errs = page(b, {'profile': 'words'})
    pg.click('#abcBtn'); pg.click('#pbYes')
    check('topics without my phrases', pg.inner_text('#pbQ').endswith('…?'))
    pg.evaluate("tyText='Я хо';pbTop()")
    check('words before phrases when typing', pg.inner_text('#pbQ').startswith('«'))
    check('phrases item after words', pg.evaluate("pbItems().findIndex(x=>x.k==='ph')") == pg.evaluate("pbItems().filter(x=>x.k==='w').length"))
    c.close()

    # обучение на «По буквам»
    c, pg, errs = page(b, {'profile': 'words'}, extra="localStorage.setItem('mv.tour.seen',JSON.stringify({home:1,tiles:1,show:1,type:1}));")
    pg.click('#abcBtn'); pg.wait_for_timeout(900)
    check('tour offered on pb', pg.locator('#tourBox').count() == 1)
    pg.click('#tourBox .go'); pg.wait_for_timeout(150)
    steps = 0
    for _ in range(6):
        if not pg.locator('#tourBox').count(): break
        steps += 1; pg.click('#tourBox .go'); pg.wait_for_timeout(120)
    check('tour pb steps', steps == 4, steps)
    check('no errors tour', not errs, errs)
    c.close()

    # 5. Вёрстка
    for (w, hgt) in [(360, 640), (313, 556), (277, 492), (800, 1280)]:
        for lang in ['uk', 'ru', 'en']:
            c, pg, errs = page(b, {'profile': 'words'}, lang, w, hgt)
            tag = f'{w}x{hgt} {lang}'
            fit = "document.documentElement.scrollWidth<=innerWidth+1"
            pg.click('#typeBtn')
            check(f'type fits {tag}', pg.evaluate(fit))
            check(f'action buttons fit {tag}', pg.evaluate("[...document.querySelectorAll('#tyAct .tyb')].every(b=>b.getBoundingClientRect().right<=innerWidth+1&&b.scrollWidth<=b.clientWidth+2)"))
            check(f'bottom row fits {tag}', pg.evaluate("[...document.querySelectorAll('.tykb .tybot .lt')].every(b=>{const r=b.getBoundingClientRect();return r.right<=innerWidth+1&&r.width>=30&&b.scrollWidth<=b.clientWidth+2})"))
            pg.click('.tykb .letters .lt >> nth=2')
            check(f'word list fits {tag}', pg.evaluate(fit) and pg.evaluate("[...document.querySelectorAll('.tyflw .wd')].every(b=>b.getBoundingClientRect().right<=innerWidth+1)"))
            check(f'word list header visible {tag}', pg.evaluate("(()=>{const r=$('.tyflh').getBoundingClientRect(),h=$('.tyhead').getBoundingClientRect();return r.top>=h.bottom-1})()"))
            pg.click('#abcBtn')
            check(f'pb fits {tag}', pg.evaluate(fit))
            check(f'pb yes/no visible {tag}', pg.evaluate("(()=>{const m=$('#main').getBoundingClientRect();return [...document.querySelectorAll('.pbb')].every(b=>{const r=b.getBoundingClientRect();return r.bottom<=m.bottom&&r.height>=60})})()"))
            check(f'pb letters fit {tag}', pg.evaluate("[...document.querySelectorAll('.pbl')].every(b=>{const r=b.getBoundingClientRect();return r.right<=innerWidth+1&&r.width>=30})"))
            pg.click('#pbYes')
            check(f'phrase list fits {tag}', pg.evaluate(fit) and pg.evaluate("[...document.querySelectorAll('.pbli')].every(b=>b.getBoundingClientRect().right<=innerWidth+1&&b.scrollWidth<=b.clientWidth+2)"))
            pg.evaluate('appBack()'); pg.click('#pbNo'); pg.click('#pbYes')
            check(f'current row visible {tag}', pg.evaluate("(()=>{const m=$('#main').getBoundingClientRect(),r=document.querySelector('.pbrow.cur').getBoundingClientRect();return r.top>=m.top-1&&r.bottom<=m.bottom+1})()"))
            pg.click('#home')
            check(f'home header fits {tag}', pg.evaluate("['#home','#typeBtn','#abcBtn','#micBtn','#settingsBtn','#helpBtn','#gear'].every(s=>{const e=document.querySelector(s),r=e.getBoundingClientRect();return r.right<=innerWidth+1&&r.width>0&&e.scrollWidth<=e.clientWidth+2})"))
            pg.screenshot(path=f'/tmp/v7home_{w}_{lang}.png')
            check(f'no errors layout {tag}', not errs, errs)
            c.close()
    b.close()
print(f'OK {OK}  FAIL {FAIL}')
sys.exit(1 if FAIL else 0)
