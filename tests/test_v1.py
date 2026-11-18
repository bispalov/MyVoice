#!/usr/bin/env python3
"""Тесты «Мій голос» v1 (Playwright, Chromium).
Запуск: из корня сайта, где рядом лежат папки MyVoice/ (и при желании Govorim/):
  python3 -m http.server 8765   # в отдельном окне
  python3 MyVoice/tests/test_v1.py
Подменяются speechSynthesis (записываются произнесённые фразы) и window.open; service worker отключён."""
import json, sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765/MyVoice/'
URL = BASE + 'index.html'
OK = FAIL = 0
def check(name, cond, extra=''):
    global OK, FAIL
    if cond: OK += 1
    else:
        FAIL += 1; print('FAIL:', name, extra)

INIT = """
if(!localStorage.getItem('mv.tour.seen'))localStorage.setItem('mv.tour.seen',JSON.stringify({home:1,tiles:1,hear:1,show:1,abc:1,type:1}));
window.__spoken=[];window.__opened=[];
Object.defineProperty(window,'speechSynthesis',{value:{speak:u=>{window.__spoken.push(u.text);setTimeout(()=>{u.onend&&u.onend()},5)},cancel(){},getVoices:()=>[],speaking:false,pending:false,paused:false,onvoiceschanged:null}});
window.open=(u)=>{window.__opened.push(u);return {}};
"""
def spoken(pg): return pg.evaluate('window.__spoken')
def clear_spoken(pg): pg.evaluate('window.__spoken.length=0')

def new_page(b, w=360, hgt=640, lang='uk', settings=None, extra=''):
    c = b.new_context(viewport={'width': w, 'height': hgt}, service_workers='block')
    pre = f"if(!localStorage.getItem('mv.lang'))localStorage.setItem('mv.lang','{lang}');"
    settings = dict({'profile': 'words', 'tyFirst': False}, **(settings or {}))   # v7: в «Писать» набор по буквам   # назначение задано — без вопроса при первом запуске
    pre += f"if(!localStorage.getItem('mv.settings'))localStorage.setItem('mv.settings',{json.dumps(json.dumps(settings))});"
    c.add_init_script(INIT + pre + extra)
    pg = c.new_page(); pg.set_default_timeout(5000)
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(400)
    return c, pg, errs

def inside(pg, sel):
    """Элемент целиком в пределах экрана по ширине и не вылезает за свой контейнер."""
    return pg.evaluate("""s=>{const e=document.querySelector(s);if(!e)return false;const r=e.getBoundingClientRect();return r.left>=-1&&r.right<=innerWidth+1&&r.width>0}""", sel)

def no_hscroll(pg):
    return pg.evaluate("document.documentElement.scrollWidth<=innerWidth+1")

