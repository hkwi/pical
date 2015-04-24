try:
	from setuptools import setup
except:
	from distutils.core import setup

setup(name="pical",
	version="0.3",
	author="Hiroaki KAWAI",
	author_email="hiroaki.kawai+pypi@gmail.com",
	url="https://github.com/hkwi/pical",
	description="icalendar parser,builder library with query function",
	py_modules=["pical"],
)
