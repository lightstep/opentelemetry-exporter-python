# Releasing

Once all the changes for a release have been merged to master, ensure the following:

- [ ] version has been updated in `cat src/opentelemetry/ext/lightstep/version.py` 
- [ ] tests are passing
- [ ] user facing documentation has been updated

# Publishing

Publishing to [pypi](https://pypi.org/project/opentelemetry-ext-lightstep/) is automated via GitHub actions. Once a tag is pushed to the repo, a new GitHub Release is created and package is published  via the actions defined here: https://github.com/lightstep/opentelemetry-exporter-python/blob/master/.github/workflows/release.yml

```
$ git clone git@github.com:lightstep/opentelemetry-exporter-python && cd opentelemetry-exporter-python

# ensure the version matches the version beind released
$ cat cat src/opentelemetry/ext/lightstep/version.py
__version__ = '0.7b0'

$ git tag v0.7b0 && git push origin v0.7b0
```
