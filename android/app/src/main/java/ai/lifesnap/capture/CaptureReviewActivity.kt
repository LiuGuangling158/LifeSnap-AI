package ai.lifesnap.capture

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.ViewGroup
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import kotlin.concurrent.thread

class CaptureReviewActivity : Activity() {
    private lateinit var preview: ImageView
    private var selectedUri: Uri? = null
    private var selectedSource = "screenshot"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        selectedUri = intent.getStringExtra(EXTRA_CAPTURE_URI)?.let(Uri::parse)
        if (selectedUri == null) {
            finish()
            return
        }
        setContentView(content())
        showPreview()
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_ALBUM && resultCode == RESULT_OK && data?.data != null) {
            selectedUri = data.data
            selectedSource = "album"
            showPreview()
        }
    }

    private fun content(): LinearLayout {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(20), dp(20), dp(20))
        }
        root.addView(TextView(this).apply {
            text = "选择记账图片"
            textSize = 22f
            setTypeface(typeface, 1)
        })
        root.addView(TextView(this).apply {
            text = "确认截图，或从相册选择另一张支付截图。导入后会进入账单确认页。"
            textSize = 14f
            setPadding(0, dp(8), 0, dp(16))
        })
        preview = ImageView(this).apply {
            adjustViewBounds = true
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = "待导入的账单图片"
            setBackgroundColor(0xfff2f5f2.toInt())
        }
        root.addView(preview, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1f,
        ))
        root.addView(Button(this).apply {
            text = "使用这张图片记账"
            setOnClickListener { selectedUri?.let { upload(it, selectedSource) } }
        }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
            topMargin = dp(16)
        })
        root.addView(Button(this).apply {
            text = "从相册选择"
            setOnClickListener {
                startActivityForResult(
                    Intent(Intent.ACTION_OPEN_DOCUMENT)
                        .addCategory(Intent.CATEGORY_OPENABLE)
                        .setType("image/*")
                        .putExtra(
                            Intent.EXTRA_MIME_TYPES,
                            arrayOf("image/jpeg", "image/png", "image/webp"),
                        ),
                    REQUEST_ALBUM,
                )
            }
        }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        root.addView(Button(this).apply {
            text = "取消"
            setOnClickListener { finish() }
        }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        return root
    }

    private fun showPreview() {
        preview.setImageURI(selectedUri)
    }

    private fun upload(uri: Uri, source: String) {
        val progress = AlertDialog.Builder(this)
            .setMessage("正在安全导入图片…")
            .setCancelable(false)
            .create()
        progress.show()
        thread {
            runCatching { AttachmentUploader.upload(this, uri, source) }
                .onSuccess { attachment ->
                    runOnUiThread {
                        progress.dismiss()
                        startActivity(MainActivity.openWithAttachment(this, attachment))
                        finish()
                    }
                }
                .onFailure { error ->
                    runOnUiThread {
                        progress.dismiss()
                        offerPendingUpload(uri, source, error)
                    }
                }
        }
    }

    private fun offerPendingUpload(uri: Uri, source: String, error: Throwable) {
        AlertDialog.Builder(this)
            .setTitle("图片暂未上传")
            .setMessage("${error.message ?: "网络或服务器暂时不可用"}\n\n保留图片后，可在应用顶部的“待上传”中重试。")
            .setNegativeButton("继续编辑", null)
            .setPositiveButton("保留待上传") { _, _ ->
                runCatching { PendingUploadStore.enqueue(this, uri, source) }
                    .onSuccess {
                        Toast.makeText(this, "已保留到待上传列表", Toast.LENGTH_LONG).show()
                        finish()
                    }
                    .onFailure {
                        Toast.makeText(this, "无法保留图片：${it.message}", Toast.LENGTH_LONG).show()
                    }
            }
            .show()
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    companion object {
        private const val EXTRA_CAPTURE_URI = "capture_uri"
        private const val REQUEST_ALBUM = 812

        fun intent(context: Context, uri: Uri): Intent = Intent(context, CaptureReviewActivity::class.java)
            .putExtra(EXTRA_CAPTURE_URI, uri.toString())
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
}
