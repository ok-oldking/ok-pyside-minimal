# ok-pyside-minimal

An **unofficial**, smaller redistribution of the official [PySide6-Essentials](https://pypi.org/project/PySide6-Essentials/) wheels for Qt Widgets applications. Native binaries are retained unchanged; this project removes files and rewrites package metadata. It does not rebuild Qt.

```sh
python -m pip install ok-pyside-minimal
```

Imports keep their normal names:

```python
from PySide6.QtWidgets import QApplication, QLabel

app = QApplication([])
label = QLabel("Hello from Qt Widgets")
label.show()
app.exec()
```

Use a clean environment. This distribution owns the `PySide6` namespace: do not install it alongside `PySide6`, `PySide6-Essentials`, or `PySide6-Addons`. It does not satisfy another package's declared dependency on `PySide6-Essentials`; that dependency must be changed by the consuming project. `shiboken6` is installed at exactly the matching upstream version.

## Contents

| Kept | Removed |
| --- | --- |
| QtCore, QtGui, QtWidgets | Qt Quick and QML, including Labs and Lottie modules |
| QtNetwork, QtConcurrent, QtDBus where provided upstream | QtOpenGL and QtOpenGLWidgets |
| QtXml, QtTest, QtSvg, QtSvgWidgets | QtSql, QtDesigner, QtPrintSupport |
| Platform, image, SVG, style, network and TLS plugins that pass dependency checks | QtHelp (depends on SQL), QtUiTools (depends on OpenGLWidgets) |
| `uic`, `rcc` and selected Python helpers | Designer, Assistant, QML tools, translation tools, deployment/project generators and associated plugins |

OpenGL removal means removing the separate Qt OpenGL modules, their plugins, and the bundled Windows software OpenGL renderer. QtGui itself is upstream's unchanged binary and still contains graphics APIs, including OpenGL interfaces, and may use system graphics libraries. A Qt build with OpenGL support disabled would require a separate source-build project.

`.ui` files can still be compiled with `pyside6-uic`; runtime `QUiLoader` is unavailable. Native dependency scans remove optional plugins that link to removed libraries and stop the build if a required runtime binary would break.

## Automatic releases

[publish.yml](.github/workflows/publish.yml) checks PyPI every six hours and can also be run manually. Stable upstream releases from **6.12.0** onward are processed oldest first, one per run. All official platform wheels are included: currently Windows x64/ARM64, Linux x64/ARM64, and macOS universal2. A new unknown platform stops planning until a runner is configured. Prereleases are manual only; yanked releases are rejected.

Each release:

1. Downloads only official PyPI files and verifies their published SHA-256 digests.
2. Removes excluded bindings, libraries, tools, plugins and related assets.
3. Checks PE, ELF and Mach-O dependencies; rewrites module lists, entry points, wheel metadata and RECORD hashes.
4. Installs and tests each wheel on its native platform, including both macOS architectures, and runs `twine check`.
5. Publishes through **GitHub Actions OIDC / PyPI Trusted Publishing**, then creates a GitHub release with wheels and build reports.

Version numbers match upstream. For a packaging correction, manually run the workflow with the upstream version and a positive `revision`, producing e.g. `6.12.0.post1`. The Shiboken dependency and `PySide6.__version__` remain at the upstream version. Retries build all artifacts and skip wheels already uploaded to PyPI, allowing partial uploads to recover. Scheduled workflows may be delayed by GitHub and may be disabled after 60 days of repository inactivity; re-enable them in Actions if needed.

## One-time publishing setup

No PyPI API token is used. In the PyPI account that will own the project, register a [pending trusted publisher](https://pypi.org/manage/account/publishing/):

| Field | Value |
| --- | --- |
| PyPI project name | `ok-pyside-minimal` |
| GitHub owner | `ok-oldking` |
| Repository | `ok-pyside-minimal` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

Create the matching `pypi` environment in GitHub repository settings. Then run **Publish to PyPI → Run workflow**. The first successful OIDC publication creates the PyPI project. GitHub authentication authorizes the workflow, but PyPI still requires this account-side trust registration. See [PyPI's instructions](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

## Local development

```sh
python -m venv .venv
# Activate .venv, then:
python -m pip install -r requirements-dev.txt
python -m pytest
python -m scripts.release plan
python -m scripts.release build --version 6.12.0
python -m twine check dist/*
```

`build --filename OFFICIAL_WHEEL_NAME` selects one wheel. Downloads are cached under `.cache/`; output wheels go to `dist/` and reports to `reports/`. Install the matching wheel into a fresh environment, then run `python -m scripts.smoke`. No source distribution is produced: the deliverables are transformed platform wheels. The tooling deliberately has no setuptools build backend.

## Licensing and source

Qt and PySide remain under their upstream licenses, not this repository's MIT tooling license. Original copyright notices and bundled license material are retained; copies of LGPLv3, GPLv2 and GPLv3 from the upstream PySide 6.12.0 source tree are included under `licenses/` and added to every wheel. See [NOTICE](NOTICE) for attribution and source locations. Every wheel includes an `upstream.json` containing the exact original wheel URL, SHA-256, version, removed-file manifest, and corresponding source locations. This project is not affiliated with The Qt Company.
