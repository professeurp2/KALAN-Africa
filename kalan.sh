#!/usr/bin/env sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Kalan en une commande (Linux, macOS). Première fois : installe tout, avec Internet.
set -e
cd "$(dirname "$0")"
export PYTHONUTF8=1
if [ ! -f .venv/.kalan-installe ]; then
  echo "Première installation de Kalan : quelques minutes, Internet requis..."
  [ -x .venv/bin/python ] || python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
  echo ok > .venv/.kalan-installe
fi
exec .venv/bin/python -m kalan.lancer "$@"
