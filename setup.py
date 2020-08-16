import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="btrfssnapshottools",
    version="1.0.0",
    author="Jordan Leppert",
    author_email="jordanleppert@gmail.com",
    description="A tool to take regular snapshots of BTRFS subvolumes, and optionally back them up to a remote location.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/JordanL2/BTRFS-Snapshot-Tool",
    packages=setuptools.find_packages() + setuptools.find_namespace_packages(include=['btrfssnapshottools.*']),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: LGPL-2.1 License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points = {'console_scripts': [
        'snapshot=btrfssnapshottools.snapshot:main',
        'snapshot-backup=btrfssnapshottools.snapshotbackup:main',
        ], },
)
