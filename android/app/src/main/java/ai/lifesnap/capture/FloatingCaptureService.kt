package ai.lifesnap.capture

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.pm.ServiceInfo
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.ImageButton

class FloatingCaptureService : Service() {
    private lateinit var windowManager: WindowManager
    private var bubble: ImageButton? = null
    private var attached = false

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        createNotificationChannel()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(
                NOTIFICATION_ID,
                notification(),
                ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE,
            )
        } else {
            startForeground(NOTIFICATION_ID, notification())
        }
        showBubble()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (Settings.canDrawOverlays(this)) showBubble()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        if (attached) bubble?.let(windowManager::removeViewImmediate)
        bubble = null
        attached = false
        super.onDestroy()
    }

    private fun showBubble() {
        if (attached || !Settings.canDrawOverlays(this)) return
        val button = ImageButton(this).apply {
            contentDescription = "LifeSnap 截图记账"
            setImageResource(android.R.drawable.ic_menu_camera)
            setColorFilter(Color.WHITE)
            background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(Color.rgb(23, 107, 82))
            }
            elevation = dp(8).toFloat()
            setPadding(dp(14), dp(14), dp(14), dp(14))
            setOnClickListener {
                hideBubble()
                startActivity(
                    Intent(this@FloatingCaptureService, CapturePermissionActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
                )
            }
            setOnLongClickListener {
                Toast.makeText(this@FloatingCaptureService, "悬浮记账已关闭", Toast.LENGTH_SHORT).show()
                stopSelf()
                true
            }
        }
        val params = WindowManager.LayoutParams(
            dp(56),
            dp(56),
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            android.graphics.PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.END or Gravity.CENTER_VERTICAL
            x = preferences().getInt(KEY_X, dp(16))
            y = preferences().getInt(KEY_Y, 0)
        }
        button.setOnTouchListener(dragListener(params))
        windowManager.addView(button, params)
        bubble = button
        attached = true
    }

    private fun hideBubble() {
        if (!attached) return
        bubble?.let(windowManager::removeViewImmediate)
        attached = false
    }

    private fun dragListener(params: WindowManager.LayoutParams): View.OnTouchListener {
        var downX = 0f
        var downY = 0f
        var initialX = 0
        var initialY = 0
        var moved = false
        val threshold = dp(8)
        return View.OnTouchListener { view, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downX = event.rawX
                    downY = event.rawY
                    initialX = params.x
                    initialY = params.y
                    moved = false
                    false
                }
                MotionEvent.ACTION_MOVE -> {
                    val deltaX = (event.rawX - downX).toInt()
                    val deltaY = (event.rawY - downY).toInt()
                    if (!moved && (kotlin.math.abs(deltaX) > threshold || kotlin.math.abs(deltaY) > threshold)) {
                        moved = true
                        view.isPressed = false
                    }
                    if (moved && attached) {
                        params.x = initialX - deltaX
                        params.y = initialY + deltaY
                        windowManager.updateViewLayout(view, params)
                    }
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    if (moved) {
                        preferences().edit().putInt(KEY_X, params.x).putInt(KEY_Y, params.y).apply()
                        true
                    } else {
                        false
                    }
                }
                else -> false
            }
        }
    }

    private fun preferences() = getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "LifeSnap 悬浮记账",
            NotificationManager.IMPORTANCE_LOW,
        ).apply { description = "让截图记账悬浮窗保持可用" }
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(channel)
    }

    private fun notification(): Notification = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setContentTitle("LifeSnap 悬浮记账已开启")
            .setContentText("点击悬浮按钮截屏或选择账单图片")
            .setOngoing(true)
            .build()
    } else {
        Notification.Builder(this)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setContentTitle("LifeSnap 悬浮记账已开启")
            .setOngoing(true)
            .build()
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    companion object {
        private const val CHANNEL_ID = "lifesnap_floating_capture"
        private const val NOTIFICATION_ID = 4301
        private const val PREFERENCES = "lifesnap_floating_capture"
        private const val KEY_X = "bubble_x"
        private const val KEY_Y = "bubble_y"
    }
}
