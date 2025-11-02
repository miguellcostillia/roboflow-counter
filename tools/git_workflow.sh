#!/usr/bin/env bash
set -e

# Branch mit Zeitpräfix anlegen: nb feat title-of-thing
nb() {
  local kind="$1"; shift || true
  local rest="$*"
  local ts; ts=$(date +"%Y%m%d-%H%M")
  local slug; slug=$(echo "$rest" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9\-]/-/g;s/--*/-/g;s/^-//;s/-$//')
  [ -z "$slug" ] && slug="work"
  local br="${ts}_${kind}-${slug}"
  git switch -c "$br"
  echo "✅ new branch: $br"
}

# Aktuellen Branch pushen + PR erstellen/öffnen (Browser)
prup() {
  local br; br=$(git branch --show-current)
  if [ "$br" = "main" ]; then
    echo "❌ Du bist auf 'main'. Bitte Feature-Branch verwenden."; return 1
  fi
  git push -u origin "$br"
  if command -v gh >/dev/null 2>&1; then
    gh pr create --fill --base main --head "$br" || gh pr view --web
  else
    echo "➡️  Öffne GitHub und klicke auf 'Compare & pull request' für $br"
  fi
}

# Nach Merge: main synchronisieren & Branch aufräumen
finish_branch() {
  local br; br=$(git branch --show-current)
  if [ "$br" = "main" ]; then
    echo "ℹ️ Schon auf main."; return 0
  fi
  git switch main
  git pull --ff-only
  git branch -d "$br" || true
  git push origin --delete "$br" 2>/dev/null || true
  git fetch --prune
  echo "✅ Branch '$br' bereinigt; main aktuell."
}

# main nur ff-only holen (Safety)
sync_main() {
  git switch main
  git fetch origin
  git pull --ff-only origin main
  echo "✅ main synched."
}
