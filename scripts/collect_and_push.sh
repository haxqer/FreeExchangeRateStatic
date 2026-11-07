#!/usr/bin/env bash
# Hourly job on the collection server: collect this hour, commit, and push to main.
# GitHub Pages publishes main after each push.
set -uo pipefail

# Run from a function so a pull that updates this file cannot change the running job.
main() {
  cd "$(dirname "$0")/.." || return 1

  # Rebase a snapshot commit left by an earlier failed push onto the latest main.
  if ! git pull --rebase --quiet origin main; then
    git rebase --abort 2>/dev/null
    echo 'Could not update from origin; collecting on the local copy' >&2
  fi

  python3 scripts/collect_rates.py
  local status=$?

  # Keep a collected hour even when updating latest or rebuilding indexes failed.
  git add latest.json history/ || return 1
  if ! git diff --cached --quiet; then
    git commit --quiet -m 'Collect hourly exchange rate snapshot' || return 1
  fi
  # Unpushed commits stay local and are pushed by the next run.
  git push --quiet origin HEAD:main || return 1
  return "$status"
}

main
exit
