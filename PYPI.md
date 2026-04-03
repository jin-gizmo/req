# Req - A Software Prerequisite Checker & Installer

**Req** (aka *JinReq*) is a simple Python based CLI gizmo for checking that
software prerequisites are installed and, optionally, installing them. It is
designed for use in software projects, CI/CD pipelines, makefiles etc.

**Req** uses a simple YAML based format to specify required software components
and the means to check if they are installed and, optionally, to install them.

![Linux](https://img.shields.io/badge/linux-F4BC00?logo=linux&logoColor=black)
![macOS](https://img.shields.io/badge/macOS-999999?logo=apple)
[![PyPI version](https://img.shields.io/pypi/v/jinreq)](https://pypi.org/project/jinreq/)
[![Python versions](https://img.shields.io/pypi/pyversions/jinreq)](https://pypi.org/project/jinreq/)
[![GitHub Licence](https://img.shields.io/github/license/jin-gizmo/req)](https://github.com/jin-gizmo/req/blob/master/LICENCE.txt)

## Installation

**Req** requires Python3.10+. It consists of a single Python file and has only
one external package dependency: [pyyaml](https://pypi.org/project/PyYAML/).

It can be installed from PyPI, but is also trivial to install manually.

```bash
pip install jinreq

# Check that it works
req --help
```

## Usage

See [req on GitHub](https://github.com/jin-gizmo/req).

To whet your appetite, here is simple example covering the
[aspell](http://aspell.net) open source spelling checker.

The values for the `if`, `check` and `install` keys are **bash** scripts. We're
using some helper functions and environment variables provided by **req**.

```yaml
name: demo
description: Introduction to req (jinreq)

require:
  - name: aspell
    description: Open source spell checker (http://aspell.net)

    # Requirement only applies if there is a doc directory present.
    # "req_has_dir" is a helper function.
    if: "req_has_dir doc"

    # Check if already installed. "req_has_command" is a helper function.
    check: "req_has_command aspell"

    # Install script (when requested). Req provides some environment variables
    # to assist with handling platform variations.
    install: |
      case "$REQ_FAMILY"
      in
        darwin)
                brew install aspell
                ;;
        debian)
                sudo apt update
                sudo apt install aspell aspell-en
                ;;
        fedora)
                sudo dnf install aspell aspell-en
                ;;
        arch)
                sudo pacman -S aspell aspell-en
                ;;
        alpine)
                sudo apk add aspell aspell-en
                ;;
        *)
                echo "Try searching your distro package manager index for \"aspell\""
                exit 1
                ;;
      esac
```

## More Gizmos

For more gizmos, check out Jin Gizmo.

[![Jin Gizmo Home](https://img.shields.io/badge/Jin_Gizmo_Home-d30000?logo=GitHub&color=d30000)](https://jin-gizmo.github.io)
