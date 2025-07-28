from setuptools import setup, find_packages

setup(
    name='nova_can',
    version='0.1',
    packages=find_packages(where='src/python'),
    package_dir={'': 'src/python'},
    entry_points={
        'console_scripts': [
            'ncc = ncc.ncc:main',  # Adjust if your main function is elsewhere
        ],
    },
)