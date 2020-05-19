#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name="cachet-url-monitor",
    version="0.6.10",
    description="Cachet URL monitor plugin",
    author="Mitsuo Takaki",
    author_email="mitsuotakaki@gmail.com",
    url="https://github.com/mtakaki/cachet-url-monitor",
    packages=find_packages(),
    license="MIT",
    requires=["requests", "PyYAML", "Click", "boto3"],
    setup_requires=["pytest-runner"],
    tests_require=["pytest", "requests-mock"],
)
