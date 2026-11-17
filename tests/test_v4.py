#!/usr/bin/env python3
"""Тесты «Мій голос» v4: черновик «Писать» и строка «Азбуки» переживают перезагрузку,
«Запуск с последнего экрана» включён по умолчанию, настройки сохраняются сразу. Запуск как test_v1.py."""
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
Object.defineProperty(window,'speechSynthesis',{value:{speak:u=>{window.__spoken.push(u.text);setTimeout(()=>{u.onend&&u.onend()},5)},cancel(){},getVoices:()=>[],speaking:false,pending:false,paused:false,onvoiceschanged:null}});
"""
def page(b, st="{profile:'words'}", lang='uk', w=360, hgt=640):
    c = b.new_context(viewport={'width': w, 'height': hgt}, service_workers='block')
    c.add_init_script(INIT + f"if(!localStorage.getItem('mv.settings'))localStorage.setItem('mv.settings',JSON.stringify({st}));if(!localStorage.getItem('mv.lang'))localStorage.setItem('mv.lang','{lang}');")
    pg = c.new_page(); pg.set_default_timeout(5000)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(400)
    return c, pg, errs
S = lambda pg: pg.evaluate("JSON.parse(localStorage.getItem('mv.settings')||'{}')")
def reload(pg): pg.reload(); pg.wait_for_timeout(400)

with sync_playwright() as p:
    b = p.chromium.launch()

    # 1. Черновик «Писать»
    c, pg, errs = page(b)
    pg.click('#typeBtn')
    for ch in ['М', 'Е', 'Н', 'І']:
        pg.click(f'.tykb .letters .lt:text-is("{ch}")')
    check('draft saved at once', pg.evaluate("JSON.parse(localStorage.getItem('mv.draft.uk')).ty") == 'Мені')
    reload(pg)
    check('draft restored', pg.evaluate('tyText') == 'Мені', pg.evaluate('tyText'))
    check('reopened on Type (resume default)', pg.locator('#tyBox').count() == 1 and 'Мені' in pg.inner_text('#tyBox'))
    pg.click('#tySay'); pg.wait_for_timeout(100)
    check('spoken', 'Мені' in pg.evaluate('window.__spoken'))
    pg.wait_for_timeout(100)
    check('draft cleared after say', pg.evaluate("localStorage.getItem('mv.draft.uk')") is None)
    reload(pg)
    check('empty after reload', pg.evaluate('tyText') == '')
    # отменённое стирание: «Очистить» → перезагрузка — пусто (так и задумано), «Вернуть» восстанавливает и сохраняет
    pg.evaluate("$('#ov .ans.yes')&&$('#ov .ans.yes').click()")
    pg.click('.tykb .letters .lt:text-is("Т")'); pg.click('#tyAct .tyb.cl'); pg.click('#tyAct .tyb.un')
    check('undo saved', pg.evaluate("JSON.parse(localStorage.getItem('mv.draft.uk')).ty") == 'Т')
    # клавиатура телефона
    pg.click('#tyAct .tyb.op'); pg.click('.tyopts .tyb:has-text("📱")')
    pg.fill('#tyIn', 'Добрий ранок')
    check('textarea draft', pg.evaluate("JSON.parse(localStorage.getItem('mv.draft.uk')).ty") == 'Добрий ранок')
    reload(pg)
    check('textarea restored', pg.input_value('#tyIn') == 'Добрий ранок')
    # свой черновик для каждого языка
    pg.evaluate("setLang('ru')")
    check('ru draft empty', pg.evaluate('tyText') == '')
    pg.evaluate("tyText='Привет';tyRefresh()")
    pg.evaluate("setLang('uk')")
    check('uk draft back', pg.evaluate('tyText') == 'Добрий ранок')
    pg.evaluate("setLang('ru')")
    check('ru draft back', pg.evaluate('tyText') == 'Привет')
    check('no errors draft', not errs, errs)
    c.close()

    # 2. Строка «Азбуки»
    c, pg, errs = page(b)
    pg.click('#abcBtn'); pg.wait_for_timeout(100)
    pg.evaluate("abcLine.push('Я','хочу');renderAbc()")
    pg.wait_for_timeout(1300)   # сохраняется не позже чем через секунду
    check('abc line saved', pg.evaluate("JSON.parse(localStorage.getItem('mv.draft.uk')).abc") == ['Я', 'хочу'])
    reload(pg)
    check('abc screen restored', pg.evaluate('!!abc'))
    check('abc line restored', pg.evaluate('abcLine') == ['Я', 'хочу'], pg.evaluate('abcLine'))
    check('abc line shown', 'хочу' in pg.inner_text('#main'))
    pg.evaluate("abcLine.length=0;renderAbc()"); pg.wait_for_timeout(1300)
    check('abc cleared removed', pg.evaluate("localStorage.getItem('mv.draft.uk')") is None)
    check('no errors abc', not errs, errs)
    c.close()

    # 3. Запуск с последнего экрана: по умолчанию включён, выбор человека сохраняется
    c, pg, errs = page(b)
    check('resume default on', pg.evaluate('settings.resume') is True)
    pg.click('#settingsBtn'); pg.click('#sett .sg[data-g=home] .sgh')
    check('resume checkbox on', pg.is_checked('#setResume'))
    pg.click('#closeSettBtn')
    pg.click('#main .tile >> nth=0'); pg.wait_for_timeout(100)
    d = pg.evaluate('path.length'); reload(pg)
    check('tile section restored', d > 0 and pg.evaluate('path.length') == d)
    c.close()
    c, pg, errs = page(b, st="{profile:'words',resume:false,resumeDef:1}")
    check('explicit off kept', pg.evaluate('settings.resume') is False)
    pg.click('#typeBtn'); reload(pg)
    check('off: opens home', pg.locator('.mvhome').count() == 1)
    c.close()
    c, pg, errs = page(b, st="{profile:'words',resume:false}")   # установка v1–v3
    check('old install migrated on', pg.evaluate('settings.resume') is True and pg.evaluate('settings.resumeDef') == 1)
    c.close()

    # 4. Настройки сохраняются сразу
    c, pg, errs = page(b)
    pg.on('dialog', lambda d: d.accept())
    pg.click('#settingsBtn')
    pg.click('#sett .sg[data-g=type] .sgh')
    pg.uncheck('#setQuickBar'); pg.wait_for_timeout(100)
    check('checkbox saved at once', S(pg).get('quickBar') is False)
    check('settings still open', pg.evaluate("$('#sett').style.display") == 'block')
    check('quick strip hidden at once', pg.evaluate("$('#quick').hidden"))
    check('group still open', pg.evaluate("document.querySelector('#sett .sg.open').dataset.g") == 'type')
    pg.evaluate("$('#sett').scrollTop=150"); st0 = pg.evaluate("$('#sett').scrollTop")
    pg.select_option('#setKbLayout', 'qw'); pg.wait_for_timeout(100)
    check('select saved', S(pg).get('kbLayout') == 'qw')
    check('scroll kept', pg.evaluate("$('#sett').scrollTop") == st0, (st0, pg.evaluate("$('#sett').scrollTop")))
    pg.click('#sett .sg[data-g=main] .sgh')
    pg.select_option('#setSeg', 'L4'); pg.wait_for_timeout(150)
    check('level saved and tree reloaded', S(pg).get('level') == 'L4' and pg.evaluate('settings.level') == 'L4')
    pg.select_option('#setProfile', 'speak'); pg.wait_for_timeout(150)
    check('profile applied and saved', S(pg).get('profile') == 'speak' and S(pg).get('level') == 'L5' and S(pg).get('start') == 'type')
    pg.click('#sett .sg[data-g=card] .sgh')
    pg.fill('#setCardName', 'Олена'); pg.locator('#setCardName').blur(); pg.wait_for_timeout(100)
    check('text field saved on change', S(pg).get('card', {}).get('name') == 'Олена')
    pg.fill('#setCardDx', 'Афазія')
    pg.evaluate("Object.defineProperty(document,'hidden',{value:true,configurable:true});document.dispatchEvent(new Event('visibilitychange'));dispatchEvent(new Event('visibilitychange'))")
    pg.wait_for_timeout(100)
    check('saved when app hidden', S(pg).get('card', {}).get('dx') == 'Афазія')
    pg.evaluate("Object.defineProperty(document,'hidden',{value:false,configurable:true})")
    # касание заголовка другой группы сразу после правки поля срабатывает с первого раза
    pg.fill('#setCardNotes', 'Не чує правим вухом')
    pg.evaluate("document.querySelector('#sett .sg[data-g=touch] .sgh').scrollIntoView({block:'center'})")
    r = pg.locator('#sett .sg[data-g=touch] .sgh').bounding_box()
    pg.mouse.click(r['x'] + r['width'] / 2, r['y'] + r['height'] / 2); pg.wait_for_timeout(100)
    check('header tap right after field edit', pg.evaluate('settOpen') == 'touch', pg.evaluate('settOpen'))
    check('field saved by that tap', S(pg).get('card', {}).get('notes') == 'Не чує правим вухом')
    pg.select_option('#setSelMode', 'dwell'); pg.wait_for_timeout(100)
    check('selMode saved, dwell visible', S(pg).get('selMode') == 'dwell' and pg.is_visible('#setDwell'))
    pg.select_option('#setSelMode', 'tap'); pg.wait_for_timeout(100)
    pg.click('#sett .sg[data-g=main] .sgh')
    pg.select_option('#setLang', 'ru'); pg.wait_for_timeout(150)
    check('lang change saved, values kept', pg.evaluate("localStorage.getItem('mv.lang')") == 'ru' and S(pg).get('card', {}).get('name') == 'Олена')
    pg.click('#closeSettBtn')
    check('close still works', pg.evaluate("$('#sett').style.display") != 'block')
    pg.click('#settingsBtn'); pg.evaluate('appBack()')
    check('back closes settings', pg.evaluate("$('#sett').style.display") != 'block')
    check('no errors settings', not errs, errs)
    c.close()

    # 5. Вёрстка не изменилась (поле «Писать» с восстановленным черновиком)
    for (w, hgt) in [(360, 640), (277, 492)]:
        c, pg, errs = page(b, w=w, hgt=hgt)
        pg.evaluate("localStorage.setItem('mv.draft.uk',JSON.stringify({ty:'Я хочу пити воду, будь ласка, і ще трохи чаю з лимоном',abc:[]}))")
        pg.evaluate("$('#typeBtn').click()"); reload(pg)
        vis = pg.evaluate("(()=>{const m=$('#main').getBoundingClientRect(),r=$('#tyBox').getBoundingClientRect();return r.top>=m.top-1&&r.bottom<=m.bottom&&document.documentElement.scrollWidth<=innerWidth+1})()")
        check(f'restored draft layout {w}', vis)
        c.close()
    b.close()
print(f'OK {OK}  FAIL {FAIL}')
sys.exit(1 if FAIL else 0)
