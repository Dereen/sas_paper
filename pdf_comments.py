#!/usr/bin/env python3
"""Keep PDF review comments alive across latexmk rebuilds.

latexmk overwrites root.pdf, and annotations live inside the PDF, so every
rebuild destroys the review. Archiving a copy elsewhere preserves the record but
not the thing the reviewer actually opens. This keeps a sidecar JSON of every
comment ever seen and re-applies it to the freshly built PDF.

  collect [pdf...]   read annotations out of the given PDFs (default root.pdf)
                     and merge them into root.annots.json. Comments are keyed by
                     (note, anchor) so re-collecting is idempotent.
  restore [pdf]      re-apply every stored comment to the PDF (default root.pdf)

A comment is re-anchored by SEARCHING the new PDF for the text it was attached
to. Where that text still exists the highlight lands exactly where it did. Where
it no longer exists -- which is the normal case for a comment that has been
acted on, since acting on it changed the words -- the comment is placed as a
sticky note in the page margin and its status says so, rather than being dropped
or silently moved somewhere wrong.
"""
import json
import os
import re
import sys

import fitz

STORE = 'root.annots.json'
MINE = 'review'   # title stamped on every annotation this script places
YELLOW, GREY = (1, 0.85, 0.2), (0.6, 0.6, 0.6)


def anchor_of(page, a):
    """The cleanest single fragment of the highlighted text, for re-searching."""
    q = a.vertices or []
    if a.type[1] != 'Highlight' or not q:
        return ''
    frags = [' '.join(page.get_textbox(fitz.Quad(q[k:k + 4]).rect).split())
             for k in range(0, len(q), 4)]
    frags = [f for f in frags if len(f) > 6]
    return max(frags, key=len) if frags else ''


def anchor_full_of(page, a):
    """The whole highlighted span, de-duplicated. A short fragment like
    'Gazebo simulation' occurs many times in the paper and re-anchors onto the
    wrong one; the full span is far likelier to be unique."""
    q = a.vertices or []
    if a.type[1] != 'Highlight' or not q:
        return ''
    out = []
    for k in range(0, len(q), 4):
        t = ' '.join(page.get_textbox(fitz.Quad(q[k:k + 4]).rect).split())
        if t and (not out or out[-1] != t):
            out.append(t)
    return ' '.join(out)


def collect(paths):
    store = json.load(open(STORE)) if os.path.exists(STORE) else []
    seen = {(c['note'], c['anchor']) for c in store}
    added = 0
    for p in paths:
        d = fitz.open(p)
        for i, page in enumerate(d):
            for a in page.annots() or []:
                # annotations this script wrote are already in the store; only a
                # reviewer's own comments are new. Without this the round trip
                # re-collects its own output and the store grows every build.
                if a.info.get('title', '') == MINE:
                    continue
                raw = a.info.get('content', '').strip()
                note, _, done = raw.partition('\n\nDONE:')
                key = (note.strip(), anchor_of(page, a))
                if key in seen:
                    continue
                seen.add(key)
                store.append({'note': note.strip(), 'anchor': key[1],
                              'anchor_full': anchor_full_of(page, a),
                              'done': done.strip(), 'page_hint': i + 1,
                              'source': os.path.basename(p)})
                added += 1
        d.close()
    json.dump(store, open(STORE, 'w'), indent=1)
    print(f'{added} new, {len(store)} stored -> {STORE}')


def restore(path):
    store = json.load(open(STORE))
    d = fitz.open(path)
    exact = drifted = 0
    for c in store:
        body = c['note'] + (f"\n\nDONE: {c['done']}" if c['done'] else '')
        rects, pno = [], None
        probes = [re.sub(r'\s+', ' ', p).strip()
                  for p in (c.get('anchor_full', ''), c.get('anchor', '')) if p]
        # the page the comment was made on is tried first, so a short anchor that
        # also occurs elsewhere does not drag the comment onto another page
        hint = min(max(c.get('page_hint', 1), 1), d.page_count) - 1
        # only the hinted page and its neighbours: text reflows across a page
        # break, but a comment never belongs on the far side of the paper. If the
        # anchor is gone from here it was edited away, so pin it rather than hunt
        # for the same words somewhere else.
        order = [p for p in (hint, hint - 1, hint + 1) if 0 <= p < d.page_count]
        for probe in probes:
            if len(probe) < 8:
                continue
            for i in order:
                hits = d[i].search_for(probe)
                if hits:
                    rects, pno = hits, i
                    break
            if rects:
                break
        if rects:
            page = d[pno]
            an = page.add_highlight_annot(rects)
            an.set_colors(stroke=YELLOW)
            exact += 1
        else:
            page = d[min(c['page_hint'], d.page_count) - 1]
            y = 40 + 16 * (drifted % 40)
            an = page.add_text_annot(fitz.Point(page.rect.width - 26, y), '')
            an.set_colors(stroke=GREY)
            body += ('\n\n[the text this was attached to no longer appears -- '
                     'it was changed in response. Pinned to the margin.]'
                     '\n\nIt referred to: ' + repr(c.get('anchor_full') or c.get('anchor') or '(none)'))
            drifted += 1
        an.set_info(content=body, title='review')
        an.update()
    d.saveIncr() if d.can_save_incrementally() else d.save(path + '.tmp')
    if os.path.exists(path + '.tmp'):
        os.replace(path + '.tmp', path)
    print(f'{exact} re-anchored in place, {drifted} pinned to the margin, '
          f'{len(store)} total -> {path}')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'restore'
    if cmd == 'collect':
        collect(sys.argv[2:] or ['root.pdf'])
    else:
        restore(sys.argv[2] if len(sys.argv) > 2 else 'root.pdf')
