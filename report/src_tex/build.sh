#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -d "$HOME/.texlive/2026/bin/x86_64-linux" ]; then
  export PATH="$HOME/.texlive/2026/bin/x86_64-linux:$PATH"
fi

xelatex -no-pdf -interaction=nonstopmode -halt-on-error tjumain.tex
xelatex -no-pdf -interaction=nonstopmode -halt-on-error tjumain.tex
xelatex -no-pdf -interaction=nonstopmode -halt-on-error tjumain.tex
xdvipdfmx -o tjumain-build.pdf tjumain.xdv
mv tjumain-build.pdf "../课程报告.pdf"
