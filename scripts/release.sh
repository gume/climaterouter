#!/usr/bin/env bash
#
# Build and (optionally) push a ClimateRouter release.
#
# The default is a dry run: it collects the version, the commits since the
# previous tag, the open issues and the release notes, then prints the exact
# commands it would run. Nothing is pushed until --push is given.
#
# The repository owner runs this script. Agents must not run it with --push.
#
# Usage:
#   scripts/release.sh                    # dry run, full checks
#   scripts/release.sh --skip-checks      # fast dry run
#   scripts/release.sh --push             # run checks, push main + tag, create release
#   scripts/release.sh --push --no-release # push main + tag only
#
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

DRY_RUN=1
RUN_CHECKS=1
CREATE_RELEASE=1
ASSUME_YES=0
FETCH=1

usage() {
  cat <<'EOF'
Usage: scripts/release.sh [options]

Options:
  --push             Actually push main, create/push the tag and create the
                     GitHub release. Without it the script only prints the plan.
  --skip-checks      Do not run pytest, ruff and mypy.
  --no-release       Do not create a GitHub release (push main and the tag only).
  --no-fetch         Do not fetch origin before checking the remote state.
  -y, --yes          Do not ask for confirmation with --push.
  -h, --help         Show this help.

The version is read from custom_components/climaterouter/manifest.json and must
match const.py VERSION and pyproject.toml. The previous release is the newest
v* tag. Release notes are generated from the commits since that tag.
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

warn() {
  printf 'warning: %s\n' "$*" >&2
}

print_cmd() {
  printf '    '
  local first=1 arg
  for arg in "$@"; do
    if (( first )); then
      first=0
    else
      printf ' '
    fi
    printf '%q' "$arg"
  done
  printf '\n'
}

run_cmd() {
  print_cmd "$@"
  "$@"
}

push_cmd() {
  if (( DRY_RUN )); then
    print_cmd "$@"
  else
    run_cmd "$@"
  fi
}

while (($#)); do
  case "$1" in
    --push) DRY_RUN=0 ;;
    --skip-checks) RUN_CHECKS=0 ;;
    --no-release) CREATE_RELEASE=0 ;;
    --no-fetch) FETCH=0 ;;
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

# ---------------------------------------------------------------------------
# Repository state
# ---------------------------------------------------------------------------
BRANCH="$(git symbolic-ref --quiet --short HEAD || true)"
[[ "$BRANCH" == "main" ]] || die "releases must be cut from main (current: ${BRANCH:-detached HEAD})"

if ! git diff --quiet || ! git diff --cached --quiet; then
  die "the working tree has uncommitted tracked changes; commit or stash them first"
fi

untracked="$(git ls-files --others --exclude-standard)"
if [[ -n "$untracked" ]]; then
  warn "untracked files are not part of the release:"
  printf '%s\n' "$untracked" | sed 's/^/  /' >&2
fi

if (( FETCH )); then
  printf 'Fetching origin...\n'
  git fetch --tags --quiet origin
fi

git rev-parse --verify --quiet refs/remotes/origin/main >/dev/null \
  || die "origin/main is not available; run git fetch origin"

BEHIND="$(git rev-list --count HEAD..origin/main)"
AHEAD="$(git rev-list --count origin/main..HEAD)"
(( BEHIND == 0 )) || die "main is $BEHIND commit(s) behind origin/main; pull/rebase first"

# ---------------------------------------------------------------------------
# Version and previous release
# ---------------------------------------------------------------------------
MANIFEST="custom_components/climaterouter/manifest.json"
CONST="custom_components/climaterouter/const.py"

