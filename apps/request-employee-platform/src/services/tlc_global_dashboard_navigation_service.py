from __future__ import annotations

from fastapi import Response


MARKER = "TLC_GLOBAL_DASHBOARD_RETURN_LINK_R1"
EXCLUDED_PATHS = {"/dashboard", "/login", "/change-password"}


def inject_dashboard_link(html: str, path: str) -> str:
    if (
        path in EXCLUDED_PATHS
        or MARKER in html
        or 'href="/dashboard"' in html
        or "href='/dashboard'" in html
    ):
        return html
    fragment = f"""
<!-- {MARKER} -->
<style>
#tlc-global-dashboard-link{{position:fixed;right:22px;bottom:22px;z-index:2147483000;
display:inline-flex;align-items:center;gap:6px;padding:11px 16px;border-radius:999px;
background:#173a70;color:#fff;text-decoration:none;font:700 14px/1.2 "Microsoft YaHei","Segoe UI",sans-serif;
box-shadow:0 8px 24px rgba(15,23,42,.28);border:1px solid rgba(255,255,255,.35)}}
#tlc-global-dashboard-link:hover{{background:#0f2f61;transform:translateY(-1px)}}
</style>
<a id="tlc-global-dashboard-link" href="/dashboard" aria-label="Return to Dashboard">&#8592; &#36820;&#22238; Dashboard</a>
"""
    if "</body>" in html:
        return html.replace("</body>", fragment + "</body>", 1)
    return html + fragment


def install_global_dashboard_navigation(app) -> None:
    @app.middleware("http")
    async def global_dashboard_navigation(request, call_next):
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if response.status_code != 200 or "text/html" not in content_type:
            return response
        body_iterator = getattr(response, "body_iterator", None)
        if body_iterator is None:
            return response
        body = b"".join([chunk async for chunk in body_iterator])
        try:
            html = body.decode("utf-8")
        except UnicodeDecodeError:
            headers = dict(response.headers)
            headers.pop("content-length", None)
            headers.pop("content-type", None)
            return Response(
                content=body,
                status_code=response.status_code,
                headers=headers,
                media_type="application/octet-stream",
                background=response.background,
            )
        decorated = inject_dashboard_link(html, request.url.path)
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers.pop("content-type", None)
        return Response(
            content=decorated,
            status_code=response.status_code,
            headers=headers,
            media_type="text/html",
            background=response.background,
        )
