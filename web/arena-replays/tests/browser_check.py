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
    assert 'Card 0 of 52' in page.locator('#position-label0').inner_text()
    assert page.locator('.table-contract').all_text_contents() == ['3S by South', '3S by South']
    page.locator('#next0').click()
    assert 'Card 1 of 52' in page.locator('#position-label0').inner_text()
    assert 'Card 0 of 52' in page.locator('#position-label1').inner_text()
    assert '♣J' in page.locator('#table0 .center').inner_text()
    page.locator('#trick1').click()
    assert 'Card 4 of 52' in page.locator('#position-label1').inner_text()
    assert 'Card 1 of 52' in page.locator('#position-label0').inner_text()
    page.locator('#previous1').click()
    assert 'Card 3 of 52' in page.locator('#position-label1').inner_text()
    page.locator('#end0').click()
    assert 'Card 52 of 52' in page.locator('#position-label0').inner_text()
    assert page.locator('#next0').is_disabled()
    assert page.locator('#next1').is_enabled()
    page.locator('#difference0').click()
    assert 'Card 1 of 52' in page.locator('#position-label0').inner_text()
    assert 'Card 3 of 52' in page.locator('#position-label1').inner_text()
    assert 'ply1=1' in page.url and 'ply2=3' in page.url
    page.reload()
    page.wait_for_selector('#viewer:not(.hidden)')
    assert 'Card 1 of 52' in page.locator('#position-label0').inner_text()
    assert 'Card 3 of 52' in page.locator('#position-label1').inner_text()
    page.locator('#play0').click()
    page.wait_for_function("Number(document.querySelector('#position0').value)>=2")
    page.locator('#play0').click()
    assert 'Card 3 of 52' in page.locator('#position-label1').inner_text()
    page.locator('#start0').click()
    page.locator('#table0').press('ArrowRight')
    assert 'Card 1 of 52' in page.locator('#position-label0').inner_text()
    assert 'Card 3 of 52' in page.locator('#position-label1').inner_text()
    page.screenshot(path=str(ROOT/'board-replay-desktop.png'), full_page=True)
    mobile = browser.new_page(viewport={'width':390,'height':844}, device_scale_factor=1, is_mobile=True, has_touch=True)
    mobile.on('pageerror', lambda e: errors.append(str(e)))
    mobile.goto(BASE+f'replays/board.html?cohort={COHORT}&board=1&ply=4')
    mobile.wait_for_selector('#viewer:not(.hidden)')
    assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
    mobile.screenshot(path=str(ROOT/'board-replay-mobile.png'), full_page=True)
    mobile.locator('#next1').click()
    assert 'Card 5 of 52' in mobile.locator('#position-label1').inner_text()
    assert 'Card 4 of 52' in mobile.locator('#position-label0').inner_text()
    assert not errors, errors
    print(json.dumps({'browser_errors':errors,'checks':['IMP links','matrix links','missing live data state','cohort switch','pair totals','gain/loss/time sorting','independent table play', 'per-table contracts','trick navigation','end','first divergence','autoplay','keyboard','deep links','390px mobile layout']}))
    browser.close()
