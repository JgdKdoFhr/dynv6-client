FROM python:3.15-alpine@sha256:0f9552bb28711333da16915ec146f5e6bb44a7fdac9ced15dc17c2e0206346dd

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /usr/src/app

COPY requirements.txt .
RUN PIP_ROOT_USER_ACTION=ignore pip install --no-cache-dir --disable-pip-version-check --require-hashes -r requirements.txt

COPY client.py .

USER nobody
ENTRYPOINT ["python", "client.py"]
CMD ["--help"]
