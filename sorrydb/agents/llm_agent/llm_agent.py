import json
import logging
import time
from pathlib import Path

import dotenv
import requests
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from sorrydb.utils.git_ops import prepare_repository
from sorrydb.utils.lean_repo import build_lean_project
from sorrydb.utils.verify import verify_proof

# EXAMPLE PROMPTS IN LITERATURE
# https://github.com/cmu-l3/llmlean/blob/77448d68e51166f60bd43c6284b43d65209321b0/LLMlean/API.lean#L258
# https://plmlab.math.cnrs.fr/nuccio/octonions/-/blob/c3569703fd17191c279908509b8845735d5c507e/Mathlib/Tactic/GPT/Sagredo/Dialog.lean
# https://github.com/GasStationManager/LeanTool/blob/main/leantool.py
# https://github.com/quinn-dougherty/fvapps/blob/master/src/baselines/baselines_config.py
# https://github.com/Goedel-LM/Goedel-Prover/blob/5988bb0e3650f0417b61da4b10885e7ad6ca75fc/prover/utils.py#L23
# https://github.com/lean-dojo/LeanCopilot/blob/e2aebdab8e9b1c74a5334b36ba2c288c5a5f175d/python/external_models/hf_runner.py#L41
# https://github.com/oOo0oOo/lean-scribe/blob/main/default_scribe_folder/default_prompts/progress_in_proof.md


PROMPT = """You are an advanced AI that has studied all known mathematics. Solve the following proof:

Proof Goal:
```lean
{goal}
```

Lean Code:
```lean
{file_text}
```

Write Lean 4 code to exactly replace the sorry starting at line {line}, column {column}.

You cannot import any additional libraries to the ones already imported in the file.
Write a short, simple and elegant proof.
Do not re-state the theorem or "by".
ONLY WRITE EXACTLY THE CODE TO REPLACE THE SORRY, including indentation.
DO NOT WRITE ANY COMMENTS OR EXPLANATIONS! Just write code!
"""


logger = logging.getLogger(__name__)


