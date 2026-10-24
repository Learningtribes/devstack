"""Setup for pdf XBlock."""

import os
from setuptools import setup


def package_data(pkg, root_list):
    """Generic function to find package_data for `pkg` under `root`."""
    data = []
    for root in root_list:
        for dirname, _, files in os.walk(os.path.join(pkg, root)):
            for fname in files:
                data.append(os.path.relpath(os.path.join(dirname, fname), pkg))

    return {pkg: data}


setup(
    name='xblock-pdf',
    version='1.0.2.post0',
    description='Course component (Open edX XBlock) that provides an easy way to embed a PDF',
    packages=[
        'pdf',
    ],
    install_requires=[
        'XBlock>=1.2.9',
        'django-crequest',
        'lxml',
        'web-fragments>=0.2.2',
    ],
    dependency_links=[
        'git+https://github.com/Learningtribes/xblock-utils.git@ec95e5e718c4144dc8a43d116a545f210d929667#egg=xblock-utils'
    ],
    entry_points={
        'xblock.v1': [
            'pdf = pdf.pdf:PdfBlock',
        ]
    },
    package_data=package_data('pdf', ['public', 'static', 'templates', 'translations']),
)
