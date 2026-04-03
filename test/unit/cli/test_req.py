"""Test cases for the req CLI."""

import re
import subprocess
import sys

import pytest

from req.cli import req
from req.conf import __version__

REQ_ENV_VARS = ('REQ_OS', 'REQ_FAMILY', 'REQ_ID', 'REQ_ID_LIKE', 'REQ_VERSION_ID')


# ------------------------------------------------------------------------------
def test_req_cli_version(capsys, monkeypatch) -> None:
    """Test the "version" command."""

    monkeypatch.setattr(sys, 'argv', ['req', '--version'])

    # argparse will exit on it's own for --version option (grrr)
    with pytest.raises(SystemExit) as exc_info:
        req.main()

    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == __version__


# ------------------------------------------------------------------------------
@pytest.mark.parametrize('var_name', REQ_ENV_VARS)
def test_req_cli_env_local(var_name, capsys, monkeypatch) -> None:
    """Test the "env" command on the local machine."""

    monkeypatch.setattr(sys, 'argv', ['req', 'env'])
    assert req.main() == 0
    out = capsys.readouterr().out

    assert f'{var_name}=' in out


def test_req_cli_env_debian(dirs, capsys) -> None:

    result = subprocess.run(
        [
            'docker',
            'run',
            '--rm',
            '-v',
            f'{dirs.base}:/req',
            'req-test:debian',
            'python3',
            '-m',
            'req.cli.req',
            'env',
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert 'REQ_FAMILY=debian' in result.stdout


# ------------------------------------------------------------------------------
def test_check_python_version_ok(monkeypatch) -> None:
    assert req.check_python_version() is None


def test_check_python_version_fail(monkeypatch) -> None:

    monkeypatch.setattr('req.cli.req.MIN_PYTHON', (99, 999))
    with pytest.raises(RuntimeError, match='requires Python 99.999 or later'):
        req.check_python_version()


# ------------------------------------------------------------------------------
def test_run_script_ok(capfd, tmp_path):
    script = f'echo stdout; echo stderr >&2'
    ctx = req.Context()

    rc = req.run_script(script, ctx, label='test')
    assert rc == 0
    # Need capfd not capsys to capture output of subprocess.
    out, err = capfd.readouterr()
    assert out.strip() == 'stdout'
    # A successful run without verbose or tracing will suppress stderr.
    assert err.strip() == ''


def test_run_script_verbose_ok(capfd, tmp_path):
    script = f'echo stdout; echo stderr >&2'
    ctx = req.Context()

    rc = req.run_script(script, ctx, label='test', verbose=True)
    assert rc == 0
    # Need capfd not capsys to capture output of subprocess.
    out, err = capfd.readouterr()
    assert out.strip() == 'stdout'
    assert err.strip() == 'stderr'


def test_run_script_fail(capfd, tmp_path):
    script = f'echo stdout; echo stderr >&2; exit 23'
    ctx = req.Context()

    rc = req.run_script(script, ctx, label='test')
    assert rc == 23
    # Need capfd not capsys to capture output of subprocess.
    out, err = capfd.readouterr()
    assert out.strip() == 'stdout'
    assert err.strip() == 'test: stderr'  # We get the label applied in this case.


def test_run_script_trace_ok(capfd, tmp_path):
    script = f'echo stdout; echo stderr >&2'
    ctx = req.Context()

    rc = req.run_script(script, ctx, label='test', trace=True)
    assert rc == 0
    # Need capfd not capsys to capture output of subprocess.
    out, err = capfd.readouterr()
    assert out.strip() == 'stdout'
    assert err.strip() == """
+ echo stdout
+ echo stderr
stderr
""".strip()


# ------------------------------------------------------------------------------
class TestContext:

    def test_as_env(self) -> None:

        ctx = req.Context()
        env = ctx.as_env()
        env_set = set(env)
        assert set(REQ_ENV_VARS) < env_set
        # Check a few general env vars got preserver
        assert {'PATH', 'USER', 'HOME'} < env_set

    def test_print_event(self, capsys):
        ctx = req.Context(colour=False)
        ctx.print_event('info', 'Hello World')
        out = capsys.readouterr().out

        assert out == '[INFO]  Hello World\n'

    def test__repr__(self) -> None:
        ctx = req.Context(colour=False)
        r = repr(ctx)
        for k in REQ_ENV_VARS:
            assert f"'{k}': " in r

    def test__str__(self) -> None:
        ctx = req.Context(colour=False)
        s = str(ctx)
        for k in REQ_ENV_VARS:
            assert f"'{k}': " in s


# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    'req_id, req_id_like, expected',
    [
        ('darwin', '', 'darwin'),
        ('ubuntu', 'debian', 'debian'),  # Ubuntu
        ('amzn', 'fedora', 'fedora'),  # Amazon Linux 2023
        ('rocky', 'rhel centos fedora', 'fedora'),  # Rocky 9
        ('alpine', '', 'alpine'),  # Alpine
        ('debian', '', 'debian'),  # Debian
    ],
)
def test_detect_distro_family(req_id: str, req_id_like: str, expected: str) -> None:
    assert req.detect_distro_family(req_id, req_id_like) == expected


# ------------------------------------------------------------------------------
class TestRequirement:

    def test_from_dict_ok(self):
        data = {
            'name': 'test',
            'description': 'A test',
            'check': 'true',  # Shell "true" command
        }
        r = req.Requirement.from_dict(data)
        assert r.name == data['name']
        assert r.description == data['description']

    def test_from_dict_not_a_dict(self):
        data = ['no', 'lists', 'allowed']
        with pytest.raises(ValueError, match='must be a mapping'):
            req.Requirement.from_dict(data)  # noqa

    def test_from_dict_no_name(self):
        data = {
            'description': 'A test',
            'check': 'true',  # Shell "true" command
        }
        with pytest.raises(ValueError, match='missing "name"'):
            req.Requirement.from_dict(data)

    def test_from_dict_no_check_script(self):
        data = {
            'name': 'test',
            'description': 'A test',
        }
        with pytest.raises(ValueError, match='missing "check"'):
            req.Requirement.from_dict(data)

    def test_report(self, capsys):
        ctx = req.Context(colour=False)
        data = {
            'name': 'test',
            'description': 'A test',
            'optional': True,
            'check': 'true',  # Shell "true" command
        }
        r = req.Requirement.from_dict(data)
        r.report('warn', ctx)
        out, _ = capsys.readouterr()
        assert out.strip() == f'[WARN]  {r.name} (optional) -- {r.description}'

    def test_check_ok(self):
        ctx = req.Context(colour=False)
        data = {
            'name': 'test',
            'description': 'A test',
            'check': 'true',  # Shell "true" command
        }
        r = req.Requirement.from_dict(data)
        assert r.check(ctx) == 'ok'

    def test_check_fail(self):
        """Test a failed optional check."""
        ctx = req.Context(colour=False)
        data = {
            'name': 'test',
            'description': 'A test',
            'check': 'false',  # Shell "false" command
        }
        r = req.Requirement.from_dict(data)
        assert r.check(ctx) == 'fail'

    def test_check_optional(self):
        """Test a failed optional check."""
        ctx = req.Context(colour=False)
        data = {
            'name': 'test',
            'description': 'A test',
            'optional': True,
            'check': 'false',  # Shell "false" command
        }
        r = req.Requirement.from_dict(data)
        assert r.check(ctx) == 'warn'


# ------------------------------------------------------------------------------
class TestRequirementsSpec:

    def test_bad_require_type(self, td):
        with pytest.raises(ValueError, match='"require" must be a list'):
            req.RequirementsSpec.from_file(td / 'req-bad-spec-require-type.yaml')

    def test_bad_require_item(self, td):
        with pytest.raises(
            req.RequirementError, match='Item #2: Requirement "no-check" is missing "check"'
        ):
            req.RequirementsSpec.from_file(td / 'req-bad-spec-require-item.yaml')

    def test_bad_require_none(self, td):
        with pytest.raises(req.RequirementError, match='No requirements specified'):
            req.RequirementsSpec.from_file(td / 'req-bad-spec-require-none.yaml')

    def test_bad_spec_template_type(self, td):
        with pytest.raises(ValueError, match='"template" must be a YAML mapping'):
            req.RequirementsSpec.from_file(td / 'req-bad-spec-template-type.yaml')

    def test_bad_spec_template_no_req(self, td):
        """Test missing requirement key in template."""
        with pytest.raises(ValueError, match='"template" must contain "requirement"'):
            req.RequirementsSpec.from_file(td / 'req-bad-spec-template-no-req.yaml')

    def test_template_ok(self, td):

        r = req.RequirementsSpec.from_file(td / 'req-template.yaml')
        assert set(r.template) == {'prologue', 'epilogue', 'requirement'}
        assert r.doc == """
Prologue
1 : req1
2 : req2
Epilogue
"""


# ------------------------------------------------------------------------------
class TestCommandCheck:

    def test_check_ok_simple(self, td, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['req', 'check', str(td / 'req-docker.yaml')])
        assert req.main() == 0
        out, err = capsys.readouterr()
        assert err.strip() == ''
        assert re.match(r'\[OK]\s+docker', out)

    def test_check_bad_spec(self, td, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['req', 'check', str(td / 'req-bad-spec-type.yaml')])
        assert req.main() == 1
        assert 'Requirements spec must be a YAML mapping' in capsys.readouterr().err

    def test_check_unknown_requirement(self, td, monkeypatch, capsys):
        monkeypatch.setattr(
            sys, 'argv', ['req', 'check', str(td / 'req-docker.yaml'), 'unknown-req']
        )
        assert req.main() == 1
        assert 'Unknown requirements: unknown-req' in capsys.readouterr().err

    def test_check_ok_named_requirement(self, td, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['req', 'check', str(td / 'req-multi.yaml'), 'bash'])
        assert req.main() == 0
        out, err = capsys.readouterr()
        assert err.strip() == ''
        # Only 1 requirement should be in the report.
        assert len(out.strip().splitlines()) == 1
        assert re.match(r'^\[OK]\s+bash', out, re.MULTILINE)

    def test_check_make_sure_optional_are_skipped(self, td, monkeypatch, capsys):

        monkeypatch.setattr(sys, 'argv', ['req', 'check', str(td / 'req-multi.yaml')])
        assert req.main() == 0
        out, err = capsys.readouterr()
        assert err.strip() == ''
        for name in ('bash', 'docker'):
            assert re.search(fr'^\[OK]\s+{name}', out, re.MULTILINE)
        # Make sure the optional ones are skipped
        for name in ('optional-no-exist', 'optional-exist'):
            assert re.search(fr'^\[SKIP]\s+{name}', out, re.MULTILINE)

    def test_check_if_not_satisfied(self, td, monkeypatch, capsys):
        """Check when the `if` clause is not satisfied."""
        monkeypatch.setattr(
            sys, 'argv', ['req', 'check', str(td / 'req-multi.yaml'), 'if-not-satisfied']
        )
        assert req.main() == 0
        out, err = capsys.readouterr()
        assert re.match(r'^\[SKIP]\s+if-not-satisfied', out, re.MULTILINE)

    def test_check_optional_requested_not_satisfied(self, td, monkeypatch, capsys):
        """
        Check an explicitly requested unsatisfied optional requested.

        Because the unsatisfied optional has been explicitly requested, it
        should produce a fail.
        """
        monkeypatch.setattr(
            sys,
            'argv',
            ['req', 'check', str(td / 'req-optional-no-exist.yaml'), 'optional-no-exist'],
        )
        assert req.main() == 1
        out, err = capsys.readouterr()
        assert re.match(r'^\[FAIL]\s+optional-no-exist', out, re.MULTILINE)

    def test_check_optional_not_satisfied(self, td, monkeypatch, capsys):
        """
        Check an unsatisfied optional requested.

        Because the unsatisfied optional has not been explicitly requested, it
        should produce a warning.
        """

        monkeypatch.setattr(
            sys, 'argv', ['req', 'check', '--optional', str(td / 'req-optional-no-exist.yaml')]
        )
        assert req.main() == 0  # warning only
        out, err = capsys.readouterr()
        assert re.match(r'^\[WARN]\s+optional-no-exist', out, re.MULTILINE)

    def test_check_fail_fast(self, td, monkeypatch, capsys):
        """Check that early failure aborts on fail fast."""
        monkeypatch.setattr(
            sys, 'argv', ['req', 'check', '--fail-fast', str(td / 'req-fail-fast.yaml')]
        )
        assert req.main() == 1
        out, err = capsys.readouterr()
        assert re.match(r'^\[FAIL]\s+no-exist', out, re.MULTILINE)
        # Make sure no further output due to abort.
        assert len(out.strip().splitlines()) == 1


# ------------------------------------------------------------------------------
class TestCommandInstall:

    def test_install_bad_spec(self, td, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['req', 'install', str(td / 'req-bad-spec-type.yaml')])
        assert req.main() == 1
        assert 'Requirements spec must be a YAML mapping' in capsys.readouterr().err

    def test_install_unknown_requirement(self, td, monkeypatch, capsys):
        monkeypatch.setattr(
            sys, 'argv', ['req', 'install', str(td / 'req-docker.yaml'), 'unknown-req']
        )
        assert req.main() == 1
        assert 'Unknown requirements: unknown-req' in capsys.readouterr().err

    def test_install_if_not_satisfied(self, td, monkeypatch, capsys):
        """Don't install when the `if` clause is not satisfied."""
        monkeypatch.setattr(
            sys, 'argv', ['req', 'install', str(td / 'req-multi.yaml'), 'if-not-satisfied']
        )
        assert req.main() == 0
        out, err = capsys.readouterr()
        assert re.match(r'^\[SKIP]\s+if-not-satisfied', out, re.MULTILINE)

    def test_install_simple(self, td, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(
            sys,
            'argv',
            ['req', 'install', str(td / 'req-install-simple.yaml')],
        )
        test_file = tmp_path / 'test-file'
        monkeypatch.setenv('TEST_FILE', str(test_file))
        assert not test_file.exists()
        assert req.main() == 0
        assert test_file.exists()
        out, err = capsys.readouterr()
        assert err.strip() == ''
        assert re.search(r'^\[INFO]\s+Processing touch ', out, re.MULTILINE)
        assert re.search(r'^\[OK]\s+touch', out, re.MULTILINE)
        assert not re.search(r'^\[INFO]\s+Processing already-installed ', out, re.MULTILINE)
        assert re.search(r'^\[OK]\s+already-installed', out, re.MULTILINE)
        assert re.search(r'^\[SKIP]\s+optional-no-exist ', out, re.MULTILINE)

    def test_install_no_script(self, td, monkeypatch, capsys):
        monkeypatch.setattr(
            sys,
            'argv',
            ['req', 'install', str(td / 'req-install-no-script.yaml')],
        )
        assert req.main() == 1
        out = capsys.readouterr().out
        assert re.match(
            r'^\[FAIL]\s+install-no-script -- not satisfied and no install recipe available',
            out,
            re.MULTILINE,
        )

    def test_install_dry_run(self, td, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(
            sys,
            'argv',
            ['req', 'install', '--dry-run', str(td / 'req-install-simple.yaml')],
        )
        monkeypatch.setenv('TEST_FILE', str(tmp_path / 'test-file'))
        assert req.main() == 0
        out, err = capsys.readouterr()
        assert err.strip() == ''
        assert re.search(r'^\[WARN]\s+touch -- would install \(dry run\)', out, re.MULTILINE)
        assert re.search(r'^\[OK]\s+already-installed', out, re.MULTILINE)
        assert re.search(r'^\[SKIP]\s+optional-no-exist ', out, re.MULTILINE)

    def test_install_fail(self, td, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(sys, 'argv', ['req', 'install', str(td / 'req-install-fail.yaml')])
        assert req.main() == 1
        out = capsys.readouterr().out
        assert re.search(r'^\[INFO]\s+Processing install-fail ', out, re.MULTILINE)
        assert re.search(r'^\[FAIL]\s+install-fail', out, re.MULTILINE)

    def test_install_no_recheck(self, td, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(
            sys, 'argv', ['req', 'install', str(td / 'req-install-no-recheck.yaml')]
        )
        assert req.main() == 0
        out = capsys.readouterr().out
        assert re.search(r'^\[INFO]\s+Processing install-no-recheck ', out, re.MULTILINE)
        assert re.search(r'^\[INFO]\s+install-no-recheck', out, re.MULTILINE)

    def test_install_recheck(self, td, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(sys, 'argv', ['req', 'install', str(td / 'req-install-recheck.yaml')])
        assert req.main() == 1
        out = capsys.readouterr().out
        assert re.search(r'^\[INFO]\s+Processing install-recheck ', out, re.MULTILINE)
        assert re.search(
            r'^\[FAIL]\s+install-recheck -- install script succeeded but check still fails',
            out,
            re.MULTILINE,
        )


# ------------------------------------------------------------------------------
class TestCommandValidate:

    def test_validate_simple(self, td, monkeypatch, capsys):
        """Validate a simple, correct, requirements spec file."""

        monkeypatch.setattr(
            sys,
            'argv',
            [
                'req',
                'validate',
                str(td / 'req-install-simple.yaml'),
                # Yep -- validate same spec twice
                str(td / 'req-install-simple.yaml'),
            ],
        )
        assert req.main() == 0
        out, err = capsys.readouterr()
        assert err.strip() == ''
        assert re.search(r'^\[OK]', out, re.MULTILINE)

    def test_validate_bad_spec(self, td, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['req', 'validate', str(td / 'req-bad-spec-type.yaml')])
        assert req.main() == 1
        assert 'Requirements spec must be a YAML mapping' in capsys.readouterr().err

    def test_validate_script_error(self, td, monkeypatch, capsys):
        """Test with a script syntax error."""
        monkeypatch.setattr(
            sys, 'argv', ['req', 'validate', str(td / 'req-bad-spec-script-error.yaml')]
        )
        assert req.main() == 1
        # req.main()
        out = capsys.readouterr().out
        assert re.search(r'^\[FAIL]\s+script-error\.check', out, re.MULTILINE)


# ------------------------------------------------------------------------------
class TestCommandDoc:

    def test_doc_ok(self, td, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['req', 'doc', str(td / 'req-template.yaml')])
        assert req.main() == 0
        out = capsys.readouterr().out
        assert out.strip() == """
Prologue
1 : req1
2 : req2
Epilogue
""".strip()

    def test_doc_bad_spec(self, td, monkeypatch, capsys):
        monkeypatch.setattr(sys, 'argv', ['req', 'doc', str(td / 'req-bad-spec-type.yaml')])
        assert req.main() == 1
        assert 'Requirements spec must be a YAML mapping' in capsys.readouterr().err
