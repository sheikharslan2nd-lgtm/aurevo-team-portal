"""Server-side helpers for the PakSEOtools integration.

This module deliberately does **not** bypass CAPTCHA, MFA or any other security
control. If the login flow cannot be completed with the supplied credentials,
the function returns a failure so the admin can be warned instead of
implementing an insecure workaround.
"""

import json
import os
import re
from pathlib import Path

from django.conf import settings


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)


def pakseo_http_login(username, password, login_url):
    """Log in server-side with a plain HTTP session.

    This is the deployment-friendly path: it works on hosts (including
    Vercel) where a browser binary is unavailable. It does not bypass
    CAPTCHA/MFA; if a challenge is detected the login is refused.
    """

    result = {"ok": False, "cookies": [], "user_agent": "", "error": ""}
    try:
        import requests
    except Exception as exc:  # pragma: no cover
        result["error"] = f"requests is not available: {exc}"
        return result

    session = requests.Session()
    session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
    try:
        page = session.get(login_url, timeout=30)
        html = page.text
        lower = html.lower()
        # Refuse to bypass a visible CAPTCHA challenge.
        if "g-recaptcha" in lower or "h-captcha" in lower or "cf-turnstile" in lower:
            result["error"] = "PakSEOtools presented a CAPTCHA/human-verification challenge; automated login is not permitted."
            return result

        data = {
            "amember_login": username,
            "amember_pass": password,
        }
        match = re.search(r'name="login_attempt_id"\s+value="([^"]+)"', html)
        if match:
            data["login_attempt_id"] = match.group(1)

        action_match = re.search(r'<form[^>]+name="login"[^>]+action="([^"]+)"', html)
        action = action_match.group(1) if action_match else login_url
        if action.startswith("/"):
            from urllib.parse import urljoin

            action = urljoin(login_url, action)

        response = session.post(action, data=data, timeout=30, allow_redirects=True)
        body = response.text
        body_lower = body.lower()
        if "user name or password is incorrect" in body_lower or "invalid username" in body_lower:
            result["error"] = "PakSEOtools rejected the stored credentials."
            return result
        if "captcha" in body_lower and "incorrect" not in body_lower:
            result["error"] = "PakSEOtools requires CAPTCHA/MFA; automated login is not permitted."
            return result
        still_login = ('name="amember_login"' in body) and ('name="amember_pass"' in body)
        if still_login:
            result["error"] = "Login failed. Check the stored credentials or whether MFA/CAPTCHA is required."
            return result

        result["ok"] = True
        result["cookies"] = [
            {"name": cookie.name, "value": cookie.value, "domain": cookie.domain, "path": cookie.path}
            for cookie in session.cookies
        ]
        result["user_agent"] = DEFAULT_USER_AGENT
    except Exception as exc:
        result["error"] = str(exc)
    return result


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