# Survey of LLM/Agent Invocation Shapes (Python)

Purpose: catalogue how "call the model" actually looks across the Python
ecosystem, so a framework-agnostic retry/validation wrapper can be designed
against real shapes rather than an assumed one. Sources are current as of
mid-2026; SDKs move fast, treat exact type names as "last known accurate,"
not permanent.

---

## 1. Raw provider SDKs

### 1a. OpenAI — Chat Completions (legacy-but-supported)

```python
response = client.chat.completions.create(
    model="gpt-5.5",
    messages=[{"role": "user", "content": "..."}],
    tools=[...],          # optional
    tool_choice=...,      # optional
    stream=True/False,    # changes return type entirely
)
```

- **Input**: `messages: list[dict]` (role/content dicts; content can itself be
  a string or a list of typed parts — text / image_url / input_audio / file).
- **Output (non-streaming)**: `ChatCompletion` object with a `.choices: list`
  — each choice has its own `message` and `finish_reason`. Plural by design
  (`n` > 1 sampling). The "one answer" a caller wants is usually
  `response.choices[0].message.content`, a derived path, not the return
  value itself.
- **Output (streaming)**: an iterator/async-iterator of `ChatCompletionChunk`
  objects. No single "output" exists until the stream is drained and
  reassembled.
- Tool calls surface as `message.tool_calls`, a list, separate from
  `.content`.

### 1b. OpenAI — Responses API (now the recommended primary interface)

```python
response = client.responses.create(
    model="gpt-5.5",
    instructions="...",      # separate from input, not a message role
    input="..." ,            # str OR list of message-like items
)
print(response.output_text)  # convenience flattened accessor
```

- **Input**: `input` can be a bare string *or* a list of structured items
  (messages, prior outputs re-fed in for multi-turn/compaction). Distinct
  from Chat Completions' `messages` in both name and shape.
- **Output**: `Response` object; `.output` is a list of typed output items
  (message, reasoning, tool call, etc.), `.output_text` is a convenience
  string accessor that concatenates text parts. This is a *different*
  object graph from `ChatCompletion` even for equivalent requests.
- Notable: supports a `.compact()` operation that returns "compaction
  blocks" meant to be spliced back into the next call's `input` list —
  i.e. the framework itself sometimes rewrites history, not just the user.

### 1c. OpenAI — legacy Completions (frozen, still live)

```python
client.completions.create(model="gpt-3.5-turbo-instruct", prompt="...")
```

- **Input**: `prompt: str` (freeform), not messages at all.
- Included because plenty of production code and "raw completion" style
  wrapper functions still mimic this str-in shape even against chat models
  (people pre-template a whole conversation into one string).

### 1d. Anthropic — Messages API

```python
message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,          # required, not optional — no server-side default
    messages=[{"role": "user", "content": "..."}],
    tools=[...],              # optional
    thinking={"type": "enabled", "budget_tokens": 10000},  # optional
)
```

- **Input**: `messages: list[dict]`, alternating user/assistant turns.
  `content` can be a string or a list of typed content blocks (text, image,
  tool_result, document, etc.).
