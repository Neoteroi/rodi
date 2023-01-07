import glob
import importlib
import sys

import pytest

examples = [file for file in glob.glob("./examples/*.py")]


sys.path.append("./examples")


@pytest.mark.parametrize("file_path", examples)
def test_example(file_path: str):
    module_name = file_path.replace("./examples/", "").replace(".py", "")
    # assertions are in imported modules
    importlib.import_module(module_name)
