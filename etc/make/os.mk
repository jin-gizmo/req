OS_TYPE:=$(shell uname -s)

ifeq ($(OS_TYPE),Darwin)
_host_is_mac:
else
_host_is_mac:
	$(error "This is not macOS")
endif

ifeq ($(OS_TYPE),Linux)
_host_is_linux:
else
_host_is_linux:
	$(error "This is not Linux")
endif
