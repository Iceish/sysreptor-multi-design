"""Synthetic local browser acceptance. Run via scripts/dev.sh smoke; never against real data."""
import io
import os
from pathlib import Path
import secrets
import time
from urllib.error import URLError
from urllib.request import urlopen

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sysreptor.conf.settings')
import django

django.setup()

from django.core.management import call_command
from playwright.sync_api import sync_playwright, expect
from sysreptor.users.models import PentestUser
from sysreptor.pentests.models import PentestProject
from sysreptor_plugins.multidesign.apps import MultiDesignConfig

username = 'mdo_smoke'
password = secrets.token_urlsafe(32)
user, _ = PentestUser.objects.get_or_create(username=username, defaults={'roles': ['regular_user'], 'is_superuser': True, 'is_staff': True})
user.set_password(password)
user.save()
initial_project_count = PentestProject.objects.filter(members__user=user).count()
call_command('multidesign_demo', username=username, stdout=io.StringIO())
project = PentestProject.objects.filter(members__user=user).latest('created')
plugin_id = MultiDesignConfig.plugin_id
source_design = project.project_type_id
source_data = project.data
artifacts = Path('/artifacts')
artifacts.mkdir(exist_ok=True)

for attempt in range(30):
    try:
        with urlopen('http://127.0.0.1:8000/api/public/utils/healthcheck/', timeout=2) as response:
            if response.status == 200:
                break
    except (URLError, TimeoutError):
        time.sleep(1)
else:
    raise RuntimeError('Local SysReptor did not become healthy within 30 attempts.')

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
    context = browser.new_context(base_url='http://127.0.0.1:8000', viewport={'width': 1440, 'height': 1100})
    login = context.request.post('/api/v1/auth/login/', data={'username': username, 'password': password})
    assert login.ok, f'Local synthetic login failed: {login.status}'
    page = context.new_page()
    page_errors = []
    page.on('pageerror', lambda error: page_errors.append(str(error)))
    page.goto(f'/projects/{project.pk}/')
    page.get_by_role('link', name='Outputs', exact=True).click()
    frame = page.frame_locator('iframe').first
    expect(frame.get_by_role('heading', name='Outputs', exact=True)).to_be_visible(timeout=30000)
    frame.get_by_label('Saved output', exact=True).press('ArrowDown')
    frame.get_by_role('option', name='Technical report', exact=True).click()
    frame.get_by_role('button', name='Generate PDF', exact=True).click()
    expect(frame.get_by_role('button', name='Download PDF', exact=True)).to_be_enabled(timeout=90000)
    frame.get_by_label('Download filename (.pdf)', exact=True).fill('browser-technical.pdf')
    with page.expect_download() as download_event:
        frame.get_by_role('button', name='Download PDF', exact=True).click()
    download = download_event.value
    assert download.suggested_filename == 'browser-technical.pdf'
    download.save_as(artifacts / download.suggested_filename)

    frame.get_by_label('Saved output', exact=True).press('ArrowDown')
    frame.get_by_role('option', name='Presentation', exact=True).click()
    expect(frame.get_by_role('button', name='Download PDF', exact=True)).to_be_disabled()
    frame.get_by_role('button', name='Generate PDF', exact=True).click()
    expect(frame.get_by_role('button', name='Download PDF', exact=True)).to_be_enabled(timeout=90000)
    with page.expect_download() as download_event:
        frame.get_by_role('button', name='Download PDF', exact=True).click()
    download_event.value.save_as(artifacts / 'browser-presentation.pdf')
    expect(frame.get_by_title('PDF Viewer')).to_be_visible(timeout=30000)
    expect(frame.frame_locator('iframe[title="PDF Viewer"]').locator('canvas').first).to_be_visible(timeout=30000)
    page.screenshot(path=str(artifacts / 'outputs-browser.png'), full_page=True)

    # Exercise HTTP failure/retry UI independently of the backend's real-PDF tests.
    route_pattern = f'**/api/plugins/{plugin_id}/api/projects/{project.pk}/render/'
    page.route(route_pattern, lambda route: route.fulfill(status=503, json={'detail': 'Synthetic worker unavailable; retry.'}))
    frame.get_by_role('button', name='Generate PDF', exact=True).click()
    expect(frame.get_by_role('alert').filter(has_text='Synthetic worker unavailable')).to_be_visible()
    expect(frame.get_by_role('button', name='Download PDF', exact=True)).to_be_disabled()
    page.unroute(route_pattern)
    frame.get_by_role('button', name='Retry PDF', exact=True).click()
    expect(frame.get_by_role('button', name='Download PDF', exact=True)).to_be_enabled(timeout=90000)
    assert not page_errors, page_errors
    browser.close()

project.refresh_from_db()
assert project.project_type_id == source_design
assert project.data == source_data
assert PentestProject.objects.filter(members__user=user).count() == initial_project_count + 1
print('Browser acceptance passed: registered menu, saved choices, two real PDFs, editable download, stale-preview reset, synthetic HTTP error and real retry.')
print(f'Synthetic demo retained locally: {project.pk}')
