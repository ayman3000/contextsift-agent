# Security policy

## Supported status

ContextSift is currently an experimental proof of concept. It has no production security-support guarantee or hardened release channel.

## Important limitations

- `terminal_run` uses a non-shell subprocess and a small denylist. This does not prevent every destructive, indirect, or environment-specific command.
- `code_execute_python` uses Python isolated mode and a sanitized environment. It is not an operating-system sandbox and does not enforce network or memory isolation.
- Filesystem tools validate configured roots, but allowed files may still contain sensitive data.
- Conversation logs, tool receipts, context manifests, artifacts, benchmark runs, and execution directories may contain prompts, source code, credentials printed by other programs, personal data, or absolute paths.
- Model-generated tool arguments are untrusted input and should be treated accordingly.
- Tavily queries and returned content leave the local machine when `web_search` is used.

Do not run ContextSift against untrusted prompts or repositories without an additional container or virtual-machine boundary. Do not expose the agent as a public multi-user service.

## Reporting a vulnerability

Do not include secrets, exploit payloads, private repository content, or personal data in a public issue.

When the repository is hosted on GitHub, enable private vulnerability reporting and use the repository's **Security → Report a vulnerability** flow. Until a private channel is configured, repository owners should add a security contact before inviting public security testing.

Useful reports include:

- Affected commit and platform.
- Minimal reproduction steps.
- Expected and observed permission boundary.
- Whether filesystem, terminal, Python, web, artifact, or provider behavior is involved.
- A safe description of potential impact.

## Secret handling

- Supply API keys through environment variables.
- Never commit `.env` files, runtime `data/`, or generated `benchmarks/results/` directories.
- Rotate a key immediately if it appears in a prompt, log, screenshot, artifact, issue, or commit.
- Review sanitized reference results before publication.
