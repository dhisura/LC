# GitHub Deploy & Free Hosting (GitHub Pages)

## What This Skill Does
Deploys any web project to the user's GitHub account and enables **GitHub Pages** for instant 100% free hosting.

## Capabilities
1. Initializes Git repository if not present.
2. Commits all project files with a clean descriptive message.
3. Creates a public repository under the user's GitHub account (`dhisura`) using the authenticated GitHub CLI (`gh`).
4. Pushes the code to GitHub.
5. Enables GitHub Pages on the `main` branch to host the static website publicly at `https://dhisura.github.io/<repo-name>/`.

## Instructions for Agents
- Whenever the user asks to "host freely", "push to github", or "deploy online", use this skill.
- Ensure the root directory has a valid, complete `index.html` file so GitHub Pages can serve it immediately.
- Use relative paths for assets (e.g., `./styles.css` instead of `/styles.css`) so GitHub Pages serves them correctly under the repository subpath.
