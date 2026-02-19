#!/usr/bin/env bash
set -euo pipefail

REMOTE="${1:-huggingface}"
TARGET_BRANCH="${2:-main}"
DEPLOY_BRANCH="hf-deploy-$(date +%Y%m%d%H%M%S)"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "Error: run this script inside a git repository." >&2
  exit 1
fi

if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
  echo "Error: remote '$REMOTE' does not exist." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Error: working tree is not clean. Commit or stash changes first." >&2
  exit 1
fi

ORIGINAL_REF="$(git symbolic-ref --short -q HEAD || true)"
if [[ -z "$ORIGINAL_REF" ]]; then
  ORIGINAL_REF="$(git rev-parse --short HEAD)"
fi

CHECKED_OUT_DEPLOY_BRANCH=0

cleanup() {
  local exit_code=$?
  trap - EXIT

  if [[ "$CHECKED_OUT_DEPLOY_BRANCH" -eq 1 ]]; then
    git checkout -q "$ORIGINAL_REF" >/dev/null 2>&1 || true
  fi

  if git show-ref --verify --quiet "refs/heads/$DEPLOY_BRANCH"; then
    git branch -D "$DEPLOY_BRANCH" >/dev/null 2>&1 || true
  fi

  if [[ "$exit_code" -eq 0 ]]; then
    echo "Pushed snapshot to $REMOTE/$TARGET_BRANCH"
  fi

  exit "$exit_code"
}

trap cleanup EXIT

git checkout --orphan "$DEPLOY_BRANCH"
CHECKED_OUT_DEPLOY_BRANCH=1

git add -A
git commit -m "Deploy snapshot to $REMOTE/$TARGET_BRANCH"
git push --force "$REMOTE" "$DEPLOY_BRANCH:$TARGET_BRANCH"
