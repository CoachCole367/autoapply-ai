"""Conservative, explicitly authorized dry-run form inspection and filling.

No submit actions, AI-generated answers, session credentials or arbitrary navigation.
The container must additionally use an egress firewall in production: DNS checks alone
cannot defend against a malicious host changing its DNS between resolution and connect.
"""

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from playwright.sync_api import sync_playwright

HOSTS = {
    "greenhouse": {"boards.greenhouse.io", "job-boards.greenhouse.io"},
    "lever": {"jobs.lever.co", "jobs.eu.lever.co"},
    "ashby": {"jobs.ashbyhq.com"},
}
FIELDS = {
    "greenhouse": {"first_name": "first", "last_name": "last", "email": "email", "phone": "phone"},
    "lever": {"name": "name", "email": "email", "phone": "phone"},
    "ashby": {"_systemfield_name": "name", "_systemfield_email": "email", "_systemfield_phone": "phone"},
}


def validate_url(url, provider, allowed_hosts, resolver=socket.getaddrinfo):
    parsed = urlsplit(url)
    host = parsed.hostname
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or host not in HOSTS.get(provider, set())
        or host not in allowed_hosts
    ):
        raise ValueError("Application host is not explicitly authorized")
    addresses = resolver(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
        raise ValueError("Private or reserved network destination blocked")


def fill(page, provider, profile):
    parts = profile.name.strip().split(maxsplit=1)
    values = {
        "name": profile.name,
        "first": parts[0] if parts else "",
        "last": parts[1] if len(parts) > 1 else "",
        "email": profile.email,
        "phone": profile.phone,
    }
    filled = []
    for name, key in FIELDS[provider].items():
        field = page.locator(f'input[name="{name}"]')
        if field.count() == 1 and field.is_visible() and values[key]:
            field.fill(values[key])
            filled.append(key)
    return filled


def dry_run(job, profile, policy, directory):
    if policy.emergency_stop or not profile.verified or not policy.dry_run or policy.auto_submit:
        raise ValueError("Verified profile and active dry-run policy required")
    validate_url(job.url, job.provider, policy.allowed_hosts)
    target = Path(directory) / "screenshots"
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{uuid4().hex}.png"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(service_workers="block", accept_downloads=False)

            def route(request_route):
                request = request_route.request
                try:
                    validate_url(request.url, job.provider, policy.allowed_hosts)
                    # Prevent autosaves, telemetry and file uploads; this adapter inspects and fills only.
                    if request.method != "GET":
                        raise ValueError("Dry-run writes blocked")
                    request_route.continue_()
                except (ValueError, OSError):
                    request_route.abort()

            context.route("**/*", route)
            page = context.new_page()
            page.goto(job.url, wait_until="domcontentloaded", timeout=30000)
            if page.locator('iframe[src*="captcha"], input[autocomplete="one-time-code"]').count():
                filled = []
                reason = "Security check requires human intervention"
            else:
                filled = fill(page, job.provider, profile)
                reason = "Dry run complete; review remaining fields manually. Nothing submitted."
            page.screenshot(path=str(path), full_page=True)
            return {
                "reason": reason,
                "filled_fields": filled,
                "screenshot": str(path.resolve()),
                "submitted": False,
            }
        finally:
            browser.close()
