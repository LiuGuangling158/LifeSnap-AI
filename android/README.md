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

If an upload cannot complete, choose **Keep for later upload**. The image is
copied to the app's private storage and can be retried or deleted from the
**Pending uploads** button in the companion toolbar. It is never turned into a
financial record until the existing LifeSnap confirmation screen is completed.

The floating button can be dragged to a comfortable position. Long-press it to
close it; choosing **Enable Floating Capture** in LifeSnap starts it again.

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

Debug builds permit cleartext traffic to support local emulator development.
Release builds require HTTPS both in the manifest and when a server URL is
saved, so a production APK cannot accidentally send financial images over HTTP.

## Android permissions

- `SYSTEM_ALERT_WINDOW`: system overlay button.
- `FOREGROUND_SERVICE_SPECIAL_USE`: keeps the overlay button available.
- `FOREGROUND_SERVICE_MEDIA_PROJECTION`: captures a single screenshot only
  after Android's explicit consent dialog.

The app does not record continuously. Each capture requires the Android
MediaProjection consent flow and is reviewed before upload.

## Acceptance checklist

Run this on at least one emulator and one physical device before release:

1. Enable and deny the overlay permission; verify the app explains the next
   step and never starts the overlay without approval.
2. Drag the floating button, leave and reopen the app, then verify its position
   is retained. Long-press it and verify that it closes.
3. Allow and deny the MediaProjection prompt. A denial must restore the
   floating button and upload nothing.
4. Capture a payment screen, replace it with a JPEG from the gallery, and
   verify the server receives the correct `screenshot` or `album` source.
5. Turn off the network during upload, choose **Keep for later upload**, force
   close and reopen the app, then retry from **Pending uploads**.
6. Confirm a recognized candidate and verify exactly one bill is created;
   cancel a candidate and verify no bill is created.

Test Android 10, 13, and 14+ where possible. Overlay permission and background
service behavior varies noticeably across device vendors, so a physical device
check is required in addition to emulator testing.
