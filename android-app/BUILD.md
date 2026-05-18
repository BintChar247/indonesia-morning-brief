# Building the Morning Brief APK

## What this app does

A fully standalone Android app that shows the Indonesia Morning Brief dashboard.
**No Supabase. No GitHub Actions. No server setup.**

On every app open it fetches live data directly from:
- Yahoo Finance (market quotes via allorigins.win CORS proxy)
- FRED (US Treasury yield curve)
- Public RSS feeds (Reuters, Yahoo Finance, Jakarta Post, Antara, CNBC, EIA)

Flagged articles and custom RSS sources are saved locally in the device's `localStorage`.

---

## Option A — Open in Android Studio (recommended)

1. **Open Android Studio** (Electric Eel or newer)
2. **File → Open** → select the `android-app/` folder
3. Let Gradle sync finish (~2 min on first run)
4. **Build → Generate Signed Bundle / APK → APK**
5. Follow the signing wizard (create a new keystore if you don't have one)
6. The APK is written to `app/release/app-release.apk`
7. Transfer to your phone and install (Settings → Install unknown apps must be enabled)

> If Android Studio reports "SDK not found", go to **SDK Manager** and install Android API 35.

---

## Option B — Build from the command line

Requires: JDK 17+, Android SDK (set `ANDROID_HOME` or `ANDROID_SDK_ROOT`)

```bash
cd android-app/
./gradlew assembleRelease
```

The unsigned APK is at `app/build/outputs/apk/release/app-release-unsigned.apk`.

Sign it:
```bash
# Create keystore (once)
keytool -genkey -v -keystore morning-brief.jks \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -alias morning-brief

# Sign
$ANDROID_HOME/build-tools/<version>/apksigner sign \
    --ks morning-brief.jks \
    --out app-release-signed.apk \
    app/build/outputs/apk/release/app-release-unsigned.apk
```

---

## Rebuild after dashboard updates

If you update `../index.html`, regenerate the bundled asset:

```bash
cd android-app/
python3 build_standalone.py   # re-patches index.html → assets/index.html
```

Then rebuild the APK.

---

## App details

| Property | Value |
|---|---|
| Package | `com.mufg.morningbrief` |
| Min Android | 8.0 (API 26) |
| Target Android | 15 (API 35) |
| App name | Morning Brief |
| Data sources | Yahoo Finance · FRED · RSS (no auth needed) |
| Backend | None — fully standalone |
