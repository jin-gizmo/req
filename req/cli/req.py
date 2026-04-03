#!/usr/bin/env python3
"""Prerequisite checker and installer for software projects."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
from collections.abc import Callable
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path
from platform import freedesktop_os_release
from shlex import quote
from string import Template
from typing import Any, ClassVar

import yaml

from req.conf import DOC_URL, MIN_PYTHON, __version__

__author__ = 'Murray Andrews'

# ------------------------------------------------------------------------------
PROG = Path(sys.argv[0]).stem
# Installs that exit with this status suppress a post install recheck.
STATUS_NO_RECHECK = 126
DEFAULT_DOC_TEMPLATE = {
    'prologue': """
### ${name} - ${description}

| # | Name | Description |
|:-:|------|-------------|
""",
    'requirement': '| ${index} | ${name} | ${description} |\n',
    'epilogue': '\n',
}

# Emoji / ASCII reporting markers
EMOJI = {
    'ok': '✅',
    'fail': '❌',
    'warn': '⚠️',
    'skip': '🚫',
    'info': '🔵',
}
ASCII = {
    'ok': '[OK]  ',
    'fail': '[FAIL]',
    'warn': '[WARN]',
    'skip': '[SKIP]',
    'info': '[INFO]',
}

# Map of canonical distro family name -> set of ID/ID_LIKE values that indicate membership.
DISTRO_FAMILIES: dict[str, set[str]] = {
    'debian': {'debian', 'ubuntu', 'mint', 'raspbian', 'pop'},
    'fedora': {'fedora', 'rhel', 'centos', 'rocky', 'alma', 'ol', 'amzn'},
    'arch': {'arch', 'manjaro', 'endeavouros'},
    'alpine': {'alpine'},
    'suse': {'suse', 'opensuse'},
}


# ------------------------------------------------------------------------------
class RequirementError(Exception):
    """Raised when one or more mandatory requirements are not satisfied."""


# ------------------------------------------------------------------------------
class Context:
    """Runtime environment context passed to all command handlers."""

    # --------------------------------------------------------------------------
    def __init__(self, colour: bool = True) -> None:
        """
        Detect the current platform and build a Context instance.

        :param colour:  Whether or not to use colour / emoji when stdout is a tty.
        """

        self.use_emoji = sys.stdout.isatty() and colour
        self.req_os = platform.system().lower()  # 'darwin' or 'linux'
        self.helper_script = load_bash_helpers()

        if self.req_os == 'darwin':
            self.req_id = 'darwin'
            self.req_family = 'darwin'
            self.req_id_like = ''
            self.req_version_id = platform.mac_ver()[0]
            return

        # If its not Linux we're in trouble.
        try:
            os_release = freedesktop_os_release()
        except OSError as e:
            raise RuntimeError(f'Unable to determine OS details: {e}') from e

        self.req_id = os_release.get('ID', '').lower()
        self.req_id_like = os_release.get('ID_LIKE', '').lower()
        self.req_family = detect_distro_family(self.req_id, self.req_id_like)
        self.req_version_id = os_release.get('VERSION_ID', '')

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the platform bits of the context."""
        return {
            'REQ_OS': self.req_os,
            'REQ_FAMILY': self.req_family,
            'REQ_ID': self.req_id,
            'REQ_ID_LIKE': self.req_id_like,
            'REQ_VERSION_ID': self.req_version_id,
        }

    # --------------------------------------------------------------------------
    def as_env(self) -> dict[str, str]:
        """Return a copy of the current environment augmented with REQ_* variables."""
        return {**os.environ, **self.as_dict()}

    # --------------------------------------------------------------------------
    def print_event(self, kind: str, msg: str) -> None:
        """
        Print an event with an associated status.

        :param kind: The kind of event (ok/fail/warn/skip).
        :param msg: The message for the event.
        """

        marker = EMOJI[kind] if self.use_emoji else ASCII[kind]
        print(f'{marker}  {msg}')

    # --------------------------------------------------------------------------
    def __repr__(self):
        """Return a string representation of the platform bits of the context."""
        return f'{self.__class__.__name__}({self.as_dict()!r})'

    # --------------------------------------------------------------------------
    def __str__(self):
        """Return a string representation of the platform bits of the context."""
        return str(self.as_dict())


