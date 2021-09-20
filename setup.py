from os import makedirs
from os.path import exists
from setuptools import setup

with open('./requirements.txt', 'r') as requirements:
    requirements = requirements.read().split('\n')

setup(
    name='autorebalance',
    install_requires=requirements
)
