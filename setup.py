from setuptools import setup, find_packages

setup(
    name='nova_can',
    version='0.1',
    packages=find_packages(where='src/python') + find_packages(where='tooling'),
    package_dir={
        '': 'src/python',
        'ncc': 'tooling/ncc',
        'mqtt_handler': 'tooling/mqtt_handler',  # maps tooling/mqtt_handler into nova_can.mqtt_handler
    },
    entry_points={
        'console_scripts': [
            'ncc = ncc.ncc:main',
            'compose_report = nova_can.utils.compose_system:compose_report'
        ]
    }
)
