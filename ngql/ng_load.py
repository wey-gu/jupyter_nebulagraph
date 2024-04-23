import requests
import pandas as pd
from io import StringIO
from typing import Callable

from nebula3.data.ResultSet import ResultSet
from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config as NebulaConfig

from ngql.types import LoadDataArgsModel

try:
    import IPython

    if IPython.get_ipython() is not None:
        from tqdm.notebook import tqdm
    else:
        from tqdm import tqdm
except ImportError:
    from tqdm import tqdm


def ng_load(execute_fn: Callable[[str], ResultSet], args: LoadDataArgsModel):
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

    # Check if space is specified
    space = args.space
    execute_fn(f"USE `{space}`")
    # Inspect space to get Vid Type
    r = execute_fn(f"DESC SPACE `{space}`")
    try:
        if not len(r.column_values("Vid Type")) == 1:
            raise ValueError("Space may not exist")
        vid_type = str(r.column_values("Vid Type")[0])
    except Exception as e:
        raise ValueError(f"Failed to get Vid Type from space '{space}', error: {e}")

    vid_length = 0
    if vid_type.find("FIXED_STRING") != -1:
        vid_length = int(vid_type.split("(")[1].split(")")[0])
    is_vid_int = vid_length == 0

    # Validate required arguments
    if not args.tag and not args.edge:
        raise ValueError(
            "Missing required argument: --tag tag_name for vertex loading or --edge edge_type for edge loading"
        )

    # If with header
    with_header = args.header

    limit = args.limit

    # Function to safely load CSV with limit
    def safe_load_csv(source, header_option, limit=None):
        temp_df = pd.read_csv(source, header=header_option)
        if isinstance(limit, int) and limit > 0:
            return temp_df.head(limit)
        return temp_df

    # Load CSV from file or URL
    if args.source.startswith("http://") or args.source.startswith("https://"):
        response = requests.get(args.source)
        csv_string = response.content.decode("utf-8")
        df = safe_load_csv(
            StringIO(csv_string),
            header_option=0 if with_header else None,
            limit=limit,
        )
    else:
        df = safe_load_csv(
            args.source, header_option=0 if with_header else None, limit=limit
        )

    # Build schema type map for tag or edge type
    prop_schema_map = {}
    DESC_TYPE = "TAG" if args.tag else "EDGE"
    DESC_TARGET = args.tag if args.tag else args.edge
    r = execute_fn(f"DESCRIBE {DESC_TYPE} `{DESC_TARGET}`")
    props, types, nullable = (
        r.column_values("Field"),
        r.column_values("Type"),
        r.column_values("Null"),
    )
    for i in range(r.row_size()):
        # back compatible with old version of nebula-python
        prop_schema_map[props[i].cast()] = {
            "type": types[i].cast(),
            "nullable": nullable[i].cast() == "YES",
        }

    # Process properties mapping
    props_mapping = (
        {int(k): v for k, v in (prop.split(":") for prop in args.props.split(","))}
        if args.props
        else {}
    )
    # Values of props_mapping are property names they should be strings
    # Keys of props_mapping are column indexes they should be integers
    for k, v in props_mapping.items():
        if not isinstance(k, int):
            raise ValueError(
                f"ERROR during prop mapping validation: Key '{k}' in property mapping is not an integer"
            )
        if not isinstance(v, str):
            raise ValueError(
                f"ERROR during prop mapping validation: Value '{v}' in property mapping is not a string"
            )
        if k >= len(df.columns) or k < 0:
            raise ValueError(
                f"ERROR during prop mapping validation: Key '{k}' in property mapping is out of range: 0-{len(df.columns)-1}"
            )

    with_props = True if props_mapping else False

    # Validate props_mapping against schema
    matched = True
    for i, prop in props_mapping.items():
        if prop not in prop_schema_map:
            print(
                f"Error: Property '{prop}' not found in schema for {DESC_TYPE} '{args.tag}'"
            )
            matched = False
    for prop in prop_schema_map:
        # For not nullable properties, check if they are in props_mapping
        if not prop_schema_map[prop]["nullable"] and prop not in props_mapping.values():
            print(
                f"Error: Property '{prop}' is not nullable and not found in property mapping"
            )
            matched = False

    if not matched:
        raise ValueError("Error: Property mapping does not match schema")

    if args.rank is not None:
        with_rank = True
    else:
        with_rank = False

    # Prepare data for loading
    if args.tag and not args.edge:
        if args.vid is None:
            raise ValueError("Missing required argument: --vid for vertex ID")
        # Process properties mapping
        vertex_data_columns = ["___vid"] + [
            props_mapping[i] for i in sorted(props_mapping)
        ]
        vertex_data_indices = [args.vid] + sorted(props_mapping.keys())
        vertex_data = df.iloc[:, vertex_data_indices]
        vertex_data.columns = vertex_data_columns
        # Here you would load vertex_data into NebulaGraph under the specified tag and space
        print(
            f"Parsed {len(vertex_data)} vertices '{space}' for tag '{args.tag}' in memory"
        )
    elif args.edge and not args.tag:
        if args.src is None or args.dst is None:
            raise ValueError(
                "Missing required arguments: --src and/or --dst for edge source and destination IDs"
            )
        # Process properties mapping
        edge_data_columns = ["___src", "___dst"] + [
            props_mapping[key] for key in sorted(props_mapping)
        ]
        edge_data_indices = [args.src, args.dst] + sorted(props_mapping.keys())
        if with_rank:
            edge_data_columns.append("___rank")
            edge_data_indices.append(args.rank)
        edge_data = df.iloc[:, edge_data_indices]
        edge_data.columns = edge_data_columns
        # Here you would load edge_data into NebulaGraph under the specified edge type and space
        print(
            f"Parsed {len(edge_data)} edges '{space}' for edge type '{args.edge}' in memory"
        )
    else:
        raise ValueError(
            "Specify either --tag for vertex loading or --edge for edge loading, not both"
        )

    # Load data into NebulaGraph
    batch_size = args.batch

    QUOTE_VID = "" if is_vid_int else '"'
    QUOTE = '"'

    if args.tag:
        # Load vertex_data into NebulaGraph under the specified tag and space
        # Now prepare INSERT query for vertices in batches
        # Example of QUERY: INSERT VERTEX t2 (name, age) VALUES "13":("n3", 12), "14":("n4", 8);

        for i in tqdm(range(0, len(vertex_data), batch_size), desc="Loading Vertices"):
            batch = vertex_data.iloc[i : i + batch_size]
            prop_columns = [col for col in vertex_data.columns if col != "___vid"]
            if len(vertex_data.columns) == 1:
                query = f"INSERT VERTEX `{args.tag}` () VALUES "
            else:
                query = f"INSERT VERTEX `{args.tag}` (`{'`, `'.join(prop_columns)}`) VALUES "
            for index, row in batch.iterrows():
                vid_str = f'{QUOTE_VID}{row["___vid"]}{QUOTE_VID}'
                prop_str = ""
                if with_props:
                    for prop_name in prop_columns:
                        prop_value = row[prop_name]
                        if pd.isnull(prop_value):
                            if not prop_schema_map[prop_name]["nullable"]:
                                raise ValueError(
                                    f"Error: Property '{prop_name}' is not nullable but received NULL value, "
                                    f"data: {row}, column: {prop_name}"
                                )
                            prop_str += "NULL, "
                        elif prop_schema_map[prop_name]["type"] == "string":
                            prop_str += f"{QUOTE}{prop_value}{QUOTE}, "
                        elif prop_schema_map[prop_name]["type"] == "date":
                            prop_str += f"date({QUOTE}{prop_value}{QUOTE}), "
                        elif prop_schema_map[prop_name]["type"] == "datetime":
                            prop_str += f"datetime({QUOTE}{prop_value}{QUOTE}), "
                        elif prop_schema_map[prop_name]["type"] == "time":
                            prop_str += f"time({QUOTE}{prop_value}{QUOTE}), "
                        elif prop_schema_map[prop_name]["type"] == "timestamp":
                            prop_str += f"timestamp({QUOTE}{prop_value}{QUOTE}), "
                        else:
                            prop_str += f"{prop_value}, "
                    prop_str = prop_str[:-2]
                query += f"{vid_str}:({prop_str}), "
            query = query[:-2] + ";"
            try:
                execute_fn(query)
            except Exception as e:
                raise Exception(f"INSERT Failed on row {i + index}, data: {row}") from e
            tqdm.write(f"Loaded {i + len(batch)} of {len(vertex_data)} vertices")

        print(
            f"Successfully loaded {len(vertex_data)} vertices '{space}' for tag '{args.tag}'"
        )
    elif args.edge:
        # Load edge_data into NebulaGraph under the specified edge type and space
        # Now prepare INSERT query for edges in batches
        # Example of QUERY:
        # with_rank INSERT EDGE e1 (name, age) VALUES "13" -> "14"@1:("n3", 12), "14" -> "15"@132:("n4", 8);
        # without_rank INSERT EDGE e1 (name, age) VALUES "13" -> "14":("n3", 12), "14" -> "15":("n4", 8);

        for i in tqdm(range(0, len(edge_data), batch_size), desc="Loading Edges"):
            batch = edge_data.iloc[i : i + batch_size]
            prop_columns = [
                col
                for col in edge_data.columns
                if col not in ["___src", "___dst", "___rank"]
            ]
            if len(prop_columns) == 0:
                query = f"INSERT EDGE `{args.edge}` () VALUES "
            else:
                query = (
                    f"INSERT EDGE `{args.edge}` (`{'`, `'.join(prop_columns)}`) VALUES "
                )
            for index, row in batch.iterrows():
                src_str = f'{QUOTE_VID}{row["___src"]}{QUOTE_VID}'
                dst_str = f'{QUOTE_VID}{row["___dst"]}{QUOTE_VID}'
                prop_str = ""
                if with_props:
                    for prop_name in prop_columns:
                        prop_value = row[prop_name]
                        if pd.isnull(prop_value):
                            if not prop_schema_map[prop_name]["nullable"]:
                                raise ValueError(
                                    f"Error: Property '{prop_name}' is not nullable but received NULL value, "
                                    f"data: {row}, column: {prop_name}"
                                )
                            prop_str += "NULL, "
                        elif prop_schema_map[prop_name]["type"] == "string":
                            prop_str += f"{QUOTE}{prop_value}{QUOTE}, "
                        elif prop_schema_map[prop_name]["type"] == "date":
                            prop_str += f"date({QUOTE}{prop_value}{QUOTE}), "
                        elif prop_schema_map[prop_name]["type"] == "datetime":
                            prop_str += f"datetime({QUOTE}{prop_value}{QUOTE}), "
                        elif prop_schema_map[prop_name]["type"] == "time":
                            prop_str += f"time({QUOTE}{prop_value}{QUOTE}), "
                        elif prop_schema_map[prop_name]["type"] == "timestamp":
                            prop_str += f"timestamp({QUOTE}{prop_value}{QUOTE}), "
                        else:
                            prop_str += f"{prop_value}, "
                    prop_str = prop_str[:-2]
                if with_rank:
                    rank_str = f"@{row['___rank']}"
                else:
                    rank_str = ""
                query += f"{src_str} -> {dst_str}{rank_str}:({prop_str}), "
            query = query[:-2] + ";"
            try:
                execute_fn(query)
            except Exception as e:
                raise Exception(f"INSERT Failed on row {i + index}, data: {row}") from e
            tqdm.write(f"Loaded {i + len(batch)} of {len(edge_data)} edges")
        print(
            f"Successfully loaded {len(edge_data)} edges '{space}' for edge type '{args.edge}'"
        )


