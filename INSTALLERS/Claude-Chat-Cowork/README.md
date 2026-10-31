# Install Dravux in Claude Chat or Cowork

No terminal. About five minutes.

## The file you need

`dravux.zip`, in this folder. Upload it exactly as it is — do not unzip it first, and do not zip it
again. Its contents start with a single folder named `dravux`, which is the shape Claude expects.

If you only have the source checkout and this folder has no `dravux.zip` in it, the archive is
created at build time. Build it with `python3 scripts/build_release.py --output-dir <somewhere>` from
the top of the package, or download the published release, which ships the archive in place.

## Before you start

Some organization plans and admin settings turn custom skills or code execution off entirely, and if
yours does the upload option may be missing or greyed out — this is an account setting Dravux cannot
change, so ask whoever administers your Claude account to enable custom skills and code execution.

## Steps

1. In Claude, open **Customize > Skills** — the screen where skills are uploaded. Some versions place
   it under Settings and label it Capabilities; either way, you are looking for the skills screen.
2. Turn on code execution for your account if it is not already on. Dravux validates its own results
   by running a small bundled program; without code execution it cannot establish a result.
3. Choose **+ > Create skill > Upload a skill**.
4. Select `dravux.zip`.
5. Switch Dravux on.
6. Start a **new** conversation. A conversation that was already open will not see the new skill.

## Check that it worked

In the new conversation, ask:

```text
Run your bundled contract-only self-test and show me the receipt.
```

You should get back a short receipt naming the contract result, the automated result, and a final
status of `INCOMPLETE`. That is the correct outcome for a self-test: the machinery is proven, and no
website has been examined yet.

## What you have, and what you do not

You have: the Dravux method, its schemas, its validators, and its self-test fixtures.

Uploading `dravux.zip` does not give you: a web browser, a rendered page, the ability to click or
type on a page, screenshots, or a repository's commit and pull-request history. Those depend on the
Claude session you are in. Dravux will tell you which of them are present before it audits anything,
and it will stop and ask you rather than quietly downgrading the evidence.

## If it will not install

- **The upload is rejected or the skill never appears.** Check that you uploaded `dravux.zip` and
  not the large package archive. Only `dravux.zip` has the folder shape Claude requires.
- **The skill is on but nothing happens.** Start a fresh conversation.
- **Dravux stops and asks permission before auditing.** That is the design. See
  [Troubleshooting](../../README.md#troubleshooting).
