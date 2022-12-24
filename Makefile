.PHONY: release test


artifacts: test
	python -m build


clean:
	rm -rf dist/


prepforbuild:
	pip install build


build:
	python -m build


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
