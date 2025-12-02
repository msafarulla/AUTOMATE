"""
Comprehensive tests for DB/database.py to improve coverage.
"""
import pytest
from unittest.mock import MagicMock, Mock, patch, call, mock_open
from DB.database import DB


class TestDBInit:
    """Tests for DB initialization."""

    def test_init_loads_config(self):
        """Test __init__ loads configuration."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "clean_content": "content",
            "system_name": "Linux",
            "node_name": "test-node",
            "where": "dev"
        }

        mock_config.__getitem__ = MagicMock(side_effect=lambda key: {
            "dev": {"conn_str": "jdbc:oracle:thin:@localhost:1521:XE"},
            "where": {"whse": "WH01", "close_pallet": "true"}
        }[key])

        with patch.object(DB, '_load_config', return_value=mock_config_data):
            db = DB()

            assert db.where == "dev"
            assert db.system_name == "Linux"
            assert db.node_name == "test-node"

    def test_init_with_custom_where(self):
        """Test __init__ with custom where parameter."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "clean_content": "content",
            "system_name": "Linux",
            "node_name": "test-node",
            "where": "prod"
        }

        mock_config.__getitem__ = MagicMock(side_effect=lambda key: {
            "prod": {"conn_str": "jdbc:oracle:thin:@prod:1521:XE"},
            "where": {"whse": "WH02", "close_pallet": "false"}
        }[key])

        with patch.object(DB, '_load_config', return_value=mock_config_data):
            db = DB(where="prod")

            assert db.where == "prod"

    def test_init_with_custom_whse(self):
        """Test __init__ with custom whse parameter."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "clean_content": "content",
            "system_name": "Linux",
            "node_name": "test-node",
            "where": "dev"
        }

        mock_config.__getitem__ = MagicMock(side_effect=lambda key: {
            "dev": {"conn_str": "jdbc:oracle:thin:@localhost:1521:XE"},
            "where": {"whse": "CUSTOM_WH", "close_pallet": "true"}
        }[key])

        with patch.object(DB, '_load_config', return_value=mock_config_data):
            db = DB(whse="CUSTOM_WH")

            assert db.whse == "CUSTOM_WH"


class TestGetConfigFromServer:
    """Tests for get_config_from_server class method."""

    def test_get_config_from_server_linux(self):
        """Test get_config_from_server on Linux system."""
        mock_client = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"[section]\nkey=value"

        mock_client.exec_command.return_value = (None, mock_stdout, None)

        with patch('DB.database.paramiko.SSHClient', return_value=mock_client), \
             patch('DB.database.platform.system', return_value="Linux"), \
             patch('DB.database.platform.node', return_value="test-node"):

            content, system, node = DB.get_config_from_server()

            assert content == "[section]\nkey=value"
            assert system == "Linux"
            assert node == "test-node"

    def test_get_config_from_server_macos(self):
        """Test get_config_from_server on macOS."""
        mock_client = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"[section]\nkey=value"

        mock_client.exec_command.return_value = (None, mock_stdout, None)

        with patch('DB.database.paramiko.SSHClient', return_value=mock_client), \
             patch('DB.database.platform.system', return_value="Darwin"), \
             patch('DB.database.platform.node', return_value="Macs-MacBook.local"), \
             patch('DB.database.getpass.getuser', return_value="macuser"), \
             patch('DB.database.os.path.expanduser', return_value="/Users/macuser/SUBARU/config/config.ini"):

            content, system, node = DB.get_config_from_server()

            assert system == "Darwin"
            # Should connect to localhost
            mock_client.connect.assert_called_once()
            call_args = mock_client.connect.call_args
            assert call_args[0][0] == "localhost"


class TestLoadConfig:
    """Tests for _load_config class method."""

    def test_load_config_basic(self):
        """Test _load_config basic functionality."""
        mock_config_content = "[where]\nwhere=dev\nwhse=WH01\n[dev]\nconn_str=jdbc:test"

        with patch.object(DB, 'get_config_from_server', return_value=(mock_config_content, "Linux", "test-node")):
            result = DB._load_config()

            assert result['where'] == "dev"
            assert result['system_name'] == "Linux"
            assert result['node_name'] == "test-node"
            assert 'config' in result

    def test_load_config_with_custom_where(self):
        """Test _load_config with custom where parameter."""
        mock_config_content = "[where]\nwhere=dev\nwhse=WH01\n[prod]\nconn_str=jdbc:prod"

        with patch.object(DB, 'get_config_from_server', return_value=(mock_config_content, "Linux", "test-node")):
            result = DB._load_config(where="prod")

            assert result['where'] == "prod"

    def test_load_config_macos_uses_local(self):
        """Test _load_config uses 'local' on macOS."""
        mock_config_content = "[where]\nwhere=dev\nwhse=WH01\n[local]\nconn_str=jdbc:local"

        with patch.object(DB, 'get_config_from_server', return_value=(mock_config_content, "Darwin", "Mac.local")):
            result = DB._load_config()

            assert result['where'] == "local"
            assert result['system_name'] == "Darwin"

    def test_load_config_with_custom_whse(self):
        """Test _load_config with custom whse parameter."""
        mock_config_content = "[where]\nwhere=dev\nwhse=WH01\n[dev]\nconn_str=jdbc:test"

        with patch.object(DB, 'get_config_from_server', return_value=(mock_config_content, "Linux", "test-node")):
            result = DB._load_config(whse="CUSTOM_WH")

            assert result['config']['where']['whse'] == "CUSTOM_WH"

    def test_load_config_cleans_content(self):
        """Test _load_config removes non-printable characters."""
        mock_config_content = "[where]\nwhere=dev\x00\x01\nwhse=WH01\n[dev]\nconn_str=jdbc:test"

        with patch.object(DB, 'get_config_from_server', return_value=(mock_config_content, "Linux", "test-node")):
            result = DB._load_config()

            # Should have cleaned content
            assert '\x00' not in result['clean_content']
            assert '\x01' not in result['clean_content']


class TestGetCredentials:
    """Tests for get_credentials class method."""

    def test_get_credentials_returns_dict(self):
        """Test get_credentials returns credentials dictionary."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "where": "dev"
        }

        mock_section = {
            "app_server": "server.example.com",
            "app_server_user": "user",
            "app_server_pass": "pass"
        }

        mock_config.__getitem__ = MagicMock(return_value=mock_section)

        with patch.object(DB, '_load_config', return_value=mock_config_data):
            creds = DB.get_credentials()

            assert creds['app_server'] == "server.example.com"
            assert creds['app_server_user'] == "user"
            assert creds['app_server_pass'] == "pass"

    def test_get_credentials_with_custom_where(self):
        """Test get_credentials with custom where parameter."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "where": "prod"
        }

        mock_section = {
            "app_server": "prod.example.com",
            "app_server_user": "prod_user",
            "app_server_pass": "prod_pass"
        }

        mock_config.__getitem__ = MagicMock(return_value=mock_section)

        with patch.object(DB, '_load_config', return_value=mock_config_data):
            creds = DB.get_credentials(where="prod")

            assert creds['app_server'] == "prod.example.com"


class TestContextManager:
    """Tests for context manager functionality."""

    def test_enter_connects_and_sets_schema(self):
        """Test __enter__ connects to database and sets schema."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "clean_content": "content",
            "system_name": "Linux",
            "node_name": "test-node",
            "where": "dev"
        }

        mock_config.__getitem__ = MagicMock(side_effect=lambda key: {
            "dev": {"conn_str": "jdbc:test"},
            "where": {"whse": "WH01", "close_pallet": "true"}
        }[key])

        with patch.object(DB, '_load_config', return_value=mock_config_data), \
             patch.object(DB, 'connect') as mock_connect, \
             patch.object(DB, 'setSchema') as mock_set_schema:

            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            mock_connection.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_connection

            db = DB()
            result = db.__enter__()

            assert result is db
            mock_connect.assert_called_once()
            mock_set_schema.assert_called_once()

    def test_exit_commits_on_success(self):
        """Test __exit__ commits transaction on success."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "clean_content": "content",
            "system_name": "Linux",
            "node_name": "test-node",
            "where": "dev"
        }

        mock_config.__getitem__ = MagicMock(side_effect=lambda key: {
            "dev": {"conn_str": "jdbc:test"},
            "where": {"whse": "WH01", "close_pallet": "true"}
        }[key])

        with patch.object(DB, '_load_config', return_value=mock_config_data), \
             patch.object(DB, 'runSQL') as mock_run_sql, \
             patch.object(DB, 'close') as mock_close:

            db = DB()
            db.__exit__(None, None, None)

            # Should commit when no exception
            calls = [str(call) for call in mock_run_sql.call_args_list]
            assert any('commit' in str(call) for call in calls)
            mock_close.assert_called_once()

    def test_exit_rolls_back_on_exception(self):
        """Test __exit__ rolls back transaction on exception."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "clean_content": "content",
            "system_name": "Linux",
            "node_name": "test-node",
            "where": "dev"
        }

        mock_config.__getitem__ = MagicMock(side_effect=lambda key: {
            "dev": {"conn_str": "jdbc:test"},
            "where": {"whse": "WH01", "close_pallet": "true"}
        }[key])

        with patch.object(DB, '_load_config', return_value=mock_config_data), \
             patch.object(DB, 'runSQL') as mock_run_sql, \
             patch.object(DB, 'close') as mock_close:

            db = DB()
            db.__exit__(Exception, Exception("Test error"), None)

            # Should rollback when exception occurred
            calls = [str(call) for call in mock_run_sql.call_args_list]
            assert any('rollback' in str(call) for call in calls)
            mock_close.assert_called_once()


