import os
from setuptools import setup

import sabacan

BASEDIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASEDIR, 'README.rst'), 'r') as f:
    LONG_DESCRIPTION = f.read()

setup(
    name='sabacan',
    version=sabacan.__version__,
    description='Command Line Interface for various application servers',
    long_description=LONG_DESCRIPTION,
    url='https://github.com/amedama41/sabacan',
    author='amedama41',
    author_email='kamo.devel41@gmail.com',
    keywords=['plantuml', 'redpen'],
    packages=['sabacan'],
    entry_points={
        'console_scripts': ['sabacan = sabacan:main'],
    },
    python_requires='>=3.5',
    classifiers=[
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Topic :: Utilities',
    ]
)
