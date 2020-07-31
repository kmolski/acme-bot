"""Setup module for the application."""
import setuptools

# with open("README.md", "r") as fh:
#     long_description = fh.read()

setuptools.setup(
    name="acme-bot",
    version="0.0.1",
    author="kmolski",
    # description="A small example package",
    # long_description=long_description,
    # long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    install_requires=["discord.py", "textx", "youtube_dl"],
    entry_points={"console_scripts": "acme-bot=acme_bot:run"},
    python_requires='>=3.7',
)
