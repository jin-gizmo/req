#!/bin/bash
# ex: ts=4 sw=4 et ai

# req helper: platform predicates
# These are just syntactic sugar really. Marginal value.
# These functions are injected into every if/check/install script.

function req_is_darwin()  { [ "$REQ_OS"     = 'darwin'  ]; }
function req_is_macos()   { [ "$REQ_OS"     = 'darwin'  ]; }

function req_is_linux()   { [ "$REQ_OS"     = 'linux'   ]; }
function req_is_debian()  { [ "$REQ_FAMILY" = 'debian'  ]; }
function req_is_fedora()  { [ "$REQ_FAMILY" = 'fedora'  ]; }
function req_is_arch()    { [ "$REQ_FAMILY" = 'arch'    ]; }
function req_is_alpine()  { [ "$REQ_FAMILY" = 'alpine'  ]; }
function req_is_suse()    { [ "$REQ_FAMILY" = 'suse'    ]; }
