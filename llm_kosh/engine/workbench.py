import os
import sys
import json
import shutil
import webbrowser
import zipfile
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, HTTPServer

from llm_kosh.core.utils import write_json, append_ledger, slugify, now_iso
from llm_kosh.core.memory import ensure_root
from llm_kosh.engine.search import rebuild_index, get_db

def _html_escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

_CSS = """
:root{--bg:#0f1115;--card:#181b22;--ink:#e6e8ee;--mut:#9aa3b2;--acc:#6ea8fe;--line:#262a33}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
header{padding:24px 28px;border-bottom:1px solid var(--line)}
header h1{margin:0;font-size:18px}header .mut{color:var(--mut);font-size:13px}
.wrap{max-width:960px;margin:0 auto;padding:24px 28px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.card h3{margin:0 0 8px;font-size:14px}.tag{display:inline-block;font-size:11px;color:var(--mut);
border:1px solid var(--line);border-radius:6px;padding:1px 7px;margin-right:6px}
.search{width:100%;padding:10px 12px;background:var(--card);border:1px solid var(--line);
border-radius:8px;color:var(--ink);margin-bottom:16px}
.muted{color:var(--mut)}.list li{margin:4px 0}h2{font-size:15px;margin:22px 0 10px;color:var(--mut)}
footer{color:var(--mut);font-size:12px;padding:24px 28px;border-top:1px solid var(--line)}
nav{padding: 0 28px; border-bottom: 1px solid var(--line); display: flex; gap: 16px; background: var(--card);}
nav a{display: block; padding: 12px 0; color: var(--mut); font-size: 14px;}
nav a:hover{color: var(--ink);}
"""

_SEARCH_JS = """
let DATA=[];
fetch('data/memory_map.json').then(r=>r.json()).then(d=>{DATA=d||[]});
function go(q){
  q=(q||'').toLowerCase().trim();
  const out=document.getElementById('results');
  if(!q){out.innerHTML='';return;}
  const hits=DATA.filter(x=>(x.title+' '+x.project+' '+x.kind).toLowerCase().includes(q)).slice(0,50);
  out.innerHTML=hits.map(h=>`<li><span class="tag">${h.kind}</span><a href="${h.href}">${h.title}</a>${h.project?' <span class="muted">· '+h.project+'</span>':''}</li>`).join('')||'<li class="muted">no matches</li>';
}
"""

def _page(title: str, body_html: str) -> str:
    nav_links = [
        ("Dashboard", "index.html"),
        ("Projects", "projects.html"),
        ("Decisions", "decisions.html"),
        ("Search", "search.html")
    ]
    nav_html = "".join(
        f"<a href='{href}' style='{'font-weight:bold;color:var(--ink)' if title == label else ''}'>{label}</a>"
        for label, href in nav_links
    )
    
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{_html_escape(title)}</title><link rel=stylesheet href='style.css'></head>"
            f"<body><header><h1>LlmKosh Workbench</h1>"
            f"<div class=mut>{_html_escape(title)}</div></header>"
            f"<nav>{nav_html}</nav>"
            f"<div class=wrap>{body_html}</div>"
            f"<footer>Generated {now_iso()} · local static site · stdlib only</footer></body></html>")

