"""
Generates a README.md file for the examples folder.
"""

import glob
import importlib
import sys

examples = [file for file in glob.glob("./examples/*.py")]
examples.sort()
sys.path.append("./examples")

with open("./examples/README.md", mode="wt", encoding="utf8 ") as examples_readme:
    examples_readme.write(
        "<!-- generated file, to update use: python examples-summary.py -->\n\n"
    )
    examples_readme.write("""# Examples""")

    for file_path in examples:
        if "__init__" in file_path:
            continue

        module_name = file_path.replace("./examples/", "").replace(".py", "")

        module = importlib.import_module(module_name)

        if not module.__doc__:
            continue

        examples_readme.write(f"\n\n## {module_name}.py\n")
        examples_readme.write(str(module.__doc__))
