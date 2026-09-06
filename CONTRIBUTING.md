# Contributing

The two most useful things you can send: an adapter, or a payload that breaks detection.

## Payloads that break detection

If `tokenprof` cannot read your logs, that is a bug and the fix is usually small. Open an issue with a **redacted** sample: replace the actual prompt and tool result text with filler of roughly the same length, keep the structure. Structure is all the parser cares about, and length is all the profiler cares about, so a redacted sample is just as useful as a real one and safe to post.

## Writing an adapter

An adapter has three methods and no framework dependency in the core:

```python
class MyAdapter:
    name = "my_provider"

    def matches(self, request: dict) -> bool: ...
    def model_of(self, request: dict) -> str: ...
    def segments(self, request: dict, tok: Tokenizer) -> list[Segment]: ...
```

Add the module under `src/tokenprof/adapters/`, register it in `ADAPTERS`, and add a fixture under `tests/fixtures/`.

Two rules that matter more than they look:

**`matches` must be exclusive.** There is a test asserting exactly one adapter claims any given payload. If two match, registry ordering silently decides correctness, and that bug surfaces months later as wrong numbers rather than an error. Discriminate on a field only your provider has.

**Emit segments in prompt order.** Cache prefixes are computed over the order you emit, so it has to match the order the provider actually assembles the prompt. Anthropic is tools, then system, then messages. Getting this wrong puts the cache break point in the wrong place and the numbers look plausible while being wrong.

**Name your segments.** A tool schema segment named `search_docs` is actionable. An unnamed one is trivia. The per-tool breakdown is the most useful view in the tool, and it only works if adapters carry names through.

**Carry the digest through.** `measure()` returns `(tokens, chars, digest)`. A segment without a digest can never count as a cache hit, which is the safe default, but it also means `tokenprof cache` goes blind on your provider. Pass it into every `Segment` you build.

**Mark cached segments if your provider has explicit markers.** Anthropic uses `cache_control`, where the marker caches the whole prefix up to and including that block, so only the last marker matters. OpenAI caches automatically with no markers, so its adapter marks nothing and the prefix analysis does the work instead.

## Categories

`Category` is deliberately small. A new one has to pass a simple test: could someone do something different in response to seeing it broken out? If the answer is no, it belongs in an existing bucket.

## Tests

`pytest -q`. Everything runs offline with no API keys and no network.

Fixtures are hand-built rather than captured, so they can be committed without redaction and can encode the specific situations worth testing. The OpenAI fixture deliberately contains one bloated auto-generated tool and registers a new tool partway through the session, because those are the two cases the reports exist to catch.

If you add behavior, add the test that would fail without it. If you fix a bug, add the test that was missing.

## Accuracy claims

Be careful with numbers in docs and output. The default tokenizer is an approximation and every report says so. If you add a counting path, make it report its own name, and do not describe approximate counts as exact anywhere in the interface.

## Style

- `ruff check .` and `ruff format .` before opening a PR. CI runs both.
- Plain names. `fixed_overhead_tokens` over `calc_fo`.
- Comments explain why, not what. The code says what.

## Review

Pull requests get looked at within a day or two. Ping the thread if yours goes quiet.
