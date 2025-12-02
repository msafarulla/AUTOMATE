"""
Comprehensive tests for database module (DB/database.py).
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
import configparser
from DB.database import DB


class TestDBConfiguration:
    """Test suite for DB configuration methods."""

    @patch('DB.database.paramiko.SSHClient')
    @patch('DB.database.platform.system', return_value='Linux')
    def test_get_config_from_server_linux(self, mock_system, mock_ssh):
        """Test getting config from server on Linux."""
        mock_client = MagicMock()
        mock_ssh.return_value = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"[test]\nkey=value"
        mock_client.exec_command.return_value = (None, mock_stdout, None)

        config_content, system_name, node_name = DB.get_config_from_server()

        assert system_name == 'Linux'
        assert "key=value" in config_content
        mock_client.connect.assert_called_once()
        mock_client.close.assert_called_once()

    @patch('DB.database.paramiko.SSHClient')
    @patch('DB.database.platform.system', return_value='Darwin')
    @patch('DB.database.getpass.getuser', return_value='testuser')
    def test_get_config_from_server_macos(self, mock_getuser, mock_system, mock_ssh):
        """Test getting config from server on macOS."""
        mock_client = MagicMock()
        mock_ssh.return_value = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"[test]\nkey=value"
        mock_client.exec_command.return_value = (None, mock_stdout, None)

        config_content, system_name, node_name = DB.get_config_from_server()

        assert system_name == 'Darwin'
        mock_client.connect.assert_called_once_with('localhost', username='testuser')

    @patch('DB.database.DB.get_config_from_server')
    def test_load_config_with_defaults(self, mock_get_config):
        """Test loading config with default values."""
        config_content = """
[where]
where=dev
whse=TEST

[dev]
conn_str=jdbc:oracle:thin:@localhost:1521:TEST
app_server=http://test.com
app_server_user=testuser
app_server_pass=testpass
db_user=dbuser
db_password=dbpass
schema=testschema
autocommit=0
"""
        mock_get_config.return_value = (config_content, 'Linux', 'testnode')

        result = DB._load_config()

        assert result['where'] == 'dev'
        assert result['system_name'] == 'Linux'
        assert result['node_name'] == 'testnode'
        assert 'config' in result

    @patch('DB.database.DB.get_config_from_server')
    def test_load_config_custom_where(self, mock_get_config):
        """Test loading config with custom environment."""
        config_content = """
[where]
where=dev
whse=TEST

[prod]
conn_str=jdbc:oracle:thin:@prod:1521:PROD
app_server=http://prod.com
app_server_user=produser
app_server_pass=prodpass
db_user=proddbuser
db_password=proddbpass
schema=prodschema
autocommit=1
"""
        mock_get_config.return_value = (config_content, 'Linux', 'testnode')

        result = DB._load_config(where='prod')

        assert result['where'] == 'prod'

    @patch('DB.database.DB.get_config_from_server')
    def test_get_credentials(self, mock_get_config):
        """Test getting credentials."""
        config_content = """
[where]
where=dev
whse=TEST

[dev]
conn_str=jdbc:oracle:thin:@localhost:1521:TEST
app_server=http://test.com
app_server_user=myuser
app_server_pass=mypass
db_user=dbuser
db_password=dbpass
schema=testschema
autocommit=0
"""
        mock_get_config.return_value = (config_content, 'Linux', 'testnode')

        creds = DB.get_credentials()

        assert creds['app_server'] == 'http://test.com'
        assert creds['app_server_user'] == 'myuser'
        assert creds['app_server_pass'] == 'mypass'


class TestDBInitialization:
    """Test suite for DB initialization."""

    @patch('DB.database.DB.get_config_from_server')
    def test_db_initialization_with_defaults(self, mock_get_config):
        """Test DB initialization with default parameters."""
        config_content = """
[where]
where=dev
whse=LPM

[dev]
conn_str=jdbc:oracle:thin:@localhost:1521:TEST
app_server=http://test.com
app_server_user=testuser
app_server_pass=testpass
db_user=dbuser
db_password=dbpass
schema=testschema
autocommit=0
close_pallet=Y
"""
        mock_get_config.return_value = (config_content, 'Linux', 'testnode')

        db = DB()

        assert db.who == 'Mohamed'
        assert db.where == 'dev'
        assert db.whse == 'LPM'
        assert db.schema == 'testschema'
        assert db.autocommit is False
        assert db.connection is None
        assert db.cursor is None

    @patch('DB.database.DB.get_config_from_server')
    def test_db_initialization_custom_where(self, mock_get_config):
        """Test DB initialization with custom environment."""
        config_content = """