def workbench_build(root: Path, include_private: bool = False) -> Path:
    """Generate a local static HTML dashboard under exports/workbench/. No server, no framework."""
    ensure_root(root)
    rebuild_index(root)
    site = root / "exports" / "workbench"
    if site.exists():
        shutil.rmtree(site)
    (site / "projects").mkdir(parents=True)
    (site / "decisions").mkdir(parents=True)
    (site / "data").mkdir(parents=True)
    (site / "assets").mkdir(parents=True)

    (site / "style.css").write_text(_CSS, encoding="utf-8")
    (site / "search.js").write_text(_SEARCH_JS, encoding="utf-8")

    conn = get_db(root)
    vis_filter = "" if include_private else " AND visibility NOT IN ('private','blocked','quarantine')"
    docs = conn.execute(
        f"SELECT id,kind,title,project,status,path,body FROM documents WHERE 1=1{vis_filter}"
    ).fetchall()
    
    excluded = 0
    if not include_private:
        excluded = conn.execute("SELECT COUNT(*) FROM documents WHERE "
                              "visibility IN ('private','blocked','quarantine')").fetchone()[0]
    conn.close()

    projects = sorted({d[3] for d in docs if d[3]})
    decisions = [d for d in docs if d[1] == "decision"]
    search_items = []

    # decision pages
    for d in decisions:
        did, _, title, project, status, path, body = d
        fn = f"decisions/{slugify(did)}.html"
        html = (f"<p><a href='../decisions.html'>← back to decisions</a></p>"
                f"<div class=card><h3>{_html_escape(title)}</h3>"
                f"<p><span class=tag>decision</span>"
                f"{('<span class=tag>'+_html_escape(project)+'</span>') if project else ''}"
                f"<span class=tag>{_html_escape(status)}</span></p>"
                f"<pre style='white-space:pre-wrap'>{_html_escape(body)}</pre>"
                f"<p class=muted>source: {_html_escape(path)}</p></div>")
        (site / fn).write_text(_page(title, html), encoding="utf-8")
        search_items.append({"title": title, "project": project, "kind": "decision", "href": fn})

    # project pages
    for proj in projects:
        items = [d for d in docs if d[3] == proj]
        fn = f"projects/{slugify(proj)}.html"
        rows = "".join(
            f"<li><span class=tag>{d[1]}</span>"
            + (f"<a href='../decisions/{slugify(d[0])}.html'>{_html_escape(d[2])}</a>"
               if d[1] == "decision" else _html_escape(d[2]))
            + f" <span class=muted>· {_html_escape(d[4])}</span></li>"
            for d in items)
        html = (f"<p><a href='../projects.html'>← back to projects</a></p><h2>{_html_escape(proj)}</h2>"
                f"<ul class=list>{rows}</ul>")
        (site / fn).write_text(_page(f"Project · {proj}", html), encoding="utf-8")
        search_items.append({"title": proj, "project": proj, "kind": "project", "href": fn})

    write_json(site / "data" / "memory_map.json", search_items)
    write_json(site / "data" / "intake.json", [])
    write_json(site / "data" / "receipts.json", [])
    write_json(site / "data" / "corrections.json", [])
    write_json(site / "data" / "projects.json", projects)
    write_json(site / "data" / "decisions.json", [{"id": d[0], "title": d[2], "project": d[3]} for d in decisions])

    # Index page
    proj_cards = "".join(
        f"<div class=card><h3><a href='projects/{slugify(p)}.html'>{_html_escape(p)}</a></h3>"
        f"<p class=muted>{sum(1 for d in docs if d[3]==p)} item(s)</p></div>" for p in projects)
    dec_list = "".join(
        f"<li><a href='decisions/{slugify(d[0])}.html'>{_html_escape(d[2])}</a>"
        f"{(' <span class=muted>· '+_html_escape(d[3])+'</span>') if d[3] else ''}</li>"
        for d in decisions if d[4] == "active")
    note = (f"<p class=muted>{excluded} private/blocked item(s) excluded. "
            f"Re-run with --include-private to include them.</p>") if excluded else ""
    body = (f"<h2>Projects</h2><div class=grid>{proj_cards or '<p class=muted>none</p>'}</div>"
            f"<h2>Active decisions</h2><ul class=list>{dec_list or '<li class=muted>none</li>'}</ul>"
            f"{note}")
    (site / "index.html").write_text(_page("Dashboard", body), encoding="utf-8")

    # Search page
    search_body = (f"<input class=search placeholder='Search memories…' oninput='go(this.value)'>"
            f"<ul class=list id=results></ul>"
            f"<script src='search.js'></script>")
    (site / "search.html").write_text(_page("Search", search_body), encoding="utf-8")

    # Projects page
    (site / "projects.html").write_text(_page("Projects", f"<div class=grid>{proj_cards or '<p class=muted>none</p>'}</div>"), encoding="utf-8")

    # Decisions page
    (site / "decisions.html").write_text(_page("Decisions", f"<ul class=list>{dec_list or '<li class=muted>none</li>'}</ul>"), encoding="utf-8")

    # Empty stubs
    stub_pages = ["intake", "corrections", "receipts", "packs"]
    for stub in stub_pages:
        (site / f"{stub}.html").write_text(_page(stub.capitalize(), f"<p class=muted>No {stub} data available in this version.</p>"), encoding="utf-8")

    append_ledger(root, "workbench.built",
                  {"path": str(site.relative_to(root)), "include_private": include_private,
                   "projects": len(projects), "decisions": len(decisions)})
    print(f"Generated workbench: {site / 'index.html'}")
    print(f"  projects: {len(projects)} · decisions: {len(decisions)}"
          + (f" · excluded private/blocked: {excluded}" if excluded else ""))
    return site

def workbench_serve(root: Path, port: int = 8765):
    """Serve the static workbench locally."""
    site = root / "exports" / "workbench"
    if not site.exists() or not (site / "index.html").exists():
        print("Workbench not built. Building now...")
        site = workbench_build(root, include_private=False)
    
    os.chdir(str(site))
    server_address = ('', port)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print(f"Serving workbench at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\\nShutting down server.")
        httpd.server_close()

def workbench_open(root: Path):
    """Open the local workbench in the default browser."""
    site = root / "exports" / "workbench"
    if not site.exists() or not (site / "index.html").exists():
        print("Workbench not built. Building now...")
        site = workbench_build(root, include_private=False)
    
    index_path = site / "index.html"
    webbrowser.open(index_path.as_uri())

def workbench_export(root: Path, safe: bool = True):
    """Export the workbench as a zip file."""
    site = root / "exports" / "workbench"
    
    if safe:
        print("Building safe export (no private content)...")
        workbench_build(root, include_private=False)
    elif not site.exists():
        print("Building full export...")
        workbench_build(root, include_private=True)

    export_zip = root / "exports" / "workbench_export.zip"
    
    with zipfile.ZipFile(export_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in site.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(site))
    
    print(f"Exported workbench to {export_zip}")
    append_ledger(root, "workbench.exported", {"path": str(export_zip.relative_to(root)), "safe": safe})

def workbench_clean(root: Path):
    """Delete the generated workbench."""
    site = root / "exports" / "workbench"
    if site.exists():
        shutil.rmtree(site)
        print(f"Cleaned {site}")
    else:
        print("Workbench not found.")
