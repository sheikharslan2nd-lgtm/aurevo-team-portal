"""Server-side helpers for the PakSEOtools integration.

This module deliberately does **not** bypass CAPTCHA, MFA or any other security
control. If the login flow cannot be completed with the supplied credentials,
the function returns a failure so the admin can be warned instead of
implementing an insecure workaround.
"""

import json
import os
from pathlib import Path

from django.conf import settings


def chrome_executable_path():
    configured = os.environ.get("CHROME_EXECUTABLE_PATH", "").strip()
    if configured and Path(configured).exists():
        return configured
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def pakseo_login(username, password, login_url):
    """Attempt a server-side login and return cookies + user agent.

    Returns a dict with keys ``ok``, ``cookies``, ``user_agent`` and ``error``.
    """

    result = {"ok": False, "cookies": [], "user_agent": "", "error": ""}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - optional dependency
        result["error"] = f"Playwright is not available: {exc}"
        return result

    executable = chrome_executable_path()
    try:
        with sync_playwright() as playwright:
            launch_kwargs = {"headless": True}
            if executable:
                launch_kwargs["executable_path"] = executable
            browser = playwright.chromium.launch(**launch_kwargs)
            context = browser.new_context()
            page = context.new_page()
            page.goto(login_url, timeout=30000, wait_until="domcontentloaded")
            # If the site already shows a CAPTCHA challenge we must not bypass it.
            content = page.content().lower()
            if "recaptcha" in content and "display: none" not in content.replace(" ", ""):
                # Only treat as blocking when a visible challenge widget exists.
                if page.locator("iframe[src*='recaptcha']").count() > 0:
                    browser.close()
                    result["error"] = "PakSEOtools presented a CAPTCHA challenge; automated login is not permitted."
                    return result
            page.fill('input[name="amember_login"]', username)
            page.fill('input[name="amember_pass"]', password)
            page.click('input[type="submit"]')
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass
            final_url = page.url
            final_html = page.content().lower()
            # Success heuristic: left the login form or a dashboard element is present.
            still_login = ("amember_login" in final_html) and ("amember_pass" in final_html)
            if still_login:
                result["error"] = "Login failed. Check the stored credentials or whether MFA/CAPTCHA is required."
            else:
                result["ok"] = True
                result["cookies"] = context.cookies()
                try:
                    result["user_agent"] = page.evaluate("navigator.userAgent")
                except Exception:
                    result["user_agent"] = getattr(settings, "PAKSEO_USER_AGENT", "")
            browser.close()
    except Exception as exc:
        result["error"] = str(exc)
    return result


def serialize_cookies(cookies):
    return json.dumps(cookies or [])


def deserialize_cookies(value):
    if not value:
        return []
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []