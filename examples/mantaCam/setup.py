#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-06-23
# @Filename: setup.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-06-24 23:45:53

# Setup file based on https://github.com/pybind/python_example

import os
import sys
import tempfile

import setuptools
from setuptools import Extension, find_packages, setup
from setuptools.command.build_ext import build_ext


__version__ = '0.1.0'


class get_pybind_include(object):
    """Helper class to determine the pybind11 include path.

    The purpose of this class is to postpone importing pybind11
    until it is actually installed, so that the ``get_include()``
    method can be invoked.

    """

    def __init__(self, user=False):
        self.user = user

    def __str__(self):
        import pybind11
        return pybind11.get_include(self.user)


ext_modules = [
    Extension(
        'mantacam/cmanta',
        ['mantacam/cmanta.cpp'],
        include_dirs=[
            # Path to pybind11 headers
            get_pybind_include(),
            get_pybind_include(user=True)
        ],
        libraries=['VimbaCPP', 'VimbaC'],
        language='c++'
    ),
]


# As of Python 3.6, CCompiler has a ``has_flag`` method.
# cf http://bugs.python.org/issue26689
def has_flag(compiler, flagname):
    """Return a boolean indicating whether a flag name is supported on
    the specified compiler.
    """

    with tempfile.NamedTemporaryFile('w', suffix='.cpp') as f:
        cwd = os.getcwd()
        f.write('int main (int argc, char **argv) { return 0; }')
        os.chdir(os.path.dirname(f.name))
        try:
            compiler.compile([f.name], extra_postargs=[flagname])
        except setuptools.distutils.errors.CompileError:
            os.chdir(cwd)
            return False

    os.chdir(cwd)
    return True


def cpp_flag(compiler):
    """Return the -std=c++[11/14] compiler flag.

    The c++14 is preferred over c++11 (when it is available).

    """

    if has_flag(compiler, '-std=c++14'):
        return '-std=c++14'
    elif has_flag(compiler, '-std=c++11'):
        return '-std=c++11'
    else:
        raise RuntimeError('Unsupported compiler -- at least C++11 support '
                           'is needed!')


class BuildExt(build_ext):
    """A custom build extension for adding compiler-specific options."""

    c_opts = {
        'msvc': ['/EHsc'],
        'unix': [],
    }

    if sys.platform == 'darwin':
        c_opts['unix'] += ['-stdlib=libc++', '-mmacosx-version-min=10.7']

    def build_extensions(self):
        ct = self.compiler.compiler_type
        opts = self.c_opts.get(ct, [])
        if ct == 'unix':
            opts.append('-DVERSION_INFO="%s"' % self.distribution.get_version())
            opts.append(cpp_flag(self.compiler))
            if has_flag(self.compiler, '-fvisibility=hidden'):
                opts.append('-fvisibility=hidden')
        elif ct == 'msvc':
            opts.append('/DVERSION_INFO=\\"%s\\"' % self.distribution.get_version())
        for ext in self.extensions:
            ext.extra_compile_args = opts
        build_ext.build_extensions(self)


with open('requirements.txt', 'r') as ff:
    install_requires = ff.read().splitlines()


setup(
    name='mantacam',
    version=__version__,
    author='José Sánchez-Gallego',
    author_email='gallegoj@uw.edu',
    url='https://github.com/sdss/baseCam',
    description='An example of baseCam implementation using a Manta camera',
    long_description='',
    ext_modules=ext_modules,
    install_requires=install_requires,
    packages=find_packages('./'),
    cmdclass={'build_ext': BuildExt},
    zip_safe=False,
)
