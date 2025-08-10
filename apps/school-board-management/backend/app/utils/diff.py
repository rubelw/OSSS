import html, difflib

CSS = """<style>
.redline .del { background:#ffecec; color:#b71c1c; text-decoration: line-through; }
.redline .ins { background:#e8f5e9; color:#1b5e20; }
.redline { line-height:1.6; font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }
.redline p { margin: 0.6em 0; }
</style>"""

def redline_html(old: str, new: str) -> str:
    a = old.split()
    b = new.split()
    sm = difflib.SequenceMatcher(None, a, b)
    out = [CSS, '<div class="redline">']
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.append(html.escape(" ".join(a[i1:i2])) + " ")
        elif tag == "delete":
            out.append('<span class="del">' + html.escape(" ".join(a[i1:i2])) + "</span> ")
        elif tag == "insert":
            out.append('<span class="ins">' + html.escape(" ".join(b[j1:j2])) + "</span> ")
        elif tag == "replace":
            if i1 != i2:
                out.append('<span class="del">' + html.escape(" ".join(a[i1:i2])) + "</span> ")
            if j1 != j2:
                out.append('<span class="ins">' + html.escape(" ".join(b[j1:j2])) + "</span> ")
    out.append("</div>")
    return "".join(out)
