PYTHON3:=python3

include etc/make/help.mk
include etc/make/venv.mk

SHELL:=/bin/bash
HELP_CATEGORY=Getting started
APP=req
draft=false

#+ **Welcome to $(APP) (v$(VERSION))** - $(REPO_URL)
#- Help brought to you by **MakeHelp** - https://github.com/jin-gizmo/makehelp.


# Force help category ordering
#:cat Getting started
#:cat Build targets
#:cat Install targets
#:cat Documentation targets
#:cat Test targets
#:cat Miscellaneous targets

pypi=pypi

# ------------------------------------------------------------------------------
PKG=jin$(APP)
REPO_URL=https://github.com/jin-gizmo/$(APP)
VERSION:=$(shell python3 -c 'from $(APP).conf import __version__; print(__version__)')
SRC=$(shell find $(APP) -type d -name '__pycache__' -prune  -o -type f -print)
RELEASE_SRC=$(APP).schema.yaml
PYTEST_WORKERS=5
DOC:=$(wildcard *.md)
CUSTOM_DICT=$(realpath .aspell-dict)

.PHONY: init pkg check toc spell test coverage pypi clean release

# ------------------------------------------------------------------------------
#:cat Getting started

## Initialise / update the project (create venv etc.). Idempotent.
init:	_venv pre-req
	git config core.hooksPath etc/git-hooks

## Check prerequisites required to work with the repo are installed.
pre-req:
	@( \
		source "$(VENV)/bin/activate" ; \
		echo ; \
		echo "Checking prerequisites ..." ; \
		python3 -m "$(APP).cli.$(APP)" check "$(APP).yaml" ; \
	)


# ------------------------------------------------------------------------------
#:cat Build targets

## Build the Python package
pkg:	_venv_is_on
	@mkdir -p dist/pkg
	python3 setup.py sdist --dist-dir dist/pkg

# ------------------------------------------------------------------------------
#:cat Install targets

~/.pypirc:
	$(error You need to create $@ with an index-server section for "$(pypi)")

## Upload the pkg to the `pypi` PyPI server via twine. The `pypi` server must be
## defined in `~/.pypirc`.
#:opt pypi
pypi:	_venv_is_on ~/.pypirc pkg
	twine check "dist/pkg/$(PKG)-$(VERSION).tar.gz"
	twine upload -r "$(pypi)" "dist/pkg/$(PKG)-$(VERSION).tar.gz"

_repo_is_clean:
	@if ! git diff-index --quiet HEAD --; \
	then \
		echo "Working directory not clean! Commit or stash first."; \
		exit 1; \
	fi

_on_master:
	@if [ "$$(git rev-parse --abbrev-ref HEAD)" != "master" ]; \
	then \
		echo "Not on master branch!"; \
		exit 1; \
	fi

## Create a github release. Set *draft* to either `true` or `false`.
## To force updating an existing full version tag, set *force* to `-f`.
#:opt draft force
release: _repo_is_clean _on_master
	git tag $(force) "v$(VERSION)"
	git push origin $(force) "v$(VERSION)"
	git tag -f "v$(V_MAJOR)"
	git push origin -f "v$(V_MAJOR)"
	@echo "Creating GitHub release ..."
	@if gh release view "v$(VERSION)" > /dev/null 2>&1 ; \
	then \
		echo "Updating existing release for tag v$(VERSION)" ; \
		gh release upload --clobber "v$(VERSION)" $(RELEASE_SRC) ; \
		gh release edit \
			--draft="$(draft)" \
			--verify-tag=false \
			--title "Version $(VERSION)" \
			--notes "$(REPO_URL)/tree/master?tab=readme-ov-file#release-notes" \
			"v$(VERSION)" ; \
	else \
		echo "Creating new release for tag v$(VERSION)" ; \
		gh release create \
			--draft="$(draft)" \
			--fail-on-no-commits \
			--verify-tag=false \
			--title "Version $(VERSION)" \
			--notes "$(REPO_URL)/tree/master?tab=readme-ov-file#release-notes" \
			"v$(VERSION)" \
			$(RELEASE_SRC) ; \
	fi
	@gh release view "v$(VERSION)"


# ------------------------------------------------------------------------------
#:cat Documentation targets
## Spell check the documentation (requires **aspell**).
spell:
	@for i in $(DOC) ; \
	do \
		echo "$$i" ; \
		aspell -p "$(CUSTOM_DICT)" check "$$i" ; \
	done

## Update the TOC in `README.md`.
toc:
	@set -e ; \
	tmp=$$(mktemp) ; \
	z=1 ; \
	trap '/bin/rm -f $$tmp; exit $$z' 0 ; \
	etc/tocmark README.md > $$tmp || exit ; \
	if cmp -s README.md $$tmp ; \
	then \
		echo "README.md already up to date" ; \
	else \
		cp README.md README.md.bak ; \
		mv $$tmp README.md ; \
		echo "README.md TOC updated" ; \
	fi ; \
	z=0


# ------------------------------------------------------------------------------
#:cat Test targets

TESTENVS:=$(patsubst test/resources/test-%.Dockerfile,%,$(wildcard test/resources/*.Dockerfile))
_TE:=$(foreach env,$(TESTENVS), `$(env)`)

## Build a docker image for running $(APP) tests for the target environment.
## `%` must be one of $(_TE).
image.%:
	@mkdir -p dist/docker-context
	cp requirements.txt dist/docker-context
	docker buildx build --pull -f "test/resources/test-$*.Dockerfile" -t "$(APP)-test:$*" dist/docker-context


## Build all available test images.
image-all: $(foreach env,$(TESTENVS),image.$(env))

## Run the unit tests and produce a coverage report.
coverage: _venv_is_on
	@mkdir -p dist/test
	pytest --cov=. --cov-report html:dist/test/htmlcov -n "$(PYTEST_WORKERS)"

## Run the unit tests.
test:	_venv_is_on
	pytest -v -s -n "$(PYTEST_WORKERS)"

# ------------------------------------------------------------------------------
#:cat Miscellaneous targets

## Run the pre-commit checks (code quality etc.).
check:	_venv_is_on
	etc/git-hooks/pre-commit

## Remove the ephemeral stuff.
clean:
	$(RM) -r dist
	docker images --filter=reference='$(APP)-test:*' --format '{{.Repository}}:{{.Tag}}' | \
	while read -r img ; \
	do \
		docker rmi -f "$$img" ; \
	done
