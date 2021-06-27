.PHONY: release test


artifacts: test
	python setup.py sdist bdist_wheel


clean:
	rm -rf dist/


prepforbuild:
	pip install --upgrade twine setuptools wheel


uploadtest:
	twine upload --repository-url https://test.pypi.org/legacy/ dist/*


release: clean artifacts
	twine upload --repository-url https://upload.pypi.org/legacy/ dist/*


test:
	flake8 && pytest


testcov:
	pytest --cov-report html --cov-report annotate --cov=rodi tests/


format:
	isort rodi
	isort tests
	black rodi
	black tests
