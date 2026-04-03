#!/bin/bash
# ex: ts=4 sw=4 et ai

# req helper: version comparison utilities
# These functions are injected into every if/check/install script.
# Versions are compared component-wise as integers.
# Missing components default to 0, so 1.0 == 1.0.0.

# req_version_gte <v1> <v2>
# Return 0 if <v1> >= <v2>.
function req_version_gte() {
    awk -v a="$1" -v b="$2" 'BEGIN {
        na = split(a, av, "."); nb = split(b, bv, ".")
        n = (na < nb) ? na : nb
        for (i=1; i<=n; i++) {
            if (av[i]+0 > bv[i]+0) exit 0
            if (av[i]+0 < bv[i]+0) exit 1
        }
        exit 0
    }'
}

function req_version_eq() {
    awk -v a="$1" -v b="$2" 'BEGIN {
        na = split(a, av, "."); nb = split(b, bv, ".")
        n = (na < nb) ? na : nb
        for (i=1; i<=n; i++) {
            if (av[i]+0 != bv[i]+0) exit 1
        }
        exit 0
    }'
}

function req_version_gt() {
    req_version_gte "$1" "$2" && ! req_version_eq "$1" "$2"
}

# Extract the first string from stdin that looks like a version number.
# Eg. bash --version | req_extract_version
function req_extract_version() {
    grep -oE '[0-9]+(\.[0-9]+){0,2}' | head -1
}