# ------------------------------------------------------------------------------
def check_python_version() -> None:
    """Raise RuntimeError if Python version is below the minimum supported version."""
    if sys.version_info < MIN_PYTHON:
        major, minor = MIN_PYTHON
        raise RuntimeError(
            f'{PROG} requires Python {major}.{minor} or later (running {platform.python_version()})'
        )


# ------------------------------------------------------------------------------
def detect_distro_family(req_id: str, req_id_like: str) -> str:
    """
    Determine the O/S distro family.

    If ID_LIKE is present it is the distro's own declaration of family membership
    and is used directly. When ID_LIKE is absent or unrecognised we fall
    back to ID itself.

    """
    if req_id_like:
        # ID_LIKE is authoritative -- trust it directly
        tokens = set(req_id_like.lower().split())
        for family, members in DISTRO_FAMILIES.items():
            if tokens & members:
                return family

    # No ID_LIKE, or ID_LIKE contained no recognised family token -- resolve ID
    if req_id:
        tokens = {req_id.lower()}
        for family, members in DISTRO_FAMILIES.items():
            if tokens & members:
                return family

    return req_id or 'unknown'


# ------------------------------------------------------------------------------
def load_bash_helpers() -> str:
    """
    Load all *.sh helper files from the package helpers directory.

    Requires req to be run as a package: python3 -m req.cli.req or installed via
    pip.
    """

    fragments = []
    helpers = files('req.helpers')
    for sh_file in sorted(helpers.iterdir(), key=lambda f: f.name):
        if sh_file.name.endswith('.sh'):
            fragments.append(sh_file.read_text(encoding='utf-8'))

    return '\n'.join(fragments)


# ------------------------------------------------------------------------------
@dataclass(frozen=True)
class Requirement:
    """A single prerequisite requirement."""

    name: str
    description: str
    optional: bool
    if_script: str  # shell snippet; exit 0 = applicable
    check_script: str  # shell snippet; exit 0 = satisfied
    install_script: str  # shell snippet; empty = no recipe

    # ------------------------------------------------------------------------------
    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> Requirement:
        """Load a requirement from a dictionary."""

        if not isinstance(item, dict):
            raise ValueError('Requirement must be a mapping')

        name = item.get('name')
        if not name:
            raise ValueError('Requirement is missing "name"')

        check_script = item.get('check', '').strip()
        if not check_script:
            raise ValueError(f'Requirement "{name}" is missing "check"')

        return cls(
            name=str(name),
            description=str(item.get('description', '')).strip(),
            optional=bool(item.get('optional', False)),
            if_script=str(item.get('if', '')).strip(),
            check_script=check_script,
            install_script=str(item.get('install', '')).strip(),
        )

    # --------------------------------------------------------------------------
    def report(self, kind: str, context: Context) -> None:
        """
        Print a single requirement result line.

        :param kind:    One of: 'ok', 'fail', 'warn', 'skip', 'info'.
        :param context: The platform context in which the requirement is checked.

        """

        desc = f' -- {self.description}' if self.description else ''
        optional_tag = ' (optional)' if self.optional else ''
        context.print_event(kind, f'{self.name}{optional_tag}{desc}')

    # --------------------------------------------------------------------------
    def check(self, context: Context, trace: bool = False, verbose: bool = False) -> str:
        """
        Run the check for the requirement.

        :param context: The platform context in which the requirement is checked.
        :param trace:   If true, run the script in trace mode (bash -x).
        :param verbose: If True, always pass stderr through. By default, stderr is
                        suppressed when not in trace mode and the script exits ok.
        :return:        One of: 'ok', 'fail', 'warn', 'skip', 'info'.
        """

        rc = run_script(
            self.check_script, context, label=f'{self.name}:check', trace=trace, verbose=verbose
        )
        if rc == 0:
            return 'ok'

        return 'warn' if self.optional else 'fail'

    # --------------------------------------------------------------------------
    def is_applicable(self, context: Context, trace: bool = False, verbose: bool = False) -> bool:
        """
        Evaluate the "if" condition for a requirement.

        :param context: The platform context in which the script is run.
        :param trace:   If true, run the script in trace mode (bash -x).
        :param verbose: If True, always pass stderr through. By default, stderr is
                        suppressed when not in trace mode and the script exits ok.

        :return:        True if the requirement is applicable, False otherwise.
        """

        if not self.if_script:
            return True
        return (
            run_script(
                self.if_script, context, label=f'{self.name}:if', trace=trace, verbose=verbose
            )
            == 0
        )


