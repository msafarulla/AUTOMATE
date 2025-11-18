import itertools
import jaydebeapi
import configparser
import re
import paramiko
import os
import platform
import getpass
from core.logger import app_log

class DB:
    def __enter__(self):    
        self.connection = self.connect()
        self.cursor = self.connection.cursor()
        self.setSchema()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type:  # There was an exception
                self.runSQL('rollback')
            else:
                self.runSQL('commit')
        finally:
            self.close()

    @classmethod
    def get_config_from_server(cls):
        # Default server values
        hostname = "soa430"
        username = "vxmsafar"
        config_file_path = "~/config.ini"

        # Detect if running on Mac
        system_name = platform.system()
        node_name = platform.node()  # e.g. "Mohameds-MacBook-Pro.local"

        if system_name == "Darwin":  # macOS check
            hostname = "localhost"
            username = getpass.getuser()   # your Mac username automatically
            # optionally, point to your local config path
            config_file_path = os.path.expanduser("~/SUBARU/config/config.ini")

        # Initialize SSH client
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect (passwordless / ssh-agent expected)
        client.connect(hostname, username=username)

        # Read the config.ini
        stdin, stdout, stderr = client.exec_command(f"cat {config_file_path}")
        config_content = stdout.read().decode()

        client.close()
        return config_content, system_name, node_name

    @classmethod
    def _load_config(cls, where=None, whse=None):
        config = configparser.ConfigParser()
        config_content, system_name, node_name = cls.get_config_from_server()
        clean_content = re.sub(r'[^\x20-\x7E\n\r]', '', config_content)
        config.read_string(clean_content)

        selected_where = config["where"]["where"] if not where else where
        if system_name == "Darwin":  # macOS check
            selected_where = 'local'
        config['where']['whse'] = whse if whse else config['where']['whse']

        return {
            "config": config,
            "clean_content": clean_content,
            "system_name": system_name,
            "node_name": node_name,
            "where": selected_where,
        }

    @classmethod
    def get_credentials_for(cls, where=None, whse=None):
        data = cls._load_config(where, whse)
        section = data["config"][data["where"]]
        return {
            "app_server_user": section["app_server_user"],
            "app_server_pass": section["app_server_pass"],
        }

    def __init__(self, where=None, whse=None):
        self.who = 'Mohamed'
        self.query = None
        config_data = self._load_config(where, whse)
        config = config_data["config"]
        self.clean_content = config_data["clean_content"]
        self.system_name = config_data["system_name"]
        self.node_name = config_data["node_name"]
        self.where = config_data["where"]
        self.conn_str = config[self.where]['conn_str']
        self.whse = config['where']['whse']
        self.close_pallet = config['where']['close_pallet']
        self.app_server_user = config[self.where]['app_server_user']
        self.app_server_pass = config[self.where]['app_server_pass']
        self.db_user = config[self.where]['db_user']
        self.db_psw = config[self.where]['db_password']
        self.schema = config[self.where]['schema']
        self.autocommit = False if config[self.where]['autocommit'] == 0 else True
        self.column_names = []
        self.column_types = []
        self.connection = None
        self.cursor = None

    def connect(self):
        driver_path = os.path.dirname(os.path.abspath(__file__)) + '/../drivers'
        java_oracle_driver_path = [f'{driver_path}/ojdbc8.jar']
        connection = jaydebeapi.connect('oracle.jdbc.OracleDriver', self.conn_str, [self.db_user, self.db_psw], java_oracle_driver_path)
        connection.jconn.setAutoCommit(False)
        return connection

    def setSchema(self):
        if self.system_name != 'Darwin':
            self.cursor.execute(f'alter session set current_schema = {self.schema}')
        else:
            self.cursor.execute(f'set search_path to {self.schema}')

    def extract_table_names_with_aliases(self, query):
        tables = {}

        # Handle UPDATE queries
        update_match = re.search(r'\bUPDATE\s+([^\s]+)', query, re.IGNORECASE)
        if update_match:
            table = update_match.group(1).strip().split('.')[-1]
            tables[table] = table.upper()

        # Handle FROM clause (SELECTs, JOINs, etc.)
        from_match = re.search(r'\bFROM\s+(.+?)(?:\bWHERE\b|\bGROUP BY\b|\bORDER BY\b|\bSET\b|$)', query, re.IGNORECASE | re.DOTALL)
        if from_match:
            from_clause = from_match.group(1)
            for table in from_clause.split(','):
                parts = table.strip().split()
                table_name = parts[0].strip().split('.')[-1]
                alias = parts[1].strip() if len(parts) > 1 else table_name
                tables[alias] = table_name.upper()

        return tables

    def addWHSE(self, query):
        updated_query = query
        table_aliases = self.extract_table_names_with_aliases(updated_query)
        whse_conditions = []
        join_conditions = []

        # DEBUG: Extracted Tables and Aliases can be logged here if needed.

        if 1==1:
            whse_tables = []  # List of tables that have a WHSE column

            # Check each table for the WHSE column
            for alias, table in table_aliases.items():
                column_check_query = f"""
                SELECT column_name FROM all_tab_columns 
                WHERE table_name = '{table}' AND column_name = 'WHSE'
                """
                # DEBUG: Checking WHSE column for table (alias) details here if needed.
                self.runSQL(column_check_query, False)
                if self.fetchone():  # If WHSE column exists
                    whse_conditions.append(f"{alias}.WHSE = '{self.whse}'")
                    whse_tables.append(alias)

            # Generate join conditions for all pairs of tables with WHSE columns
            for table1, table2 in itertools.combinations(whse_tables, 2):
                join_conditions.append(f"{table1}.WHSE = {table2}.WHSE")

            # DEBUG: WHSE and Join conditions available for inspection if needed.

            # Combine all WHSE filters and join conditions
            all_conditions = whse_conditions + join_conditions

            if all_conditions:
                combined_clause = " AND ".join(all_conditions)

                # Improved regex to handle multiline WHERE clause injection
                where_match = re.search(r'(\bWHERE\b)([\s\S]*?)(\bORDER BY\b|\Z)', updated_query, re.IGNORECASE)

                if where_match:
                    # Extract existing WHERE conditions
                    existing_conditions = where_match.group(2).strip()
                    new_where = f"{where_match.group(1)} {combined_clause} AND {existing_conditions} {where_match.group(3)}"
                    updated_query = re.sub(r'(\bWHERE\b)([\s\S]*?)(\bORDER BY\b|\Z)', new_where, updated_query,
                                           flags=re.IGNORECASE)
                else:
                    # If no WHERE clause exists, add one
                    updated_query += f" WHERE {combined_clause}"

        return updated_query

    def runSQL(self, query, whse_specific=True):
        if self.connection is None:  #enable call withought context manager
            self.connection = self.connect()
            self.cursor = self.connection.cursor()
            self.setSchema()
        if self.whse != '' and whse_specific and query not in ['commit', 'rollback']:
            query = self.addWHSE(query)
        self.cursor.execute(query)
        self.query = query
        if 'UPDATE' not in query.upper() and 'INSERT' not in query.upper() and 'DELETE' not in query.upper() and 'COMMIT' not in query.upper() and 'ROLLBACK' not in query.upper():
            self.column_names = [i[0] for i in self.cursor.description]
            self.column_types = [i[1] for i in self.cursor.description]
        return self


    def fetchall(self):
        return self.cursor.fetchall(),[desc[0] for desc in self.cursor.description]

    def fetchone(self,metadata=False):
        result_set = self.cursor.fetchone()
        if not result_set:      
            return None
        return dict(zip(self.column_names, result_set)) if not metadata else (dict(zip(self.column_names, result_set)),dict(zip(self.column_names, self.column_types)))

    def dual(self, proc):
        query = f"select {proc} next_up from DUAL"
        connection = self.connect()
        cursor = connection.cursor()
        cursor.execute(f'alter session set current_schema = {self.schema}')
        cursor.execute(query)
        result_set = cursor.fetchone()
        if not result_set:
            connection.close()
            return None
        connection.close()
        return result_set[0]

    def close(self):
        self.cursor.close()
        self.connection.close()


if __name__ == '__main__':
    cnx1 = DB('dev')
    c1 = cnx1.runSQL('select * from ITEM_CBO fetch first 10 rows only',False)
    # c2 = cnx2.runSQL('select * from LPN_DETAIL fetch 10 rows')
    while row := c1.fetchone():
        app_log(str(row))
