# GitHub Deploy & Free Hosting (GitHub Pages)

## What This Skill Does
Deploys a static web project to the user's GitHub account and enables **GitHub Pages** for free hosting.

## When to Use
Activate on: "host this free", "push to github", "deploy online", "publish this site".

## Confirmation required — read this first

This skill creates a **PUBLIC** repository and publishes a live site. Both are
outward-facing and hard to walk back: a public repo can be scraped or cloned by
anyone, and content pushed stays in git history even if the repo is later deleted.

**Every invocation requires `confirm=True` in the context.** Without it the skill
makes no remote changes and returns the plan it would have executed. Do not set
`confirm=True` on the user's behalf — surface the plan and let them decide.

Pass `dry_run=True` to print the plan without contacting GitHub at all.

## Refusals

The skill stops rather than proceeding when:

- No root `index.html` exists (required by GitHub Pages).
- The workspace sits **inside** an existing git repository. Initialising a nested
  repo detaches the files from the parent's history; move the site to its own
  directory instead.
- Credential-like files are present (`.env*`, `*.pem`, `*.key`, `id_rsa`,
  `credentials*`, `.netrc`, `service-account.json`, …). These would be published
  permanently, so the deploy is refused and the offending paths are listed.
- The requested repository name is not a plain slug (`[A-Za-z0-9._-]`, max 100).

## Safety properties

- **No shell.** Every subprocess runs from an argv list with `shell=False`, so
  LLM-supplied values (commit messages, repo names) cannot inject commands.
- **No force-push.** The previous version used `git push --force`, which silently
  destroyed remote history. It now does a plain push.
- **Git identity is not overwritten.** `user.name` / `user.email` are only set
  when the repository has none; an existing identity is left alone.
- **Partial success is reported as such.** If Pages fails after the push, the
  result says so with the repo URL, rather than returning a bare failure.

## Instructions for Agents

- Ensure the root has a complete `index.html`, or the deploy will be refused.
- Use **relative** asset paths (`./styles.css`, not `/styles.css`). GitHub Pages
  serves the site under `/<repo-name>/`, so absolute paths 404.
- Present the returned `plan` to the user and get an explicit yes before
  re-running with `confirm=True`.
- Do not set `confirm=True` merely because the user said "deploy" earlier in a
  long conversation — confirm for this specific repository and directory.
- Report `live_url` only when the result is not `partial`.