# ------------------------------------------------------------------------------
@dataclass(frozen=True)
class RequirementsSpec:
    """A parsed prerequisite specification file."""

    source: Path
    name: str
    description: str
    template: dict[str, str]
    requirements: list[Requirement]

    # --------------------------------------------------------------------------
    @classmethod
    def from_file(cls, path: Path | str) -> RequirementsSpec:
        """Load and parse a YAML requirements specification file."""
        if not isinstance(path, Path):
            path = Path(path)

        raw = yaml.safe_load(path.read_text())
        if not isinstance(raw, dict):
            raise ValueError('Requirements spec must be a YAML mapping')

        raw_reqs = raw.get('require', []) or []
        if not isinstance(raw_reqs, list):
            raise ValueError('"require" must be a list')

        requirements: list[Requirement] = []
        for i, item in enumerate(raw_reqs, start=1):
            try:
                requirements.append(Requirement.from_dict(item))
            except Exception as e:
                raise RequirementError(f'Item #{i}: {e}') from e
        if not requirements:
            raise RequirementError('No requirements specified')

        template = raw.get('template')
        return cls(
            source=path,
            name=str(raw.get('name', path.stem)),
            description=str(raw.get('description', '')),
            requirements=requirements,
            template=cls._normalise_doc_template(template) if template else DEFAULT_DOC_TEMPLATE,
        )

    # --------------------------------------------------------------------------
    @classmethod
    def _normalise_doc_template(cls, template: dict[str, str]) -> dict[str, str]:
        """Validate and normalise the doc template."""
        if not isinstance(template, dict):
            raise ValueError('"template" must be a YAML mapping')
        if not template.get('requirement'):
            raise ValueError('"template" must contain "requirement"')

        return {
            'prologue': template.get('prologue') or template.get('prolog'),
            'epilogue': template.get('epilogue') or template.get('epilog'),
            'requirement': template['requirement'],
        }

    # --------------------------------------------------------------------------
    @property
    def doc(self) -> str:
        """Use the document template to format the specification."""
        s = ''
        if self.template['prologue']:
            s += Template(self.template['prologue']).safe_substitute(asdict(self))

        t = Template(self.template['requirement'])
        for i, req in enumerate(self.requirements, start=1):
            s += t.safe_substitute(asdict(req), index=i)

        if self.template['epilogue']:
            s += Template(self.template['epilogue']).safe_substitute(asdict(self))
        return s


# ------------------------------------------------------------------------------
def run_script(
    script: str, context: Context, label: str, trace: bool = False, verbose: bool = False
) -> int:
    """
    Run a shell snippet with the REQ_* environment and helper functions injected.

    Returns the exit code of the script.

    :param script:  The bash script to run.
    :param context: The platform context in which the script is run.
    :param label:   A label identifying the script for the user.
    :param trace:   If true, run the script in trace mode (bash -x).
    :param verbose: If True, always pass stderr through. By default, stderr is
                    suppressed when not in trace mode and the script exits ok.

    """
    full_script = '\n'.join(filter(None, [context.helper_script, script]))
    suppress_stderr = not (trace or verbose)
    result = subprocess.run(
        ['bash', '-ex' if trace else '-e', '-c', full_script],
        env=context.as_env(),
        stderr=None if not suppress_stderr else subprocess.PIPE,
        text=True,
    )
    # If we have swallowed stderr but we have a problem or have been asked to
    # trace, we need to emit it manually.
    if suppress_stderr and result.returncode != 0 and result.stderr:
        for line in result.stderr.strip().splitlines():
            print(f'    {label}: {line}', file=sys.stderr)
    return result.returncode


