## `%ngql help`

Don't remember anything but one command:

```bash
%load_ext ngql
```

Then you can get help by:

```bash
%ngql help
```

All the magic commands and examples are there for you to copy and paste.

## `%ngql`

**Connect & oneliner query**

```python
%ngql --address 127.0.0.1 --port 9669 --user root --password nebula
%ngql USE demo_basketballplayer;
%ngql MATCH (v:player{name:"Tim Duncan"})-->(v2:player) RETURN v2.player.name AS Name;
```

See more from [magic_words/ngql](magic_words/ngql.md).

## `%%ngql`

**Multiple lines query**

```python
%%ngql
CREATE TAG player(name string, age int);
CREATE EDGE follow(degree int);
```

See more from [magic_words/ngql](magic_words/ngql.md).

## `%ngql_load`

**Load data from CSV**

`%ng_load --source <source> [--header] --space <space> [--tag <tag>] [--vid <vid>] [--edge <edge>] [--src <src>] [--dst <dst>] [--rank <rank>] [--props <props>] [-b <batch>]`

```python
# load CSV from a URL
%ng_load --source https://github.com/wey-gu/jupyter_nebulagraph/raw/main/examples/actor.csv --tag player --vid 0 --props 1:name,2:age --space demo_basketballplayer
# with rank column
%ng_load --source follow_with_rank.csv --edge follow --src 0 --dst 1 --props 2:degree --rank 3 --space basketballplayer
# without rank column
%ng_load --source follow.csv --edge follow --src 0 --dst 1 --props 2:degree --space basketballplayer
```

See more from [magic_words/ng_load](magic_words/ng_load.md).

## `%ngql_draw`

**Draw Last Query Result**

```python
# one query
%ngql GET SUBGRAPH 2 STEPS FROM "player101" YIELD VERTICES AS nodes, EDGES AS relationships;
%ng_draw

# another query
%ngql match p=(:player)-[]->() return p LIMIT 5
%ng_draw
```

See more from [magic_words/ng_draw](magic_words/ng_draw.md).

## `%ngql_draw_schema`

**Draw Graph Schema**

> Note: This call assumes there are data in the graph per each edge type.

```python
%ng_draw_schema
```

See more from [magic_words/ng_draw_schema](magic_words/ng_draw_schema.md).