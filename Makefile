.PHONY: release test


artifacts: test
	python -m build


clean:
	rm -rf dist/


prepforbuild:
	pip install --upgrade twine setuptools wheel


test-release:
	twine upload --repository testpypi dist/*


release:
	twine upload --repository pypi dist/*


test:
	flake8 && pytest


test-cov:
	pytest --cov-report html --cov=rodi tests/


format:
	isort rodi
	isort tests
	black rodi
	black tests
