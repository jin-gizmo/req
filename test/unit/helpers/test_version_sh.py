"""Test version.sh helpers."""

from req.cli.req import load_bash_helpers
import pytest
import subprocess

HELPER_SCRIPT = load_bash_helpers()


# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    'v1,v2,expected',
    [
        ('1.2.3', '1.2.3.x', True),  # Only first 3 components count
        ('1.2.3', '1.2.3', True),
        ('1.2.3', '1.2.4', False),
        ('1.2.3', '1.02.03', True),
        ('1.2.3', '1.2', True),
        ('1.2.3', '1.02', True),
        ('1.2.3', '1', True),
        ('1', '1.2', True),
        ('1', '1.2.3', True),
    ],
)
def test_req_version_eq(v1, v2, expected):
    script = '\n'.join([HELPER_SCRIPT, f'req_version_eq "{v1}" "{v2}"'])
    result = subprocess.run(['bash', '-c', script])
    assert (result.returncode == 0) is expected


# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    'v1,v2,expected',
    [
        ('1.2.3', '1.2.3.x', True),  # Only first 3 components count
        ('1.2.3', '1.2.3', True),
        ('1.2.3', '1.2.4', False),
        ('1.2.4', '1.2.3', True),
        ('1.2.4', '1.3', False),
        ('2', '10.1.2', False),
        ('2.4', '1.8', True),
    ],
)
def test_req_version_gte(v1, v2, expected):
    script = '\n'.join([HELPER_SCRIPT, f'req_version_gte "{v1}" "{v2}"'])
    result = subprocess.run(['bash', '-c', script])
    assert (result.returncode == 0) is expected


# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    'v1,v2,expected',
    [
        ('1.2.3', '1.2.3.x', False),  # Only first 3 components count
        ('1.2.3', '1.2.3', False),
        ('1.2.4', '1.2.3', True),
        ('1.3', '1.2.3', True),
        ('2', '10.1.2', False),
        ('2.4', '1.8', True),
    ],
)
def test_req_version_gt(v1, v2, expected):
    script = '\n'.join([HELPER_SCRIPT, f'req_version_gt "{v1}" "{v2}"'])
    result = subprocess.run(['bash', '-c', script])
    assert (result.returncode == 0) is expected


# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    's_version,expected',
    [
        ('1.2.3', '1.2.3'),
        ('1.2', '1.2'),
        ('1', '1'),
        ('1.', '1'),
        ('GNU bash, version 3.2.57(1)-release (arm64-apple-darwin24)', '3.2.57'),
        ('awk version 20200816', '20200816'),
        ('no-version', ''),
    ],
)
def test_req_extract_version(s_version, expected):
    script = '\n'.join([HELPER_SCRIPT, f'req_extract_version'])
    result = subprocess.run(['bash', '-c', script], input=s_version, capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == expected
