from setuptools import setup, find_packages

requires = [
    'clld',
    'fabric',
    'fabtools==0.19',
    'Jinja2',
    'path.py',
    'pathlib',
    'pytz',
    ]

setup(name='clldfabric',
      version='0.0',
      description='clldfabric',
      long_description='',
      classifiers=[
        "Programming Language :: Python",
        ],
      author='',
      author_email='',
      url='',
      keywords='fabric',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=requires,
      test_suite="clldfabric",
      )
