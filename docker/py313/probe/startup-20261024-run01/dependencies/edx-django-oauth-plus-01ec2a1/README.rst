django-oauth-plus
=================

.. image:: https://travis-ci.org/edx/django-oauth-plus.svg?branch=master
    :target: https://travis-ci.org/edx/django-oauth-plus

This is an edX-customized fork of *django-oauth-plus*. It is intended to be a short-term fork as we are planning on
replacing this authentication backend soon.

`Documentation <https://bitbucket.org/david/django-oauth-plus/wiki/Home>`_

Testing
=======

Tests are best run through `tox`, which will test against several versions of Python and Django. Simply
`pip install tox` then run `tox` to test all environments, or test one environment by using `tox -e py2.7-django1.8`.

Release Notes
=============
2.2.9.edx-1
-----------

- Initial fork of version 2.2.9 + unreleased changes for Django 1.10 compatibility
