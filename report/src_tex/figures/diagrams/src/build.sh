#!/bin/sh
set -eu
export PATH="/home/wenli/.texlive/2026/bin/x86_64-linux:${PATH}"
cd "$(dirname "$0")"
for f in d01-roadmap d02-project-stats d03-architecture d04-data-pipeline d05-repair-protocol d06-frontend-modules d07-qa-matrix d08-research-cube d09-collab-git d10-ast-v2-pipeline d11-bootstrap-cluster; do
  xelatex -interaction=nonstopmode -halt-on-error "${f}.tex" > /dev/null
  cp "${f}.pdf" "../${f}.pdf"
done
echo "ALL_DIAGRAMS_BUILT"