class TestConnect:
    """Tests for connect method."""

    def test_connect_establishes_connection(self):
        """Test connect establishes database connection."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "clean_content": "content",
            "system_name": "Linux",
            "node_name": "test-node",
            "where": "dev"
        }

        mock_config.__getitem__ = MagicMock(side_effect=lambda key: {
            "dev": {"conn_str": "jdbc:oracle:thin:@localhost:1521:XE"},
            "where": {"whse": "WH01", "close_pallet": "true"}
        }[key])

        mock_connection = MagicMock()

        with patch.object(DB, '_load_config', return_value=mock_config_data), \
             patch('DB.database.jaydebeapi.connect', return_value=mock_connection) as mock_connect:

            db = DB()
            result = db.connect()

            assert result is mock_connection
            mock_connect.assert_called_once()


class TestSetSchema:
    """Tests for setSchema method."""

    def test_set_schema_executes_sql(self):
        """Test setSchema executes ALTER SESSION."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "clean_content": "content",
            "system_name": "Linux",
            "node_name": "test-node",
            "where": "dev"
        }

        mock_config.__getitem__ = MagicMock(side_effect=lambda key: {
            "dev": {"conn_str": "jdbc:test"},
            "where": {"whse": "WH01", "close_pallet": "true"}
        }[key])

        with patch.object(DB, '_load_config', return_value=mock_config_data):
            db = DB()
            db.cursor = MagicMock()
            db.whse = "WH01"

            db.setSchema()

            # Should execute ALTER SESSION
            db.cursor.execute.assert_called_once()
            call_args = db.cursor.execute.call_args[0][0]
            assert "ALTER SESSION" in call_args


