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

Use a clean environment. This distribution owns the `PySide6` namespace: do not install it alongside `PySide6`, `PySide6-Essentials`, or `PySide6-Addons`. It does not satisfy another package's declared dependency on `PySide6-Essentials`; that dependency must be changed by the consuming project. **The only Python dependency is `shiboken6`**, pinned to the exact upstream version. No Addons, PySide6 metapackage, PDF, WebEngine, Shiboken generator, NumPy or setuptools is required at runtime. `requirements-dev.txt` is only for building and testing this repository.

## Contents

| Kept | Removed |
| --- | --- |
| QtCore, QtGui, QtWidgets | Qt Quick and QML, including Labs and Lottie modules |
| QtSvg for rendering and SVG icons | QtOpenGL, QtOpenGLWidgets, QtSql, QtDesigner, QtPrintSupport |
| Platform plugins and native styles | QtNetwork, QtConcurrent, QtTest, QtXml, QtSvgWidgets, Python QtDBus bindings |
| GIF, ICNS, ICO, JPEG, SVG and WebP image plugins (PNG/BMP are built into QtGui) | QtHelp (depends on SQL), QtUiTools (depends on OpenGLWidgets), TLS/network plugins, PDF/TIFF/TGA/WBMP image plugins |
| Native QtDBus library on Linux/macOS, required by QtGui | Windows QtDBus DLL, bundled translations, CMake files, headers, type systems, glue, metatypes and documentation |
| Runtime support and Python type stubs | All bundled development tools and console entry points, including `uic` and `rcc` |
| Required MSVC runtime DLLs and `qwindows.dll` on Windows | Chromium `resources/icudtl.dat`, unused `vcamp140`/`concrt140`/`vccorlib140`/`vcomp140`/`msvcp140_codecvt_ids` DLLs, `qdirect2d.dll` and the Windows virtual keyboard plugin |

OpenGL removal means removing the separate Qt OpenGL modules, their plugins, and the bundled Windows software OpenGL renderer. QtGui itself is upstream's unchanged binary and still contains graphics APIs, including OpenGL interfaces, and may use system graphics libraries. A Qt build with OpenGL support disabled would require a separate source-build project.

Compile `.ui` and `.qrc` files in a separate development environment using official PySide6; ship the generated Python files with your application. Runtime `QUiLoader` is unavailable. Native dependency scans remove optional plugins that link to removed libraries and stop the build if a required runtime binary would break. QtGui's native DBus dependency on Linux/macOS and other upstream system libraries cannot be removed through file pruning.

## Automatic releases

[publish.yml](.github/workflows/publish.yml) checks PyPI every six hours and can also be run manually. Stable upstream releases from **6.12.0** onward are processed oldest first, one per run. All official platform wheels are included: currently Windows x64/ARM64, Linux x64/ARM64, and macOS universal2. A new unknown platform stops planning until a runner is configured. Prereleases are manual only; yanked releases are rejected.

Each release:

1. Downloads only official PyPI files and verifies their published SHA-256 digests.
2. Removes excluded bindings, libraries, tools, plugins and related assets.
3. Checks PE, ELF and Mach-O dependencies; rewrites module lists, entry points, wheel metadata and RECORD hashes.
4. Installs and tests each wheel on its native platform, including both macOS architectures, and runs `twine check`.
5. Publishes through **GitHub Actions OIDC / PyPI Trusted Publishing**, then creates a GitHub release with wheels and build reports.

Version numbers match upstream, except **6.12.0 currently uses 6.12.0.post2**, which removes additional unused Windows payloads. The original 6.12.0 PyPI release was deleted; post releases use new filenames because PyPI does not permit reusing deleted ones. Automatic discovery and local builds both apply the latest minimum packaging revision. For a packaging correction, manually run the workflow with the upstream version and a positive `revision`. The Shiboken dependency and `PySide6.__version__` remain at the upstream version. Retries build all artifacts and skip wheels already uploaded to PyPI, allowing partial uploads to recover. Scheduled workflows may be delayed by GitHub and may be disabled after 60 days of repository inactivity; re-enable them in Actions if needed.

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
