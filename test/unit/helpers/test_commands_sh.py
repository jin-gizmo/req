"""Test version.sh helpers."""

import subprocess

import pytest

from req.cli.req import load_bash_helpers

HELPER_SCRIPT = load_bash_helpers()


# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    'cmd,expected',
    [
        ('bash', True),
        ('ls', True),
        ('no-way-this-one-exists', False),
    ],
)
def test_req_has_command(cmd, expected):
    script = '\n'.join([HELPER_SCRIPT, f'req_has_command "{cmd}"'])
    result = subprocess.run(['bash', '-c', script])
    assert (result.returncode == 0) is expected


# ------------------------------------------------------------------------------
def test_req_has_file(tmp_path):
    path = tmp_path / 'file.txt'
    assert not path.exists()

    # First check before the target file exists.
    script = '\n'.join([HELPER_SCRIPT, f'req_has_file "{path}"'])
    result = subprocess.run(['bash', '-c', script])
    assert result.returncode != 0

    # Create target file and recheck.
    path.touch()
    result = subprocess.run(['bash', '-c', script])
    assert result.returncode == 0


# ------------------------------------------------------------------------------
def test_req_has_dir(tmp_path):
    path = tmp_path / 'file.txt'
    assert not path.exists()

    # First check before the target file exists.
    script = '\n'.join([HELPER_SCRIPT, f'req_has_dir "{path}"'])
    result = subprocess.run(['bash', '-c', script])
    assert result.returncode != 0

    # Create target dir and recheck.
    path.mkdir(parents=True)
    result = subprocess.run(['bash', '-c', script])
    assert result.returncode == 0
