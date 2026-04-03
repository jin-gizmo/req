#!/bin/bash
# ex: ts=4 sw=4 et ai

# req helper: command/path detection utilities
# These functions are injected into every if/check/install script.

# ------------------------------------------------------------------------------
# req_has_command <cmd>
# Return 0 if <cmd> is available on PATH.
# Prefer this over `which` or `type` for portability.
function req_has_command() {
    command -v "$1" > /dev/null 2>&1
}

# ------------------------------------------------------------------------------
# req_has_file <path>
# Return 0 if <path> exists and is a regular file.
function req_has_file() {
    [ -f "$1" ]
}

# ------------------------------------------------------------------------------
# req_has_dir <path>
# Return 0 if <path> exists and is a directory.
function req_has_dir() {
    [ -d "$1" ]
}
