# -*- coding: utf-8 -*-

from setuptools import setup, find_packages


with open('README.rst') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='transport-analyst',
    version='0.1.0',
    description='A series of tools for transport planners.',
    long_description=readme,
    author='Saeid ADli',
    author_email='saeid.adli@gmail.com',
    license=license,
    packages=find_packages(exclude=('tests', 'docs'))
)

