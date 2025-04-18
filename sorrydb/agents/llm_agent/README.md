# LLM agent

This agent will attempt to prove sorries in the SorryDB using a single-shot LLM call.
It serves as an example implementation of an agent for the `sorrydb` library.

## Usage

1. Get any API key from Anthropic, OpenAI or Google GenAI.

2. Create a `.env` file in the root of this repository and add your key(s):
```
ANTHROPIC_API_KEY=your-key
GOOGLE_API_KEY=your-key
OPENAI_API_KEY=your-key
```

3. Run the agent e.g.:
```
poetry run run_llm_agent
poetry run run_llm_agent --log-file llm_proof.log --sorry-db https://s.com/db.json --model-json path/to/model.json
```

## Model JSON Format

You can change the underlying model by providing a JSON file or change the hard-coded default.

```json
{
    "provider": "anthropic",  # anthropic, openai, google
    "cost": [3, 15],          # $/1M tokens (in, out)
    "params": {
        "model": "claude-3-7-sonnet-latest",
        "temperature": 0.0,   # optional, check langchain docs for more options
    },
}
```

## Token Usage

Token usage is variable depending on the model and the prompt. Attempting 508 sorries using Claude 3.7 resulted in 2981533 input tokens and 163996 output tokens.