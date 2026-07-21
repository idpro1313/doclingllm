# region MODULE_CONTRACT [DOMAIN(7): Testing; CONCEPT(7): EnvironmentCheck; TECH(7): importlib]
## @purpose Verify that gateway runtime dependencies are importable before running the test suite.
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import importlib


REQUIRED_PACKAGES = [
    "pydantic_settings",
    "yaml",
    "pytest",
]


def test_required_packages_importable():
    missing = []
    for package_name in REQUIRED_PACKAGES:
        try:
            importlib.import_module(package_name)
        except ImportError:
            missing.append(package_name)
    assert not missing, f"Missing packages: {missing}"
