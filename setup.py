import setuptools

with open("README.md", "r") as file:
    long_description = file.read()

setuptools.setup(
    name='requestshook',
    version='0.0.1',
    author='jade-kinx',
    author_email='jade@kinx.net',
    description='openstack API req/resp sequence logging tools',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/jade-kinx/requestshook',
    packages=['requestshook'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],    
    python_requires='>=3.8',
    entry_points={
        'requestshook.api_middleware': [
            'seq_logger = requestshook:SeqLogger',
        ]
    },
)