# ..............................................................................
# region CLI commands
# ..............................................................................


# ------------------------------------------------------------------------------
class CliCommand(ABC):
    """CLI command handler base class."""

    commands: ClassVar[dict[str, type[CliCommand]]] = {}
    name: ClassVar[str | None] = None
    help_: ClassVar[str | None] = None

    # --------------------------------------------------------------------------
    @classmethod
    def register(cls, name: str) -> Callable:
        """Register a CLI command handler class."""

        def decorate(cmd: type[CliCommand]) -> type[CliCommand]:
            """Register the command handler class."""
            cmd.name = name
            try:
                cmd.help_ = cmd.__doc__.strip().splitlines()[0]
            except (AttributeError, IndexError):
                raise Exception(f'Class {cmd.__name__} must have a docstring')
            cls.commands[name] = cmd
            return cmd

        return decorate

    # --------------------------------------------------------------------------
    def __init__(self, subparser) -> None:
        """Initialise the command handler and register it with argparse."""
        self.argp = subparser.add_parser(self.name, help=self.help_, description=self.help_)
        self.argp.set_defaults(handler=self)

    # --------------------------------------------------------------------------
    def add_arguments(self) -> None:  # noqa: B027
        """Add arguments to the subparser."""
        pass

    # --------------------------------------------------------------------------
    @staticmethod  # noqa: B027
    def check_arguments(args: Namespace) -> None:  # noqa: B027
        """
        Validate parsed arguments.

        :param args:        The namespace containing the arguments.
        :raise ValueError:  If the arguments are invalid.
        """
        pass

    # --------------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def execute(args: Namespace, context: Context) -> None:
        """Execute the CLI command."""
        raise NotImplementedError('execute')


# ------------------------------------------------------------------------------
@CliCommand.register('check')
class CheckCommand(CliCommand):
    """Check that specified requirements are satisfied."""

    # --------------------------------------------------------------------------
    def add_arguments(self) -> None:
        """Add check-specific arguments."""

        self.argp.add_argument(
            '--fail-fast',
            action='store_true',
            help='Stop on first failed mandatory requirement.',
        )

        self.argp.add_argument(
            '--optional',
            action='store_true',
            help=(
                'Also check optional requirements. By default, these are excluded'
                ' unless explicitly specified.'
            ),
        )

        self.argp.add_argument(
            '--verbose',
            action='store_true',
            help=(
                'Always print stderr for the scripts. By default, stderr is'
                ' suppressed when not in trace mode (-x / --trace) and the script'
                ' exits with zero status.'
            ),
        )

        self.argp.add_argument(
            '-x',
            '--trace',
            action='store_true',
            help='Trace shell script execution (bash -x) for debugging.',
        )

        self.argp.add_argument('spec', metavar='SPEC.yaml', help='Requirements specification file.')

        self.argp.add_argument(
            'requirements',
            metavar='REQUIREMENT',
            nargs='*',
            default=[],
            help=(
                'Only check the requirements with the specified name(s). By default,'
                ' all mandatory requirements are checked. Any explicitly specified'
                ' optional requirements will be checked, regardless of the --optional flag.'
                ' The checks will be performed in the order specified in the specification'
                ' file, not the order on the command line.'
            ),
        )

    # --------------------------------------------------------------------------
    @staticmethod
    def execute(args: Namespace, context: Context) -> None:
        """Run checks and report results."""

        failed = False
        try:
            spec = RequirementsSpec.from_file(args.spec)
        except Exception as e:
            raise RequirementError(f'{args.spec}: {e}') from e

        requested_requirements = set(args.requirements)
        all_requirements = {req.name for req in spec.requirements}
        if requested_requirements and (unknown_reqs := requested_requirements - all_requirements):
            raise RequirementError(f'Unknown requirements: {", ".join(sorted(unknown_reqs))}')

        for req in spec.requirements:
            if requested_requirements and req.name not in requested_requirements:
                continue
            if not requested_requirements and req.optional and not args.optional:
                req.report('skip', context)
                continue
            if not req.is_applicable(context, trace=args.trace):
                req.report('skip', context)
                continue

            state = req.check(context)
            # Upgrade a warning to a failure for explicitly specified requirements.
            if requested_requirements and state == 'warn':
                state = 'fail'
            req.report(state, context)
            if state == 'fail':
                failed = True
                if args.fail_fast:
                    raise RequirementError('Requirement not satisfied — abort')

        if failed:
            raise RequirementError('One or more requirements are not satisfied')