if __name__ == "__main__":
    conn_pool = ConnectionPool()
    conn_pool.init(addresses=[("127.0.0.1", 9669)], configs=NebulaConfig())

    def args_load(line: str):
        kv_str = line.strip().split("--")
        kv = {
            k.strip(): v.strip()
            for k, v in [item.strip().split(" ") for item in kv_str if item]
        }
        if "header" in kv:
            kv["header"] = kv["header"] == "True" or kv["header"] == "true"
        for int_string in ["batch", "limit", "vid", "src", "dst", "rank"]:
            if int_string in kv:
                kv[int_string] = int(kv[int_string])
        return LoadDataArgsModel.model_validate(kv)

    test = """
# https://graph-hub.siwei.io/en/latest/datasets/shareholding
%ng_load  --source https://github.com/wey-gu/awesome-graph-dataset/raw/main/datasets/shareholding/tiny/person.csv --tag person --vid 0 --props 1:name --space shareholding
%ng_load  --source https://github.com/wey-gu/awesome-graph-dataset/raw/main/datasets/shareholding/tiny/corp.csv --tag corp --vid 0 --props 1:name --space shareholding
%ng_load  --source https://github.com/wey-gu/awesome-graph-dataset/raw/main/datasets/shareholding/tiny/person_corp_role.csv --edge role_as --src 0 --dst 1 --props 2:role  --space shareholding
%ng_load  --source https://github.com/wey-gu/awesome-graph-dataset/raw/main/datasets/shareholding/tiny/corp_rel.csv --edge is_branch_of --src 0 --dst 1   --space shareholding
%ng_load  --source https://github.com/wey-gu/awesome-graph-dataset/raw/main/datasets/shareholding/tiny/corp_share.csv --edge hold_share --src 0 --dst 1 --props 2:share  --space shareholding
%ng_load  --source https://github.com/wey-gu/awesome-graph-dataset/raw/main/datasets/shareholding/tiny/person_corp_share.csv --edge hold_share --src 0 --dst 1 --props 2:share  --space shareholding
%ng_load  --source https://github.com/wey-gu/awesome-graph-dataset/raw/main/datasets/shareholding/tiny/person_rel.csv --edge reletive_with --src 0 --dst 1 --props 2:degree  --space shareholding
"""
    execute_fn = conn_pool.get_session("root", "nebula").execute
    for line in test.split("\n"):
        if line.startswith("%ng_load"):
            args = args_load(line[9:])
            ng_load(execute_fn, args)
