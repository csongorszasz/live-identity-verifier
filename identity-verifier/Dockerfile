FROM python:3.8

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY . /app

RUN apt-get update -y && \
    apt-get install build-essential cmake pkg-config -y

RUN pip install -e .

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]

EXPOSE 8000

CMD ["gunicorn", "identity_verifier.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "120"]
