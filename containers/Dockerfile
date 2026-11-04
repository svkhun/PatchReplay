# Supply a reviewed digest: docker build --build-arg BASE_IMAGE=python@sha256:... .
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir -r /tmp/requirements.lock && rm /tmp/requirements.lock
USER 65534:65534
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/python"]
