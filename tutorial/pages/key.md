---
layout: default
title: Tutorial — add your AI key
---

# 3 · Add your AI key

[← Connect your databases](02-databases.html)

Everything so far ran with no AI at all. The next chapters are the
conversational side — asking questions in plain English, building
dashboards from a sentence, getting model guidance — and those use
Claude.

Two ways to bring a key:

- **An Anthropic API key** (`sk-ant-…`) from
  [console.anthropic.com](https://console.anthropic.com), or
- **A Claude subscription token** — if you have a Claude Pro/Max
  subscription and the Claude CLI, run `claude setup-token` and use the
  token it prints.

Set it in the shell you run Docker from, then restart the app:

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # or: export CLAUDE_CODE_OAUTH_TOKEN=...
docker compose up -d analyst               # picks up the key
```

That's it — the compose file passes the key through to the app.

**What the AI can and cannot see.** This matters and is worth stating
plainly: the model is never handed your data wholesale. It sees table
schemas, the profile summaries, the catalog's descriptions, small capped
samples, and the small result sets of queries — enough to reason about
your data's *shape and meaning*. The queries themselves run locally on
your machine, and your bulk data never leaves it.

Next: [Ask your data questions →](03-ask.html)
