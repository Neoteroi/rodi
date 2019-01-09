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
	pytest