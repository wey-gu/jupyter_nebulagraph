import logging

import pprint
from typing import Any, ClassVar, Dict, List, Optional

from IPython.core.magic import (
    Magics,
    magics_class,
    line_cell_magic,
    needs_local_scope,
)
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring


import networkx as nx


from jinja2 import Template, Environment, meta
from traitlets.config.configurable import Configurable
from traitlets import Bool, Int, Unicode

from nebula3.data.DataObject import Node, Relationship, PathWrapper
from nebula3.gclient.net import ConnectionPool as NebulaConnectionPool
from nebula3.Config import Config as NebulaConfig
from nebula3.Config import SSL_config
from nebula3.data.ResultSet import ResultSet

from ngql.ng_load import ng_load
from ngql.types import LoadDataArgsModel


rel_query_sample_edge = Template(
    """
MATCH ()-[e:`{{ edge_type }}`]->()
RETURN [src(e), dst(e)] AS sample_edge LIMIT 10
"""
)


rel_query_edge_type = Template(
    """
MATCH (m)-[:`{{ edge_type }}`]->(n)
  WHERE id(m) == "{{ src_id }}" AND id(n) == "{{ dst_id }}"
RETURN tags(m)[0] AS src_tag, tags(n)[0] AS dst_tag
"""
)


CONNECTION_POOL_INIT_FAILURE = -2  # Failure occurred during connection_pool.init
CONNECTION_POOL_NONE = -1  # self.connection_pool was never initiated
CONNECTION_POOL_EXISTED = 0  # self.connection_pool existed & no new created
CONNECTION_POOL_CREATED = 1  # self.connection_pool newly created/recreated

STYLE_PANDAS = "pandas"
STYLE_RAW = "raw"

# COLORS = ["#E2DBBE", "#D5D6AA", "#9DBBAE", "#769FB6", "#188FA7"]
# solarized dark
COLORS = [
    "#93A1A1",
    "#B58900",
    "#CB4B16",
    "#DC322F",
    "#D33682",
    "#6C71C4",
    "#268BD2",
    "#2AA198",
    "#859900",
]

ESCAPE_ARROW_STRING = "__ar_row__"


def truncate(string: str, length: int = 10) -> str:
    if len(string) > length:
        return string[:length] + ".."
    else:
        return string


def get_color(input_str):
    hash_val = 0
    for char in input_str:
        hash_val = (hash_val * 31 + ord(char)) & 0xFFFFFFFF
    return COLORS[hash_val % len(COLORS)]


def is_human_readable(field):
    return any(c.isalpha() for c in field) and len(field) < 20


class FancyPrinter:
    pp = pprint.PrettyPrinter(indent=2, sort_dicts=False)
    # Thanks to https://www.learnui.design/tools/data-color-picker.html
    COLORS_rgb: ClassVar[Dict[str, str]] = {
        "dark_blue": "38;2;0;63;92",
        "blue": "38;2;47;75;124",
        "light_blue": "38;2;0;120;215",
        "green": "38;2;0;135;107",
        "light_green": "38;2;102;187;106",
        "purple": "38;2;102;81;145",
        "magenta": "38;2;160;81;149",
        "pink": "38;2;212;80;135",
        "red": "38;2;249;93;106",
        "orange": "38;2;255;124;67",
        "yellow": "38;2;255;166;0",
    }

    color_idx: int = 0

    def __call__(self, val: Any, color: Optional[str] = None):
        if color in self.COLORS_rgb:
            self.color_idx = list(self.COLORS_rgb.keys()).index(color)
            color = self.COLORS_rgb[color]
        else:
            self.color_idx += 1
            self.color_idx %= len(self.COLORS_rgb)
            color = list(self.COLORS_rgb.values())[self.color_idx]

        if isinstance(val, str):
            print(f"\033[1;3;{color}m{val}\033[0m")
        else:
            text = self.pp.pformat(val)
            print(f"\033[1;3;{color}m{text}\033[0m")


