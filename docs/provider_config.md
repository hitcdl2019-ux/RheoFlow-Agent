# Provider Configuration

RheoFlow-Agent reads model-provider settings from environment variables. Keep credentials outside Git.

## Common variables

| Variable | Purpose |
|---|---|
| `FOAMAGENT_MODEL_PROVIDER` | Provider branch, such as `novaapi`, `openai`, `openai-codex`, `anthropic`, `bedrock`, or `ollama`. |
| `FOAMAGENT_MODEL_VERSION` | Model name used by the selected provider. |
| `NOVA_API_KEY` | API key for OpenAI-compatible gateway configurations named `novaapi`. |
| `NOVA_API_BASE_URL` | Base URL for the `novaapi` gateway. |
| `OPENAI_API_KEY` | OpenAI API key when using OpenAI-compatible official endpoints. |
| `ANTHROPIC_API_KEY` | Anthropic API key. |
| `CODEBUDDY_API_KEY` | Optional CodeBuddy gateway credential where supported. |
| `CODEBUDDY_BASE_URL` | Optional CodeBuddy gateway base URL. |
| `CODEBUDDY_MODEL` | Optional CodeBuddy model identifier. |

## Example: OpenAI-compatible gateway

```bash
export FOAMAGENT_MODEL_PROVIDER="novaapi"
export FOAMAGENT_MODEL_VERSION="deepseek-v4-pro"
export NOVA_API_KEY="your-private-key"
export NOVA_API_BASE_URL="https://your-provider.example/v1"
```

## Example: MCP config fragment

```json
{
  "mcpServers": {
    "rheoflow-agent": {
      "command": "rheoflow-agent-mcp",
      "args": ["--transport", "stdio"],
      "env": {
        "FOAMAGENT_MODEL_PROVIDER": "${FOAMAGENT_MODEL_PROVIDER:-novaapi}",
        "FOAMAGENT_MODEL_VERSION": "${FOAMAGENT_MODEL_VERSION:-}",
        "NOVA_API_KEY": "${NOVA_API_KEY:-}",
        "NOVA_API_BASE_URL": "${NOVA_API_BASE_URL:-}"
      }
    }
  }
}
```

## Notes

- Provider names should be normalized and validated by the application. Do not rely on arbitrary user text as a trusted provider branch.
- If the provider is OpenAI-compatible but hosted by a third-party gateway, configure both key and base URL.
- Never print or commit API keys in logs, reports, screenshots, or examples.
