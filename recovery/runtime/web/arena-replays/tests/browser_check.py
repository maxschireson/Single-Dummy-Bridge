import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
COHORT = '8373b7b6adc88bb1cd3755840bb961797a61e47d9d8fbac79d1f81bf3cf8227f'
BASE = 'http://127.0.0.1:8766/arena/'
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1350, 'height': 1100})
    page.on('pageerror', lambda e: errors.append(str(e)))
    # Snapshot and missing-live-record behavior are deterministic in this test.
    page.route('https://raw.githubusercontent.com/**', lambda route: route.fulfill(status=404, body='{}'))
    page.goto(BASE, wait_until='networkidle')
    page.wait_for_selector('#results tr td:nth-child(3) a')
    assert page.locator('#matrix a').count() == 6
    page.wait_for_selector('#replay-archive h3')
    assert '465' in page.locator('#replay-archive').inner_text()
    page.locator('#results tr td:nth-child(3) a').first.click()
    page.wait_for_function("document.querySelector('#coverage').textContent.includes('not been published')")
    page.select_option('#cohort', COHORT)
    page.wait_for_selector('#rows a.record-link')
    page.select_option('#pair', 'AB')
    page.wait_for_function("document.querySelector('#coverage').textContent.includes('266')")
    assert '-122' in page.locator('#coverage').inner_text()
    page.select_option('#sort', 'loss')
    assert page.locator('#rows tr td:nth-child(7)').first.inner_text() == '-14'
    page.select_option('#sort', 'gain')
    assert page.locator('#rows tr td:nth-child(7)').first.inner_text() == '+14'
    page.select_option('#sort', 'newest')
    page.screenshot(path=str(ROOT/'board-list-desktop.png'), full_page=True)
    page.goto(BASE+f'replays/board.html?cohort={COHORT}&board=1')
    page.wait_for_selector('#viewer:not(.hidden)')
    assert '+5 IMPs' in page.locator('#result').inner_text()
    assert page.locator('.hand').count() == 8
    assert 'Card 0 of 52' in page.locator('#position-label').inner_text()
    page.locator('#next').click()
    assert 'Card 1 of 52' in page.locator('#position-label').inner_text()
    assert page.locator('#table0 .center').inner_text().find('♣J') >= 0
    assert page.locator('#table1 .center').inner_text().find('♦2') >= 0
    page.locator('#trick').click()
    assert 'Card 4 of 52' in page.locator('#position-label').inner_text()
    page.locator('#end').click()
    assert 'Card 52 of 52' in page.locator('#position-label').inner_text()
    assert page.locator('#next').is_disabled()
    page.locator('#difference').click()
    assert 'Card 1 of 52' in page.locator('#position-label').inner_text()
    assert 'ply=1' in page.url
    page.locator('#play').click()
    page.wait_for_function("Number(document.querySelector('#position').value)>=2")
    page.locator('#play').click()
    page.locator('#start').click()
    page.keyboard.press('ArrowRight')
    # Focus remains on a button; keyboard button semantics intentionally win.
    page.locator('h1').click()
    page.keyboard.press('ArrowRight')
    assert 'Card 1 of 52' in page.locator('#position-label').inner_text()
    page.screenshot(path=str(ROOT/'board-replay-desktop.png'), full_page=True)
    mobile = browser.new_page(viewport={'width':390,'height':844}, device_scale_factor=1, is_mobile=True, has_touch=True)
    mobile.on('pageerror', lambda e: errors.append(str(e)))
    mobile.goto(BASE+f'replays/board.html?cohort={COHORT}&board=1&ply=4')
    mobile.wait_for_selector('#viewer:not(.hidden)')
    assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
    mobile.screenshot(path=str(ROOT/'board-replay-mobile.png'), full_page=True)
    mobile.locator('#next').click()
    assert 'Card 5 of 52' in mobile.locator('#position-label').inner_text()
    assert not errors, errors
    print(json.dumps({'browser_errors':errors,'checks':['IMP links','matrix links','missing live data state','cohort switch','pair totals','gain/loss/time sorting','two-table play','trick navigation','end','first divergence','autoplay','keyboard','deep links','390px mobile layout']}))
    browser.close()