[where]
where=dev
whse=LPM

[prod]
conn_str=jdbc:oracle:thin:@prod:1521:PROD
app_server=http://prod.com
app_server_user=produser
app_server_pass=prodpass
db_user=proddbuser
db_password=proddbpass
schema=prodschema
autocommit=1
close_pallet=N
"""
        mock_get_config.return_value = (config_content, 'Linux', 'testnode')

        db = DB(where='prod')

        assert db.where == 'prod'
        assert db.autocommit is True


class TestDBConnectionManagement:
    """Test suite for DB connection management."""

    @patch('DB.database.jaydebeapi.connect')
    @patch('DB.database.DB.get_config_from_server')
    def test_connect_creates_connection(self, mock_get_config, mock_connect):
        """Test that connect() creates a database connection."""
        config_content = """
[where]
where=dev
whse=TEST

[dev]
conn_str=jdbc:oracle:thin:@localhost:1521:TEST
app_server=http://test.com
app_server_user=testuser
app_server_pass=testpass
db_user=dbuser
db_password=dbpass
schema=testschema
autocommit=0
close_pallet=Y
"""
        mock_get_config.return_value = (config_content, 'Linux', 'testnode')

        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection

        db = DB()
        connection = db.connect()

        assert connection == mock_connection
        mock_connection.jconn.setAutoCommit.assert_called_once_with(False)

    @patch('DB.database.jaydebeapi.connect')
    @patch('DB.database.DB.get_config_from_server')
    def test_context_manager_enter(self, mock_get_config, mock_connect):
        """Test DB context manager __enter__."""
        config_content = """
[where]
where=dev
whse=TEST

[dev]
conn_str=jdbc:oracle:thin:@localhost:1521:TEST
app_server=http://test.com
app_server_user=testuser
app_server_pass=testpass
db_user=dbuser
db_password=dbpass
schema=testschema
autocommit=0
close_pallet=Y
"""
        mock_get_config.return_value = (config_content, 'Linux', 'testnode')

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        db = DB()
        result = db.__enter__()

        assert result == db
        assert db.connection == mock_connection
        assert db.cursor == mock_cursor

    @patch('DB.database.jaydebeapi.connect')
    @patch('DB.database.DB.get_config_from_server')
    def test_context_manager_exit_success(self, mock_get_config, mock_connect):
        """Test DB context manager __exit__ on success."""
        config_content = """
[where]
where=dev
whse=TEST

[dev]
conn_str=jdbc:oracle:thin:@localhost:1521:TEST
app_server=http://test.com
app_server_user=testuser
app_server_pass=testpass
db_user=dbuser
db_password=dbpass
schema=testschema
autocommit=0
close_pallet=Y
"""
        mock_get_config.return_value = (config_content, 'Linux', 'testnode')

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        with DB() as db:
            pass

        # Should commit on successful exit
        mock_cursor.execute.assert_called_with('commit')

    @patch('DB.database.jaydebeapi.connect')
    @patch('DB.database.DB.get_config_from_server')
    def test_context_manager_exit_with_exception(self, mock_get_config, mock_connect):
        """Test DB context manager __exit__ on exception."""
        config_content = """
[where]
where=dev
whse=TEST

[dev]
conn_str=jdbc:oracle:thin:@localhost:1521:TEST
app_server=http://test.com
app_server_user=testuser
app_server_pass=testpass
db_user=dbuser
db_password=dbpass
schema=testschema
autocommit=0
close_pallet=Y
"""
        mock_get_config.return_value = (config_content, 'Linux', 'testnode')

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        try:
            with DB() as db:
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should rollback on exception
        mock_cursor.execute.assert_called_with('rollback')


class TestDBQueryExecution:
    """Test suite for DB query execution."""

    @patch('DB.database.jaydebeapi.connect')
    @patch('DB.database.DB.get_config_from_server')
    def test_runSQL_basic_query(self, mock_get_config, mock_connect):
        """Test running a basic SQL query."""
        config_content = """
