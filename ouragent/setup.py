from setuptools import setup

ver = '1.2.1'

setup(
    name='superparty',
    version=ver,
    description='A python3 party that places random bids with sufficient utility',
    url='https://tracinsy.ewi.tudelft.nl/pubtrac/GeniusWeb',
    author='Yaniv',
    packages=['randomparty'],
    install_requires=[ "geniusweb@https://tracinsy.ewi.tudelft.nl/pubtrac/GeniusWebPython/export/93/geniuswebcore/dist/geniusweb-1.2.1.tar.gz"],
    py_modules=['party']
)
