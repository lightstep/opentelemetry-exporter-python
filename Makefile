test:
	pytest

cover:
	pytest --cov src/opentelemetry/ext/lightstep

lint:
	pip install black
	black .

clean-dist:
	rm -Rf ./dist

dist: clean-dist
	mkdir -p dist
	python setup.py sdist      # source distribution
	python setup.py bdist_wheel

publish: dist
	git push --tags
	twine upload dist/*

publish-test:
	twine upload --repository-url https://test.pypi.org/legacy/ dist/*
