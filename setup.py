from setuptools import setup


def readme():
    with open('README.md') as f:
        contents = f.read()

    # replace relative picture paths with absolute paths to GitHub
    contents = contents.replace("](./", "](https://raw.githubusercontent.com/RobertoPrevato/rodi/master/")
    return contents


setup(name='rodi',
      version='1.0.0',
      description='Implementation of dependency injection for Python 3',
      long_description=readme(),
      long_description_content_type='text/markdown',
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 3',
          'Operating System :: OS Independent'
      ],
      url='https://github.com/RobertoPrevato/rodi',
      author='RobertoPrevato',
      author_email='roberto.prevato@gmail.com',
      keywords='dependency injection type hints typing convention',
      license='MIT',
      packages=['rodi'],
      install_requires=[],
      include_package_data=True,
      zip_safe=False)
