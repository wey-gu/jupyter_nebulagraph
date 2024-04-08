
[![for NebulaGraph](https://img.shields.io/badge/Toolchain-NebulaGraph-blue)](https://github.com/vesoft-inc/nebula) [![Docker Image](https://img.shields.io/docker/v/weygu/nebulagraph-jupyter?label=Image&logo=docker)](https://hub.docker.com/r/weygu/nebulagraph-jupyter) [![Docker Extension](https://img.shields.io/badge/Docker-Extension-blue?logo=docker)](https://hub.docker.com/extensions/weygu/nebulagraph-dd-ext) [![GitHub release (latest by date)](https://img.shields.io/github/v/release/wey-gu/jupyter_nebulagraph?label=Version)](https://github.com/wey-gu/jupyter_nebulagraph/releases)
[![pypi-version](https://img.shields.io/pypi/v/jupyter_nebulagraph)](https://pypi.org/project/jupyter_nebulagraph/)

## Google Colab

Experience it directly on Google Colab: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wey-gu/jupyter_nebulagraph/blob/main/docs/get_started.ipynb)

## Introduction

`jupyter_nebulagraph`, formerly `ipython-ngql`, is a Python package that simplifies the process of connecting to NebulaGraph from Jupyter Notebooks or iPython environments. It enhances the user experience by streamlining the creation, debugging, and sharing of Jupyter Notebooks. With `jupyter_nebulagraph`, users can effortlessly connect to NebulaGraph, load data, execute queries, visualize results, and fine-tune query outputs, thereby boosting collaborative efforts and productivity.

<video controls style="width: 80%;">
  <source src="https://github.com/wey-gu/jupyter_nebulagraph/assets/1651790/10135264-77b5-4d3c-b68f-c5810257feeb" type="video/mp4">
Your browser does not support the video tag.
</video>



## Get Started

For a more comprehensive guide on how to get started with `jupyter_nebulagraph`, please refer to the [Get Started Guide](/get_started_docs). This guide provides step-by-step instructions on installation, connecting to NebulaGraph, making queries, and visualizing query results, making it easier for new users to get up and running.

## Features

| Feature | Cheat Sheet | Example | Command Documentation |
| ------- | ----------- | --------- | ---------------------- |
| Connect | `%ngql --address 127.0.0.1 --port 9669 --user user --password password` | [Connect](https://jupyter-nebulagraph.readthedocs.io/en/latest/get_started/#connect-to-nebulagraph) | [`%ngql`](https://jupyter-nebulagraph.readthedocs.io/en/latest/magic_words/ngql/#connect-to-nebulagraph) |
| Load Data from CSV | `%ng_load --source actor.csv --tag player --vid 0 --props 1:name,2:age --space basketballplayer` | [Load Data](https://jupyter-nebulagraph.readthedocs.io/en/latest/get_started/#load-data-from-csv) | [`%ng_load`](https://jupyter-nebulagraph.readthedocs.io/en/latest/magic_words/ng_load/) |
| Query Execution | `%ngql MATCH p=(v:player{name:"Tim Duncan"})-->(v2:player) RETURN p;`| [Query Execution](https://jupyter-nebulagraph.readthedocs.io/en/latest/get_started/#query) | [`%ngql` or `%%ngql`(multi-line)](https://jupyter-nebulagraph.readthedocs.io/en/latest/magic_words/ngql/#make-queries) |
| Result Visualization | `%ng_draw` | [Draw Graph](https://jupyter-nebulagraph.readthedocs.io/en/latest/magic_words/ng_draw/) | [`%ng_draw`](https://jupyter-nebulagraph.readthedocs.io/en/latest/magic_words/ng_draw/) |
| Draw Schema | `%ng_draw_schema` | [Draw Schema](https://jupyter-nebulagraph.readthedocs.io/en/latest/magic_words/ng_draw_schema/) | [`%ng_draw_schema`](https://jupyter-nebulagraph.readthedocs.io/en/latest/magic_words/ng_draw_schema/) |
| Tweak Query Result | `df = _` to get last query result as `pd.dataframe` or [`ResultSet`](https://github.com/vesoft-inc/nebula-python/blob/master/nebula3/data/ResultSet.py) | [Tweak Result](https://jupyter-nebulagraph.readthedocs.io/en/latest/get_started/#result-handling) | [Configure `ngql_result_style`](https://jupyter-nebulagraph.readthedocs.io/en/latest/configurations/#configure-ngql_result_style) |

## Acknowledgments ♥️

- Inspiration for this project comes from [ipython-sql](https://github.com/catherinedevlin/ipython-sql), courtesy of [Catherine Devlin](https://catherinedevlin.blogspot.com/).
- Graph visualization features are enabled by [pyvis](https://github.com/WestHealth/pyvis), a project by [WestHealth](https://github.com/WestHealth).
- Generous sponsorship and support provided by [Vesoft Inc.](https://www.vesoft.com/) and the [NebulaGraph community](https://github.com/vesoft-inc/nebula).
