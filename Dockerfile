FROM jupyter/minimal-notebook:python-3.9.13

RUN pip install ipython-ngql && \
    pip install pyvis && \
    rm -rf /home/$NB_USER/.cache/pip

ENV JUPYTER_TOKEN=nebula

# docker buildx build --push --platform linux/arm64/v8,linux/amd64 --tag weygu/nebulagraph-jupyter:0.7.3 .
# docker buildx build --push --platform linux/arm64/v8,linux/amd64 --tag weygu/nebulagraph-jupyter:latest .
