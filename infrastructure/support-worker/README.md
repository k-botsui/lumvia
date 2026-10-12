# Lumvia support gateway

See [operator setup](../../docs/development/SUPPORT.md). End users do not authenticate to GitHub.

The worker is designed for **Workers Free** with SQLite-backed Durable Objects. It is not deployed yet. Never change the account to a paid plan as part of setup.

```sh
pnpm install --frozen-lockfile
pnpm test
pnpm check
```

Only an operator creates and deploys this gateway. `GITHUB_TOKEN` is a Worker Secret with Issues write access to `k-botsui/lumvia` only. Do not commit it, put it in a client build, or paste it in chat. Raw message contents and raw IP addresses are not stored. Workers request logging is disabled.
