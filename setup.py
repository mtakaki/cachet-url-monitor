#!/usr/bin/env python
from distutils.core import setup

setup(name='cachet-url-monitor',
      version='0.4',
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
          ]
     )
