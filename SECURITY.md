# Security policy

## Reporting

Email m_waqar@live.com rather than opening a public issue.

## What this package does and does not do

`ctxprof` reads local files and prints to stdout. It makes no network calls, sends no telemetry, and has no runtime dependencies. The optional `tiktoken` extra downloads encoding files on first use, which is the only network activity anywhere in the project.

It does not intercept your requests. It reads payloads you have already recorded, deliberately, so that a profiler can never sit in the path of a production request.

## The real risk here is your own data

A recorded `.jsonl` contains your system prompts, your conversation history, and your tool results in full. That is likely to include credentials, customer data, and internal system detail.

- The default `.gitignore` excludes `*.jsonl`. Keep it that way.
- Redact before attaching one to an issue. Replacing text with filler of similar length preserves everything the profiler needs.
- Treat these files with the same care as an application log containing PII, because that is what they are.
