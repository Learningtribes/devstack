"""Setup for LBM Done XBlock."""

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
    name='lbmdone-xblock',
    version='2.0.2',
    description='Learning By Mooc Done XBlock',   # TODO: write a better description.
    license='UNKNOWN',          # TODO: choose a license: 'AGPL v3' and 'Apache 2.0' are popular.
    packages=[
        'lbmdonexblock',
    ],
    install_requires=[
        'XBlock>=1.2.9',
        'lxml',
        'web-fragments>=0.2.2',
    ],
    dependency_links=[
        'git+https://github.com/Learningtribes/xblock-utils.git@ec95e5e718c4144dc8a43d116a545f210d929667#egg=xblock-utils',
    ],
    entry_points={
        'xblock.v1': [
            'lbmdonexblock = lbmdonexblock:LbmDoneXBlock',
        ]
    },
    package_data=package_data("lbmdonexblock", ["static", "public"]),
)
