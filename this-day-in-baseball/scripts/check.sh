#!/usr/bin/env bash
# One command that runs every quality check on the site.
# Run it from anywhere inside the project:   bash scripts/check.sh
# It only reads files. It never changes anything.
cd "$(dirname "$0")/.." || exit 1

if ! command -v node >/dev/null 2>&1 || ! command -v npx >/dev/null 2>&1; then
  echo "Node.js is not installed, so the checks cannot run."
  echo "Install it from https://nodejs.org (the LTS button), then try again."
  exit 2
fi

fail=0
run() {
  name="$1"; shift
  printf '\n== %s ==\n' "$name"
  if "$@"; then echo "ok"; else echo "PROBLEMS FOUND: $name"; fail=1; fi
}

run "JavaScript syntax" bash -c 'for f in app.js more.js; do node --check "$f" || exit 1; done'
run "Python syntax" python3 -I -c '
import ast, glob, sys
bad = 0
for f in sorted(glob.glob("scripts/*.py")):
    try:
        ast.parse(open(f, encoding="utf-8").read(), f)
    except SyntaxError as e:
        print(f"{f}: line {e.lineno}: {e.msg}")
        bad = 1
sys.exit(bad)'
run "HTML (HTMLHint)" npx --yes htmlhint@1 index.html about.html
run "CSS (Stylelint)" npx --yes stylelint@16 style.css
run "JavaScript (ESLint)" npx --yes eslint@9 app.js more.js

printf '\n'
if [ "$fail" -eq 0 ]; then echo "All checks passed."; else echo "Some checks found problems. Read the lines above."; fi
exit "$fail"
