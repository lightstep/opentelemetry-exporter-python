test:
	pip install -e .[test]
	pytest

cover:
	pytest --cov src/opentelemetry/ext/lightstep

lint:
	black . --diff --check
	isort --recursive . 
	# stop the build if there are Python syntax errors or undefined names
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	# exit-zero treats all errors as warnings. The GitHub editor is 127 chars wide
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

clean-dist:
	rm -Rf ./dist

dist: clean-dist
	mkdir -p ./dist
	python setup.py sdist      # source distribution
	python setup.py bdist_wheel

publish: dist
	twine upload dist/*

publish-test:
	twine upload --repository-url https://test.pypi.org/legacy/ dist/*

changelog:
	pip install pystache gitchangelog
	gitchangelog
