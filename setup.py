#!/usr/bin/env python
#from distutils.core import setup
from setuptools import setup, find_packages

setup(name='cachet-url-monitor',
      version='0.5.1',
      description='Cachet URL monitor plugin',
      author='Mitsuo Takaki',
      author_email='mitsuotakaki@gmail.com',
      url='https://github.com/mtakaki/cachet-url-monitor',
      packages=find_packages(),
      license='MIT',
      install_requires=[
          'PyYAML==5.1.2',
          'requests==2.22.0',
          'schedule==0.6.0'
      ],
      setup_requires=["pytest-runner"],
      tests_require=[
          "pytest",
          "codacy-coverage",
          "mock",
          "pytest-cov",
          "coverage"
          ]
      )
