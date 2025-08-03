from setuptools import find_packages, setup

setup(
    name="identity_verifier",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "Django==4.2.16",
        "django-cors-headers==4.4.0",
        "djangorestframework==3.15.2",
        "face-recognition==1.3.0",
        "opencv-python-headless==4.10.0.84",
        "pillow==10.4.0",
        "gunicorn",
        "psycopg2",
        "easyocr",
    ],
    entry_points={
        "console_scripts": [
            "manage = identity_verifier.manage:main",
        ],
    },
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 3.2",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
)
