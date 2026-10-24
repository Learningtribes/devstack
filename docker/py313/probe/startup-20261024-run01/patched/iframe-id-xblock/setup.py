"""Setup for iframe XBlock."""

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
    name='iframe-id-xblock',
    version='0.1',
    description='iframe with anonymous ID XBlock',
    packages=[
        'iframe',
    ],
    install_requires=[
        'XBlock>=1.2.9',
        'web-fragments>=0.2.2',
        'lxml',
    ],
    entry_points={
        'xblock.v1': [
            'iframe = iframe:IframeWithAnonymousIDXBlock',
        ]
    },
    package_data=package_data("iframe", ["static", "templates", "public"]),
)
