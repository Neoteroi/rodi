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
	pytest


test-cov:
	pytest --cov-report html --cov=rodi tests/


format:
	isort rodi
	isort tests
	black rodi
	black tests


lint-types:
	mypy rodi --explicit-package-bases


check-flake8:
	@echo "$(BOLD)Checking flake8$(RESET)"
	@flake8 rodi 2>&1
	@flake8 tests 2>&1


check-isort:
	@echo "$(BOLD)Checking isort$(RESET)"
	@isort --check-only rodi 2>&1
	@isort --check-only tests 2>&1


check-black:  ## Run the black tool in check mode only (won't modify files)
	@echo "$(BOLD)Checking black$(RESET)"
	@black --check rodi 2>&1
	@black --check tests 2>&1


lint: check-flake8 check-isort check-black