class TestRunSQL:
    """Tests for runSQL method."""

    def test_run_sql_basic(self):
        """Test runSQL executes query."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "clean_content": "content",
            "system_name": "Linux",
            "node_name": "test-node",
            "where": "dev"
        }

        mock_config.__getitem__ = MagicMock(side_effect=lambda key: {
            "dev": {"conn_str": "jdbc:test"},
            "where": {"whse": "WH01", "close_pallet": "true"}
        }[key])

        with patch.object(DB, '_load_config', return_value=mock_config_data):
            db = DB()
            db.cursor = MagicMock()
            db.query = None

            db.runSQL("SELECT * FROM test")

            assert db.query == "SELECT * FROM test"
            db.cursor.execute.assert_called_once_with("SELECT * FROM test")

    def test_run_sql_with_params(self):
        """Test runSQL with parameters."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "clean_content": "content",
            "system_name": "Linux",
            "node_name": "test-node",
            "where": "dev"
        }

        mock_config.__getitem__ = MagicMock(side_effect=lambda key: {
            "dev": {"conn_str": "jdbc:test"},
            "where": {"whse": "WH01", "close_pallet": "true"}
        }[key])

        with patch.object(DB, '_load_config', return_value=mock_config_data):
            db = DB()
            db.cursor = MagicMock()

            db.runSQL("SELECT * FROM test WHERE id = ?", ("123",))

            db.cursor.execute.assert_called_once_with("SELECT * FROM test WHERE id = ?", ("123",))


