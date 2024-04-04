## Load Data from CSV

It's supported to load data from a CSV file into NebulaGraph with the help of `ng_load_csv` magic.

### Examples

For example, to load data from a CSV file `actor.csv` into a space `basketballplayer` with tag `player` and vid in column `0`, and props in column `1` and `2`:

```csv
"player999","Tom Hanks",30
"player1000","Tom Cruise",40
"player1001","Jimmy X",33
```

Just run the below line:

```python
%ng_load --source actor.csv --tag player --vid 0 --props 1:name,2:age --space basketballplayer
```

Some other examples:

```python
# load CSV from a URL
%ng_load --source https://github.com/wey-gu/jupyter_nebulagraph/raw/main/examples/actor.csv --tag player --vid 0 --props 1:name,2:age --space demo_basketballplayer
# with rank column
%ng_load --source follow_with_rank.csv --edge follow --src 0 --dst 1 --props 2:degree --rank 3 --space basketballplayer
# without rank column
%ng_load --source follow.csv --edge follow --src 0 --dst 1 --props 2:degree --space basketballplayer
```

### Usage

```
%ng_load --source <source> [--header] --space <space> [--tag <tag>] [--vid <vid>] [--edge <edge>] [--src <src>] [--dst <dst>] [--rank <rank>] [--props <props>] [-b <batch>]
```

### Arguments

| Argument | Requirement | Description |
|----------|-------------|-------------|
| `--header` | Optional | Indicates if the CSV file contains a header row. If this flag is set, the first row of the CSV will be treated as column headers. |
| `-n`, `--space` | Required | Specifies the name of the NebulaGraph space where the data will be loaded. |
| `-s`, `--source` | Required | The file path or URL to the CSV file. Supports both local paths and remote URLs. |
| `-t`, `--tag` | Optional | The tag name for vertices. Required if loading vertex data. |
| `--vid` | Optional | The column index for the vertex ID. Required if loading vertex data. |
| `-e`, `--edge` | Optional | The edge type name. Required if loading edge data. |
| `--src` | Optional | The column index for the source vertex ID when loading edges. |
| `--dst` | Optional | The column index for the destination vertex ID when loading edges. |
| `--rank` | Optional | The column index for the rank value of edges. Default is None. |
| `--props` | Optional | Comma-separated column indexes for mapping to properties. The format for mapping is column_index:property_name. |
| `-b`, `--batch` | Optional | Batch size for data loading. Default is 256. |
