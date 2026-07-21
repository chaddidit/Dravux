#!/bin/sh
set -eu

usage() {
  printf '%s\n' \
    'Usage:' \
    '  sh install.sh --claude --personal' \
    '  sh install.sh --codex --personal' \
    '  sh install.sh --claude --project-dir "/absolute/path/to/project"' \
    '  sh install.sh --codex --project-dir "/absolute/path/to/project"'
  exit 2
}

fail() {
  code=$1
  shift
  printf 'ERROR: %s\n' "$*" >&2
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

command -v python3 >/dev/null 2>&1 || fail 3 'python3 is required; nothing was installed.'
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' \
  || fail 3 'Python 3.8 or newer is required; nothing was installed.'

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P) \
  || fail 3 'Could not resolve the release directory.'
source_dir=$script_dir/plugins/dravux/skills/dravux

[ -d "$source_dir" ] && [ ! -L "$source_dir" ] \
  || fail 3 'The bundled Dravux skill is missing or is a symlink.'
[ -f "$source_dir/SKILL.md" ] \
  || fail 3 'The bundled Dravux SKILL.md is missing.'

if [ -n "$(find "$source_dir" -type l -print -quit)" ]; then
  fail 3 'The bundled skill contains a symlink; nothing was installed.'
fi

python3 -B "$source_dir/scripts/dravux_contract.py" "$source_dir/assets/report-template.json" >/dev/null \
  || fail 3 'The bundled report template failed validation; nothing was installed.'
python3 -B "$source_dir/scripts/dravux_run.py" validate "$source_dir/assets/run-envelope-template.json" >/dev/null \
  || fail 3 'The bundled operational run template failed validation; nothing was installed.'

if [ "$scope" = personal ]; then
  case ${HOME-} in
    /*) : ;;
    *) fail 3 'HOME must be set to an absolute path for a personal install.' ;;
  esac
  [ "$HOME" != / ] || fail 3 'Refusing to use / as HOME.'
  base_dir=$HOME
else
  [ -d "$project_dir" ] && [ ! -L "$project_dir" ] \
    || fail 3 'The project directory must already exist and must not be a symlink.'
  base_dir=$(CDPATH= cd -- "$project_dir" && pwd -P) \
    || fail 3 'Could not resolve the project directory.'
fi

case "$platform:$scope" in
  claude:personal) destination=$base_dir/.claude/skills/dravux ;;
  codex:personal) destination=$base_dir/.agents/skills/dravux ;;
  claude:project) destination=$base_dir/.claude/skills/dravux ;;
  codex:project) destination=$base_dir/.agents/skills/dravux ;;
  *) usage ;;
esac

if [ -e "$destination" ] || [ -L "$destination" ]; then
  fail 4 "Destination already exists; refusing to merge or overwrite: $destination"
fi

parent_dir=$(dirname -- "$destination")
mkdir -p "$parent_dir" || fail 5 "Could not create destination parent: $parent_dir"

staging=$(mktemp -d "$parent_dir/.dravux-install.XXXXXX") \
  || fail 5 'Could not create a private staging directory.'

cleanup() {
  if [ -n "${staging-}" ] && [ -d "$staging" ]; then
    rm -rf -- "$staging"
  fi
}
trap cleanup EXIT HUP INT TERM

cp -R "$source_dir"/. "$staging"/ \
  || fail 5 'Copy failed; the incomplete staging copy was removed.'
python3 -B "$staging/scripts/dravux_contract.py" "$staging/assets/report-template.json" >/dev/null \
  || fail 5 'Installed-copy validation failed; the incomplete staging copy was removed.'
python3 -B "$staging/scripts/dravux_run.py" validate "$staging/assets/run-envelope-template.json" >/dev/null \
  || fail 5 'Installed-copy operational validation failed; the incomplete staging copy was removed.'

if [ -e "$destination" ] || [ -L "$destination" ]; then
  fail 4 "Destination appeared during installation; refusing to overwrite: $destination"
fi

mv "$staging" "$destination" || fail 5 'Could not finalize the installation.'
staging=
trap - EXIT HUP INT TERM

printf 'INSTALLED: Dravux 1.0.1\n'
printf 'Platform: %s\n' "$platform"
printf 'Scope: %s\n' "$scope"
printf 'Destination: %s\n' "$destination"
printf 'Next: start a new local app session and confirm Dravux in the Skills UI or invoke it explicitly.\n'
