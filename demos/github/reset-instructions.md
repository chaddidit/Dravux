# Reset Instructions

Do not rewrite the tracked demo in place for an ordinary demonstration. From the package root, create
a disposable directory outside the verified release tree and write the selected state there:

```bash
DRAVUX_DEMO_DIR="$(mktemp -d "${TMPDIR:-/tmp}/dravux-demo.XXXXXX")"
python3 -B demos/github/reset_demo.py --state broken --destination "$DRAVUX_DEMO_DIR/index.html"
printf 'Disposable demo: %s\n' "$DRAVUX_DEMO_DIR/index.html"
```

To show the repaired state in the same disposable directory:

```bash
python3 -B demos/github/reset_demo.py --state repaired --destination "$DRAVUX_DEMO_DIR/index.html"
```

The script can replace the tracked `demos/github/live/index.html` when `--destination` is omitted,
but that intentionally invalidates the release manifest until the original bytes are restored. That
maintainer-only path is not the demo default.

Maintainer-only in-place reset:

```bash
python3 -B demos/github/reset_demo.py --state broken
```

No Git command, remote, token, package install, or network connection is required.
