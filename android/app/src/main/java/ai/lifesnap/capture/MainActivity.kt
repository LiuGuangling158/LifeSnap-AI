package ai.lifesnap.capture

import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import org.json.JSONObject

class MainActivity : Activity() {
    private lateinit var webView: WebView
    private var pendingAttachment: UploadedAttachment? = null
    private var deliveryAttempts = 0
    private var overlayRequested = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        pendingAttachment = attachmentFromIntent(intent)
        setContentView(createContent())
        loadWorkspace()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        pendingAttachment = attachmentFromIntent(intent)
        deliveryAttempts = 0
        loadWorkspace("#bills")
    }

    override fun onResume() {
        super.onResume()
        updatePendingUploadsLabel()
        if (overlayRequested && Settings.canDrawOverlays(this)) {
            overlayRequested = false
            startFloatingCapture()
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun createContent(): LinearLayout {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(244, 246, 244))
        }
        val toolbar = LinearLayout(this).apply {
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(18), dp(10), dp(12), dp(10))
            setBackgroundColor(Color.rgb(249, 251, 249))
        }
        toolbar.addView(TextView(this).apply {
            text = "LifeSnap"
            textSize = 20f
            setTextColor(Color.rgb(32, 53, 44))
            setTypeface(typeface, 1)
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        toolbar.addView(Button(this).apply {
            text = "服务器"
            setOnClickListener { editServerAddress() }
        })
        toolbar.addView(Button(this).apply {
            text = pendingUploadsLabel()
            tag = PENDING_UPLOADS_BUTTON_TAG
            setOnClickListener {
                startActivity(Intent(this@MainActivity, PendingUploadsActivity::class.java))
            }
        })

        webView = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            addJavascriptInterface(AndroidBridge(this@MainActivity), "LifeSnapAndroid")
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, url: String) {
                    super.onPageFinished(view, url)
                    deliverPendingAttachment()
                }

                override fun shouldOverrideUrlLoading(view: WebView, url: String): Boolean {
                    if (isWorkspaceUrl(url)) return false
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                    return true
                }
            }
        }
        root.addView(toolbar)
        root.addView(webView, LinearLayout.LayoutParams(0, 0, 1f))
        return root
    }

    private fun loadWorkspace(fragment: String = "#dashboard") {
        webView.loadUrl("${WorkspaceConfig.baseUrl(this)}/$fragment")
    }

    private fun enableFloatingCapture() {
        if (!Settings.canDrawOverlays(this)) {
            overlayRequested = true
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
            Toast.makeText(this, "请允许 LifeSnap 显示在其他应用上层", Toast.LENGTH_LONG).show()
            return
        }
        startFloatingCapture()
    }

    private fun isWorkspaceUrl(url: String): Boolean {
        val candidate = Uri.parse(url)
        val workspace = Uri.parse(WorkspaceConfig.baseUrl(this))
        return candidate.scheme == workspace.scheme
            && candidate.host == workspace.host
            && candidate.port == workspace.port
    }

    private fun startFloatingCapture() {
        val service = Intent(this, FloatingCaptureService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(service) else startService(service)
        Toast.makeText(this, "悬浮记账已开启", Toast.LENGTH_SHORT).show()
    }

    private fun editServerAddress() {
        val input = EditText(this).apply {
            setText(WorkspaceConfig.baseUrl(this@MainActivity))
            hint = "https://your-lifesnap.example"
            selectAll()
        }
        AlertDialog.Builder(this)
            .setTitle("LifeSnap 服务器地址")
            .setMessage("生产环境请使用 HTTPS。开发模拟器默认使用 http://10.0.2.2:8023。")
            .setView(input)
            .setNegativeButton("取消", null)
            .setPositiveButton("保存") { _, _ ->
                runCatching { WorkspaceConfig.saveBaseUrl(this, input.text.toString()) }
                    .onSuccess { loadWorkspace() }
                    .onFailure { Toast.makeText(this, it.message, Toast.LENGTH_LONG).show() }
            }
            .show()
    }

    private fun pendingUploadsLabel(): String {
        val count = PendingUploadStore.count(this)
        return if (count == 0) "待上传" else "待上传($count)"
    }

    private fun updatePendingUploadsLabel() {
        val root = webView.parent as? ViewGroup ?: return
        root.findViewWithTag<Button>(PENDING_UPLOADS_BUTTON_TAG)?.text = pendingUploadsLabel()
    }

    private fun deliverPendingAttachment() {
        val attachment = pendingAttachment ?: return
        if (deliveryAttempts >= 12) {
            Toast.makeText(this, "图片已上传，但页面未能接收，请在 AI 帮记中重新选择。", Toast.LENGTH_LONG).show()
            return
        }
        deliveryAttempts += 1
        val payload = JSONObject()
            .put("id", attachment.id)
            .put("filename", attachment.filename)
            .put("contentType", attachment.contentType)
            .put("fileSize", attachment.fileSize)
            .put("source", attachment.source)
        val script = """
            (function(payload) {
              if (window.LifeSnapNative && typeof window.LifeSnapNative.receiveAttachment === 'function') {
                window.LifeSnapNative.receiveAttachment(payload);
                return true;
              }
              return false;
            })($payload);
        """.trimIndent()
        webView.evaluateJavascript(script) { accepted ->
            if (accepted == "true") {
                pendingAttachment = null
            } else {
                webView.postDelayed({ deliverPendingAttachment() }, 350)
            }
        }
    }

    private fun attachmentFromIntent(intent: Intent): UploadedAttachment? {
        val id = intent.getStringExtra(EXTRA_ATTACHMENT_ID) ?: return null
        return UploadedAttachment(
            id = id,
            filename = intent.getStringExtra(EXTRA_ATTACHMENT_FILENAME) ?: "lifesnap-capture.png",
            contentType = intent.getStringExtra(EXTRA_ATTACHMENT_TYPE) ?: "image/png",
            fileSize = intent.getLongExtra(EXTRA_ATTACHMENT_SIZE, 0L),
            source = intent.getStringExtra(EXTRA_ATTACHMENT_SOURCE) ?: "screenshot",
        )
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private class AndroidBridge(private val activity: MainActivity) {
        @JavascriptInterface
        fun enableFloatingCapture() {
            activity.runOnUiThread {
                if (activity.isWorkspaceUrl(activity.webView.url ?: "")) {
                    activity.enableFloatingCapture()
                }
            }
        }
    }

    companion object {
        private const val EXTRA_ATTACHMENT_ID = "attachment_id"
        private const val EXTRA_ATTACHMENT_FILENAME = "attachment_filename"
        private const val EXTRA_ATTACHMENT_TYPE = "attachment_type"
        private const val EXTRA_ATTACHMENT_SIZE = "attachment_size"
        private const val EXTRA_ATTACHMENT_SOURCE = "attachment_source"
        private const val PENDING_UPLOADS_BUTTON_TAG = "pending_uploads"

        fun openWithAttachment(context: Context, attachment: UploadedAttachment): Intent =
            Intent(context, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                .putExtra(EXTRA_ATTACHMENT_ID, attachment.id)
                .putExtra(EXTRA_ATTACHMENT_FILENAME, attachment.filename)
                .putExtra(EXTRA_ATTACHMENT_TYPE, attachment.contentType)
                .putExtra(EXTRA_ATTACHMENT_SIZE, attachment.fileSize)
                .putExtra(EXTRA_ATTACHMENT_SOURCE, attachment.source)
    }
}
