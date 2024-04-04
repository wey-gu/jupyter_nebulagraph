## Load Data from CSV

It's supported to load data from a CSV file into NebulaGraph with the help of `ng_load_csv` magic.

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