- **Output**: `Message` object; `.content` is a **list of content blocks**
  (`text`, `tool_use`, `thinking`, etc.), not a single unit. Checking "did
  the model call a tool" means scanning `.content` for `block.type ==
  "tool_use"`. Checking "what did it say" means concatenating `text` blocks.
- Streaming (`client.messages.stream(...)`) yields events
  (`content_block_delta`, `content_block_stop`, ...); `stream.get_final_message()`
  reassembles the accumulated `Message` after the stream is fully consumed.
- Distinctive quirk relevant to any wrapper: `max_tokens` is a *required*
  parameter here, unlike OpenAI — a detail that leaks into anyone's
  "invariant config" closure.

---

## 2. Structured-output / validation-first libraries (direct prior art)

### 2a. Instructor

```python
client = instructor.from_provider("openai/gpt-4o")  # or anthropic/, google/, ollama/...
user = client.chat.completions.create(
    response_model=UserModel,          # a Pydantic BaseModel class
    messages=[{"role": "user", "content": "..."}],
)
```

- **Input**: same `messages` list as the underlying provider, plus a bolted-on
  `response_model=` kwarg that changes what "the call" even means (it now
  wraps tool-calling or JSON-mode under the hood to force schema
  conformance).
- **Output**: an *instance of your own Pydantic model*, not a provider
  response object at all. Instructor discards/wraps the raw completion;
  `client.create_with_completion(...)` is the escape hatch to get both.
- **Already does validation-triggered retry internally**: if a
  `field_validator` raises, Instructor automatically re-asks the model with
  the validation error appended, up to a configured attempt count. This is
  the single closest existing analog to your library's core loop — worth
  explicitly differentiating against ("Instructor retries within its own
  schema-bound call; ours retries around any callable, schema or not").

### 2b. `validation-loop` (PyPI, competitor already surveyed)

- Wraps Instructor + LiteLLM + Tenacity. Input is `schema` (Pydantic) +
  `prompt` (str or list) + a `validation_callable`. Output is whatever your
  `validation_callable` returns. Confirms the "own the call path" pattern
  discussed earlier — not a counter-example to the shape survey, but a
  reminder that "bring your own schema" and "bring your own invocation" are
  different design choices.

### 2c. `langcore-guardrails` (PyPI, competitor already surveyed)

- Input/output shape is whatever the wrapped `BaseLanguageModel` uses
  (LangCore's own abstraction) — i.e. it inherits LangChain-like message
  lists, and its `GuardrailLanguageModel.async_infer(prompts: list[str])`
  takes a list of prompt strings for batch use. Another data point that
  "framework-agnostic" competitors still tend to pick one canonical shape
  and standardize everyone onto it.

---

## 3. Orchestration / agent frameworks

### 3a. LangChain — `Runnable` protocol (`BaseChatModel`, `BaseLLM`)

```python
model.invoke(input, config=None, *, stop=None, **kwargs) -> AIMessage
await model.ainvoke(input, ...) -> AIMessage
model.stream(input, ...) -> Iterator[AIMessageChunk]
model.batch([input1, input2], ...) -> list[AIMessage]
model.generate(prompts: list[str], ...) -> LLMResult          # BaseLLM
await model.agenerate(prompts: list[str], ...) -> LLMResult   # BaseLLM
```

- **Input** (`LanguageModelInput`): a union type — can be a plain `str`, a
  `PromptValue`, or `list[BaseMessage]` (or the loose `list[dict | tuple |
  BaseMessage]` accepted at the boundary and coerced). Three different
  shapes are all "valid input" to the same method.
- **Output for chat models**: always `AIMessage` for `.invoke`/`.ainvoke` —
  genuinely the closest real-world match to your assumed
  `f(list[Unit]) -> Unit` shape. But:
  - `.generate()`/`.agenerate()` (older `BaseLLM`-style, str-in/str-out
    models) return `LLMResult`: a **batch-with-metadata wrapper** —
    `generations: list[list[Generation]]` (outer list = one per prompt,
    inner list = one per requested completion) plus `llm_output` (token
    usage, model name). Not a `Unit` at all.
  - `.batch()` returns `list[AIMessage]`, one per input, not a single Unit.
  - `.stream()`/`.astream()` return chunk iterators; no completed Unit
    until consumed.
- `AIMessage.content` can itself be a string or a list of provider-specific
  content blocks (`AIMessage.content_blocks` lazily normalizes this in
  newer versions) — so even the "one Unit" case has an internal shape
  fork depending on `output_version`.
- `.with_structured_output(Schema)` returns a *new* Runnable whose `.invoke`
  now returns a parsed `Schema` instance (or a dict) instead of `AIMessage`
  — the return type of "the same method name" changes based on how the
  Runnable was constructed, not by inspecting the call.

### 3b. LangGraph (graph/node execution, referenced in the user's own harness README)

- Nodes are typically `def node(state: State) -> dict` (a partial-state
  update merged into the graph's state), or async equivalents. The
  "invocation" a harness wraps is usually one `model.ainvoke(messages)`
  call *inside* a node's `transform_state`, with the node itself owning
  how the result gets folded back into graph state (as seen in the
  user's own `AgentMethodHarnessAdapter` design: adapter calls
  `Agent.ainvoke()` for plain flows, but a lower-level single-structured-
  attempt path for schema-driven flows, specifically to avoid a
  double-fallback problem).
- Confirms: even within one company's abstraction, "the invocation" forks
  into at least two different call paths (plain vs. structured) with
  different retry/fallback semantics — reinforcing that a generic wrapper
  should not assume one call path per framework.

### 3c. PydanticAI

```python
agent = Agent("openai:gpt-5.2", output_type=SomeModel, retries=3)
result = agent.run_sync(user_prompt: str | Sequence[UserContent] | None,
                         message_history: Sequence[ModelMessage] | None = None,
                         ...)
