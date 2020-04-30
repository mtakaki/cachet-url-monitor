# Status
[![CircleCI](https://circleci.com/gh/mtakaki/cachet-url-monitor/tree/master.svg?style=svg)](https://circleci.com/gh/mtakaki/cachet-url-monitor/tree/master)
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
endpoints:
  - name: Google
    url: http://www.google.com
    method: GET
    header:
      SOME-HEADER: SOME-VALUE
    timeout: 1 # seconds
    expectation:
      - type: HTTP_STATUS
        status_range: 200-205
      - type: LATENCY
        threshold: 1
      - type: REGEX
        regex: ".*<body>.*"
    allowed_fails: 0
    component_id: 1
    metric_id: 1
    action:
      - UPDATE_STATUS
    public_incidents: true
    latency_unit: ms
    frequency: 5
  - name: Amazon
    url: http://www.amazon.com
    method: GET
    header:
      SOME-HEADER: SOME-VALUE
    timeout: 1 # seconds
    expectation:
      - type: HTTP_STATUS
        status_range: 200-205
        incident: MAJOR
      - type: LATENCY
        threshold: 1
      - type: REGEX
        regex: ".*<body>.*"
        threshold: 10
    allowed_fails: 0
    component_id: 2
    action:
      - CREATE_INCIDENT
    public_incidents: true
    latency_unit: ms
    frequency: 5
cachet:
  api_url: http://status.cachethq.io/api/v1
  token: mytoken
webhooks:
  - url: "https://push.example.com/message?token=<apptoken>"
    params:
      title: "{title}"
      message: "{message}"
      priority: 5
messages:
  incident_outage: "{name} is unavailable"
  incident_operational: "{name} is operational"
  incident_performance: "{name} has degraded performance"
```

- **endpoints**, the configuration about the URL/Urls that will be monitored.
    - **name**, The name of the component. This is now mandatory (since 0.6.0) so we can distinguish the logs for each URL being monitored.
    - **url**, the URL that is going to be monitored. *mandatory*
    - **method**, the HTTP method that will be used by the monitor. *mandatory*
    - **header**, client header passed to the request. Remove if you do not want to pass a header.
    - **timeout**, how long we'll wait to consider the request failed. The unit of it is seconds. *mandatory*
    - **expectation**, the list of expectations set for the URL. *mandatory*
        - **HTTP_STATUS**, we will verify if the response status code falls into the expected range. Please keep in mind the range is inclusive on the first number and exclusive on the second number. If just one value is specified, it will default to only the given value, for example `200` will be converted to `200-201`. 
        - **LATENCY**, we measure how long the request took to get a response and fail if it's above the threshold. The unit is in seconds.
        - **REGEX**, we verify if the response body matches the given regex.
    - **allowed_fails**, create incident/update component status only after specified amount of failed connection trials.
    - **component_id**, the id of the component we're monitoring. This will be used to update the status of the component. *mandatory*
    - **metric_id**, this will be used to store the latency of the API. If this is not set, it will be ignored.
    - **action**, the action to be done when one of the expectations fails. This is optional and if left blank, nothing will be done to the component.
        - **CREATE_INCIDENT**, we will create an incident when the expectation fails.
        - **UPDATE_STATUS**, updates the component status.
        - **PUSH_METRICS**, uploads response latency metrics.
    - **public_incidents**, boolean to decide if created incidents should be visible to everyone or only to logged in users. Important only if `CREATE_INCIDENT` or `UPDATE_STATUS` are set.
    - **latency_unit**, the latency unit used when reporting the metrics. It will automatically convert to the specified unit. It's not mandatory and it will default to **seconds**. Available units: `ms`, `s`, `m`, `h`.
    - **frequency**, how often we'll send a request to the given URL. The unit is in seconds.
- **cachet**, this is the settings for our cachet server.
    - **api_url**, the cachet API endpoint. *mandatory*
    - **token**, the API token. *mandatory*
- **webhooks**, generic webhooks to be notified about incident updates
    - **url**, webhook URL, will be interpolated
    - **params**, POST parameters, will be interpolated
- **messages**, customize text for generated events, use any of **endpoint** parameter in interpolation
    - **incident_outage**, title of incident in case of outage
    - **incident_performace**, title of incident in case of performance issues
    - **incident_operational**, title of incident in case service is operational

Each `expectation` has their own default incident status. It can be overridden by setting the `incident` property to any of the following values:
- `PARTIAL`
- `MAJOR`
- `PERFORMANCE`

By choosing any of the aforementioned statuses, it will let you control the kind of incident it should be considered. These are the default incident status for each `expectation` type:

| Expectation | Incident status |
| ----------- | --------------- |
| HTTP_STATUS | PARTIAL |
| LATENCY | PERFORMANCE |
| REGEX | PARTIAL |

Following parameters are available in webhook interpolation

| Parameter | Description |
| --------- | ----------- |
| `{title}` | Event title, includes endpoint name and short status |
| `{message}` | Event message, same as sent to Cachet |

## Setting up

The application should be installed using **virtualenv**, through the following command:

```bash
$ git clone https://github.com/mtakaki/cachet-url-monitor.git
$ virtualenv cachet-url-monitor
$ cd cachet-url-monitor
$ source bin/activate
$ pip install -r requirements.txt
$ python3 setup.py install
```

To start the agent:

```bash
$ python3 cachet_url_monitor/scheduler.py config.yml
```

## Docker

You can run the agent in docker, so you won't need to worry about installing python, virtualenv, or any other dependency into your OS. The `Dockerfile` is already checked in and it's ready to be used.

You have two choices, checking this repo out and building the docker image or it can be pulled directly from [dockerhub](https://hub.docker.com/r/mtakaki/cachet-url-monitor/). You will need to create your own custom `config.yml` file and run (it will pull latest):

```bash
$ docker pull mtakaki/cachet-url-monitor
$ docker run --rm -it -v "$PWD":/usr/src/app/config/ mtakaki/cachet-url-monitor
```

If you're going to use a file with a name other than `config.yml`, you will need to map the local file, like this:

```bash
$ docker run --rm -it -v "$PWD"/my_config.yml:/usr/src/app/config/config.yml:ro mtakaki/cachet-url-monitor
```

## Generating configuration from existing CachetHQ instance (since 0.6.2)
 
In order to expedite the creation of your configuration file, you can use the client to automatically scrape the CachetHQ instance and spit out a YAML file. It can be used like this:
```bash
$ python cachet_url_monitor/client.py http://localhost/api/v1 my-token test.yml
``` 
Or from docker (you will end up with a `test.yml` in your `$PWD/tmp` folder):
```bash
$ docker run --rm -it -v $PWD/tmp:/home/tmp/ mtakaki/cachet-url-monitor python3.7 ./cachet_url_monitor/client.py http://localhost/api/v1 my-token /home/tmp/test.yml
```
The arguments are:
- **URL**, the CachetHQ API URL, so that means appending `/api/v1` to your hostname.
- **token**, the token that has access to your CachetHQ instance.
- **filename**, the file where it should write the configuration.

### Caveats
Because we can't predict what expectations will be needed, it will default to these behavior:
- Verify a [200-300[ HTTP status range.
- If status fail, make the incident major and public.
- Frequency of 30 seconds.
- `GET` request.
- Timeout of 1s.
- We'll read the `link` field from the components and use it as the URL. 

## Troubleshooting

### SSLERROR
If it's throwing the following exception:
```python
raise SSLError(e, request=request)
requests.exceptions.SSLError: HTTPSConnectionPool(host='redacted', port=443): Max retries exceeded with url: /api/v1/components/19 (Caused by SSLError(SSLError(1, u'[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed (_ssl.c:579)'),))
```

It can be resolved by seting the CA bundle environment variable `REQUESTS_CA_BUNDLE` pointing at your certificate file. It can either be set in your python environment, before running this tool, or in your docker container.