class TestFetchAll:
    """Tests for fetchall method."""

    def test_fetchall_returns_rows_and_columns(self):
        """Test fetchall returns rows and column names."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "clean_content": "content",
            "system_name": "Linux",
            "node_name": "test-node",
            "where": "dev"
        }

        mock_config.__getitem__ = MagicMock(side_effect=lambda key: {
            "dev": {"conn_str": "jdbc:test"},
            "where": {"whse": "WH01", "close_pallet": "true"}
        }[key])

        with patch.object(DB, '_load_config', return_value=mock_config_data):
            db = DB()
            db.cursor = MagicMock()
            db.cursor.fetchall.return_value = [("row1",), ("row2",)]
            db.cursor.description = [("COL1",), ("COL2",)]

            rows, columns = db.fetchall()

            assert rows == [("row1",), ("row2",)]
            assert columns == ["COL1", "COL2"]


class TestFetchOne:
    """Tests for fetchone method."""

    def test_fetchone_returns_dict(self):
        """Test fetchone returns dictionary."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "clean_content": "content",
            "system_name": "Linux",
            "node_name": "test-node",
            "where": "dev"
        }

        mock_config.__getitem__ = MagicMock(side_effect=lambda key: {
            "dev": {"conn_str": "jdbc:test"},
            "where": {"whse": "WH01", "close_pallet": "true"}
        }[key])

        with patch.object(DB, '_load_config', return_value=mock_config_data):
            db = DB()
            db.cursor = MagicMock()
            db.cursor.fetchone.return_value = ("value1", "value2")
            db.cursor.description = [("COL1",), ("COL2",)]

            result = db.fetchone()

            assert result == {"COL1": "value1", "COL2": "value2"}

    def test_fetchone_returns_none_when_no_rows(self):
        """Test fetchone returns None when no rows."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "clean_content": "content",
            "system_name": "Linux",
            "node_name": "test-node",
            "where": "dev"
        }

        mock_config.__getitem__ = MagicMock(side_effect=lambda key: {
            "dev": {"conn_str": "jdbc:test"},
            "where": {"whse": "WH01", "close_pallet": "true"}
        }[key])

        with patch.object(DB, '_load_config', return_value=mock_config_data):
            db = DB()
            db.cursor = MagicMock()
            db.cursor.fetchone.return_value = None

            result = db.fetchone()

            assert result is None


class TestClose:
    """Tests for close method."""

    def test_close_closes_connection(self):
        """Test close closes database connection."""
        mock_config = MagicMock()
        mock_config_data = {
            "config": mock_config,
            "clean_content": "content",
            "system_name": "Linux",
            "node_name": "test-node",
            "where": "dev"
        }

        mock_config.__getitem__ = MagicMock(side_effect=lambda key: {
            "dev": {"conn_str": "jdbc:test"},
            "where": {"whse": "WH01", "close_pallet": "true"}
        }[key])

        with patch.object(DB, '_load_config', return_value=mock_config_data):
            db = DB()
            db.connection = MagicMock()
            db.cursor = MagicMock()

            db.close()

            db.cursor.close.assert_called_once()
            db.connection.close.assert_called_once()
