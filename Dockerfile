FROM python:3.12.6-slim-bullseye

ENV PYTHONUNBUFFERED True

ENV APP_HOME /app

ENV PORT 8080

WORKDIR $APP_HOME

COPY . ./

RUN pip install --no-cache-dir -r requirements.txt

# https://cloud.google.com/run/docs/tips/python#optimize_gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 -k gevent main:app
