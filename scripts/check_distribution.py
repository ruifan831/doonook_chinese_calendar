"""Check the built wheel and sdist before uploading them to PyPI."""

import hashlib
from pathlib import Path
import tarfile
import tomllib
import zipfile

EXPECTED = "c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2"
SUFFIX = "doonook_chinese_calendar/data/de440s.bsp"


def check(names, read):
    matches = [name for name in names if name.endswith(SUFFIX)]
    assert len(matches) == 1, "Missing or duplicate ephemeris"
    assert hashlib.sha256(read(matches[0])).hexdigest() == EXPECTED, "Invalid kernel"
    assert any(
        name.endswith("doonook_chinese_calendar/data/NOTICE.txt") for name in names
    )
    assert not any(
        Path(name).name == ".env"
        or (Path(name).name.startswith(".env.") and Path(name).name != ".env.example")
        for name in names
    ), "Private dotenv file included"


if __name__ == "__main__":
    project = tomllib.loads(Path("pyproject.toml").read_text())["project"]
    prefix = project["name"].replace("-", "_") + "-" + project["version"]
    wheels = list(Path("dist").glob(prefix + "-*.whl"))
    sources = list(Path("dist").glob(prefix + ".tar.gz"))
    assert wheels and sources, "Build both wheel and sdist first"
    for file in wheels:
        with zipfile.ZipFile(file) as archive:
            check(archive.namelist(), archive.read)
        print(f"PASS {file.name}: bundled kernel + notice; no private dotenv")
    for file in sources:
        with tarfile.open(file) as archive:
            check(archive.getnames(), lambda name: archive.extractfile(name).read())
        print(f"PASS {file.name}: bundled kernel + notice; no private dotenv")
