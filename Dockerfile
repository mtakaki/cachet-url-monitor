FROM python:2.7-alpine
MAINTAINER Mitsuo Takaki <mitsuotakaki@gmail.com>

WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt

COPY cachet_url_monitor/* /usr/src/app/cachet_url_monitor/

COPY config.yml /usr/src/app/config/
VOLUME /usr/src/app/config/

CMD ["python", "cachet_url_monitor/scheduler.py", "config/config.yml"]
