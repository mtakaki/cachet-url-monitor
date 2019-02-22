FROM python:3.7.2-alpine
MAINTAINER Mitsuo Takaki <mitsuotakaki@gmail.com>

WORKDIR /usr/src/app

RUN python3.7 -m pip install --upgrade pip
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY cachet_url_monitor/*.py /usr/src/app/cachet_url_monitor/
COPY setup.py /usr/src/app/
RUN python3.7 setup.py install

COPY config.yml /usr/src/app/config/
VOLUME /usr/src/app/config/

CMD ["python3.7", "./cachet_url_monitor/scheduler.py", "config/config.yml"]
