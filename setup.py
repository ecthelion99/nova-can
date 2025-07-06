from setuptools import setup, find_packages

setup(
    name='nova_can',
    version='0.1',
    packages=find_packages(where='src/python'),
    package_dir={'': 'src/python'},
)