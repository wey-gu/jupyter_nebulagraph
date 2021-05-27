> Note, this is an pre-release version. Becuase the tabular return resut is not yet fully supported in some queries.
>
> Still you can use it with `%config IPythonNGQL.ngql_result_style="raw"`, after which line being executed, the result will be raw ResultSet.
>
> If you like to use it, please let me know, I may put more time into this project to make the tabular work.



`ipython-ngql` is a python package to extend the ability to connect Nebula Graph from your Jupyter Notebook or iPython. It's easier for data scientists to create, debug and share reusable and all-in-one Jupyter Notebooks with Nebula Graph interaction embedded.

`ipython-ngql`  is inspired by [ipython-sql](https://github.com/catherinedevlin/ipython-sql) created by [Catherine Devlin](https://catherinedevlin.blogspot.com/)

![get_started](https://github.com/wey-gu/ipython-ngql/blob/main/examples/get_started.png?raw=true)

## Get Started

### Installation

`ipython-ngql` could be installed either via pip or from this git repo itself.

> Install via pip

```bash
pip install ipython-ngql
```

> Install inside the repo

```bash
git clone git@github.com:wey-gu/ipython-ngql.git
cd ipython-ngql
python setup.py install
```

### Load it in Jupyter Notebook or iPython

```python
%load_ext ngql
```

### Connect to Nebula Graph

Arguments as below are needed to connect a Nebula Graph DB instance:

| Argument               | Description                              |
| ---------------------- | ---------------------------------------- |
| `--address` or `-addr` | IP address of the Nebula Graph Instance  |
| `--port` or `-P`       | Port number of the Nebula Graph Instance |
| `--user` or `-u`       | User name                                |
| `--password` or `-p`   | Password                                 |

Below is an exmple on connecting to `127.0.0.1:9669` with username: "user" and password: "password".

```python
%ngql --address 127.0.0.1 --port 9669 --user user --password password
```

### Make Queries

Now two kind of iPtython Magics are supported:

Option 1: The one line stype with `%ngql`:

```python
%ngql GO FROM "Tom" OVER owns_pokemon YIELD owns_pokemon._dst as pokemon_id;
```

Option 2: The multiple lines stype with `%%ngql `

```python
%%ngql
USE pokemon_club;
SHOW TAGS;
SHOW HOSTS;
```

> There will be other options in future, i.e. from a `.ngql` file.

### Query String with Variables

`ipython-ngql` supports taking variables from the local namespace, with the help of [Jinja2](https://jinja.palletsprojects.com/) template framework, it's supported to have queries like the below example.

The actual query string should be `GO FROM "Sue" OVER owns_pokemon ...`, and `"{{ trainer }}"` was renderred as `"Sue"` by consuming the local variable `trainer`:

```python
In [8]: trainer = "Sue"

In [9]: %%ngql
   ...: GO FROM "{{ trainer }}" OVER owns_pokemon YIELD owns_pokemon._dst as pokemon_id | GO FROM $-.pokemon_id OVER owns_pokemon REVERSELY YIELD owns_pokemon._dst AS Trainer_Name;
   ...:

Out[9]:
  Trainer_Name
0        Jerry
1          Sue
2          Tom
3          Wey
```

### Configure `ngql_result_style`

By default, `ipython-ngql` will use pandas dataframe as output style to enable more human readable output, while it's supported to use the raw thrift data format comes from the `nebula2-python` itself.

This can be done ad-hoc with below one line:

```python
%config IPythonNGQL.ngql_result_style="raw"
```

After above line being executed, the output will be like:

```python
ResultSet(ExecutionResponse(
    error_code=0,
    latency_in_us=2844,
    data=DataSet(
        column_names=[b'Trainer_Name'],
        rows=[Row(
            values=[Value(
                sVal=b'Tom')]),
        Row(
            values=[Value(
                sVal=b'Jerry')]),
        Row(
            values=[Value(
                sVal=b'Sue')]),
        Row(
            values=[Value(
                sVal=b'Tom')]),
        Row(
            values=[Value(
                sVal=b'Wey')])]),
    space_name=b'pokemon_club'))
```

The result are always stored in variable `_` in Jupyter Notebook, thus, to tweak the result, just refer a new var to it like:

```python
In [10]: %config IPythonNGQL.ngql_result_style="raw"

In [11]: %%ngql USE pokemon_club;
    ...: GO FROM "Tom" OVER owns_pokemon YIELD owns_pokemon._dst as pokemon_id
    ...: | GO FROM $-.pokemon_id OVER owns_pokemon REVERSELY YIELD owns_pokemon._dst AS Trainer_Name;
    ...:
    ...:
Out[11]:
ResultSet(ExecutionResponse(
    error_code=0,
    latency_in_us=3270,
    data=DataSet(
        column_names=[b'Trainer_Name'],
        rows=[Row(
            values=[Value(
                sVal=b'Tom')]),
        Row(
            values=[Value(
                sVal=b'Jerry')]),
        Row(
            values=[Value(
                sVal=b'Sue')]),
        Row(
            values=[Value(
                sVal=b'Tom')]),
        Row(
            values=[Value(
                sVal=b'Wey')])]),
    space_name=b'pokemon_club'))

In [12]: r = _

In [13]: r.column_values(key='Trainer_Name')[0]._value.value
Out[13]: b'Tom'
```

### Get Help

Don't remember anything or even relying on the cheatsheet here, oen takeaway for you: the help!

```python
In [7]: %ngql help


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
```



### Examples

#### Jupyter Notebook

Please refer here:https://github.com/wey-gu/ipython-ngql/blob/main/examples/get_started.ipynb

#### iPython

```python
venv ❯ ipython

In [1]: %load_ext ngql

In [2]: %ngql --address 127.0.0.1 --port 9669 --user user --password password
Connection Pool Created
Out[2]:
           Name
0  pokemon_club

In [3]: %ngql GO FROM "Tom" OVER owns_pokemon YIELD owns_pokemon._dst as pokemon_id | GO FROM $-.pokemon_id OVER owns_pokemon REVERSELY YIELD owns_pokemon._dst AS Trainer_Name
Out[3]:
  Trainer_Name
0          Tom
1        Jerry
2          Sue
3          Tom
4          Wey

In [4]: %%ngql
   ...: SHOW TAGS;
   ...: SHOW HOSTS;
   ...:
   ...:
Out[4]:
        Host    Port  Status  Leader count Leader distribution Partition distribution
0  storaged0  9779.0  ONLINE             0  No valid partition     No valid partition
1  storaged1  9779.0  ONLINE             1      pokemon_club:1         pokemon_club:1
2  storaged2  9779.0  ONLINE             0  No valid partition     No valid partition
3      Total     NaN    None             1      pokemon_club:1         pokemon_club:1

In [5]: trainer = "Sue"

In [6]: %%ngql
   ...: GO FROM "{{ trainer }}" OVER owns_pokemon YIELD owns_pokemon._dst as pokemon_id | GO FROM $-.pokemon_id OVER owns_pokemon REVERSELY YIELD owns_pokemon._dst AS Trainer_Name;
   ...:
Out[6]:
  Trainer_Name
0        Jerry
1          Sue
2          Tom
3          Wey

In [7]: %ngql help


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

In [8]: trainer = "Sue"

In [9]: %%ngql
   ...: GO FROM "{{ trainer }}" OVER owns_pokemon YIELD owns_pokemon._dst as pokemon_id | GO FROM $-.pokemon_id OVER owns_pokemon REVERSELY YIELD owns_pokemon._dst AS Trainer_Name;
   ...:
   ...:
Out[9]:
  Trainer_Name
0        Jerry
1          Sue
2          Tom
3          Wey

In [10]: %config IPythonNGQL.ngql_result_style="raw"

In [11]: %%ngql USE pokemon_club;
    ...: GO FROM "Tom" OVER owns_pokemon YIELD owns_pokemon._dst as pokemon_id
    ...: | GO FROM $-.pokemon_id OVER owns_pokemon REVERSELY YIELD owns_pokemon._dst AS Trainer_Name;
    ...:
    ...:
Out[11]:
ResultSet(ExecutionResponse(
    error_code=0,
    latency_in_us=3270,
    data=DataSet(
        column_names=[b'Trainer_Name'],
        rows=[Row(
            values=[Value(
                sVal=b'Tom')]),
        Row(
            values=[Value(
                sVal=b'Jerry')]),
        Row(
            values=[Value(
                sVal=b'Sue')]),
        Row(
            values=[Value(
                sVal=b'Tom')]),
        Row(
            values=[Value(
                sVal=b'Wey')])]),
    space_name=b'pokemon_club'))

In [12]: r = _

In [13]: r.column_values(key='Trainer_Name')[0]._value.value
Out[13]: b'Tom'
```

