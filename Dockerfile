FROM python:2-onbuild
MAINTAINER Mitsuo Takaki <mitsuotakaki@gmail.com>

VOLUME /usr/src/app/

ENTRYPOINT ["python", "cachet_url_monitor/scheduler.py", "config.yml"]
