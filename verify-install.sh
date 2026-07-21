#!/bin/sh
set -eu

usage() {
  printf '%s\n' \
    'Usage:' \
    '  sh verify-install.sh --claude --personal' \
    '  sh verify-install.sh --codex --personal' \
    '  sh verify-install.sh --claude --project-dir "/absolute/path/to/project"' \
    '  sh verify-install.sh --codex --project-dir "/absolute/path/to/project"'
  exit 2
}

fail() {
  code=$1
  shift
  printf 'FAIL: %s\n' "$*" >&2
  exit "$code"
}

platform=
scope=
project_dir=

while [ "$#" -gt 0 ]; do
  case "$1" in
    --claude|--codex)
      [ -z "$platform" ] || usage
      platform=${1#--}
      shift
      ;;
    --personal)
      [ -z "$scope" ] || usage
      scope=personal
      shift
      ;;
    --project-dir)
      [ -z "$scope" ] || usage
      [ "$#" -ge 2 ] || usage
      scope=project
      project_dir=$2
      shift 2
      ;;
    *) usage ;;
  esac
done

[ -n "$platform" ] && [ -n "$scope" ] || usage
command -v python3 >/dev/null 2>&1 || fail 3 'python3 is required.'
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' \
  || fail 3 'Python 3.8 or newer is required.'

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P) \
  || fail 3 'Could not resolve the release directory.'
source_dir=$script_dir/plugins/dravux/skills/dravux

if [ "$scope" = personal ]; then
  case ${HOME-} in
    /*) : ;;
    *) fail 3 'HOME must be set to an absolute path.' ;;
  esac
  [ "$HOME" != / ] || fail 3 'Refusing to use / as HOME.'
  base_dir=$HOME
else
  [ -d "$project_dir" ] && [ ! -L "$project_dir" ] \
    || fail 3 'The project directory must exist and must not be a symlink.'
  base_dir=$(CDPATH= cd -- "$project_dir" && pwd -P) \
    || fail 3 'Could not resolve the project directory.'
fi

case "$platform" in
  claude) destination=$base_dir/.claude/skills/dravux ;;
  codex) destination=$base_dir/.agents/skills/dravux ;;
  *) usage ;;
esac

printf 'Platform: %s\nScope: %s\nDestination: %s\n' "$platform" "$scope" "$destination"
[ -d "$destination" ] && [ ! -L "$destination" ] \
  || fail 4 'Installed destination is missing, not a directory, or is a symlink.'

[ -z "$(find "$destination" -type l -print -quit)" ] \
  || fail 5 'Installed destination contains a symlink.'
[ -z "$(find "$destination" ! -type d ! -type f -print -quit)" ] \
  || fail 5 'Installed destination contains a special file.'

diff -qr "$source_dir" "$destination" >/dev/null \
  || fail 5 'Installed files differ from the verified release source.'
grep -q '^name: dravux$' "$destination/SKILL.md" \
  || fail 5 'Installed SKILL.md frontmatter is invalid.'

(CDPATH= cd / && python3 -B "$destination/scripts/dravux_contract.py" "$destination/assets/report-template.json") \
  | grep -q '^VALID Dravux report' \
  || fail 5 'The standalone installed validator did not return VALID.'
(CDPATH= cd / && python3 -B "$destination/scripts/dravux_run.py" validate "$destination/assets/run-envelope-template.json") \
  | grep -q '^DRAVUX RUN RECEIPT' \
  || fail 5 'The standalone operational validator did not return a run receipt.'

printf 'VERIFIED: installed Dravux is byte-identical and both validators run standalone\n'