# ------------------------------------------------------------------------------
@CliCommand.register('install')
class InstallCommand(CliCommand):
    """Install missing prerequisites."""

    # --------------------------------------------------------------------------
    def add_arguments(self) -> None:
        """Add install-specific arguments."""

        self.argp.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be installed without doing it.',
        )

        self.argp.add_argument(
            '--optional',
            action='store_true',
            help=(
                'Also install optional requirements. By default, these are excluded'
                ' unless explicitly specified.'
            ),
        )

        self.argp.add_argument(
            '--verbose',
            action='store_true',
            help=(
                'Always print stderr for the scripts. By default, stderr is'
                ' suppressed when not in trace mode (-x / --trace) and the script'
                ' exits with zero status.'
            ),
        )

        self.argp.add_argument(
            '-x',
            '--trace',
            action='store_true',
            help='Trace shell script execution (bash -x) for debugging.',
        )

        self.argp.add_argument(
            'spec',
            metavar='SPEC.yaml',
            help='Requirements specification file.',
        )

        self.argp.add_argument(
            'requirements',
            metavar='REQUIREMENT',
            nargs='*',
            default=[],
            help=(
                'Only install the requirements with the specified name(s). By default,'
                ' all mandatory requirements are installed. Any explicitly specified'
                ' optional requirements will be installed, regardless of the --optional flag.'
                ' The installs will be performed in the order specified in the specification'
                ' file, not the order on the command line.'
            ),
        )

    # --------------------------------------------------------------------------
    @staticmethod
    def execute(args: Namespace, context: Context) -> None:
        """Check each requirement and install if missing."""

        failed = False
        try:
            spec = RequirementsSpec.from_file(args.spec)
        except Exception as e:
            raise RequirementError(f'{args.spec}: {e}') from e

        requested_requirements = set(args.requirements)
        all_requirements = {req.name for req in spec.requirements}
        if requested_requirements and (unknown_reqs := requested_requirements - all_requirements):
            raise RequirementError(f'Unknown requirements: {", ".join(sorted(unknown_reqs))}')

        for req in spec.requirements:
            if requested_requirements and req.name not in requested_requirements:
                continue
            if not requested_requirements and req.optional and not args.optional:
                req.report('skip', context)
                continue
            if not req.is_applicable(context, trace=args.trace):
                req.report('skip', context)
                continue

            # Make sure it needs to be installed. Anything else (e.g. 'fail' or
            # 'warn') means it needs installing.
            if req.check(context) == 'ok':
                req.report('ok', context)
                continue

            # Needs installing
            if not req.install_script:
                context.print_event(
                    'fail', f'{req.name} -- not satisfied and no install recipe available'
                )
                if requested_requirements or not req.optional:
                    failed = True
                continue

            if args.dry_run:
                context.print_event('warn', f'{req.name} -- would install (dry run)')
                continue

            context.print_event('info', f'Processing {req.name} ...')
            rc = run_script(
                req.install_script,
                context,
                label=f'{req.name}:install',
                trace=args.trace,
                verbose=args.verbose,
            )
            if rc not in (0, STATUS_NO_RECHECK):
                context.print_event('fail', f'{req.name} -- install script failed (exit {rc})')
                if requested_requirements or not req.optional:
                    failed = True
                continue
            if rc == STATUS_NO_RECHECK:
                req.report('info', context)
                continue

            # Rerun check to confirm the install actually worked
            if req.check(context) == 'ok':
                req.report('ok', context)
            else:
                context.print_event(
                    'fail', f'{req.name} -- install script succeeded but check still fails'
                )
                if requested_requirements or not req.optional:
                    failed = True

        if failed:
            raise RequirementError('One or more requirements could not be installed')


