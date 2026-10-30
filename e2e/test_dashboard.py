"""Actual live-service browser checks. Opt in with RUN_BROWSER_TESTS=1."""
import os
from pathlib import Path
import pytest

if os.getenv('RUN_BROWSER_TESTS')!='1':
    pytest.skip('Browser tests run separately against a deployed local stack',allow_module_level=True)
pw=pytest.importorskip('playwright.sync_api')

CASES=[('chromium',1440,1000),('firefox',1440,1000),('webkit',1440,1000),
       ('chromium',390,844),('webkit',390,844)]

@pytest.mark.parametrize('engine,width,height',CASES)
def test_live_dashboard(engine,width,height):
    with pw.sync_playwright() as playwright:
        browser=getattr(playwright,engine).launch()
        context=browser.new_context(base_url=os.getenv('DASHBOARD_URL','http://127.0.0.1:8000'),
                                   viewport={'width':width,'height':height},
                                   is_mobile=width<600,has_touch=width<600)
        page=context.new_page()
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            response=page.goto(os.getenv('DASHBOARD_URL','http://127.0.0.1:8000'),wait_until='domcontentloaded')
            assert response.status==200
            pw.expect(page.locator('#asset-count')).to_have_text('12')
            pw.expect(page.locator('#event-count')).to_have_text('800')
            pw.expect(page.get_by_role('button',name='Inspect stream-001',exact=True)).to_be_visible()
            page.get_by_role('textbox',name='Find an asset').fill('stream-001')
            pw.expect(page.locator('.asset-row')).to_have_count(1)
            page.get_by_role('button',name='Inspect stream-001',exact=True).click()
            pw.expect(page.locator('#selected-asset')).to_have_text('STREAM-001')
            pw.expect(page.locator('#risk-chart polyline')).to_have_count(1)
            page.get_by_role('textbox',name='Find an asset').fill('no-such-asset')
            pw.expect(page.get_by_text('No matching assets.',exact=True)).to_be_visible()
            page.get_by_role('textbox',name='Find an asset').fill('')
            page.get_by_role('combobox',name='Filter by status').select_option(label='Normal')
            live=page.request.get('/api/assets').json()
            normal=sum(a['status']=='normal' for a in live['assets'])
            pw.expect(page.locator('.asset-row')).to_have_count(normal)
            page.get_by_role('combobox',name='Filter by status').select_option(label='All statuses')
            pw.expect(page.locator('.asset-row')).to_have_count(12)
            page.get_by_role('button',name='Model evaluation').click()
            pw.expect(page.get_by_role('heading',name='Performance on unseen assets',exact=True)).to_be_visible()
            pw.expect(page.locator('#model-results tbody tr')).to_have_count(2)
            page.get_by_role('button',name='Data pipeline').click()
            pw.expect(page.get_by_role('heading',name='From sensor reading to review',exact=True)).to_be_visible()
            page.get_by_role('button',name='Fleet overview').click()
            page.get_by_role('button',name='Refresh',exact=False).click()
            pw.expect(page.locator('#error')).to_be_hidden()
            pw.expect(page.locator('#asset-count')).to_have_text('12')
            # The page itself must fit the viewport; table-specific scrolling is allowed.
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
            assert not errors,errors
            Path('test-results').mkdir(exist_ok=True)
            page.screenshot(path=f'test-results/dashboard-{engine}-{width}.png',full_page=True)
        except Exception:
            Path('test-results').mkdir(exist_ok=True)
            page.screenshot(path=f'test-results/failure-{engine}-{width}.png',full_page=True)
            raise
        finally:
            context.close();browser.close()

