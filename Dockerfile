FROM python:3.15-alpine@sha256:0aa144e9ec2ae8fd80dfd94070ef3e432a0df17b6e5e0091dc05323974ce9913

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /usr/src/app

COPY requirements.txt .
RUN PIP_ROOT_USER_ACTION=ignore pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY client.py .

USER nobody
ENTRYPOINT ["python", "client.py"]
CMD ["--help"]
