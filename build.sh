#!/bin/bash
# Build the paper WITHOUT losing the review comments.
#
# latexmk overwrites root.pdf, and annotations live inside the PDF, so a plain
# `latexmk -pdf root.tex` silently destroys every comment on it. Always build
# through this script: it banks the comments first and puts them back after.
set -e
cd "$(dirname "$0")"
PY=/opt/homebrew/bin/python3

$PY pdf_comments.py collect root.pdf          # bank anything new before it is lost
latexmk -pdf -interaction=nonstopmode root.tex
# comments are NOT put back on the built PDF (reviewer's choice, 2026-09-07);
# the record of every comment and what was done lives in root.annots.json
