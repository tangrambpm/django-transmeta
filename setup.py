# Copyright (c) 2023 Ernesto Revilla <ernesto.revilla@gmail.com>
# Copyright (c) 2016 by Mohi Beyki <mohibeyki@gmail.com>
# Copyright (c) 2010 by Yaco Sistemas SL
#
# This software is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

import os
from setuptools import setup, find_packages


def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

long_description = (
    read('README.rst')
    + '\n' +
    'Authors\n'
    '************\n'
    + '\n' +
    read('AUTHORS.rst')
    + '\n' +
    'Change history\n'
    '**************\n'
    + '\n' +
    read('CHANGES.rst')
    + '\n' +
    'Download\n'
    '********\n')

setup(
    name="django-transmeta",
    author="erny",
    version="0.9.0",
    author_email="ernesto.revilla@gmail.com",
    description="Transmeta is an application for translatable content in Django's models.",
    long_description=long_description,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
        'Programming Language :: Python :: 3',
        'Framework :: Django :: 3',
    ],
    license="LGPL 3",
    keywords="django,translation,internationalization,i18n,transmeta,models,translation models",
    url='https://github.com/tangrambpm/django-transmeta',
    packages=find_packages('.'),
    package_dir={'': '.'},
    zip_safe=False,
)
