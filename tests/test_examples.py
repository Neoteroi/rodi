import glob
import pytest
import subprocess


examples = [file for file in glob.glob("./examples/*.py")]


@pytest.mark.parametrize("file_path", examples)
def test_example(file_path: str):
    output = subprocess.run(["python", file_path])
    assert output.returncode == 0