class LLMAgent:
    """LLMAgent sets up Lean project and REPL, then attempts to solve it using an LLM.

    Example model JSON:
    ```json
        {
            "provider": "anthropic",
            "cost": [3, 15],  # $/1M tokens: Input, output
            "params": {"model": "claude-3-7-sonnet-latest"},
        }
    ```

    Args:
        model_json (str | None): Path to the model config JSON. Defaults to None.
        lean_dir (str): Directory to store Lean data. Defaults to "lean_data".
    """

    def __init__(self, model_json: str = None, lean_dir: str = "lean_data"):
        # Load environment variables
        dotenv.load_dotenv()

        # Load model config
        if model_json is None:
            model_config = {
                "provider": "anthropic",
                "cost": [3, 15],
                "params": {"model": "claude-3-7-sonnet-latest"},
            }
        else:
            with open(model_json) as f:
                model_config = json.load(f)
        self.model_config = model_config

        # Setup LLM
        if model_config["provider"] == "anthropic":
            self.model = ChatAnthropic(**model_config["params"])
        elif model_config["provider"] == "openai":
            self.model = ChatOpenAI(**model_config["params"])
        elif model_config["provider"] == "google":
            self.model = ChatGoogleGenerativeAI(**model_config["params"])
        else:
            raise ValueError(f"Invalid model provider: {model_config['provider']}")

        # Create lean directory if it doesn't exist
        self.lean_dir = Path(lean_dir).resolve()
        self.lean_dir.mkdir(exist_ok=True)

        # Keep track of token usage
        self.token_usage = [0, 0]

    def _invoke_model(self, prompt: str) -> str:
        """Invoke the LLM model with a given prompt.

        Args:
            prompt (str): Prompt to provide to the LLM model

        Returns:
            str: Response from the LLM model
        """
        logger.info("Prompting LLM, length: %d" % len(prompt))
        response = self.model.invoke([HumanMessage(content=prompt)])

        usage = response.response_metadata.get("usage", None)
        if usage is None:
            usage = response.usage_metadata
        self.token_usage[0] += usage["input_tokens"]
        self.token_usage[1] += usage["output_tokens"]

        logger.info("LLM response:\n" + response.content)
        return response.content

    def _preprocess_proof(self, proof: str, base_indentation: int) -> str:
        """Process the proof to increase the chance of success.

        Fix indentation, remove code block, ...

        Args:
            proof (str): Proof as a string

        Returns:
            str: Processed proof
        """
        # CLEAN
        # Extract code from ```lean ``` code block if it is present
        if "```lean" in proof:
            proof = proof.split("```lean")[1].split("```")[0]

        # Remove "by" at the beginning of the proof
        if proof.startswith("by"):
            proof = proof[2:]

        # Remove empty lines and base indentation
        lines = [line for line in proof.split("\n") if line.strip()]

        # FIX INDENTATION
        # First line is never indented
        lines[0] = lines[0].lstrip()

        # Second line is only indented more than base indentation if:
        # - Ends with by
        # - Is refine
        expected_indentation = base_indentation
        if lines[0].endswith("by") or lines[0].strip() == "refine":
            expected_indentation += 2

        # Assume all following lines are indented the same
        actual_indentation = len(lines[1]) - len(lines[1].lstrip())
        difference = actual_indentation - expected_indentation
        if difference < 0:
            # Increase indentation of all lines
            lines = [lines[0]] + ["  " * abs(difference) + line for line in lines[1:]]
        elif difference > 0:
            # Decrease indentation of all lines
            lines = [lines[0]] + [line[difference:] for line in lines[1:]]

        return "\n".join(lines)

    def solve_sorry(self, sorry_config: dict) -> str | None:
        """Solve the sorry using the LLM model.

        Returns:
            str | None: Proof (list of tactics) or None if not solved.
        """
        # Setup the Lean project
        try:
            repo = sorry_config["repo"]
            repo_path = prepare_repository(
                repo["remote"], repo["branch"], repo["commit"], self.lean_dir
            )
            if repo_path is None:
                return None
            build_lean_project(repo_path)
        except Exception as e:
            logger.error(f"Error preparing repository: {e}")
            return None

        # Load the file and render the prompt
        loc = sorry_config["location"]
        file_path = Path(repo_path, loc["file"])
        file_text = file_path.read_text()

        # Render the prompt
        prompt = PROMPT.format(
            goal=sorry_config["debug_info"]["goal"],
            file_text=file_text,
            line=loc["start_line"],
            column=loc["start_column"],
        )

        # Run the prompt, check the proof
        proof = self._invoke_model(prompt)
        processed = self._preprocess_proof(proof, loc["start_column"])

        solved = verify_proof(
            repo_path,
            repo["lean_version"],
            loc,
            processed,
        )
        if solved:
            logger.info(f"Solved sorry {sorry_config['id']}")
            return processed
        else:
            logger.info(f"Failed to solve sorry {sorry_config['id']}")
            return None

    def solve_sorry_db(self, sorry_db_url: str, out_json: str):
        """Run all sorries in the sorry DB

        Args:
            sorry_db_url (str): URL of the sorry DB
            out_json (str): Path to the output JSON file
        """
        sorry_db = json.loads(requests.get(sorry_db_url).text)

        num_repos = len(sorry_db["repos"])
        num_sorries = len(sorry_db["sorries"])
        logger.info(f"Loaded {num_sorries} sorries in {num_repos} repos.")

        # Keep only unique sorries (by goal string)
        sorries = {
            sorry["debug_info"]["goal"]: sorry for sorry in sorry_db["sorries"]
        }.values()
        logger.info(f"Filtered to {len(sorries)} unique sorries (by goal string).")

        t0 = time.time()
        llm_proofs = {}
        for sorry in sorries:
            logger.info(f"Attempting sorry {sorry['id']}")

            try:
                llm_proofs[sorry["id"]] = self.solve_sorry(sorry)
            except Exception as e:
                logger.error(f"Error solving sorry {sorry['id']}: {e}")
                llm_proofs[sorry["id"]] = None
            logger.info(f"Total model cost: $%.2f $" % self.get_cost())

            with open(out_json, "w") as f:
                json.dump(llm_proofs, f)

        msg = f"Solved {len([p for p in llm_proofs.values() if p])} / {len(llm_proofs)} sorries in {(time.time() - t0) / 60:.2f} minutes."
        logger.info(msg)
        msg = f"Total token usage: {self.token_usage[0]} input, {self.token_usage[1]} output"
        logger.info(msg)

    def get_cost(self) -> float:
        """Get the total cost of using the model.

        Returns:
            float: Total model usage in $
        """
        return sum(
            t * c / 1e6 for t, c in zip(self.token_usage, self.model_config["cost"])
        )
