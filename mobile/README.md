# Mobile Client (Flet)

Cross-platform Python UI for Arithmetic Super App.

## Run on Desktop

    pip install flet
    flet run mobile/app.py

## Run in the Browser (works on Termux)

    pip install flet
    flet run --web --port 8550 mobile/app.py
    # Open http://127.0.0.1:8550

## Build APK (via GitHub Actions)

Push a tag:

    git tag v0.4.0
    git push origin v0.4.0

The `.github/workflows/build-apk.yml` workflow builds and uploads the
APK as an artifact. Download it from the Actions tab on GitHub.

## Configure Backend URL

Edit `API_BASE` in `app.py`. For a phone on the same network, use
your laptop's LAN IP, e.g. `http://192.168.1.42:8000`.
