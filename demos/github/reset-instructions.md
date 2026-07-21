# Reset Instructions

From the package root:

```bash
python3 demos/github/reset_demo.py --state broken
```

This replaces only `demos/github/live/index.html` with the known broken fixture.

To show the repaired state:

```bash
python3 demos/github/reset_demo.py --state repaired
```

To avoid touching the checked-in live file, pass a disposable destination:

```bash
python3 demos/github/reset_demo.py --state broken --destination out/github-demo/index.html
```

No Git command, remote, token, package install, or network connection is required.
