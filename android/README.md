# LifeSnap Android Floating Capture

This is a small native Android companion for the existing LifeSnap web
application. A browser or PWA cannot draw over other Android applications or
capture the global screen, so those operations live in this native module.

## User flow

1. Open the companion and set the LifeSnap server address.
2. In **More & Settings**, select **Enable Floating Capture**.
3. Android asks for the overlay permission the first time.
4. Tap the green floating button over any app.
5. Android asks for one-time screen-capture consent, then shows the screenshot.
6. Choose **Use this image for bookkeeping** or select a replacement from the
   gallery.
7. The companion uploads the image as `source=screenshot` or `source=album`,
   preserves the original image, opens LifeSnap, and invokes its existing bill
   recognition and confirmation flow.

Nothing is auto-saved as a financial record: the user still reviews the bill
candidate in LifeSnap before confirming it.

## Build in Android Studio

Open the `android/` directory with Android Studio and choose an API 35 Android
SDK. The default backend address is `http://10.0.2.2:8023`, which works only in
the Android emulator when the FastAPI server runs on the host machine.

For a device or deployed server, set a HTTPS endpoint in the app's **Server**
control, or build with:

```powershell
./gradlew :app:assembleDebug -PlifeSnapBaseUrl=https://lifesnap.example.com
```

The Android manifest permits cleartext traffic to support local emulator
development. Release deployments should use HTTPS and restrict network security
policy before distribution.

## Android permissions

- `SYSTEM_ALERT_WINDOW`: system overlay button.
- `FOREGROUND_SERVICE_SPECIAL_USE`: keeps the overlay button available.
- `FOREGROUND_SERVICE_MEDIA_PROJECTION`: captures a single screenshot only
  after Android's explicit consent dialog.

The app does not record continuously. Each capture requires the Android
MediaProjection consent flow and is reviewed before upload.
