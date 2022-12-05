from mypyc.build import mypycify
from setuptools import setup


def readme():
    with open("README.md") as f:
        return f.read()


setup(
    name="rodi",
    version="1.1.4",
    description="Implementation of dependency injection for Python 3",
    long_description=readme(),
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    url="https://github.com/Neoteroi/rodi",
    author="RobertoPrevato",
    author_email="roberto.prevato@gmail.com",
    keywords="dependency injection type hints typing convention",
    license="MIT",
    packages=["rodi"],
    ext_modules=mypycify(["rodi/__init__.py"]),  # type: ignore
    install_requires=[],
    include_package_data=True,
    zip_safe=False,
)
