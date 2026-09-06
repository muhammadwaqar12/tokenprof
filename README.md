<h3 align="center">A profiler for the context window. See what is actually eating your tokens, per turn.</h3>

<p align="center">
  <a href="#quickstart">Quickstart</a> ·
  <a href="#where-your-tokens-went">Attribution</a> ·
  <a href="#is-your-prompt-cache-actually-working">Cache</a> ·
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

## Quickstart

```bash
pip install tokenprof                                          # once released
pip install git+https://github.com/muhammadwaqar12/tokenprof   # from source
```

Run your program through `record`. It attaches to the OpenAI and Anthropic clients, writes every outgoing request to a file, and changes nothing about what your program does.

```bash
tokenprof record -o session.jsonl -- python your_agent.py
tokenprof analyze session.jsonl
tokenprof cache   session.jsonl
```

No API keys, no config, no code changes. If you already log request payloads, skip `record` and point `analyze` at what you have.

## Where your tokens went

```
$ tokenprof analyze session.jsonl --turn 2

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

fixed overhead (system + tool schemas): 1,347 tokens (31.3% of this turn), re-sent on every request

tool schemas (4 registered)
  bloated_connector                      912  ####..............
  search_docs                             85  ..................
  trace_calls                             82  ..................
  read_file                               63  ..................
```

One auto-generated tool is eating 80% of the schema budget and is serialized into every request whether the model calls it or not. Nothing errors. Nothing in your dashboard says so.

The per-tool line is the part most tools cannot give you. Not "you have 40 tools registered" but **which ones**, ranked, in tokens.

## Is your prompt cache actually working?

Providers cache a **prefix**. If the first N tokens of a request are byte-identical to the last one, you pay a fraction for them. One volatile value near the front moves the break point to zero, and you quietly pay full price on every turn while your config still says caching is on.

<p align="center">
  <img src="https://raw.githubusercontent.com/muhammadwaqar12/tokenprof/main/docs/demo.svg" alt="tokenprof cache finding a broken prompt cache prefix" width="100%">
</p>

```
$ tokenprof cache session.jsonl

    turns    stable     total   share  what broke the prefix
--------------------------------------------------------------------------
   0 -> 1         68       248   27.4%  system:system
   1 -> 2         68       302   22.5%  system:system
   2 -> 3         68       356   19.1%  system:system
--------------------------------------------------------------------------

reusable across turns: 204 tokens | re-sent after a break: 702

segments that broke the prefix
  system:system                                  3x

WARNING: the prefix breaks early. Turn 3 reuses only 19.1% of its prompt.
  Anything that changes near the front of the prompt costs you the whole
  cache. Timestamps, session ids and reordered tool lists are the usual
  causes. Move volatile content to the end.
```

That session has a timestamp at the top of the system prompt. Every turn misses, and the tool names the segment responsible rather than just reporting a bad number.

The other common cause is subtler: **registering one new tool mid-session invalidates the whole prefix**, because tool schemas are serialized ahead of the messages. `tokenprof cache` catches that too.

Cost accounting follows the real pricing. Anthropic bills cache reads at 10% of base and OpenAI at 50%, so a turn with `cache_control` markers reports what it actually bills rather than a blended number that overstates exactly the segments you were smart enough to cache.

## Recording a session

`record` writes a `sitecustomize` shim onto the path of the process you launch, wraps the client `create` methods, and calls through untouched. Two deliberate constraints: it never raises into your program, and it records requests only, never responses.

```bash
tokenprof record --verbose -o session.jsonl -- python your_agent.py
# tokenprof: patched openai, anthropic
# tokenprof: captured 14 request(s) to session.jsonl
```

If you would rather log payloads yourself, any JSONL of request objects works. Bare payloads and anything wrapping one under `request`, `body`, `payload` or `kwargs` are all accepted, and `-` reads stdin.

> [!NOTE]
> A recording contains your prompts and your tool results in full, which usually means credentials and customer data. The default `.gitignore` excludes `*.jsonl`. Redact before attaching one to an issue.

## Adapters

An adapter turns one provider's payload shape into a list of segments. Three methods, no framework dependency in the core, which is why adding one is an afternoon rather than a refactor.

| Adapter | Status |
|---|---|
| `anthropic_messages` | Shipped, with `cache_control` support |
| `openai_chat` | Shipped |
| LangGraph / LangChain | Wanted |
| CrewAI | Wanted |
| Google ADK | Wanted |
| Bedrock Converse | Wanted |

Most frameworks ultimately emit an OpenAI or Anthropic payload, so the two shipped adapters already cover a lot of ground. Detection is automatic, and a test asserts exactly one adapter claims any payload. Pass `--provider` to override.

## Accuracy

Every report states which tokenizer produced it, because the honest answer varies.

With `tiktoken` installed and an OpenAI model, counts are exact. Otherwise it falls back to `chars / 4`, which runs low on code and non-Latin scripts. That is fine for ranking segments against each other, which is what you are here for, and it is not a context budget.

Serialization is close but not exact. Providers wrap messages and schemas in their own formatting, and that wrapper is small next to the payload. Treat the numbers as accurate to a few percent and the ranking as reliable.

## What this is not

Not a tracing tool. Langfuse, Phoenix and LangSmith show latency, spans and token *counts*, and do it well. None show token *composition*. Run both.

Not a compressor. It tells you what to cut. Cutting is your call.

Not a runtime guard. It reads recordings after the fact, on purpose, so a profiler can never sit in the path of a production request.

## Contributing

The most useful contributions are adapters, and payload shapes that break detection. If `tokenprof` cannot read your logs, that is a bug and a redacted sample is the whole fix. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE).

---

<sub>Built by <a href="https://github.com/muhammadwaqar12">Muhammad Waqar</a>. Companion to <a href="https://github.com/muhammadwaqar12/awesome-agent-failures">awesome-agent-failures</a>, where CTX-03 covers the tool schema tax and COST-03 covers prompt cache thrash.</sub>
