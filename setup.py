from setuptools import setup, find_packages

setup(
    name="nova_can",
    version="0.1",
    packages=find_packages(where="src/python"),
    package_dir={"": "src/python"},
    entry_points={
        "console_scripts": [
            "ncc = ncc.ncc:main",
            "compose_report = nova_can.utils.compose_system:compose_report",
            "mqtt_can_handler = tooling.mqtt_handler.can_mqtt_handler:start_gateway_cli",
            "db_can_handler = tooling.db_handler.can_db_handler:start_gateway_cli",
            "http_openmct_handler = tooling.http_handler.http_handler:start_gateway_cli",
            "compile_JSON_system = tooling.openMCT_system_compiler.compile_system:compile_system_JSON_cli",
        ]
    },
)
