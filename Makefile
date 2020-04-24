PACKAGE := puppetctl
.DEFAULT: test
.PHONY: all test coverage coveragereport pep8 pylint rpm clean
TEST_FLAGS_FOR_SUITE := -m unittest discover -t . -s test -f

PLAIN_PYTHON = $(shell which python 2>/dev/null)
PYTHON3 = $(shell which python3 2>/dev/null)
ifneq (, $(PYTHON3))
  PYTHON_BIN = $(PYTHON3)
endif
ifneq (, $(PLAIN_PYTHON))
  PYTHON_BIN = $(PLAIN_PYTHON)
endif

COVERAGE2 = $(shell which coverage 2>/dev/null)
COVERAGE3 = $(shell which coverage-3 2>/dev/null)
ifneq (, $(COVERAGE2))
  COVERAGE = $(COVERAGE2)
endif
ifneq (, $(COVERAGE3))
  COVERAGE = $(COVERAGE3)
endif

all: test

test:
	python -B $(TEST_FLAGS_FOR_SUITE)

coverage:
	$(COVERAGE) run $(TEST_FLAGS_FOR_SUITE)

coveragereport:
	$(COVERAGE) report -m $(PACKAGE)/*.py test/*.py

pep8:
	@find ./* -type f -name '*.py' -exec pep8 --show-source --max-line-length=100 {} \;

# lining the main script:
# useless-object-inheritancee: because this script is made for py2 and py3,
# meaning we have to declare classes with py2 syntax that py3-pylint hates.
# superfluous-parens: print statements in py2 keep tripping this up
#
# linting test
# protected-access: well OF COURSE the test suite will call protected classes
# locally-disabled: we trust the file to call out its own "don't lint this, I know what I'm doing"
pylint:
	@find ./* -path ./test -prune -o -type f -name '*.py' -exec pylint -r no --disable=useless-object-inheritance,superfluous-parens --rcfile=/dev/null {} \;
	@find ./test -type f -name '*.py' -exec pylint -r no --disable=protected-access,locally-disabled --rcfile=/dev/null {} \;

rpm:
	fpm -s python -t rpm --python-bin $(PYTHON_BIN) --python-install-bin /usr/bin --no-python-fix-name --rpm-dist "$$(rpmbuild -E '%{?dist}' | sed -e 's#^\.##')" --iteration 1 setup.py
	@rm -rf build $(PACKAGE).egg-info

clean:
	rm -f $(PACKAGE)/*.pyc test/*.pyc
	rm -rf $(PACKAGE)/__pycache__ test/__pycache__
	rm -rf build $(PACKAGE).egg-info