version_from_manifest="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$MANIFEST" | head -n1)"
version_from_const="$(sed -n 's/^VERSION: Final = "\([^"]*\)".*/\1/p' "$CONST" | head -n1)"
version_from_pyproject="$(sed -n 's/^version = "\([^"]*\)".*/\1/p' pyproject.toml | head -n1)"

[[ -n "$version_from_manifest" ]] || die "could not read the version from $MANIFEST"
[[ -n "$version_from_const" ]] || die "could not read VERSION from $CONST"
[[ -n "$version_from_pyproject" ]] || die "could not read the version from pyproject.toml"

[[ "$version_from_manifest" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
  || die "manifest version is not X.Y.Z: $version_from_manifest"

if [[ "$version_from_manifest" != "$version_from_const" || \
      "$version_from_manifest" != "$version_from_pyproject" ]]; then
  die "version mismatch: manifest=$version_from_manifest const=$version_from_const pyproject=$version_from_pyproject"
fi

VERSION="$version_from_manifest"
TAG="v$VERSION"

PREVIOUS_TAG="$(git describe --tags --abbrev=0 --match 'v[0-9]*' 2>/dev/null || true)"
if [[ -n "$PREVIOUS_TAG" ]]; then
  RANGE="$PREVIOUS_TAG..HEAD"
else
  RANGE="HEAD"
fi

TAG_AT_HEAD=0
if git rev-parse --verify --quiet "refs/tags/$TAG" >/dev/null; then
  if [[ "$(git rev-list -n1 "$TAG")" == "$(git rev-parse HEAD)" ]]; then
    TAG_AT_HEAD=1
    warn "tag $TAG already exists at HEAD; it will not be recreated"
  else
    die "tag $TAG already exists at another commit; bump the version first"
  fi
fi

if [[ -n "$PREVIOUS_TAG" ]]; then
  COMMIT_COUNT="$(git rev-list --count "$RANGE")"
else
  COMMIT_COUNT="$(git rev-list --count HEAD)"
fi
(( COMMIT_COUNT > 0 )) || die "no commits found for the release notes"

# Optional GitHub compare link.
ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
SLUG=""
case "$ORIGIN_URL" in
  git@github.com:*) SLUG="${ORIGIN_URL#git@github.com:}"; SLUG="${SLUG%.git}" ;;
  https://github.com/*) SLUG="${ORIGIN_URL#https://github.com/}"; SLUG="${SLUG%.git}" ;;
esac

# ---------------------------------------------------------------------------
# Collect commits by conventional-commit type
# ---------------------------------------------------------------------------
features=()
fixes=()
docs=()
tests=()
chores=()
other=()

while IFS= read -r line; do
  [[ -n "$line" ]] || continue
  subject="${line#* }"
  case "$subject" in
    feat:*|feat\(*\):*) features+=("$line") ;;
    fix:*|fix\(*\):*) fixes+=("$line") ;;
    docs:*|docs\(*\):*) docs+=("$line") ;;
    test:*|test\(*\):*) tests+=("$line") ;;
    chore:*|chore\(*\):*) chores+=("$line") ;;
    *) other+=("$line") ;;
  esac
done < <(git log --format='%h %s' --no-merges "$RANGE")

# Open issues from the managed issue list, first line of each open item only.
open_issues=()
if [[ -f issues.txt ]]; then
  while IFS= read -r line; do
    open_issues+=("${line#- \[ \] }")
  done < <(grep -E '^- \[ \] ' issues.txt || true)
fi

# ---------------------------------------------------------------------------
# Release notes
# ---------------------------------------------------------------------------
NOTES_FILE="$(mktemp "${TMPDIR:-/tmp}/climaterouter-release-notes.XXXXXX")"
trap 'rm -f "$NOTES_FILE"' EXIT

