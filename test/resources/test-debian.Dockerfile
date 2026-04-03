# Test image for Debian

FROM python:3.11-slim

COPY requirements.txt /tmp/requirements.txt
RUN \
    groupadd -g 99999 req ; \
    useradd -u 99999 -g req -d /req req ; \
    pip install --no-cache-dir --root-user-action=ignore --disable-pip-version-check \
        -r /tmp/requirements.txt -U

USER req

WORKDIR /req
CMD ["/bin/bash"]
