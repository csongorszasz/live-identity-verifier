FROM python:3.8

WORKDIR /app

COPY . /app

RUN pip install -e .

EXPOSE 8080

CMD ["gunicorn", "-k", "aiohttp.GunicornWebWorker", "-b", "0.0.0.0:8080", "server:app"]
