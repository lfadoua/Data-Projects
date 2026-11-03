# LLM providers

Optional OpenAI Responses API or Ollama clients for structured claims. The default extractive answering mode operates without an LLM call.

Ollama local needs no API key. The local CPU setup uses `qwen2.5:1.5b`;
`qwen2.5:3b` remains an optional, more memory-intensive comparison.
`OLLAMA_NUM_GPU=0` bypasses the Vulkan failure observed on this PC.
An empty value retains Ollama's automatic selection.

`OLLAMA_NUM_PREDICT` optionally bounds generated tokens; an empty value preserves
the server's existing limit. `OLLAMA_TIMEOUT_SECONDS` defaults to 120 seconds.
Truncated or schema-invalid output raises a safe error retaining measured usage,
then the RAG service returns an explicitly labeled extraction fallback.

The legacy `GeneratedAnswer` contract includes model-proposed supporting quotes.
The explicit generative mode uses `GeneratedSummary` (text and source ID only):
the application supplies the selected exact quotes and validates the wording.
Both schemas bound the output to two claims. Provider duration fields from Ollama
are converted from nanoseconds to milliseconds without substituting missing data.

See [the RAG guide](../../docs/rag-local-optimization.md) for response modes,
Windows commands, reproducible benchmarks, provenance checks and limitations.
