from setuptools import setup, find_packages

setup(
    name="imran_cloud_erp_auth",
    version="0.1.2",  # increase version
    packages=find_packages(),
    install_requires=["django"],
    author="Imran Murshad",
    description="Reusable Django registration module",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
)