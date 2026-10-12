package ai.lifesnap.capture

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.provider.Settings
import androidx.core.content.FileProvider
import java.io.File
import java.io.FileOutputStream
import java.nio.ByteBuffer

class ScreenCaptureService : Service() {
    private var projection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var imageReader: ImageReader? = null
    private var worker: HandlerThread? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        createNotificationChannel()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_ID,
                notification(),
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION,
            )
        } else {
            startForeground(NOTIFICATION_ID, notification())
        }
        val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
        @Suppress("DEPRECATION")
        val resultData = intent?.getParcelableExtra<Intent>(EXTRA_RESULT_DATA)
        if (resultCode == 0 || resultData == null) {
            stopSelf()
            return START_NOT_STICKY
        }
        capture(resultCode, resultData)
        return START_NOT_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        cleanup()
        super.onDestroy()
    }

    private fun capture(resultCode: Int, resultData: Intent) {
        val metrics = resources.displayMetrics
        val width = metrics.widthPixels
        val height = metrics.heightPixels
        worker = HandlerThread("LifeSnapCapture").also { it.start() }
        val handler = Handler(worker!!.looper)
        imageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
        val manager = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        projection = manager.getMediaProjection(resultCode, resultData).also { activeProjection ->
            activeProjection.registerCallback(object : MediaProjection.Callback() {
                override fun onStop() = cleanup()
            }, handler)
            virtualDisplay = activeProjection.createVirtualDisplay(
                "LifeSnap capture",
                width,
                height,
                metrics.densityDpi,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                imageReader!!.surface,
                null,
                handler,
            )
        }
        imageReader!!.setOnImageAvailableListener({ reader ->
            val image = reader.acquireLatestImage() ?: return@setOnImageAvailableListener
            try {
                val captureUri = saveImage(image, width, height)
                startActivity(
                    CaptureReviewActivity.intent(this, captureUri)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
                )
            } catch (_: Exception) {
                // The user can retry from the persistent floating window.
            } finally {
                image.close()
                cleanup()
                startForegroundService(Intent(this, FloatingCaptureService::class.java))
                stopSelf()
            }
        }, handler)
    }

    private fun saveImage(image: Image, width: Int, height: Int): android.net.Uri {
        val plane = image.planes[0]
        val buffer: ByteBuffer = plane.buffer
        val rowPadding = plane.rowStride - plane.pixelStride * width
        val fullBitmap = Bitmap.createBitmap(
            width + rowPadding / plane.pixelStride,
            height,
            Bitmap.Config.ARGB_8888,
        )
        fullBitmap.copyPixelsFromBuffer(buffer)
        val cropped = Bitmap.createBitmap(fullBitmap, 0, 0, width, height)
        fullBitmap.recycle()
        val directory = File(cacheDir, "captures").apply { mkdirs() }
        val file = File(directory, "capture-${System.currentTimeMillis()}.png")
        FileOutputStream(file).use { output -> cropped.compress(Bitmap.CompressFormat.PNG, 100, output) }
        cropped.recycle()
        return FileProvider.getUriForFile(this, "$packageName.files", file)
    }

    private fun cleanup() {
        imageReader?.close()
        imageReader = null
        virtualDisplay?.release()
        virtualDisplay = null
        val activeProjection = projection
        projection = null
        activeProjection?.stop()
        worker?.quitSafely()
        worker = null
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(CHANNEL_ID, "LifeSnap 截图", NotificationManager.IMPORTANCE_LOW)
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(channel)
    }

    private fun notification(): Notification = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setContentTitle("正在截取账单图片")
            .setOngoing(true)
            .build()
    } else {
        Notification.Builder(this)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setContentTitle("正在截取账单图片")
            .setOngoing(true)
            .build()
    }

    companion object {
        const val EXTRA_RESULT_CODE = "media_projection_result_code"
        const val EXTRA_RESULT_DATA = "media_projection_result_data"
        private const val CHANNEL_ID = "lifesnap_screen_capture"
        private const val NOTIFICATION_ID = 4302
    }
}