fancy_print = FancyPrinter()


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
            fancy_print(f"[DEBUG] Connection State: { connection_state }")
        if connection_state < 0:
            fancy_print("[ERROR] Connection is not ready", color="pink")
            return f"Connection State: { connection_state }"
        if connection_state == CONNECTION_POOL_CREATED:
            fancy_print("Connection Pool Created", color="blue")
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

    def _init_connection_pool(self, args: Optional[Any] = None):
        if args is None:
            return (
                CONNECTION_POOL_EXISTED
                if self.connection_pool is not None
                else CONNECTION_POOL_NONE
            )

        connection_info = (args.address, args.port, args.user, args.password)
        if any(connection_info):
            if not all(connection_info):
                raise ValueError(
                    "One or more arguments missing: address, port, user, "
                    "password should None or all be provided."
                )
            # all connection information ready
            connection_pool = NebulaConnectionPool()
            config = NebulaConfig()
            if self.max_connection_pool_size:
                config.max_connection_pool_size = self.max_connection_pool_size

            self.credential = args.user, args.password
            try:
                connect_init_result = connection_pool.init(
                    [(args.address, args.port)], config
                )
            except RuntimeError:
                # When GraphD is over TLS
                fancy_print(
                    "[ERROR] Got RuntimeError, trying to connect assuming GraphD is over TLS",
                    color="pink",
                )
                ssl_config = SSL_config()
                connect_init_result = connection_pool.init(
                    [(args.address, args.port)], config, ssl_config
                )
            if not connect_init_result:
                return CONNECTION_POOL_INIT_FAILURE
            else:
                self.connection_pool = connection_pool
                return CONNECTION_POOL_CREATED
        else:
            return (
                CONNECTION_POOL_EXISTED
                if self.connection_pool is not None
                else CONNECTION_POOL_NONE
            )

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
                fancy_print(f"Query String:\n { cell }", color="blue")
        return cell

    def _get_session(self):
        logger = logging.getLogger()
        # FIXME(wey-gu): introduce configurable options here via traitlets
        # Here let's disable the nebula-python logger as we consider
        # most users here are data scientists who would share the
        # notebook, thus connection info shouldn't be revealed unless
        # explicitly specified
        logger.disabled = True
        if self.connection_pool is None:
            raise ValueError(
                "Please connect to NebulaGraph first, i.e. \n"
                "%ngql --address 127.0.0.1 --port 9669 --user root --password nebula"
            )
        return self.connection_pool.get_session(*self.credential)

    def _show_spaces(self):
        session = self._get_session()
        try:
            result = session.execute("SHOW SPACES")
            self._auto_use_space(result=result)
        except Exception as e:
            fancy_print(f"[ERROR]:\n { e }", color="red")
        finally:
            session.release()
        return result

    def _auto_use_space(self, result=None):
        if result is None:
            session = self._get_session()
            result = session.execute("SHOW SPACES;")

        if result.row_size() == 1:
            self.space = result.row_values(0)[0].cast_primitive()

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
            fancy_print(f"[ERROR]:\n { e }", color="red")
        finally:
            session.release()
        return result

    def _remember_space(self, result):
        last_space_used = result.space_name()
        if last_space_used != "":
            self.space = last_space_used

    def _stylized(self, result: ResultSet, style=None):
        style = style or self.ngql_result_style
        if style == STYLE_PANDAS:
            try:
                import pandas as pd
            except ImportError:
                raise ImportError("Please install pandas to use STYLE_PANDAS")

            pd.set_option("display.max_columns", None)
            pd.set_option("display.max_colwidth", None)
            pd.set_option("display.max_rows", 300)
            pd.set_option("display.expand_frame_repr", False)

            columns = result.keys()
            d: Dict[str, list] = {}
            for col_num in range(result.col_size()):
                col_name = columns[col_num]
                col_list = result.column_values(col_name)
                d[col_name] = [x.cast() for x in col_list]
            df = pd.DataFrame(d)
            df.style.set_table_styles(
                [{"selector": "table", "props": [("overflow-x", "scroll")]}]
            )
            return df
        elif style == STYLE_RAW:
            return result
        else:
            raise ValueError(f"Unknown ngql_result_style: { style }")

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

        > Query and draw the graph of last executed query.

        %ngql GET SUBGRAPH WITH PROP 2 STEPS FROM "player101" YIELD VERTICES AS nodes, EDGES AS relationships;

        %ng_draw

        Or draw a Query

        %ng_draw GET SUBGRAPH WITH PROP 2 STEPS FROM "player101" YIELD VERTICES AS nodes, EDGES AS relationships;

        > Query and draw the graph schema

        %ng_draw_schema

        > Load data from CSV file into NebulaGraph as vertices or edges
        %ng_load --source actor.csv --tag player --vid 0 --props 1:name,2:age --space basketballplayer

        #actor.csv
        "player999","Tom Hanks",30
        "player1000","Tom Cruise",40

        %ng_load --source follow_with_rank.csv --edge follow --src 0 --dst 1 --props 2:degree --rank 3 --space basketballplayer

        #follow_with_rank.csv
        "player999","player1000",50,1

        %ng_load --source follow.csv --edge follow --src 0 --dst 1 --props 2:degree --space basketballplayer

        #follow.csv
        "player999","player1000",50

        %ng_load --source https://github.com/wey-gu/ipython-ngql/raw/main/examples/actor.csv --tag player --vid 0 --props 1:name,2:age --space demo_basketballplayer


        """
        fancy_print(help_info, color="green")
        return

    def _draw_graph(self, g: Any) -> Any:
        try:
            from IPython.display import display, IFrame, HTML

            # import get_ipython
            from IPython import get_ipython
        except ImportError:
            raise ImportError("Please install IPython to draw the graph")

        g.repulsion(
            node_distance=90,
            central_gravity=0.2,
            spring_length=200,
            spring_strength=0.05,
            damping=0.09,
        )
        # g.show_buttons(filter_='physics')
        # return g.show("nebulagraph.html", notebook=True)
        cell_num = get_ipython().execution_count
        graph_render_filename = f"nebulagraph_cell_{cell_num}.html"
        g_html_string = g.generate_html(graph_render_filename)
        with open(graph_render_filename, "w", encoding="utf-8") as f:
            f.write(g_html_string)
        # detect if we are in colab or not
        try:
            if "google.colab" in str(get_ipython()):
                display(HTML(g_html_string))
            else:
                display(IFrame(src=graph_render_filename, width="100%", height="500px"))
        except Exception as e:
            print(f"[WARN]: failed to display the graph\n { e }")
            try:
                display(IFrame(src=graph_render_filename, width="100%", height="500px"))
            except Exception as e:
                print(f"[WARN]: failed to display the graph\n { e }")

        return g

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

        except ImportError:
            raise ImportError("Please install pyvis to draw the graph")
        # when `%ng_draw foo`, varible_name is "foo", else it's "_"
        arguments_line = line.strip()

        if not arguments_line and not cell:
            # No arguments and no cell content, draw the graph with the last execution result

            variable_name = arguments_line or "_"
            # Check if the last execution result is available in the local namespace
            if variable_name not in local_ns:
                return "No result found, please execute a query first."
            result_df = local_ns[variable_name]

            if not isinstance(result_df, pd.DataFrame):
                if isinstance(result_df, ResultSet):
                    result_df = self._stylized(result_df, style=STYLE_PANDAS)
                elif isinstance(result_df, Network):
                    # A rerun of %ng_draw with the last execution result
                    g = self._draw_graph(result_df)
                    return g
                else:
                    fancy_print(
                        "[ERROR]: No valid %ngql query result available. \n"
                        "Please execute a valid query before using %ng_draw. \n"
                        "Or pass a query as an argument to %ng_draw or %%ng_draw(multiline).",
                        color="red",
                    )
                    return ""

        else:
            # Arguments provided, execute the query and draw the graph

            if line == "help":
                return self._help_info()

            cell = self._render_cell_vars(cell, local_ns)

            # Replace "->" with ESCAPE_ARROW_STRING to avoid argument parsing issues
            modified_line = line.replace("->", ESCAPE_ARROW_STRING)

            connection_state = self._init_connection_pool()
            if connection_state == CONNECTION_POOL_EXISTED:
                # Restore "->" in the query before executing it
                query = (
                    modified_line.replace(ESCAPE_ARROW_STRING, "->")
                    + "\n"
                    + (cell if cell else "")
                )
                result_df = self._stylized(self._execute(query), style=STYLE_PANDAS)

        # Create a graph
        g = Network(
            notebook=True,
            directed=True,
            cdn_resources="in_line",
            height="500px",
            width="100%",
            bgcolor="#002B36",
            font_color="#93A1A1",
            neighborhood_highlight=True,
        )
        g_nx = nx.MultiDiGraph()
        for _, row in result_df.iterrows():
            for item in row:
                self.render_pd_item(g, g_nx, item)

        try:
            # Calculate PageRank
            pagerank_scores = nx.pagerank(g_nx)

            # Update node sizes based on PageRank scores
            for node_id, score in pagerank_scores.items():
                g.get_node(node_id)["size"] = (
                    10 + score * 130
                )  # Normalized size for visibility
        except Exception as e:
            print(
                f"[WARN]: failed to calculate PageRank, left graph node unsized. Reason:\n { e }"
            )

        g = self._draw_graph(g)

        return g

    @line_cell_magic
    @magic_arguments()
    @argument("line", default="", nargs="?", type=str, help="space name")
    def ng_draw_schema(self, line, cell=None, local_ns={}):
        try:
            from pyvis.network import Network
            from IPython.display import display, IFrame, HTML

            # import get_ipython
            from IPython import get_ipython

        except ImportError:
            raise ImportError("Please install pyvis to draw the graph schema")

        args = parse_argstring(self.ng_draw_schema, line)
        space = args.line if args.line else self.space
        if space is None:
            return "Please specify the space name or run `USE <space_name>` first."
        space = space.strip()

        tags_schema, edge_types_schema, relationship_samples = [], [], []
        for tag in self._execute("SHOW TAGS").column_values("Name"):
            tag_name = tag.cast_primitive()
            tag_schema = {"tag": tag_name, "properties": []}
            r = self._execute(f"DESCRIBE TAG `{tag_name}`")
            props, types, comments = (
                r.column_values("Field"),
                r.column_values("Type"),
                r.column_values("Comment"),
            )
            for i in range(r.row_size()):
                # back compatible with old version of nebula-python
                property_defination = (
                    (props[i].cast_primitive(), types[i].cast_primitive())
                    if comments[i].is_empty()
                    else (
                        props[i].cast_primitive(),
                        types[i].cast_primitive(),
                        comments[i].cast_primitive(),
                    )
                )
                tag_schema["properties"].append(property_defination)
            tags_schema.append(tag_schema)
        for edge_type in self._execute("SHOW EDGES").column_values("Name"):
            edge_type_name = edge_type.cast_primitive()
            edge_schema = {"edge": edge_type_name, "properties": []}
            r = self._execute(f"DESCRIBE EDGE `{edge_type_name}`")
            props, types, comments = (
                r.column_values("Field"),
                r.column_values("Type"),
                r.column_values("Comment"),
            )
            for i in range(r.row_size()):
                # back compatible with old version of nebula-python
                property_defination = (
                    (props[i].cast_primitive(), types[i].cast_primitive())
                    if comments[i].is_empty()
                    else (
                        props[i].cast_primitive(),
                        types[i].cast_primitive(),
                        comments[i].cast_primitive(),
                    )
                )
                edge_schema["properties"].append(property_defination)
            edge_types_schema.append(edge_schema)

            # build sample edge
            sample_edge = self._execute(
                rel_query_sample_edge.render(edge_type=edge_type_name)
            ).column_values("sample_edge")
            if len(sample_edge) == 0:
                continue
            src_id, dst_id = sample_edge[0].cast_primitive()
            r = self._execute(
                rel_query_edge_type.render(
                    edge_type=edge_type_name, src_id=src_id, dst_id=dst_id
                )
            )
            if (
                len(r.column_values("src_tag")) == 0
                or len(r.column_values("dst_tag")) == 0
            ):
                continue
            src_tag, dst_tag = (
                r.column_values("src_tag")[0].cast_primitive(),
                r.column_values("dst_tag")[0].cast_primitive(),
            )
            relationship_samples.append(
                {
                    "src_tag": src_tag,
                    "dst_tag": dst_tag,
                    "edge_type": edge_type_name,
                }
            )

        # In case there are edges not be sampled(no data yet), add them as different node with id edge_src and edge_dst:
        for edge_schema in edge_types_schema:
            edge_type = edge_schema["edge"]
            if edge_type not in [r["edge_type"] for r in relationship_samples]:
                src_dummy_tag = edge_type + "_src"
                dst_dummy_tag = edge_type + "_dst"
                relationship_samples.append(
                    {
                        "src_tag": src_dummy_tag,
                        "dst_tag": dst_dummy_tag,
                        "edge_type": edge_type,
                    }
                )
                if src_dummy_tag not in [x["tag"] for x in tags_schema]:
                    tags_schema.append({"tag": src_dummy_tag, "properties": []})
                if dst_dummy_tag not in [x["tag"] for x in tags_schema]:
                    tags_schema.append({"tag": dst_dummy_tag, "properties": []})

        # In case there are None in relationship_samples, add placeholder node:
        for edge_sample in relationship_samples:
            edge_type = edge_sample["edge_type"]
            if edge_sample["src_tag"] is None:
                src_dummy_tag = edge_type + "_src"
                edge_sample["src_tag"] = src_dummy_tag
                if src_dummy_tag not in [x["tag"] for x in tags_schema]:
                    tags_schema.append({"tag": src_dummy_tag, "properties": []})
            if edge_sample["dst_tag"] is None:
                dst_dummy_tag = edge_type + "_dst"
                edge_sample["dst_tag"] = dst_dummy_tag
                if dst_dummy_tag not in [x["tag"] for x in tags_schema]:
                    tags_schema.append({"tag": dst_dummy_tag, "properties": []})

        if not tags_schema and not edge_types_schema:
            fancy_print("[WARN] No tags or edges found in the space", color="pink")
            return

        # Create a graph of relationship_samples
        # The nodes are tags, with their properties schema as attributes
        # The edges are relationship_samples, with their properties schema as attributes

        g = Network(
            notebook=True,
            directed=True,
            cdn_resources="in_line",
            height="500px",
            width="100%",
            bgcolor="#002B36",
            font_color="#93A1A1",
            neighborhood_highlight=True,
        )
        g_nx = nx.MultiDiGraph()
        for tag_schema in tags_schema:
            tag_name = tag_schema["tag"]
            g.add_node(
                tag_name,
                label=tag_name,
                title=str(tag_schema),
                color=get_color(tag_name),
            )
            g_nx.add_node(tag_name, **tag_schema)

        for edge_schema in relationship_samples:
            src_tag, dst_tag, edge_type = (
                edge_schema["src_tag"],
                edge_schema["dst_tag"],
                edge_schema["edge_type"],
            )
            title = (
                "{\n  "
                + "\n  ".join([f"{k}: {v}" for k, v in edge_schema.items()])
                + "\n}"
            )
            g.add_edge(src_tag, dst_tag, label=edge_type, title=title)
            g_nx.add_edge(src_tag, dst_tag, **edge_schema)

        try:
            # Calculate PageRank
            pagerank_scores = nx.pagerank(g_nx)

            # Update node sizes based on PageRank scores
            for node_id, score in pagerank_scores.items():
                g.get_node(node_id)["size"] = (
                    10 + score * 130
                )  # Normalized size for visibility
        except Exception as e:
            print(
                f"[WARN]: failed to calculate PageRank, left graph node unsized. Reason:\n { e }"
            )

        g.repulsion(
            node_distance=90,
            central_gravity=0.2,
            spring_length=200,
            spring_strength=0.05,
            damping=0.09,
        )
        # g.show_buttons(filter_='physics')
        # return g.show("nebulagraph_draw.html", notebook=True)
        cell_num = get_ipython().execution_count
        schema_html_filename = f"nebulagraph_schema_cell_{cell_num}_{space}.html"
        g_html_string = g.generate_html(schema_html_filename)
        with open(schema_html_filename, "w", encoding="utf-8") as f:
            f.write(g_html_string)
        # detect if we are in colab or not
        try:
            if "google.colab" in str(get_ipython()):
                display(HTML(g_html_string))
            else:
                display(IFrame(src=schema_html_filename, width="100%", height="500px"))
        except Exception as e:
            print(f"[WARN]: failed to display the graph\n { e }")
            try:
                display(IFrame(src=schema_html_filename, width="100%", height="500px"))
            except Exception as e:
                print(f"[WARN]: failed to display the graph\n { e }")

        return g

    def render_pd_item(self, g, g_nx, item):
        # g is pyvis graph
        # g_nx is networkx graph

        if isinstance(item, Node):
            node_id = str(item.get_id().cast())
            tags = item.tags()  # list of strings
            tags_str = tags[0] if len(tags) == 1 else ",".join(tags)
            props_raw = dict()
            for tag in tags:
                props_raw.update(item.properties(tag))
            props = {
                k: str(v.cast()) if hasattr(v, "cast") else str(v)
                for k, v in props_raw.items()
            }
            # populating empty and null properties
            props = {
                k: v for k, v in props.items() if v not in ["__NULL__", "__EMPTY__"]
            }

            if "name" in props:
                label = props["name"]
            else:
                if is_human_readable(node_id):
                    label = f"tag: {tags_str},\nid: {node_id}"
                else:
                    label = f"tag: {tags_str},\nid: {node_id[:3]}..{node_id[-3:]}"
                for k in props:
                    if "name" in str(k).lower():
                        label = props[k]
                        break

            if "id" not in props:
                props["id"] = node_id
            title = "\n".join([f"{k}: {v}" for k, v in props.items()])

            g.add_node(node_id, label=label, title=title, color=get_color(node_id))

            # networkx
            if len(tags) > 1:
                props["__tags__"] = ",".join(tags)
            g_nx.add_node(node_id, **props)
        elif isinstance(item, Relationship):
            src_id = str(item.start_vertex_id().cast())
            dst_id = str(item.end_vertex_id().cast())
            edge_name = item.edge_name()
            props_raw = item.properties()
            rank = item.ranking()
            props = {
                k: str(v.cast()) if hasattr(v, "cast") else str(v)
                for k, v in props_raw.items()
            }
            if rank != 0:
                props.update({"rank": rank})
            # populating empty and null properties
            props = {
                k: v for k, v in props.items() if v not in ["__NULL__", "__EMPTY__"]
            }
            # ensure start and end vertex exist in graph
            if src_id not in g.node_ids:
                label = (
                    f"tag: {src_id[:3]}..{src_id[-3:]}"
                    if not is_human_readable(src_id)
                    else src_id
                )
                g.add_node(
                    src_id,
                    label=label,
                    title=src_id,
                    color=get_color(src_id),
                )
            if dst_id not in g.node_ids:
                label = (
                    f"tag: {dst_id[:3]}..{dst_id[-3:]}"
                    if not is_human_readable(dst_id)
                    else dst_id
                )
                g.add_node(
                    dst_id,
                    label=label,
                    title=dst_id,
                    color=get_color(dst_id),
                )
            props_str_list: List[str] = []
            for k in props:
                if len(props_str_list) >= 1:
                    break
                props_str_list.append(f"{truncate(k, 7)}: {truncate(str(props[k]), 8)}")
            props_str = "\n".join(props_str_list)

            label = f"{props_str}\n{edge_name}" if props else edge_name
            if props:
                title = (
                    "{\n  "
                    + "\n  ".join([f"{k}: {v}" for k, v in props.items()])
                    + "\n}"
                )
            else:
                title = edge_name
            g.add_edge(
                src_id,
                dst_id,
                label=label,
                title=title,
                weight=props.get("rank", 0),
            )
            # networkx
            props["edge_type"] = edge_name
            g_nx.add_edge(src_id, dst_id, **props)

        elif isinstance(item, PathWrapper):
            for node in item.nodes():
                self.render_pd_item(g, g_nx, node)
            for edge in item.relationships():
                self.render_pd_item(g, g_nx, edge)

        elif isinstance(item, list):
            for it in item:
                self.render_pd_item(g, g_nx, it)

    @line_cell_magic
    @magic_arguments()
    @argument(
        "--header",
        action="store_true",
        help="Specify if the CSV file contains a header row",
    )
    @argument("-n", "--space", type=str, help="Space name")
    @argument("-s", "--source", type=str, help="File path or URL to the CSV file")
    @argument("-t", "--tag", type=str, help="Tag name for vertices")
    @argument("--vid", type=int, help="Vertex ID column index")
    @argument("-e", "--edge", type=str, help="Edge type name")
    @argument("--src", type=int, help="Source vertex ID column index")
    @argument("--dst", type=int, help="Destination vertex ID column index")
    @argument("--rank", type=int, help="Rank column index", default=None)
    @argument(
        "-l",
        "--limit",
        type=int,
        help="Sample maximum n lines of the CSV file",
        default=-1,
    )
    @argument(
        "--props",
        type=str,
        help="Property mapping, comma-separated column indexes",
        default=None,
    )
    @argument(
        "-b", "--batch", type=int, help="Batch size for data loading", default=256
    )
    def ng_load(self, line, cell=None, local_ns={}):
        """
        Load data from CSV file into NebulaGraph as vertices or edges

        Examples:
        %ng_load --source actor.csv --tag player --vid 0 --props 1:name,2:age --space basketballplayer
        %ng_load --source follow_with_rank.csv --edge follow --src 0 --dst 1 --props 2:degree --rank 3 --space basketballplayer
        %ng_load --source follow.csv --edge follow --src 0 --dst 1 --props 2:degree --space basketballplayer

        #actor.csv
        "player999","Tom Hanks",30
        "player1000","Tom Cruise",40

        #follow_with_rank.csv
        "player999","player1000",50,1
        """
        if self.connection_pool is None:
            print(
                "Please connect to NebulaGraph first using %ngql magic before using ng_load"
                "\nExample: %ngql --address 127.0.0.1 --port 9669 --user root --password nebula"
            )
            return

        args = parse_argstring(self.ng_load, line)
        ng_load(
            self._execute, LoadDataArgsModel.model_validate(args, from_attributes=True)
        )
