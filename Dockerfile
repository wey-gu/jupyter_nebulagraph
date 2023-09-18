FROM python:3.9 AS builder

COPY . /tmp/nebula-jupyter
WORKDIR /tmp/nebula-jupyter
RUN python setup.py bdist_wheel

FROM jupyter/minimal-notebook:python-3.9.13
COPY --from=builder /tmp/nebula-jupyter/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl pyvis && \
    rm -rf /home/$NB_USER/.cache/pip

ENV JUPYTER_TOKEN=nebula

# docker buildx build --push --platform linux/arm64/v8,linux/amd64 --tag weygu/nebulagraph-jupyter:0.7.3 .
# docker buildx build --push --platform linux/arm64/v8,linux/amd64 --tag weygu/nebulagraph-jupyter:latest .
