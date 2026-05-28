#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

def read_requirements(filename):
    with open(filename, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


PACKAGE_EXCLUDES = [
    "config",
    "dep_files",
    "incoming_path",
    "notebooks",
    "output_path",
    "pipeline_design",
    "wavebuoy/sofar",
    "netcdf"
]

PACKAGE_INCLUDES = [
    "nrt*",
]

PACKAGE_DATA = {
    "nrt.config": ["*.csv"]
}


setup(
    name='ecm-moorings',
    version='0.1.0',
    description='Toolboxes for near real-time and delayed-mode wave buoy data processing',
    author='Thiago Caminha',
    author_email='thiago.caminha@uwa.edu.au',
    url='',
    install_requires=read_requirements('requirements.txt'),
    packages=find_packages(include=PACKAGE_INCLUDES, exclude=PACKAGE_EXCLUDES),
    include_package_data=True,
    package_data=PACKAGE_DATA,
    zip_safe=False,
    python_requires='>3.8'
)
