from setuptools import setup


setup(
    name="edx-sga",
    version="0.28.0",
    packages=["edx_sga"],
    package_dir={"edx_sga": "."},
    include_package_data=True,
    entry_points={
        "xblock.v1": [
            "edx_sga = edx_sga.sga:StaffGradedAssignmentXBlock",
        ],
    },
)
