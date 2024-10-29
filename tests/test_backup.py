import os
import pytest
from unittest.mock import patch, MagicMock
import backup

@pytest.fixture
def mock_ssh_command():
    with patch('backup.run_ssh_command') as mock:
        yield mock

@pytest.fixture
def test_config():
    return {
        "backup_basedir": "/tmp/test_backups",
        "uppercase_hostname": True,
        "admin_host": "admin.example.com",
        "host_backup_dir": "/tmp/test_backups/TESTHOST"
    }

@pytest.fixture
def test_host_config():
    return {
        "directories": [
            '/etc',
            '/var'
        ],
        "exclusions": {
            '/var': ['/var/lib/yum']
        }
    }

@pytest.fixture
def args():
    class Args:
        def __init__(self):
            self.verbose = True
            self.no_op = False
            self.hostname = "testhost"
            self.config = None
            self.host_config = None
    return Args()

def test_backup_directory(mock_ssh_command, test_config, test_host_config, args):
    # Test backing up a directory without exclusions
    backup.backup_directory("testhost", "/etc", test_config, test_host_config, args)
    mock_ssh_command.assert_called_with(
        "admin.example.com",
        "rsync -avxHP  testhost:/etc /tmp/test_backups/TESTHOST/etc",
        no_op=False,
        verbose=True
    )

def test_backup_directory_with_exclusions(mock_ssh_command, test_config, test_host_config, args):
    # Test backing up a directory with exclusions
    backup.backup_directory("testhost", "/var", test_config, test_host_config, args)
    mock_ssh_command.assert_called_with(
        "admin.example.com",
        "rsync -avxHP --exclude=/var/lib/yum testhost:/var /tmp/test_backups/TESTHOST/var",
        no_op=False,
        verbose=True
    )

def test_backup_with_no_op(mock_ssh_command, test_config, test_host_config, args):
    args.no_op = True
    backup.backup_directory("testhost", "/etc", test_config, test_host_config, args)
    mock_ssh_command.assert_called_with(
        "admin.example.com",
        "rsync -avxHP  testhost:/etc /tmp/test_backups/TESTHOST/etc",
        no_op=True,
        verbose=True
    )

@patch('os.path.exists')
@patch('os.makedirs')
@patch('os.chmod')
@patch('os.lstat')
def test_main_backup_flow(mock_lstat, mock_chmod, mock_makedirs, mock_exists, mock_ssh_command):
    # Setup mocks
    mock_exists.return_value = False
    mock_lstat_result = MagicMock()
    mock_lstat_result.st_mode = 0o755
    mock_lstat.return_value = mock_lstat_result
    
    # Prepare test arguments
    test_args = ['--verbose', 'backup', 'testhost']
    with patch('sys.argv', ['backup.py'] + test_args):
        backup.main()
    
    # Verify backup directory was created
    mock_makedirs.assert_called_once()
    mock_chmod.assert_called_once_with(mock_makedirs.call_args[0][0], 0o2770)
