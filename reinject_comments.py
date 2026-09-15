#!/usr/bin/env python3
"""Put the highlight comments of an older root.pdf back onto the current one (after a rebuild has
stripped them). Each comment is re-anchored by searching its highlighted words on the same page.
Usage: reinject_comments.py <old.pdf> <current.pdf>"""
import sys, shutil, fitz
src = fitz.open(sys.argv[1]); dst = fitz.open(sys.argv[2]); n = 0
for pno, p in enumerate(src):
    words = p.get_text('words')
    for a in p.annots() or []:
        v = a.vertices; quads = [fitz.Quad(v[i:i + 4]) for i in range(0, len(v), 4)] if v else [fitz.Rect(a.rect).quad]
        sel = set()
        for q in quads:
            for w in words:
                wr = fitz.Rect(w[:4])
                if wr.intersects(q.rect) and (wr & q.rect).get_area() > 0.5 * wr.get_area(): sel.add((w[3], w[0], w[4]))
        anchor = ' '.join(s[2] for s in sorted(sel)); page = dst[pno]; hits = []
        if anchor:
            key = ' '.join(anchor.split()[:6])
            hits = [h for h in page.search_for(key) if abs(h.y0 - a.rect.y0) < 80] or page.search_for(key)
        an = page.add_highlight_annot(quads=[h.quad for h in hits] if hits else quads)
        an.set_info(content=a.info.get('content', ''), title='restored'); an.update(); n += 1
tmp = sys.argv[2] + '.tmp'; dst.save(tmp); dst.close(); shutil.move(tmp, sys.argv[2])
print(f'{n} comments put back onto {sys.argv[2]}')
