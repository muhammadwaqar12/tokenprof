<h3 align="center">A profiler for the context window. See what is actually eating your tokens, per turn.</h3>

<p align="center">
  <a href="#quickstart">Quickstart</a> ·
  <a href="#what-it-tells-you">What it tells you</a> ·
  <a href="#recording-a-session">Recording</a> ·
  <a href="#adapters">Adapters</a> ·
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-3a6b4d"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.9%2B-3a6b4d">
  <img alt="Dependencies" src="https://img.shields.io/badge/dependencies-0-9a6a15">
  <a href="CONTRIBUTING.md"><img alt="PRs welcome" src="https://img.shields.io/badge/PRs-welcome-3a6b4d"></a>
</p>

---

You know how many tokens your last request used, because the API told you. You almost certainly do not know **what they were**.

There are tools that compress your context and tools that retrieve into it. There is nothing that opens it up and shows you the bill line by line. So when a session gets slow and expensive, the usual move is to guess.

```
$ ctxprof analyze session.jsonl --turn 2

turn 2  model=gpt-4o  provider=openai_chat
tokenizer: heuristic(chars/4)

category                tokens   share                                     cost
-----------------------------------------------------------------------------
tool result              2,869   66.6%  ###################.........   $0.0072
tool schema              1,142   26.5%  #######.....................   $0.0029
system                     205    4.8%  #...........................   $0.0005
history assistant           67    1.6%  ............................   $0.0002
history user                14    0.3%  ............................   $0.0000
current user                 8    0.2%  ............................   $0.0000
-----------------------------------------------------------------------------
TOTAL                    4,305  100.0%                                  $0.0108

fixed overhead (system + tool schemas): 1,347 tokens (31.3% of this turn), paid on every request

tool schemas (4 registered)
  bloated_connector                      912  ####..............
  search_docs                             85  ..................
  trace_calls                             82  ..................
  read_file                               63  ..................
```

One auto-generated tool is consuming 80% of the schema budget and is serialized into every single request whether the model calls it or not. Nothing errors. Nothing in your dashboard says so.

## Quickstart

```bash
pip install ctxprof
```

Point it at a file of request payloads, one JSON object per line:

```bash
ctxprof analyze session.jsonl              # every turn, with growth
ctxprof analyze session.jsonl --turn 4     # one turn, broken down
ctxprof diff session.jsonl --from 0 --to 9 # what grew between two turns
```

Zero dependencies. `pip install "ctxprof[tiktoken]"` if you want exact counts for OpenAI models instead of the heuristic.

It reads bare provider payloads or anything wrapping one under `request`, `body`, `payload` or `kwargs`, so most existing logs work without reshaping. `-` reads stdin.

## What it tells you

**Fixed overhead, and what it costs over a session.** Your system prompt and every registered tool schema are serialized into context on every turn, used or not. Per turn that is easy to wave away. Multiplied across a session it is usually the largest single line item, and `analyze` prints it as both.

**Which tool is expensive.** Not "you have 40 tools" but which ones, ranked. Auto-generated schemas from OpenAPI specs are routinely 10x the size of hand-written ones, and nobody notices because tool calls keep working.

**What is growing.** `diff` compares two turns and names what changed, including tools that were registered partway through a session.

**Where tool output went.** A tool result that floods the context is attributed to the tool that produced it, so a chatty search tool cannot hide inside "conversation history."

## Recording a session

`ctxprof` reads payloads; it does not intercept them. That is deliberate, because the moment a profiler sits in your request path it can break the thing it is profiling.

Most SDKs and frameworks give you a hook. The shape you want is one JSON object per line, each being the request as it was sent:

```python
import json


def log_request(**kwargs):
    with open("session.jsonl", "a") as f:
        f.write(json.dumps({"request": kwargs}) + "\n")
```

If your framework makes this awkward, open an issue. Making recording easy for a specific stack is a good adapter contribution.

> [!NOTE]
> Payloads contain your prompts and your tool results. Treat a `.jsonl` as sensitive, and redact before sharing one in a bug report. The default `.gitignore` excludes `*.jsonl` for this reason.

## Adapters

An adapter turns one provider's payload shape into a list of segments. That is the entire interface, which is why adding one is an afternoon rather than a refactor.

| Adapter | Status |
|---|---|
| `anthropic_messages` | Shipped |
| `openai_chat` | Shipped |
| LangGraph / LangChain | Wanted |
| CrewAI | Wanted |
| Google ADK | Wanted |
| Bedrock Converse | Wanted |

Since most frameworks ultimately emit an OpenAI or Anthropic payload, the two shipped adapters already cover a lot of ground. Framework-specific adapters exist to make the recording step easier and to label segments with names the framework uses.

Detection is automatic and asserts that exactly one adapter claims a payload. Pass `--provider` to override it.

## Accuracy

Every report states which tokenizer produced it, because the honest answer varies.

With `tiktoken` installed and an OpenAI model, counts are exact. Otherwise it falls back to `chars / 4`, which runs low on code and on non-Latin scripts. That approximation is fine for ranking segments against each other, which is what you are here for, and it is not a context budget. Do not size a window with it.

Serialization is close but not exact. Providers wrap messages and tool schemas in their own formatting, and that wrapper is small next to the payload. Treat the numbers as accurate to a few percent, and the ranking as reliable.

## What this is not

Not a tracing tool. Langfuse, Phoenix and LangSmith show you latency, spans and token *counts*, and they do it well. None of them show you token *composition*, which is the gap this fills. Run both.

Not a compressor. It will tell you what to cut. Cutting is your call, because only you know which of those tools you actually need.

Not a runtime guard. It reads logs after the fact.

## Contributing

The most useful contributions are adapters and payload shapes that break detection. If `ctxprof` cannot read your logs, that is a bug worth reporting, and a redacted sample is the whole fix. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE).

---

<sub>Built by <a href="https://github.com/muhammadwaqar12">Muhammad Waqar</a>. Companion to <a href="https://github.com/muhammadwaqar12/awesome-agent-failures">awesome-agent-failures</a>, where CTX-03 covers the tool schema tax and COST-03 covers prompt cache thrash.</sub>
