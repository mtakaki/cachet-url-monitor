[![Stories in Ready](https://badge.waffle.io/mtakaki/cachet-url-monitor.png?label=ready&title=Ready)](https://waffle.io/mtakaki/cachet-url-monitor)
# Status
![Build Status](https://codeship.com/projects/5a246b70-f088-0133-9388-2640b49afa9e/status?branch=master)
[![Coverage Status](https://coveralls.io/repos/github/mtakaki/cachet-url-monitor/badge.svg?branch=master)](https://coveralls.io/github/mtakaki/cachet-url-monitor?branch=master)
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/7ef4123130ef4140b8ea7b94d460ba64)](https://www.codacy.com/app/mitsuotakaki/cachet-url-monitor?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=mtakaki/cachet-url-monitor&amp;utm_campaign=Badge_Grade)
[![Docker pulls](https://img.shields.io/docker/pulls/mtakaki/cachet-url-monitor.svg)](https://hub.docker.com/r/mtakaki/cachet-url-monitor/)
[![Docker stars](https://img.shields.io/docker/stars/mtakaki/cachet-url-monitor.svg)](https://hub.docker.com/r/mtakaki/cachet-url-monitor/)
![License](https://img.shields.io/github/license/mtakaki/cachet-url-monitor.svg)
[![Latest release](https://img.shields.io/pypi/v/cachet-url-monitor.svg)](https://pypi.python.org/pypi/cachet-url-monitor)

cachet-url-monitor
========================
Python plugin for [cachet](cachethq.io) that monitors an URL, verifying it's response status and latency. The frequency the URL is tested is configurable, along with the assertion applied to the request response.

This project is available at PyPI: [https://pypi.python.org/pypi/cachet-url-monitor](https://pypi.python.org/pypi/cachet-url-monitor)

## Configuration

```yaml
endpoint:
  url: http://www.google.com
  method: GET
  timeout: 1 # seconds
  expectation:
    - type: HTTP_STATUS
      status: 200
    - type: LATENCY
      threshold: 1
    - type: REGEX
      regex: ".*<body>.*"
  allowed_fails: 0
cachet:
  api_url: http://status.cachethq.io/api/v1
  token: my_token
  component_id: 1
  metric_id: 1
  action:
    - CREATE_INCIDENT
    - UPDATE_STATUS
  public_incidents: true
frequency: 30
```

- **endpoint**, the configuration about the URL that will be monitored.
    - **url**, the URL that is going to be monitored.
    - **method**, the HTTP method that will be used by the monitor.
    - **timeout**, how long we'll wait to consider the request failed. The unit of it is seconds.
    - **expectation**, the list of expectations set for the URL.
        - **HTTP_STATUS**, we will verify if the response status code matches what we expect.
        - **LATENCY**, we measure how long the request took to get a response and fail if it's above the threshold. The unit is in seconds.
        - **REGEX**, we verify if the response body matches the given regex.
    - **allowed_fails**, create incident/update component status only after specified amount of failed connection trials.
- **cachet**, this is the settings for our cachet server.
    - **api_url**, the cachet API endpoint.
    - **token**, the API token.
    - **component_id**, the id of the component we're monitoring. This will be used to update the status of the component.
    - **metric_id**, this will be used to store the latency of the API. If this is not set, it will be ignored.
    - **action**, the action to be done when one of the expectations fails. This is optional and if left blank, nothing will be done to the component.
        - **CREATE_INCIDENT**, we will create an incident when the expectation fails.
        - **UPDATE_STATUS**, updates the component status
    - **public_incidents**, boolean to decide if created incidents should be visible to everyone or only to logged in users. Important only if `CREATE_INCIDENT` or `UPDATE_STATUS` are set.
- **frequency**, how often we'll send a request to the given URL. The unit is in seconds.

## Setting up

The application should be installed using **virtualenv**, through the following command:

```
$ git clone https://github.com/mtakaki/cachet-url-monitor.git
$ virtualenv cachet-url-monitor
$ cd cachet-url-monitor
$ source bin/activate
$ pip install -r requirements.txt
```

To start the agent:

```
$ python cachet_url_monitor/scheduler.py config.yml
```

## Docker

You can run the agent in docker, so you won't need to worry about installing python, virtualenv, or any other dependency into your OS. The `Dockerfile` and `docker-compose.yml` files are already checked in and it's ready to be used.

To start the agent in a container using docker compose:

```
$ docker-compose build
$ docker-compose up
```

Or pulling directly from [dockerhub](https://hub.docker.com/r/mtakaki/cachet-url-monitor/). You will need to create your own custom `config.yml` file and run (it will pull latest):

```
$ docker pull mtakaki/cachet-url-monitor
$ docker run --rm -it -v "$PWD":/usr/src/app/config/ mtakaki/cachet-url-monitor
```

If you're going to use a file with a name other than `config.yml`, you will need to map the local file, like this:

```
$ docker run --rm -it -v "$PWD"/my_config.yml:/usr/src/app/config/config.yml:ro mtakaki/cachet-url-monitor
```
