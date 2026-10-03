"""Standalone actual-browser regression. Start app first.
Usage: CHROME_PATH=/path/to/chrome python tests/browser_flow.py
Uses Playwright's bundled Chromium if CHROME_PATH is unset.
"""
import os,json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
artifacts=Path(os.getenv('R2J_SCREENSHOTS','/tmp/r2j-screenshots'));artifacts.mkdir(exist_ok=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=os.getenv('CHROME_PATH') or None,headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
    page=context.new_page();errors=[];external=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    # Block all nonlocal network to prove the core workflow has no CDN dependency.
    def route(r):
        if not r.request.url.startswith('http://127.0.0.1:8000'):external.append(r.request.url);r.abort()
        else:r.continue_()
    context.route('**/*',route)
    page.goto('http://127.0.0.1:8000');page.wait_for_function("document.getElementById('mode').textContent.includes('deterministic')")
    page.screenshot(path=str(artifacts/'landing.png'),full_page=True)
    start=time.monotonic()
    page.locator('#file').set_input_files(str(ROOT/'demo/ayesha.pdf'))
    page.locator('#profile').wait_for(state='visible');page.locator('#busy').wait_for(state='hidden')
    page.locator('#field-certifications').fill('User-confirmed course completion')
    page.locator('#role').fill('Junior Python Backend Developer');page.locator('#level').select_option('junior')
    page.locator('#find').click();page.locator('#jobs').wait_for(state='visible');page.locator('#busy').wait_for(state='hidden')
    assert page.locator('[data-job]').count()>0
    page.screenshot(path=str(artifacts/'matches.png'),full_page=True)
    page.locator('[data-job="1"]').click();page.locator('#analysis').wait_for(state='visible');page.locator('#busy').wait_for(state='hidden')
    fresh=time.monotonic()-start
    assert page.locator('#report').inner_text().find('What makes this a match?')>=0
    page.screenshot(path=str(artifacts/'analysis.png'),full_page=True)
    for tab in ['Skills','Keywords','Experience','Actions']:
        page.get_by_role('tab',name=tab,exact=True).click()
        assert len(page.locator('#report').inner_text())>80
    assert 'Docker' in page.locator('#report').inner_text()
    page.screenshot(path=str(artifacts/'actions.png'),full_page=True)
    with page.expect_download() as info:page.locator('#export').click()
    assert Path(info.value.path()).stat().st_size>100
    page.get_by_role('tab',name='Improve',exact=True).click();page.locator('#improve').click();page.locator('#busy').wait_for(state='hidden')
    assert 'Only use suggestions' in page.locator('#improvement').inner_text()
    page.locator('#back').click();start=time.monotonic();page.locator('[data-job="1"]').click();page.locator('#busy').wait_for(state='hidden');cached=time.monotonic()-start
    assert 'Saved analysis reused' in page.locator('#activity').inner_text()
    page.reload();page.locator('#profile').wait_for(state='visible');assert 'User-confirmed' in page.locator('#field-certifications').input_value()
    # Invalid profile should stop navigation, not continue matching stale state.
    page.locator('#years').fill('-1');page.locator('#find').click();page.locator('#busy').wait_for(state='hidden');assert page.locator('#error').is_visible() and page.locator('#profile').is_visible()
    page.locator('#years').fill('0.2');page.locator('#location').fill('Uninhabited Mars');page.locator('#work_mode').select_option('on-site')
    page.locator('#find').click();page.locator('#jobs').wait_for(state='visible');page.locator('#busy').wait_for(state='hidden');assert 'No jobs fit' in page.locator('#job-list').inner_text()
    page.locator('#delete').click();page.locator('#upload').wait_for(state='visible');page.locator('#busy').wait_for(state='hidden')
    assert page.evaluate("sessionStorage.getItem('r2j-id')") is None
    # Mobile flow, no horizontal page overflow.
    page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(artifacts/'mobile-landing.png'),full_page=True)
    page.locator('#demo-omar').click();page.locator('#profile').wait_for(state='visible');page.locator('#busy').wait_for(state='hidden')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('#find').click();page.locator('#jobs').wait_for(state='visible');page.locator('#busy').wait_for(state='hidden')
    page.locator('[data-job]').first.click();page.locator('#analysis').wait_for(state='visible');page.locator('#busy').wait_for(state='hidden')
    page.get_by_role('tab',name='Actions',exact=True).click();page.screenshot(path=str(artifacts/'mobile-actions.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('#delete').click();page.locator('#busy').wait_for(state='hidden')
    # Paste fallback and untrusted HTML are rendered as text.
    page.locator('summary').click();page.locator('#resume-text').fill('Skills\nPython, SQL\nProjects\n<img src=x onerror=alert(1)> built a Python app with SQL and Flask.');page.locator('#paste').click();page.locator('#profile').wait_for(state='visible');page.locator('#busy').wait_for(state='hidden')
    assert page.locator('#profile-fields img').count()==0
    page.locator('#delete').click();page.locator('#busy').wait_for(state='hidden')
    assert not external,external
    expected=[e for e in errors if '422 (Unprocessable Entity)' in e]
    errors=[e for e in errors if e not in expected]
    assert len(expected)==1,expected
    assert not errors,errors
    result={'fresh_pdf_to_analysis_seconds':round(fresh,3),'cached_analysis_seconds':round(cached,3),'browser_errors':errors,'external_requests':external,'expected_validation_errors':len(expected),'desktop':'1440x1000','mobile':'390x844','status':'passed'}
    (artifacts/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));browser.close()
