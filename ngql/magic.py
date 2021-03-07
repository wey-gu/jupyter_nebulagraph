import logging

from IPython.core.magic import (
    Magics, magics_class, line_cell_magic, needs_local_scope)
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring

from jinja2 import Template, Environment, meta
from traitlets.config.configurable import Configurable
from traitlets import Bool, Int, Unicode

from nebula2.gclient.net import ConnectionPool as NebulaConnectionPool
from nebula2.Config import Config as NebulaConfig


CONNECTION_POOL_INIT_FAILURE = -2  # Failure occurred during connection_pool.init
CONNECTION_POOL_NONE = -1          # self.connection_pool was never initiated
CONNECTION_POOL_EXISTED = 0        # self.connection_pool existed & no new created
CONNECTION_POOL_CREATED = 1        # self.connection_pool newly created/recreated

STYLE_PANDAS = "pandas"
STYLE_RAW = "raw"

# FIXME:(wey-gu) add other type mappings
TYPE_MAPPING = {
    "string": str,
}

@magics_class
class IPythonNGQL(Magics, Configurable):

    ngql_verbose = Bool(False, config=True, help="Set verbose mode")
    max_connection_pool_size = Int(
        None,
        config=True,
        allow_none=True,
        help="Maximum Nebula Connection Pool Size",
    )
    ngql_result_style = Unicode(
        STYLE_PANDAS,
        config=True,
        allow_none=True,
        help="Accepted values in ('pandas', 'raw'):"
             " pandas refers to pandas DataFrame,"
             " raw refers to raw thrift data type comes with nebula-python.",
    )

    def __init__(self, shell):
        Magics.__init__(self, shell=shell)

        self.shell.configurables.append(self)
        self.connection_pool = None
        self.space = None
        self.connection_info = None
        self.credential = None

    @needs_local_scope
    @line_cell_magic
    @magic_arguments()
    @argument("line", default="", nargs="*", type=str, help="sql")
    @argument("-addr", "--address", type=str, help="IP address")
    @argument("-P", "--port", type=int, help="Port number")
    @argument("-u", "--user", type=str, help="Username")
    @argument("-p", "--password", type=str, help="Password")
    @argument("-f", "--file", type=str, help="Run a NGQL file from a path")  # TBD
    @argument("-c", "--close", type=str, help="Close the connection")  # TBD
    def ngql(self, line, cell=None, local_ns={}):
        """Magic that works both as %ngql and as %%ngql"""
        if line == "help":
            return self._help_info()

        cell = self._render_cell_vars(cell, local_ns)

        args = parse_argstring(self.ngql, line)

        connection_state = self._init_connection_pool(args)
        if self.ngql_verbose:
            print(f"[DEBUG] Connection State: { connection_state }")
        if connection_state < 0:
            print("[ERROR] Connection is not ready")
            return f"Connection State: { connection_state }"
        if connection_state == CONNECTION_POOL_CREATED:
            print("Connection Pool Created")
            if not cell:
                return self._stylized(self._show_spaces())
            else:
                # When connection info in first line and with nGQL lines followed
                return self._stylized(self._execute(cell))
        if connection_state == CONNECTION_POOL_EXISTED:
            query = line + "\n" + (cell if cell else "")
            return self._stylized(self._execute(query))
        else:  # We shouldn't reach here
            return f"Nothing triggerred, Connection State: { connection_state }"

    def _init_connection_pool(self, args):
        connection_info = (args.address, args.port, args.user, args.password)
        if any(connection_info):
            if not all(connection_info):
                raise ValueError(
                    "One or more arguments missing: address, port, user, "
                    "password should None or all be provided.")
            else:  # all connection information ready
                connection_pool = NebulaConnectionPool()
                config = NebulaConfig()
                if self.max_connection_pool_size:
                    config.max_connection_pool_size = self.max_connection_pool_size

                self.credential = args.user, args.password
                connect_init_result = connection_pool.init(
                    [(args.address, args.port)], config)
                if not connect_init_result:
                    return CONNECTION_POOL_INIT_FAILURE
                else:
                    self.connection_pool = connection_pool
                    return CONNECTION_POOL_CREATED

        # else a.k.a not any(connection_info)
        if self.connection_pool is not None:
            return CONNECTION_POOL_EXISTED
        else:
            return CONNECTION_POOL_NONE
    
    def _render_cell_vars(self, cell, local_ns):
        if cell is not None:
            env = Environment()
            cell_vars = meta.find_undeclared_variables(env.parse(cell))
            cell_params = {}
            for variable in cell_vars:
                if variable in local_ns:
                    cell_params[variable] = local_ns[variable]
                else:
                    raise NameError(variable)
            cell_template = Template(cell)
            cell = cell_template.render(**cell_params)
            if self.ngql_verbose:
                print(f"Query String:\n { cell }")
        return cell

    def _get_session(self):
        logger = logging.getLogger()
        # FIXME(wey-gu): introduce configurable options here via traitlets
        # Here let's disable the nebula-python logger as we consider
        # most users here are data scientists who would share the
        # notebook, thus connection info shouldn't be revealed unless
        # explicitly specified
        logger.disabled = True
        return self.connection_pool.get_session(*self.credential)

    def _show_spaces(self):
        session = self._get_session()
        try:
            result = session.execute("SHOW SPACES")
            self._auto_use_space(result=result)
        except Exception as e:
            print(f"[ERROR]:\n { e }")
        finally:
            session.release()
        return result

    def _auto_use_space(self, result=None):
        if result is None:
            session = self._get_session()
            result = session.execute("SHOW SPACES YIELD Name AS Space_Name;")

        if result.row_size() == 1:
            self.space = self._decode_value(result.row_values(0)[0]._value.value)

    def _execute(self, query):
        session = self._get_session()
        try:
            if self.space is not None:  # Always use space automatically
                session.execute(f"USE { self.space }")
            result = session.execute(query)
            self._remember_space(result)
        except Exception as e:
            print(f"[ERROR]:\n { e }")
        finally:
            session.release()
        return result

    def _remember_space(self, result):
        last_space_used = result.space_name()
        if last_space_used != "":
            self.space = last_space_used

    def _stylized(self, result):
        if self.ngql_result_style == STYLE_PANDAS:
            import pandas as pd
            rows = {
                    key: self._decode_column(result.column_values(key=key))
                    for key in result.keys()
                }
            return pd.DataFrame(rows, columns=(result.keys()))
        elif self.ngql_result_style == STYLE_RAW:
            return result
        else:
            raise ValueError("Unknown ngql_result_style")

    def _decode_column(self, column_values):
        return [self._decode_value(
            value._value.value,
            value.decode_type if hasattr(value, "decode_type") else "utf-8",
            value._get_type_name() if hasattr(value, "_get_type_name") else "string"
            ) for value in column_values]

    def _decode_value(self, value, decode_type="utf-8", value_type="string"):
        if self.ngql_verbose:
            print(f"[DEBUG] _decode_value: {value}, {decode_type}, {value_type}")
        if value_type in TYPE_MAPPING:
            return TYPE_MAPPING[value_type](value, decode_type)
        else:
            return value

    @staticmethod
    def _help_info():
        help_info = """

        Supported Configurations:
        ------------------------
        
        > How to config ngql_result_style in "raw", "pandas"
        %config IPythonNGQL.ngql_result_style="raw"
        %config IPythonNGQL.ngql_result_style="pandas"

        > How to config ngql_verbose in True, False
        %config IPythonNGQL.ngql_verbose=True

        > How to config max_connection_pool_size
        %config IPythonNGQL.max_connection_pool_size=10

        Quick Start:
        -----------

        > Connect to Neubla Graph
        %ngql --address 127.0.0.1 --port 9669 --user user --password password

        > Use Space
        %ngql USE nba

        > Query
        %ngql SHOW TAGS;

        > Multile Queries
        %%ngql
        SHOW TAGS;
        SHOW HOSTS;

        Reload ngql Magic
        %reload_ext ngql

        > Variables in query, we are using Jinja2 here
        name = "nba"
        %ngql USE "{{ name }}"


        """
        print(help_info)
        return
