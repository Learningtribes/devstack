"""Setup for External Content XBlock."""

from __future__ import absolute_import

import os

from setuptools import setup


def package_data(pkg, roots):
    """Generic function to find package_data.

    All of the files under each of the `roots` will be declared as package
    data for package `pkg`.

    """
    data = []
    for root in roots:
        for dirname, _, files in os.walk(os.path.join(pkg, root)):
            for fname in files:
                data.append(os.path.relpath(os.path.join(dirname, fname), pkg))

    return {pkg: data}


setup(
    name='externality-xblock',
    version='0.1',
    description='External Web Content XBlock',
    license='MPL',
    packages=[
        'externality',
    ],
    install_requires=[
        'XBlock>=1.2.9',
        'web-fragments>=0.2.2'
    ],
    entry_points={
        'xblock.v1': [
            'externality = externality:ExternalContentXBlock',
        ]
    },
    package_data=package_data("externality", ["static", "public", "templates"]),
)