[where]
where=dev
whse=TEST

[dev]
conn_str=jdbc:oracle:thin:@localhost:1521:TEST
app_server=http://test.com
app_server_user=testuser
app_server_pass=testpass
db_user=dbuser
db_password=dbpass
schema=testschema
autocommit=0
close_pallet=Y
"""
        mock_get_config.return_value = (config_content, 'Darwin', 'testnode')

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [('COL1', 'VARCHAR'), ('COL2', 'NUMBER')]
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        with DB() as db:
            result = db.runSQL("SELECT * FROM test_table", whse_specific=False)

        assert result == db
        assert db.query == "SELECT * FROM test_table"
        assert db.column_names == ['COL1', 'COL2']

    @patch('DB.database.jaydebeapi.connect')
    @patch('DB.database.DB.get_config_from_server')
    def test_fetchone_returns_dict(self, mock_get_config, mock_connect):
        """Test fetchone returns a dictionary."""
        config_content = """
[where]
where=dev
whse=TEST

[dev]
conn_str=jdbc:oracle:thin:@localhost:1521:TEST
app_server=http://test.com
app_server_user=testuser
app_server_pass=testpass
db_user=dbuser
db_password=dbpass
schema=testschema
autocommit=0
close_pallet=Y
"""
        mock_get_config.return_value = (config_content, 'Darwin', 'testnode')

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [('ID', 'NUMBER'), ('NAME', 'VARCHAR')]
        mock_cursor.fetchone.return_value = (1, 'Test')
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        with DB() as db:
            db.runSQL("SELECT * FROM test", whse_specific=False)
            result = db.fetchone()

        assert result == {'ID': 1, 'NAME': 'Test'}

    @patch('DB.database.jaydebeapi.connect')
    @patch('DB.database.DB.get_config_from_server')
    def test_fetchone_no_results(self, mock_get_config, mock_connect):
        """Test fetchone with no results."""
        config_content = """
[where]
where=dev
whse=TEST

[dev]
conn_str=jdbc:oracle:thin:@localhost:1521:TEST
app_server=http://test.com
app_server_user=testuser
app_server_pass=testpass
db_user=dbuser
db_password=dbpass
schema=testschema
autocommit=0
close_pallet=Y
"""
        mock_get_config.return_value = (config_content, 'Darwin', 'testnode')

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        with DB() as db:
            db.runSQL("SELECT * FROM test WHERE 1=0", whse_specific=False)
            result = db.fetchone()

        assert result is None

    def test_extract_table_names_simple_select(self):
        """Test extracting table names from simple SELECT."""
        db = MagicMock(spec=DB)
        db.extract_table_names_with_aliases = DB.extract_table_names_with_aliases.__get__(db)

        query = "SELECT * FROM users u"
        tables = db.extract_table_names_with_aliases(query)

        assert 'u' in tables
        assert tables['u'] == 'USERS'

    def test_extract_table_names_update_query(self):
        """Test extracting table names from UPDATE."""
        db = MagicMock(spec=DB)
        db.extract_table_names_with_aliases = DB.extract_table_names_with_aliases.__get__(db)

        query = "UPDATE orders SET status='complete' WHERE id=1"
        tables = db.extract_table_names_with_aliases(query)

        assert 'orders' in tables or 'ORDERS' in tables.values()

    def test_extract_table_names_with_schema(self):
        """Test extracting table names with schema prefix."""
        db = MagicMock(spec=DB)
        db.extract_table_names_with_aliases = DB.extract_table_names_with_aliases.__get__(db)

        query = "SELECT * FROM myschema.users u"
        tables = db.extract_table_names_with_aliases(query)

        assert 'u' in tables
        assert tables['u'] == 'USERS'


@pytest.mark.slow
class TestDBIntegration:
    """Integration tests for database (require actual DB connection)."""

    def test_full_query_cycle(self):
        """Test full query cycle with real connection."""
        # Placeholder - requires actual database
        pass

    def test_transaction_commit(self):
        """Test transaction commit."""
        # Placeholder - requires actual database
        pass

    def test_transaction_rollback(self):
        """Test transaction rollback."""
        # Placeholder - requires actual database
        pass