append_section() {
  local title="$1"
  shift
  (($#)) || return 0
  {
    printf '## %s\n\n' "$title"
    printf -- '- %s\n' "$@"
    printf '\n'
  } >>"$NOTES_FILE"
}

{
  printf '# ClimateRouter %s\n\n' "$TAG"
  if [[ -n "$PREVIOUS_TAG" ]]; then
    printf 'Changes since %s.\n\n' "$PREVIOUS_TAG"
  else
    printf 'First tagged release.\n\n'
  fi
} >"$NOTES_FILE"

append_section "Features" "${features[@]}"
append_section "Fixes" "${fixes[@]}"
append_section "Documentation" "${docs[@]}"
append_section "Tests" "${tests[@]}"
append_section "Maintenance" "${chores[@]}"
append_section "Other changes" "${other[@]}"

if ((${#open_issues[@]})); then
  append_section "Known issues" "${open_issues[@]}"
fi

if [[ -n "$SLUG" ]]; then
  {
    if [[ -n "$PREVIOUS_TAG" ]]; then
      printf '[Full comparison](https://github.com/%s/compare/%s...%s)\n' "$SLUG" "$PREVIOUS_TAG" "$TAG"
    else
      printf '[Repository](https://github.com/%s)\n' "$SLUG"
    fi
  } >>"$NOTES_FILE"
fi

CHECKS_SUMMARY="skipped (--skip-checks)"
PYTHON_BIN="${PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x .venv/bin/python ]]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

if (( RUN_CHECKS )); then
  printf '\nRunning checks with %s...\n' "$PYTHON_BIN"

  if [[ -n "${RUFF:-}" ]]; then
    RUFF_CMD=("$RUFF")
  elif command -v ruff >/dev/null 2>&1; then
    RUFF_CMD=("ruff")
  elif "$PYTHON_BIN" -m ruff --version >/dev/null 2>&1; then
    RUFF_CMD=("$PYTHON_BIN" -m ruff)
  else
    die "ruff not found; install it or use --skip-checks"
  fi

  if [[ -n "${MYPY:-}" ]]; then
    MYPY_CMD=("$MYPY")
  elif command -v mypy >/dev/null 2>&1; then
    MYPY_CMD=("mypy")
  elif "$PYTHON_BIN" -m mypy --version >/dev/null 2>&1; then
    MYPY_CMD=("$PYTHON_BIN" -m mypy)
  else
    die "mypy not found; install it or use --skip-checks"
  fi

  run_cmd "$PYTHON_BIN" -m pytest -q
  run_cmd "${RUFF_CMD[@]}" check .
  run_cmd "${RUFF_CMD[@]}" format --check .
  run_cmd "${MYPY_CMD[@]}" custom_components/climaterouter
  CHECKS_SUMMARY="passed (pytest, ruff check, ruff format, mypy)"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
printf '\n=== Release plan ===\n'
printf 'Repository:      %s\n' "${SLUG:-$ROOT}"
printf 'Branch:          main (ahead %s, behind %s)\n' "$AHEAD" "$BEHIND"
printf 'Version:         %s (manifest, const.py and pyproject.toml agree)\n' "$VERSION"
printf 'Previous tag:    %s\n' "${PREVIOUS_TAG:-<none>}"
printf 'New tag:         %s%s\n' "$TAG" "$([[ $TAG_AT_HEAD == 1 ]] && printf ' (already at HEAD)')"
printf 'Commits:         %s\n' "$COMMIT_COUNT"
printf 'Checks:          %s\n' "$CHECKS_SUMMARY"
printf 'Open issues:     %s\n' "${#open_issues[@]}"
printf '\n--- Release notes ---\n'
cat "$NOTES_FILE"

printf '\n--- Commands ---\n'
push_cmd git push origin main
if (( ! TAG_AT_HEAD )); then
  push_cmd git tag -a "$TAG" -m "ClimateRouter $TAG"
fi
push_cmd git push origin "refs/tags/$TAG"
if (( CREATE_RELEASE )); then
  push_cmd gh release create "$TAG" --title "ClimateRouter $TAG" --notes-file "$NOTES_FILE"
else
  printf '    # GitHub release skipped (--no-release)\n'
fi

if (( DRY_RUN )); then
  printf '\nDry run only. Re-run with --push to publish the release.\n'
  exit 0
fi

if (( ! ASSUME_YES )); then
  printf '\n'
  read -r -p "Push main, tag $TAG and create the GitHub release? [y/N] " answer
  [[ "$answer" =~ ^[Yy]$ ]] || { printf 'Aborted.\n'; exit 1; }
fi

if (( CREATE_RELEASE )); then
  command -v gh >/dev/null 2>&1 || die "gh is required for the GitHub release; use --no-release"
  gh auth status >/dev/null 2>&1 || die "gh is not authenticated; run gh auth login or use --no-release"
fi

if (( TAG_AT_HEAD )); then
  git push origin main
  git push origin "refs/tags/$TAG"
else
  git tag -a "$TAG" -m "ClimateRouter $TAG"
  git push --atomic origin main "refs/tags/$TAG"
fi

if (( CREATE_RELEASE )); then
  if gh release view "$TAG" >/dev/null 2>&1; then
    warn "GitHub release $TAG already exists; leaving it unchanged"
  else
    gh release create "$TAG" --title "ClimateRouter $TAG" --notes-file "$NOTES_FILE"
  fi
fi

printf '\nPublished %s. Next: refresh the Marketplace in the test Home Assistant and verify the release.\n' "$TAG"
