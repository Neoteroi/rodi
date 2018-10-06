.PHONY: release test


artifacts: test
	python setup.py sdist bdist_wheel


release: test
	python setup.py sdist upload


test:
	pytest