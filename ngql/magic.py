import logging

from IPython.core.magic import Magics, magics_class, line_cell_magic, needs_local_scope
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring

from typing import Dict

from jinja2 import Template, Environment, meta
from traitlets.config.configurable import Configurable
from traitlets import Bool, Int, Unicode

from nebula3.data.DataObject import Node, Relationship, PathWrapper
from nebula3.gclient.net import ConnectionPool as NebulaConnectionPool
from nebula3.Config import Config as NebulaConfig


CONNECTION_POOL_INIT_FAILURE = -2  # Failure occurred during connection_pool.init
CONNECTION_POOL_NONE = -1  # self.connection_pool was never initiated
CONNECTION_POOL_EXISTED = 0  # self.connection_pool existed & no new created
CONNECTION_POOL_CREATED = 1  # self.connection_pool newly created/recreated

STYLE_PANDAS = "pandas"
STYLE_RAW = "raw"

COLORS = ["#E2DBBE", "#D5D6AA", "#9DBBAE", "#769FB6", "#188FA7"]

ESCAPE_ARROW_STRING = "__ar_row__"


def get_color(input_str):
    hash_val = 0
    for char in input_str:
        hash_val = (hash_val * 31 + ord(char)) & 0xFFFFFFFF
    return COLORS[hash_val % len(COLORS)]


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
    @argument("line", default="", nargs="*", type=str, help="ngql line")
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

        # Replace "->" with ESCAPE_ARROW_STRING to avoid argument parsing issues
        modified_line = line.replace("->", ESCAPE_ARROW_STRING)

        args = parse_argstring(self.ngql, modified_line)

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
            # Restore "->" in the query before executing it
            query = (
                line.replace(ESCAPE_ARROW_STRING, "->") + "\n" + (cell if cell else "")
            )
            return self._stylized(self._execute(query))
        else:  # We shouldn't reach here
            return f"Nothing triggerred, Connection State: { connection_state }"

    def _init_connection_pool(self, args):
        connection_info = (args.address, args.port, args.user, args.password)
        if any(connection_info):
            if not all(connection_info):
                raise ValueError(
                    "One or more arguments missing: address, port, user, "
                    "password should None or all be provided."
                )
            else:  # all connection information ready
                connection_pool = NebulaConnectionPool()
                config = NebulaConfig()
                if self.max_connection_pool_size:
                    config.max_connection_pool_size = self.max_connection_pool_size

                self.credential = args.user, args.password
                connect_init_result = connection_pool.init(
                    [(args.address, args.port)], config
                )
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
            result = session.execute("SHOW SPACES;")

        if result.row_size() == 1:
            self.space = result.row_values(0)[0].cast()

    def _execute(self, query):
        session = self._get_session()
        query = query.replace("\\\n", "\n")
        try:
            if self.space is not None:  # Always use space automatically
                session.execute(f"USE { self.space }")
            result = session.execute(query)
            assert result.is_succeeded(), f"Query Failed:\n { result.error_msg() }"
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
            try:
                import pandas as pd
            except ImportError:
                raise ImportError("Please install pandas to use STYLE_PANDAS")

            columns = result.keys()
            d: Dict[str, list] = {}
            for col_num in range(result.col_size()):
                col_name = columns[col_num]
                col_list = result.column_values(col_name)
                d[col_name] = [x.cast() for x in col_list]
            return pd.DataFrame(d)
        elif self.ngql_result_style == STYLE_RAW:
            return result
        else:
            raise ValueError("Unknown ngql_result_style")

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
        %ngql USE basketballplayer

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

        > Query and draw the graph

        %ngql GET SUBGRAPH 2 STEPS FROM "player101" YIELD VERTICES AS nodes, EDGES AS relationships;

        %ng_draw


        """
        print(help_info)
        return

    @needs_local_scope
    @line_cell_magic
    @magic_arguments()
    @argument("line", default="", nargs="*", type=str, help="ngql")
    def ng_draw(self, line, cell=None, local_ns={}):
        """
        Draw the graph with the output of the last execution query
        """
        try:
            import pandas as pd
            from pyvis.network import Network
            from IPython.display import display, IFrame, HTML

            # import get_ipython
            from IPython import get_ipython

        except ImportError:
            raise ImportError("Please install pyvis to draw the graph")
        # when `%ngql foo`, varible_name is "foo", else it's "_"
        variable_name = line.strip() or "_"
        # Check if the last execution result is available in the local namespace
        if variable_name not in local_ns:
            return "No result found, please execute a query first."
        result_df = local_ns[variable_name]
        assert isinstance(
            result_df, pd.DataFrame
        ), "Result is not in Pandas DataFrame Style"

        # Create a graph
        g = Network(
            notebook=True,
            directed=True,
            cdn_resources="in_line",
            height="500px",
            width="100%",
        )
        for _, row in result_df.iterrows():
            for item in row:
                self.render_pd_item(g, item)
        g.repulsion(
            node_distance=100,
            central_gravity=0.2,
            spring_length=200,
            spring_strength=0.05,
            damping=0.09,
        )
        # g.show_buttons(filter_='physics')
        # return g.show("nebulagraph_draw.html", notebook=True)
        g_html_string = g.generate_html("nebulagraph.html")
        with open("nebulagraph.html", "w", encoding="utf-8") as f:
            f.write(g_html_string)
        # detect if we are in colab or not
        try:
            if "google.colab" in str(get_ipython()):
                display(HTML(g_html_string))
            else:
                display(IFrame(src="nebulagraph.html", width="100%", height="500px"))
        except Exception as e:
            print(f"[WARN]: failed to display the graph\n { e }")
            try:
                display(IFrame(src="nebulagraph.html", width="100%", height="500px"))
            except Exception as e:
                print(f"[WARN]: failed to display the graph\n { e }")

        return g

    def render_pd_item(self, g, item):
        if isinstance(item, Node):
            node_id = item.get_id().cast()
            tags = item.tags()  # list of strings
            props = dict()
            for tag in tags:
                props.update(item.properties(tag))

            g.add_node(
                node_id, label=node_id, title=str(props), color=get_color(node_id)
            )
        elif isinstance(item, Relationship):
            src_id = item.start_vertex_id().cast()
            dst_id = item.end_vertex_id().cast()
            edge_name = item.edge_name()
            props = item.properties()
            # ensure start and end vertex exist in graph
            if not src_id in g.node_ids:
                g.add_node(
                    src_id,
                    label=str(src_id),
                    title=str(src_id),
                    color=get_color(src_id),
                )
            if not dst_id in g.node_ids:
                g.add_node(
                    dst_id,
                    label=str(dst_id),
                    title=str(dst_id),
                    color=get_color(dst_id),
                )
            label = f"{props}\n{edge_name}" if props else edge_name
            g.add_edge(src_id, dst_id, label=label, title=str(props))
        elif isinstance(item, PathWrapper):
            for node in item.nodes():
                self.render_pd_item(g, node)
            for edge in item.relationships():
                self.render_pd_item(g, edge)
        elif isinstance(item, list):
            for it in item:
                self.render_pd_item(g, it)
