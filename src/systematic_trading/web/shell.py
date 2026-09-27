"""Shared visual contract for every application workspace and strategy report."""
import re

CSS = """
:root{--bg:#edf1f6;--panel:#fff;--text:#1b2b42;--muted:#65748a;--line:#dfe6ee;--line-soft:#edf1f6;--focus:#315bc2;--good:#246b52;--warn:#93691e;--bad:#a83232}
body{margin:0;background:var(--bg);color:var(--text);font-family:"Segoe UI",system-ui,sans-serif;font-variant-numeric:tabular-nums}
body>header{box-sizing:border-box;min-height:68px;height:auto;padding:16px 26px;display:flex;align-items:center;justify-content:space-between;gap:18px;background:#13243b;color:#fff;border:0}
body>header h1{font-size:17px;font-weight:650;letter-spacing:.01em;margin:0;color:#fff}
body>header .actions{display:flex;flex-wrap:wrap;gap:8px}
body>header .button{background:transparent;color:#d7e2f2;border:1px solid transparent;border-radius:7px;min-height:34px;padding:7px 11px;text-decoration:none;font-size:13px}
body>header .button[aria-current=page]{background:#2b4261;color:white}
body>header .button:hover{background:#243b58;color:white}
main{min-width:0}.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;box-shadow:0 1px 2px #13243b05;overflow:hidden}
.button,button,input,select{font:inherit}button,.button{border-radius:7px}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #7695de;outline-offset:2px}
.portfolio-context{margin:0 0 18px;padding:12px 16px;border:1px solid var(--line);border-radius:10px;background:#fff;color:var(--muted);font-size:13px;display:flex;gap:12px;flex-wrap:wrap}
.portfolio-context strong{color:var(--text)}
#economic-reconciliation{padding:16px 18px;margin-bottom:18px;line-height:1.5}#economic-reconciliation h3{margin:0 0 12px}#economic-reconciliation p:last-child{margin-bottom:0}
@media(max-width:650px){body>header{padding:14px;align-items:flex-start;flex-direction:column;gap:10px}body>header .actions{gap:3px}body>header .button{padding:6px 8px}}
"""


def with_app_shell(html: str, page: str) -> str:
    if 'id="application-shell-style"' in html:
        return html
    titles = {"trading":"Trading operations", "strategies":"Strategies", "system":"System", "market":"Market Data"}
    links = [("trading", "Trading", "/operator"), ("strategies", "Strategies", "/strategies"),
             ("system", "System", "/platform"), ("market", "Market Data", "/platform/market-data-audit")]
    nav = ''.join(f'<a class="button" href="{url}"'+(' aria-current="page"' if key == page else '')+f'>{label}</a>' for key,label,url in links)
    header = f'<header><h1>SYSTEMATIC / {titles[page]}</h1><nav class="actions" aria-label="Application">{nav}</nav></header>'
    html = re.sub(r'<header\b[^>]*>.*?</header>', lambda _:header, html, count=1, flags=re.S)
    return html.replace('</head>', '<style id="application-shell-style">'+CSS+'</style></head>', 1)
