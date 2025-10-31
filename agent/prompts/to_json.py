import glob
import importlib
from pathlib import Path
import json
import os


prompt_root = Path(__file__).parent

input_dir = prompt_root / "raw"
output_dir = prompt_root / "jsons"
output_dir.mkdir(exist_ok=True)


# use the current directory as the root
def run() -> None:
    """Convert all python files in agent/prompts to json files in agent/prompts/jsons

    Python files are easiser to edit
    """

    print(f"Converting python files in {input_dir} to json files in {output_dir}")

    n = 0
    for p_file in glob.glob(str(input_dir / "*.py")):
        # import the file as a module
        base_name = os.path.basename(str(p_file)).replace(".py", "")
        module = importlib.import_module(f"webarena.agent.prompts.raw.{base_name}")
        prompt = module.prompt
        # save the prompt as a json file
        with open(output_dir / f"{base_name}.json", "w+") as f:
            json.dump(prompt, f, indent=2)
        n += 1
    print(f"Converted {n} python files to json files")
    print("Done.")


if __name__ == "__main__":
    run()
