# Guides

The top-level README is the landing page. These guides go deeper where the
README stays intentionally terse.

## Reading order

1. [Getting Started](./getting_started.md): build your first working `arun(...)` loop with extraction, validation, and feedback.
2. [API Reference](./api_reference.md): look up exact signatures, callback shapes, failure semantics, and history/result details.
3. [Patterns](./patterns.md): reuse pipelines with `Runner`, wrap exceptions, and apply the loop across different SDK and request shapes.

## Start Here If...

- You want your first successful run: [Getting Started](./getting_started.md)
- You want the exact contract: [API Reference](./api_reference.md)
- You want recipes and reusable patterns: [Patterns](./patterns.md)

## Notes

- These guides document the public v1 package surface in `src/agent_feedback/`.
- Design notes under `docs/design/` are useful background, but they may discuss ideas that are not part of the shipped API.
- The files under `defunct/` are reference material, not user-facing docs.