result.output  # -> SomeModel instance, or str if no output_type
```

- **Input**: `user_prompt` (str or rich content sequence, can be `None` if
  resuming), plus optional `message_history: Sequence[ModelMessage]` — a
  fundamentally different "resume a conversation" shape than "pass the
  whole list every time."
- **Output**: `AgentRunResult[OutputDataT]`, a wrapper object; the payload
  lives at `.output`. Streaming variants (`run_stream`, `run_stream_sync`,
  `run_stream_events`) return yet other wrapper types
  (`StreamedRunResult`, async iterators of `AgentStreamEvent`).
- **Has its own native retry-with-feedback primitive**: raising
  `ModelRetry(message)` from inside a tool or an output validator causes
  PydanticAI to re-prompt the model with that message, up to a configured
  `retries` count — tracked *separately* for tool retries vs. output
  validation retries. This is the second major existing analog to your
  core loop (after Instructor) and worth explicit positioning against:
  PydanticAI's retry is intra-framework (you must be inside their agent/tool
  graph to raise `ModelRetry`); yours would work around any callable.

### 3d. OpenAI Agents SDK

- Agents configured with `output_type=SomeModel` (a Pydantic model or
  function); running an agent returns a result object exposing `.final_output`
  (or similarly named field depending on SDK version), validated against
  the schema. Same family as PydanticAI/Instructor: "the call" is
  abstracted behind an `Agent.run(...)`-style method, and structured output
  is a constructor-time property of the agent rather than a per-call
  argument.

---

## 4. Cross-cutting shape observations

1. **"Input" is never reliably just "a list of messages."** It is at least
   one of: `str`, `list[dict]`, `list[BaseMessage]`, `PromptValue`,
   `Sequence[UserContent]`, or a `messages + response_model/schema` pair —
   and which one depends on the framework, not the model.

2. **"Output" is never reliably "one unit."** Real return shapes include:
   a single message object (`AIMessage`, Anthropic `Message`), a list of
   choices (`ChatCompletion.choices`), a list of content blocks (Anthropic
   `.content`, OpenAI Responses `.output`), a batch-with-metadata wrapper
   (`LLMResult`), a parsed domain object (`response_model` result, PydanticAI
   `.output`), or a streaming iterator with no completed value at all until
   drained.

3. **The "thing you validate" is frequently *derived* from the return value,
   not the return value itself** — e.g. `response.choices[0].message.content`,
   or scanning a content-block list for a `tool_use` entry, or a value nested
   inside a result wrapper (`.output`). Any core loop that assumes
   `validate(raw_output)` directly will be wrong more often than right;
   validators effectively always need *some* extraction step first, whether
   the wrapper does it explicitly or leaves it to the user's closure.

4. **Two frameworks already have native validation-triggered re-ask
   mechanisms** (Instructor's automatic reask-on-validator-exception,
   PydanticAI's `ModelRetry`). Neither works if the caller *isn't* using
   that framework's structured-output path — which is precisely the gap a
   framework-agnostic wrapper fills, but it's worth being explicit in
   docs/positioning that these aren't being "replaced" so much as
   "made available to everyone else too."

5. **Streaming is the sharpest edge.** Every framework surveyed treats
   streaming as a structurally different return type (iterator/async
   iterator of chunks/events), not a variant of the same output shape.
   A retry/validation wrapper that wants to support streaming invocations
   at all needs a genuinely separate design (validate incrementally? buffer
   and validate at the end, defeating the point of streaming? explicitly
   out of scope for v1?) rather than a generics tweak.

6. **Retry counters are sometimes tracked per-concern, not globally**
   (PydanticAI: tool retries vs. output-validation retries are separate
   counters; the user's own harness README distinguishes retryable vs.
   terminal `ValidationFailure`s with a `feedback_mode` — tool message vs.
   system message vs. notification-style system message). A generic wrapper
   that only has one flat `max_attempts` may be under-modeling what
   real systems already need.

7. **Config that's invariant across attempts (model name, temperature,
   tools, `max_tokens`) is passed as call-site kwargs in every framework
   surveyed**, never as part of the "message" input structure itself. This
   supports the closure/partial-application approach discussed separately
   for this library's `Invokable` design — no framework threads static
   config through the same channel as the per-attempt input, so there's no
   precedent to match by inventing an args/kwargs passthrough.

---

## 5. Implication for the wrapper's core abstraction

Given the above, the shape that survives contact with all of these frameworks
is not "`f(list[Message]) -> Message`" but something closer to:

```python
Invokable = Callable[[TIn], TOut] | Callable[[TIn], Awaitable[TOut]]
```

fully generic over `TIn`/`TOut`, with the wrapper providing only:
- the loop (call → validate → decide retry/stop → repeat),
- a `Validator` contract operating on whatever the user's closure hands it
  (often *not* the raw return value — extraction is the user's job, or an
  optional user-supplied `extract_for_validation` hook),
- a `Feedbacker`/retry-input-builder contract, `(TIn, TOut, Failure) -> TIn`,
  left as full replacement rather than an assumed-appendable list, since at
  least three shapes above (`str`, `LLMResult`, content-block list) aren't
  naturally "appendable" in the way a LangChain message list is.

This matches every framework surveyed without requiring per-framework
special-casing inside the wrapper itself — the cost of supporting an
unusual shape (streaming, batch, multi-choice) is paid by the user writing
a slightly more involved closure, not by the wrapper growing branches.