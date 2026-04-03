
ifeq ($(PYTHON3),)
PYTHON3:=python3
endif
ifeq ($(VENV),)
VENV:=venv
endif


.PHONY:	_venv_is_off _venv_is_on _venv


_venv_is_off:
	@if [ "$$VIRTUAL_ENV" != "" ] ; \
	then \
		echo Deactivate your virtualenv for this operation ; \
		exit 1 ; \
	fi

_venv_is_on:
	@if [ "$$VIRTUAL_ENV" == "" ] ; \
	then \
		echo Activate your virtualenv for this operation ; \
		exit 1 ; \
	fi

# Setup the virtual environment
_venv:	_venv_is_off
	@if [ ! -d "$(VENV)" ] ; \
	then \
		echo Creating virtual environment ; \
		$(PYTHON3) -m venv "$(VENV)" ; \
	fi
	@( \
		echo Activating virtual environment ; \
		source "$(VENV)/bin/activate" ; \
		export PIP_INDEX_URL=$(PIP_INDEX_URL) ; \
		echo Installing requirements ; \
		$(PYTHON3) -m pip install pip --upgrade ; \
		$(PYTHON3) -m pip install -r requirements.txt --upgrade ; \
		$(PYTHON3) -m pip install -r requirements-build.txt --upgrade ; \
		: ; \
	)