# ------------------------------------------------------------------------------
@CliCommand.register('validate')
class ValidateCommand(CliCommand):
    """Validate the specification file without running any checks."""

    # --------------------------------------------------------------------------
    def add_arguments(self) -> None:
        """Add validate-specific arguments."""
        self.argp.add_argument(
            'specs', nargs='+', metavar='SPEC.yaml', help='Requirement specification file(s).'
        )

    # --------------------------------------------------------------------------
    @staticmethod
    def execute(args: Namespace, context: Context) -> None:
        """Parse and validate each spec file, checking shell snippet syntax."""

        failed = False
        print()
        for spec_path in args.specs:
            try:
                spec = RequirementsSpec.from_file(spec_path)
            except Exception as e:
                raise RequirementError(f'{spec_path}: {e}') from e

            if len(args.specs) > 1:
                print(f'{spec.name} -- {spec.description}' if spec.description else spec.name)

            req_failed = False
            for req in spec.requirements:
                for label, script in [
                    ('if', req.if_script),
                    ('check', req.check_script),
                    ('install', req.install_script),
                ]:
                    if not script:
                        continue
                    result = subprocess.run(
                        ['bash', '-n', '-c', script], capture_output=True, text=True
                    )
                    if result.returncode != 0:
                        context.print_event('fail', f'{req.name}.{label}: {result.stderr.strip()}')
                        req_failed = True

            failed = failed or req_failed
            if not req_failed:
                context.print_event('ok', f'{spec_path} -- {len(spec.requirements)} requirement(s)')
            print()

        if failed:
            raise RequirementError('One or more spec files failed validation.')


# ------------------------------------------------------------------------------
@CliCommand.register('doc')
class DocCommand(CliCommand):
    """Generate a text document from the specification."""

    # --------------------------------------------------------------------------
    def add_arguments(self) -> None:
        """Add doc-specific arguments."""
        self.argp.add_argument(
            'specs', nargs='+', metavar='SPEC.yaml', help='Requirement specification file(s).'
        )

    # --------------------------------------------------------------------------
    @staticmethod
    def execute(args: Namespace, context: Context) -> None:
        """Render spec file(s) as a Markdown document."""

        for spec_path in args.specs:
            try:
                spec = RequirementsSpec.from_file(spec_path)
            except Exception as e:
                raise RequirementError(f'{spec_path}: {e}') from e

            print(spec.doc)
            print()


# ------------------------------------------------------------------------------
@CliCommand.register('env')
class EnvCommand(CliCommand):
    """Show req specific environment variables for this platform."""

    def execute(self, args: Namespace, context: Context) -> None:
        """Show req specific environment variables for this platform."""

        for k, v in sorted(context.as_dict().items()):
            print(f'{k}={quote(v)}')


# ..............................................................................
# endregion CLI commands
# ..............................................................................


# ------------------------------------------------------------------------------
def process_cli_args() -> Namespace:
    """Parse and validate command line arguments."""
    argp = ArgumentParser(
        prog=PROG,
        description=__doc__,
        epilog=f'More information at {DOC_URL}',
    )

    argp.add_argument(
        '-v',
        '--version',
        action='version',
        version=__version__,
        help='Show version and exit.',
    )

    argp.add_argument(
        '-C',
        '--no-colour',
        '--no-color',
        action='store_false',
        dest='colour',
        help='Disable colour and emoji output.',
    )

    subp = argp.add_subparsers(required=True)
    for cmd in sorted(CliCommand.commands.values(), key=lambda c: c.name):
        cmd(subp).add_arguments()

    args = argp.parse_args()

    try:
        args.handler.check_arguments(args)
    except ValueError as exc:
        argp.error(str(exc))

    return args


# ------------------------------------------------------------------------------
def main() -> int:
    """Show time."""
    try:
        check_python_version()
        args = process_cli_args()
        context = Context(colour=args.colour)
        args.handler.execute(args, context)
        return 0
    except Exception as ex:
        # Uncomment for debugging
        # raise  # noqa: ERA001
        print(ex, file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        print('Interrupt', file=sys.stderr)
        return 2


# ------------------------------------------------------------------------------
# This only gets used during dev/test. Once deployed as a package, main() gets
# imported and run directly.
if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
