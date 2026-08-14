# Web UI

A branded copy of [`google/adk-web`](https://github.com/google/adk-web), vendored into `web/` at the repo root and customized for qtsolv: the logo and color theme, per-agent suggested prompts, and some markdown/message styling polish. Everything else (event trace, tracing, artifacts, evals, agent builder) is the unmodified upstream UI.

## What's different from upstream

- **Branding**: qtsolv's logo (light and dark variants, swapped automatically with the theme toggle) and a green (`#41B76C`) Material color theme, replacing the default ADK blue. See `web/src/assets/config/runtime-config.json` for the logo config and `web/src/styles.scss` for the color overrides.
- **Suggested prompts**: each agent's empty chat state shows a row of clickable prompts, sourced from a `## Try asking` section in that agent's own `agents/<name>/README.md`. Clicking one fills the chat input without sending it. See [Suggested prompts](#suggested-prompts) below.
- **Response styling**: broader markdown typography (headings, lists, tables, blockquotes, emphasis) and a bit more polish on message bubbles, both driven entirely by the same Material theme variables as the rest of the UI, so they follow whatever theme/colors are active.

## Suggested prompts

ADK's backend already reads a `README.md` from an agent's own folder, if one exists, and serves it as that agent's empty-state content (`GET /dev/apps/{app}/build_graph`, only registered when the backend is started with `--with_ui`, see [Running it](#running-it) below). Every agent in this repo has one.

Add a `## Try asking` section with a bullet list to surface prompts as clickable chips, in addition to the readme rendering as markdown above them:

```markdown
## Try asking

- "Check for new buying signals."
- "Any accounts I should reach out to this week?"
```

The parsing is a plain string match on that exact heading (`web/src/app/components/suggested-prompts/suggested-prompts.component.ts`), not a new backend field, so updating an agent's suggested prompts is just editing its `README.md`.

## Updating branding

- **Logo**: replace the SVGs under `web/src/assets/` and point `runtime-config.json`'s `logo.imageUrlLight`/`imageUrlDark` at the new filenames. `logo.text` is used for the image's alt text and aria-label, not rendered visibly (the logo images are full wordmarks already).
- **Colors**: regenerate the Material palette from a new primary color with `cd web && npx ng generate @angular/material:m3-theme --primary-color=#yourhex --defaults --force`, then transplant the generated tone values into the `--mat-sys-*` overrides in `web/src/styles.scss` (both the default/dark block and the `html.light-theme` block). The standard M3 tone mapping used here: primary/on-primary/primary-container/on-primary-container are tones 40/100/90/10 in light mode and 80/20/30/90 in dark mode, same pattern for secondary.

## Running it

### Docker

`docker compose up --build` builds and runs both `adk-agents` (the Python backend, `adk api_server --with_ui`, not published externally) and `web` (this frontend, built and served by nginx, published on port 8080). nginx proxies every API path the frontend calls (`/apps/`, `/dev/`, `/config/`, `/agent-identity/`, `/list-apps`, `/version`, `/run_sse`, `/run_live`, see `web/nginx.conf`) to `adk-agents` on the compose network, so everything is same-origin and no CORS configuration is needed. Open `http://localhost:8080`.

### Native

```bash
# terminal 1: the backend
cd agents
uv run adk api_server . --allow_origins=http://localhost:4200 --with_ui

# terminal 2: the frontend
cd web
npm install
npm run serve --backend=http://127.0.0.1:8000
```

Open `http://localhost:4200`. `--with_ui` is what registers the `/dev/apps/*` routes the suggested prompts and agent graph depend on; without it the empty state falls back to no readme content and the graph tab comes back empty, everything else still works.

### Unbranded fallback

ADK's own bundled UI still works if you just want the plain dev tool, no branding or suggested prompts:

```bash
cd agents
uv run adk web . --port 8080 --reload_agents
```

## Layout

```text
web/
  Dockerfile                  # multi-stage: npm build, then nginx serves the output
  nginx.conf                  # proxies API paths to adk-agents, serves everything else as static
  package.json, angular.json, src/  # unmodified adk-web project structure
  src/
    assets/
      qtsolv-logo-dark-bg.svg   # white wordmark, used on the dark theme
      qtsolv-logo-light-bg.svg  # near-black wordmark, used on the light theme
      config/runtime-config.json  # backendUrl + logo config, read at runtime
    app/components/
      custom-logo/                # picks the logo variant from the active theme
      suggested-prompts/           # parses "## Try asking" out of agentReadme, renders chips
    styles.scss                  # brand color overrides, markdown typography
```
