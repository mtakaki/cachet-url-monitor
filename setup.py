#!/usr/bin/env python
#from distutils.core import setup
from setuptools import setup

setup(name='cachet-url-monitor',
      version='1.4',
      description='Cachet URL monitor plugin',
      author='Mitsuo Takaki',
      author_email='mitsuotakaki@gmail.com',
      url='https://github.com/mtakaki/cachet-url-monitor',
      packages=['cachet_url_monitor'],
      license='MIT',
      requires=[
          'requests',
          'yaml',
          'schedule',
      ],
      setup_requires=["pytest-runner"],
      tests_require=["pytest"]
      )
