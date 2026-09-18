# Local Ollama AI integration

## Endpoint

Default:

```text
http://127.0.0.1:11434
```

The integration uses Ollama's REST API directly; no extra `ollama` Python package is required.

## Model discovery

`Detect Models` calls the local model list and then inspects model information/capabilities. A floorplan semantic reviewer must advertise the `vision` capability. If the installed Qwen tag is text-only, it will be rejected for image analysis even if it is otherwise a strong language model.

## Structured output

Semantic responses are requested with a JSON schema and deterministic temperature (`0`). This prevents free-form prose from becoming the interface between AI and geometry code.

## Floorplan candidate request

Each request contains a contact sheet of contextual floorplan crops. The candidate centerline is highlighted only for review-time disambiguation. The AI must classify the marked candidate, not detect or create geometry from scratch.

## Privacy

Non-local endpoints are blocked by default. This is intentional because customer floorplans/renderings may be confidential studio material. Remote transmission requires explicit opt-in.

## Training-data policy

Only manual labels are exported as training truth. Saved dataset images are raw crops without the colored review overlay. AI classifications can remain in analysis metadata for comparison, but they must never be promoted to ground-truth labels automatically.