with sync_playwright() as p:
    b = p.chromium.launch()

    # ---------- 1. Основное: название, шапка, нет вкладки «Говорю я» ----------
    for lang, title in [('uk', 'Мій голос'), ('ru', 'Мой голос'), ('en', 'My Voice')]:
        c, pg, errs = new_page(b, lang=lang)
        check(f'title {lang}', pg.title() == title, pg.title())
        check(f'h1 {lang}', pg.inner_text('#ttl') == title)
        check(f'home row {lang}', pg.locator('.mvhome .mvh').count() == 3)
        check(f'quick bar {lang}', pg.locator('#quick .qb').count() == 5)
        pg.click('#micBtn'); pg.wait_for_timeout(150)
        check(f'no tabs on 🎤 {lang}', pg.locator('#main .tabs').count() == 0 and pg.locator('#micGo').count() == 0)
        check(f'show tab {lang}', pg.locator('#showMic').count() == 1 and pg.locator('#showClip').count() == 1)
        check(f'no errors {lang}', not errs, errs)
        c.close()

    # ---------- 2. Писать: подсказки, выбор, «Сказать», учёба, «Мои фразы» ----------
    c, pg, errs = new_page(b)
    pg.click('#typeBtn'); pg.wait_for_timeout(200)
    check('type screen', pg.locator('#tyBox').count() == 1 and pg.locator('.tykb .letters .lt').count() >= 33)
    check('body.typing', pg.evaluate("document.body.classList.contains('typing')&&!document.body.classList.contains('at-home')"))
    check('say disabled empty', pg.is_disabled('#tySay'))
    for ch in ['Я', ' ', 'Х', 'О']:
        pg.click('.tykb .sp' if ch == ' ' else f'.tykb .letters .lt:text-is("{ch}")')
    check('typed text', pg.inner_text('#tyBox').strip() == 'Я хо', pg.inner_text('#tyBox'))
    sug = pg.eval_on_selector_all('#tySug .tyw', 'e=>e.map(x=>x.textContent)')
    check('suggest хочу', 'хочу' in sug, sug)
    pg.click('#tySug .tyw:text-is("хочу")')
    check('picked word', pg.inner_text('#tyBox').strip() == 'Я хочу', pg.inner_text('#tyBox'))
    sug2 = pg.eval_on_selector_all('#tySug .tyw', 'e=>e.map(x=>x.textContent)')
    check('next word after хочу', len(sug2) >= 3 and any(w in sug2 for w in ['пити', 'їсти', 'спати', 'додому']), sug2)
    pg.click('#tySug .tyw >> nth=0'); w1 = sug2[0]
    check('next word inserted', pg.inner_text('#tyBox').strip() == 'Я хочу ' + w1)
    # стереть слово и вернуть
    pg.click('#tyAct .tyb >> nth=0')
    check('delete word', pg.inner_text('#tyBox').strip() == 'Я хочу', pg.inner_text('#tyBox'))
    pg.click('#tyAct .tyb.un')
    check('undo word', pg.inner_text('#tyBox').strip() == 'Я хочу ' + w1)
    # сказать
    clear_spoken(pg)
    pg.click('#tySay'); pg.wait_for_timeout(100)
    check('spoken typed', ('Я хочу ' + w1) in spoken(pg), spoken(pg))
    check('said window', pg.locator('#ov .said').count() == 1)
    check('typed cleared', pg.evaluate('tyText') == '')
    check('learned', pg.evaluate("(JSON.parse(localStorage.getItem('mv.tw.uk'))||{w:{}}).w['хочу']>=1"))
    check('recent added', pg.evaluate("(JSON.parse(localStorage.getItem('mv.recent.uk'))||[]).some(x=>x.s.startsWith('Я хочу'))"))
    pg.click('#ov .ans.yes')  # Готово
    pg.wait_for_timeout(100)
    check('back on type after done', pg.locator('#tyBox').count() == 1)
    # учёба: после «Я» в начале подсказка из личной истории
    pg.click('.tykb .letters .lt:text-is("Я")'); pg.click('.tykb .sp')
    sug3 = pg.eval_on_selector_all('#tySug .tyw', 'e=>e.map(x=>x.textContent)')
    check('learned bigram first', sug3[:1] == ['хочу'], sug3)
    # сохранить в «Мои фразы»
    pg.click('#tySug .tyw:text-is("хочу")')
    pg.click('#tyAct .tyb.sv'); pg.wait_for_timeout(50)
    check('saved my phrase', pg.evaluate("JSON.parse(localStorage.getItem('mv.myph.uk'))[0]") == 'Я хочу')
    check('toast', pg.locator('#mvToast').count() == 1)
    pg.click('#tyAct .tyb.sv'); pg.wait_for_timeout(50)
    check('no duplicate', pg.evaluate("JSON.parse(localStorage.getItem('mv.myph.uk')).length") == 1)
    pg.click('#tyMyBtn')
    check('my panel', pg.locator('.tymy .tymyb').count() == 1 and pg.locator('.tykb').count() == 0)
    clear_spoken(pg)
    pg.click('.tymy .tymyb'); pg.wait_for_timeout(50)
    check('my phrase spoken at once', spoken(pg) == ['Я хочу'], spoken(pg))
    pg.click('#ov .ans.yes')
    # правка списка: удалить
    pg.click('.tymy .sec .mini'); pg.click('.tymy .dl')
    check('my phrase deleted', pg.evaluate("JSON.parse(localStorage.getItem('mv.myph.uk')).length") == 0)
    # ↩ закрывает список, затем выходит из экрана; текст сохраняется
    pg.click('#bar button[data-k=back]')
    check('back closes my list', pg.locator('.tykb').count() == 1)
    pg.click('#bar button[data-k=back]')
    check('back leaves type', pg.locator('.mvhome').count() == 1)
    pg.click('#typeBtn')
    check('text kept', pg.evaluate('tyText').strip() == 'Я хочу')
    # заглавная после точки, знаки
    pg.click('#tyAct .tyb.cl')
    for ch in ['Т', 'А', '.', 'Т']:
        pg.click(f'.tykb .lt:text-is("{ch}")')
    check('capital after dot', pg.evaluate('tyText') == 'Та. Т', pg.evaluate('tyText'))
    # раскладка ЙЦУКЕН и 123
    pg.click('#tyAct .tyb.op'); pg.click('.tyopts .tyb >> nth=0')
    check('qwerty layout', pg.locator('.tykb .rows .tyrow').count() == 3 and pg.evaluate('settings.kbLayout') == 'qw')
    pg.click('.tykb .fn')
    check('digits', pg.locator('.tykb .lt:text-is("7")').count() == 1)
    pg.click('.tykb .fn')
    # клавиатура телефона
    pg.click('#tyAct .tyb.op'); pg.click('.tyopts .tyb:has-text("📱")')
    check('system keyboard textarea', pg.locator('#tyIn').count() == 1 and pg.locator('.tykb').count() == 0)
    pg.fill('#tyIn', 'я хо')
    check('textarea suggestions', 'хочу' in pg.eval_on_selector_all('#tySug .tyw', 'e=>e.map(x=>x.textContent)'))
    pg.click('#tyAct .tyb.op'); pg.click('.tyopts .tyb:has-text("⌨️")')
    check('back to app keyboard', pg.locator('.tykb').count() == 1)
    check('no errors type', not errs, errs)
    c.close()

    # ---------- 3. Быстрые реплики, autoShow, «Сказано» ----------
    c, pg, errs = new_page(b)
    clear_spoken(pg)
    pg.click('#quick .qb >> nth=0'); pg.wait_for_timeout(50)
    check('quick reply spoken', spoken(pg) == ['Зачекайте, я пишу…'], spoken(pg))
    check('quick no window', pg.locator('#ov .said').count() == 0 and pg.locator('#bigShow').count() == 0)
    pg.evaluate("settings.autoShow=true")
    pg.click('#quick .qb >> nth=1')
    check('autoShow quick', pg.locator('#bigShow').count() == 1)
    pg.click('#bigShow .row button >> nth=1')
    pg.click('#typeBtn'); pg.click('.tykb .letters .lt:text-is("Т")'); pg.click('.tykb .letters .lt:text-is("А")')
    pg.click('#tySay')
    check('autoShow say', pg.locator('#bigShow').count() == 1 and pg.locator('#ov .said').count() == 1)
    pg.evaluate('appBack()')
    check('back closes bigShow first', pg.locator('#bigShow').count() == 0 and pg.locator('#ov .said').count() == 1)
    pg.evaluate("settings.quickBar=false;drawQuick()")
    check('quick bar off', pg.evaluate("document.querySelector('#quick').hidden"))
    check('no errors quick', not errs, errs)
    c.close()

    # ---------- 4. Да / Нет на весь экран, шкалы ----------
    c, pg, errs = new_page(b)
    pg.click('.mvhome .mvh >> nth=0')
    check('yn open', pg.locator('#yn .ynb').count() == 3)
    clear_spoken(pg)
    pg.click('#yn .ynb.yes'); pg.click('#yn .ynb.no'); pg.click('#yn .ynb.dk')
    check('yn spoken', spoken(pg) == ['Так', 'Ні', 'Не знаю'], spoken(pg))
    pg.click('#yn .yntab >> nth=1')
    check('pain scale', pg.locator('#yn .scb').count() == 11)
    clear_spoken(pg); pg.click('#yn .scb >> nth=7')
    check('pain spoken', spoken(pg) == ['Мій біль — 7 з 10'], spoken(pg))
    pg.click('#yn .yntab >> nth=2'); clear_spoken(pg); pg.click('#yn .scb >> nth=10')
    check('well spoken', spoken(pg) == ['Моє самопочуття — 10 з 10'], spoken(pg))
    pg.evaluate("appBack()")
    check('back closes yn', pg.locator('#yn').count() == 0)
    check('no errors yn', not errs, errs)
    c.close()

    # ---------- 5. Экстренная карточка ----------
    st = {'card': {'name': 'Олена', 'main': '', 'dx': 'Афазія після інсульту', 'meds': 'Аспірин', 'allergy': '', 'notes': '', 'sos': True},
          'sos': [{'n': 'Син', 't': '+380501112233'}, {'n': '', 't': ''}]}
    c, pg, errs = new_page(b, settings=st)
    pg.click('.mvhome .mvh >> nth=2')
    check('card open', pg.locator('#card').count() == 1)
    txt = pg.inner_text('#card')
    check('card fields', 'Олена' in txt and 'Афазія' in txt and 'Аспірин' in txt and 'Я не можу говорити' in txt, txt[:200])
    check('card no empty allergy', 'Алергія' not in txt)
    check('card phone', pg.get_attribute('#card .cdtel', 'href') == 'tel:+380501112233')
    clear_spoken(pg); pg.click('#card .cdb >> nth=0')
    check('card read', spoken(pg) and 'Олена' in spoken(pg)[0] and '🪪' not in spoken(pg)[0], spoken(pg))
    pg.evaluate('goBack()')
    check('card closed', pg.locator('#card').count() == 0)
    # с экрана «Помощь»: сигнал замолкает
    pg.click('#bar button[data-k=help]'); pg.wait_for_timeout(50)
    check('help card button', pg.locator('#ov.red .cardbtn').count() == 1)
    pg.click('#ov.red .cardbtn')
    check('card over help, alarm stopped', pg.locator('#card').count() == 1 and pg.evaluate('tmr') is None)
    pg.evaluate('goBack()'); pg.evaluate('goBack()')
    check('help closed', pg.evaluate("ov.style.display") != 'flex')
    # настройки: группа карточки
    pg.click('#settingsBtn')
    check('card group', pg.locator('#sett .sg[data-g=card]').count() == 1)
    check('card summary filled', 'заповнена' in pg.inner_text('#sett .sg[data-g=card] .sgh'))
    pg.click('#sett .sg[data-g=card] .sgh')
    pg.fill('#setCardAllergy', 'пеніцилін')
    pg.click('#closeSettBtn')
    check('card saved', pg.evaluate("JSON.parse(localStorage.getItem('mv.settings')).card.allergy") == 'пеніцилін')
    # ярлык ?open=card
    pg.goto(URL + '?open=card'); pg.wait_for_timeout(300)
    check('shortcut card', pg.locator('#card').count() == 1 and 'пеніцилін' in pg.inner_text('#card'))
    check('shortcut url cleaned', '?open' not in pg.url)
    pg.goto(URL + '?open=type'); pg.wait_for_timeout(300)
    check('shortcut type', pg.locator('#tyBox').count() == 1)
    pg.goto(URL + '?open=yn'); pg.wait_for_timeout(300)
    check('shortcut yn', pg.locator('#yn').count() == 1)
    check('no errors card', not errs, errs)
    c.close()

    # ---------- 6. Нажатие задержкой ----------
    c, pg, errs = new_page(b, settings={'selMode': 'dwell', 'dwellMs': 800})
    check('dwell class', pg.evaluate("document.body.classList.contains('dwell')"))
    clear_spoken(pg)
    pg.click('#bar button[data-k=yes]'); pg.wait_for_timeout(100)
    check('dwell: short tap ignored', spoken(pg) == [], spoken(pg))
    box = pg.locator('#bar button[data-k=yes]').bounding_box()
    x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    pg.mouse.move(x, y); pg.mouse.down()
    pg.wait_for_timeout(300)
    check('dwell bar shown', pg.evaluate("document.querySelector('#bar button[data-k=yes]').classList.contains('holding')"))
    pg.mouse.move(x + 6, y + 4); pg.wait_for_timeout(250); pg.mouse.move(x - 5, y - 3)   # дрожание пальца
    pg.wait_for_timeout(450)
    check('dwell fired once despite tremor', spoken(pg).count('Так') == 1, spoken(pg))
    pg.wait_for_timeout(900)
    check('dwell no repeat while resting', spoken(pg).count('Так') == 1, spoken(pg))
    pg.mouse.up()
    # скольжение на другую кнопку
    clear_spoken(pg)
    pg.evaluate('closeOv()')
    nb = pg.locator('#bar button[data-k=no]').bounding_box()
    pg.mouse.move(x, y); pg.mouse.down(); pg.wait_for_timeout(300)
    pg.mouse.move(nb['x'] + nb['width'] / 2, nb['y'] + nb['height'] / 2, steps=3); pg.wait_for_timeout(950)
    pg.mouse.up()
    check('dwell follows finger', spoken(pg) == ['Ні'], spoken(pg))
    # настройки работают обычным касанием
    pg.evaluate('closeOv()')
    pg.click('#settingsBtn'); pg.wait_for_timeout(100)
    check('settings not by short tap in dwell', pg.evaluate("$('#sett').style.display") != 'block')
    sb = pg.locator('#settingsBtn').bounding_box()
    pg.mouse.move(sb['x'] + 20, sb['y'] + 20); pg.mouse.down(); pg.wait_for_timeout(1000); pg.mouse.up()
    check('settings open by dwell', pg.evaluate("$('#sett').style.display") == 'block')
    pg.click('#sett .sg[data-g=touch] .sgh')
    check('dwell select shown', pg.is_visible('#setDwell') and not pg.is_visible('#setScanKeys'))
    pg.click('#closeSettBtn')
    check('no errors dwell', not errs, errs)
    c.close()

    # ---------- 7. Сканирование ----------
    c, pg, errs = new_page(b, settings={'selMode': 'scan', 'scanMs': 1000, 'scanSound': False})
    pg.wait_for_timeout(500)
    check('scan row highlighted', pg.locator('.scanrow').count() >= 1)
    first = pg.evaluate("[...document.querySelectorAll('.scanrow')].map(e=>e.id||e.className)")
    check('first row is header', 'home' in first, first)
    pg.wait_for_timeout(1000)
    second = pg.evaluate("[...document.querySelectorAll('.scanrow')].map(e=>e.id)")
    check('scan advances', second != first and 'typeBtn' in second, second)
    # выбрать строку касанием любого места, затем кнопку «Писати»
    pg.mouse.click(180, 400)   # касание по плитке — не срабатывает, а выбирает строку
    check('row -> items', pg.locator('.scanhi').count() == 1 and pg.locator('.scanhi').get_attribute('id') == 'typeBtn')
    pg.mouse.click(180, 400)
    pg.wait_for_timeout(200)
    check('scan selected Type', pg.locator('#tyBox').count() == 1, pg.inner_text('#ttl'))
    # пауза в настройках: касание работает
    pg.evaluate("$('#settingsBtn').click()"); pg.wait_for_timeout(100)
    pg.wait_for_timeout(1100)
    check('scan paused in settings', pg.locator('.scanrow,.scanhi').count() == 0)
    pg.click('#sett .sg[data-g=touch] .sgh')
    check('scan options visible', pg.is_visible('#setScanKeys') and pg.is_visible('#setScanMs'))
    pg.select_option('#setScanKeys', '2')
    pg.click('#closeSettBtn'); pg.wait_for_timeout(300)
    # две кнопки: Пробел — дальше, Enter — выбрать
    r0 = pg.evaluate("[...document.querySelectorAll('.scanrow')].map(e=>e.id||e.className).join()")
    pg.wait_for_timeout(1300)
    r1 = pg.evaluate("[...document.querySelectorAll('.scanrow')].map(e=>e.id||e.className).join()")
    check('2-switch: no auto advance', r0 == r1 and r0 != '', (r0, r1))
    pg.keyboard.press('Space')
    r2 = pg.evaluate("[...document.querySelectorAll('.scanrow')].map(e=>e.id||e.className).join()")
    check('2-switch: space advances', r2 != r1, (r1, r2))
    # дойти до строки клавиатуры с буквой «А» и выбрать её
    for _ in range(12):
        if pg.evaluate("!!document.querySelector('.scanrow.lt')"): break
        pg.keyboard.press('Space')
    check('reached letter row', pg.evaluate("!!document.querySelector('.scanrow.lt')"))
    pg.keyboard.press('Enter')
    check('item level', pg.locator('.scanhi').count() == 1)
    letter = pg.evaluate("document.querySelector('.scanhi').textContent")
    pg.keyboard.press('Enter'); pg.wait_for_timeout(150)
    check('letter typed by switch', pg.evaluate('tyText') == letter, (letter, pg.evaluate('tyText')))
    # два круга без выбора — назад к строкам
    pg.keyboard.press('Enter')  # строка
    n = pg.evaluate("document.querySelectorAll('.scanrow').length")
    pg.keyboard.press('Enter')
    for _ in range(40):
        if pg.locator('.scanrow').count(): break
        pg.keyboard.press('Space')
    check('returns to rows after two rounds', pg.locator('.scanrow').count() >= 1)
    check('no errors scan', not errs, errs)
    c.close()

    # ---------- 8. Справка, обучение, настройки ----------
    for lang in ['uk', 'ru', 'en']:
        c, pg, errs = new_page(b, lang=lang)
        n = pg.evaluate("HELP_KEYS.length")
        lens = pg.evaluate("['uk','ru','en'].map(l=>U[l].helpDoc.s.length)")
        check(f'help keys {lang}', lens == [n, n, n], (n, lens))
        txt = pg.evaluate("U[uiL()].helpDoc.s.flat(2).join(' ')")
        bad = [w for w in ['Говорит человек', 'Говорить людина', 'Підказка за сказаним', 'Подсказка по сказанному', 'Suggestions from what was said', 'Говоримо разом —', 'Говорим вместе —'] if w in txt]
        check(f'help no old names {lang}', not bad, bad)
        pg.click('#helpBtn')
        check(f'help toc {lang}', pg.locator('#help details.hi').count() == n)
        pg.click('#help .helphead button')
        pg.click('#typeBtn'); pg.click('#helpBtn')
        check(f'help type ctx {lang}', pg.locator('#help details.hi[open]').count() == 10, pg.locator('#help details.hi[open]').count())
        pg.click('#help .helphead button')
        pg.click('#settingsBtn')
        check(f'settings opens type group {lang}', pg.evaluate("document.querySelector('#sett .sg.open').dataset.g") == 'type')
        groups = pg.evaluate("[...document.querySelectorAll('#sett .sg')].map(x=>x.dataset.g)")
        check(f'groups {lang}', groups == ['main', 'sos', 'card', 'voice', 'home', 'type', 'touch', 'mic', 'abc', 'net', 'data', 'about'], groups)
        sums = pg.evaluate("[...document.querySelectorAll('#sett .sg:not(.open) .sgs')].map(x=>x.textContent)")
        check(f'summaries {lang}', all(sums), sums)
        about = pg.inner_text('#aboutBox') if pg.is_visible('#aboutBox') else pg.evaluate("$('#aboutBox').textContent")
        check(f'about link {lang}', pg.evaluate("[...document.querySelectorAll('#aboutBox a')].some(a=>a.href.endsWith('/MyVoice'))"))
        pg.click('#closeSettBtn')
        check(f'no errors help {lang}', not errs, errs)
        c.close()

    # обучение на экране «Писать»
    c, pg, errs = new_page(b, extra="localStorage.setItem('mv.tour.seen',JSON.stringify({home:1,tiles:1,show:1,abc:1}));")
    pg.click('#typeBtn'); pg.wait_for_timeout(900)
    check('tour offered on type', pg.locator('#tourBox').count() == 1)
    pg.click('#tourBox .go'); pg.wait_for_timeout(200)
    steps = 0
    for _ in range(8):
        if not pg.locator('#tourBox').count(): break
        steps += 1
        pg.click('#tourBox .go'); pg.wait_for_timeout(120)
    check('tour steps type', steps >= 4, steps)
    check('tour ended', pg.locator('#tourBox').count() == 0)
    check('no errors tour', not errs, errs)
    c.close()
    c, pg, errs = new_page(b, extra="localStorage.setItem('mv.tour.seen',JSON.stringify({tiles:1,show:1,abc:1,type:1}));")
    pg.wait_for_timeout(900)
    pg.click('#tourBox .go'); pg.wait_for_timeout(150)
    seen = []
    for _ in range(14):
        if not pg.locator('#tourBox').count(): break
        seen.append(pg.evaluate("TOUR&&TOUR.steps[TOUR.i]?TOUR.steps[TOUR.i].t:''"))
        pg.click('#tourBox .go'); pg.wait_for_timeout(120)
    check('home tour has new steps', all(k in seen for k in ['h_row', 'h_quick', 'h_type', 'h_mic']), seen)
    c.close()

    # ---------- 9. Запуск с последнего экрана и «что открывать при запуске» ----------
    c, pg, errs = new_page(b, settings={'resume': True})
    pg.click('#typeBtn'); pg.reload(); pg.wait_for_timeout(300)
    check('resume type', pg.locator('#tyBox').count() == 1)
    c.close()
    c, pg, errs = new_page(b, settings={'start': 'type'})
    check('start type', pg.locator('#tyBox').count() == 1)
    pg.click('#home')
    check('home from type', pg.locator('.mvhome').count() == 1)
    c.close()

    # ---------- 10. Резервная копия: своё имя, копия Govorim принимается ----------
    c, pg, errs = new_page(b)
    with pg.expect_download() as d:
        pg.evaluate("$('#backupBtn').click()")
    data = json.loads(open(d.value.path(), encoding='utf8').read())
    check('backup app', data['app'] == 'myvoice' and d.value.suggested_filename.startswith('myvoice-backup-'))
    check('backup keys mv.', all(k.startswith('mv.') for k in data['data']), list(data['data'])[:5])
    gv = {'app': 'govorim', 'version': 70, 'data': {'aac.settings': json.dumps({'level': 'L3', 'gender': 'm'}), 'aac.lang': 'ru'}}
    open('/tmp/gv_backup.json', 'w').write(json.dumps(gv))
    pg.on('dialog', lambda dl: dl.accept())
    pg.set_input_files('#restoreFile', '/tmp/gv_backup.json'); pg.wait_for_timeout(800)
    check('govorim backup restored', pg.evaluate("JSON.parse(localStorage.getItem('mv.settings')).level") == 'L3' and pg.evaluate("localStorage.getItem('mv.lang')") == 'ru')
    check('no aac keys', pg.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('aac.')).length") == 0)
    c.close()

    # ---------- 11. Вёрстка: все экраны при 360×640, 313×556, 277×492, 800×1280 ----------
    for (w, hgt) in [(360, 640), (313, 556), (277, 492), (800, 1280)]:
        for lang in ['uk', 'ru', 'en']:
            c, pg, errs = new_page(b, w, hgt, lang=lang)
            tag = f'{w}x{hgt} {lang}'
            check(f'home no hscroll {tag}', no_hscroll(pg))
            check(f'header buttons inside {tag}', all(inside(pg, s) for s in ['#home', '#micBtn', '#settingsBtn', '#helpBtn', '#gear', '#typeBtn', '#abcBtn']))
            check(f'home row inside {tag}', inside(pg, '.mvhome'))
            hb = pg.evaluate("[...document.querySelectorAll('.mvh')].every(b=>b.scrollWidth<=b.clientWidth+1)")
            check(f'home row labels fit {tag}', hb)
            pg.click('#typeBtn')
            check(f'type no hscroll {tag}', no_hscroll(pg))
            vis = pg.evaluate("""(()=>{const m=$('#main').getBoundingClientRect();const r=$('#tyBox').getBoundingClientRect();const s=$('#tySay').getBoundingClientRect();return r.top>=m.top-1&&r.bottom<=m.bottom&&s.right<=innerWidth+1})()""")
            check(f'type box visible {tag}', vis)
            pg.evaluate("$('#main').scrollTop=9999"); pg.wait_for_timeout(50)
            vis2 = pg.evaluate("""(()=>{const m=$('#main').getBoundingClientRect();const r=$('#tyBox').getBoundingClientRect();return r.top>=m.top-1&&r.bottom<=m.bottom})()""")
            check(f'type box stays (sticky) {tag}', vis2)
            act = pg.evaluate("[...document.querySelectorAll('#tyAct .tyb')].every(b=>b.getBoundingClientRect().right<=innerWidth+1&&b.scrollWidth<=b.clientWidth+2)")
            check(f'type actions fit {tag}', act)
            keys = pg.evaluate("[...document.querySelectorAll('.tykb .lt')].map(b=>b.getBoundingClientRect()).every(r=>r.width>=30&&r.height>=34&&r.right<=innerWidth+1)")
            check(f'keys size {tag}', keys)
            if (w, hgt) == (360, 640):
                allk = pg.evaluate("(()=>{const m=$('#main').getBoundingClientRect();return [...document.querySelectorAll('.tykb .lt')].every(b=>{const r=b.getBoundingClientRect();return r.bottom<=m.bottom+1})})()")
                pg.evaluate("$('#main').scrollTop=0")
                allk = pg.evaluate("(()=>{const m=$('#main').getBoundingClientRect();return [...document.querySelectorAll('.tykb .lt')].every(b=>{const r=b.getBoundingClientRect();return r.bottom<=m.bottom+1&&r.top>=m.top-1})})()")
                check(f'whole keyboard fits 360x640 {lang}', allk)
            pg.screenshot(path=f'/tmp/shot_type_{w}_{lang}.png')
            pg.click('#home'); pg.click('.mvhome .mvh >> nth=0')
            yb = pg.evaluate("[...document.querySelectorAll('#yn .ynb,#yn .yntab')].every(b=>{const r=b.getBoundingClientRect();return r.right<=innerWidth+1&&r.bottom<=innerHeight+1&&r.height>=50})")
            check(f'yn fits {tag}', yb)
            pg.click('#yn .yntab >> nth=1')
            sc = pg.evaluate("(()=>{const bs=[...document.querySelectorAll('#yn .scb')];return bs.every(b=>b.getBoundingClientRect().right<=innerWidth+1&&b.getBoundingClientRect().height>=50)})()")
            check(f'scale fits {tag}', sc)
            pg.screenshot(path=f'/tmp/shot_scale_{w}_{lang}.png')
            pg.click('#yn .ynx')
            pg.evaluate("settings.card={name:'Олександра Петренко',main:'',dx:'Тяжка афазія після інсульту',meds:'Аспірин, бісопролол',allergy:'Пеніцилін',notes:'',sos:true};settings.sos=[{n:'Дочка',t:'+380501112233'},{n:'',t:''}]")
            pg.click('.mvhome .mvh >> nth=2')
            cd = pg.evaluate("[...document.querySelectorAll('#card .cdb')].every(b=>{const r=b.getBoundingClientRect();return r.right<=innerWidth+1&&r.bottom<=innerHeight+1})")
            check(f'card fits {tag}', cd)
            pg.screenshot(path=f'/tmp/shot_card_{w}_{lang}.png')
            pg.evaluate('cardClose()')
            pg.click('#settingsBtn')
            for g in ['card', 'type', 'touch']:
                pg.click(f'#sett .sg[data-g={g}] .sgh')
                ok = pg.evaluate("[...document.querySelectorAll('#sett .sg.open .sgb > *')].filter(e=>e.offsetParent).every(e=>e.getBoundingClientRect().right<=innerWidth+1)")
                check(f'settings {g} fits {tag}', ok)
            pg.select_option('#setSelMode', 'scan')
            check(f'scan box shown {tag}', pg.is_visible('#scanBox') and not pg.is_visible('#dwellBox'))
            pg.click('#closeSettBtn2') if pg.is_visible('#closeSettBtn2') else pg.click('#closeSettBtn')
            pg.evaluate("settings.selMode='tap';scanApply()")
            check(f'no errors layout {tag}', not errs, errs)
            c.close()

    b.close()
print(f'OK {OK}  FAIL {FAIL}')
sys.exit(1 if FAIL else 0)
