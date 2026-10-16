package ai.lifesnap.capture

import android.app.Activity
import android.app.AlertDialog
import android.os.Bundle
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.text.DateFormat
import java.util.Date
import kotlin.concurrent.thread

class PendingUploadsActivity : Activity() {
    private lateinit var itemsContainer: LinearLayout
    private val uploadingIds = mutableSetOf<String>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(content())
        renderItems()
    }

    private fun content(): ScrollView {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(20), dp(20), dp(20))
        }
        root.addView(TextView(this).apply {
            text = "待上传图片"
            textSize = 22f
            setTypeface(typeface, 1)
        })
        root.addView(TextView(this).apply {
            text = "网络恢复后可逐项重试。成功后会回到 LifeSnap 的账单确认页。"
            textSize = 14f
            setPadding(0, dp(8), 0, dp(16))
        })
        itemsContainer = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(itemsContainer)
        return ScrollView(this).apply { addView(root) }
    }

    private fun renderItems() {
        itemsContainer.removeAllViews()
        val items = PendingUploadStore.all(this)
        if (items.isEmpty()) {
            itemsContainer.addView(TextView(this).apply { text = "没有待上传图片" })
            return
        }
        items.forEach { item ->
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(0, dp(12), 0, dp(12))
            }
            row.addView(TextView(this).apply {
                text = "${if (item.source == "album") "相册图片" else "截图"} · ${DateFormat.getDateTimeInstance().format(Date(item.createdAt))}"
                textSize = 16f
                setTypeface(typeface, 1)
            })
            row.addView(TextView(this).apply {
                text = "${item.filename.substringAfterLast('.', "图片").uppercase()} · ${formatSize(PendingUploadStore.sizeBytes(this@PendingUploadsActivity, item))}"
                textSize = 13f
            })
            val actions = LinearLayout(this)
            val retryButton = Button(this).apply {
                text = "重试上传"
                isEnabled = item.id !in uploadingIds
            }
            val deleteButton = Button(this).apply {
                text = "删除"
                isEnabled = item.id !in uploadingIds
            }
            retryButton.setOnClickListener { upload(item, retryButton, deleteButton) }
            deleteButton.setOnClickListener { confirmRemove(item) }
            actions.addView(retryButton)
            actions.addView(deleteButton)
            row.addView(actions)
            itemsContainer.addView(row, LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
            ))
        }
    }

    private fun upload(item: PendingUpload, retryButton: Button, deleteButton: Button) {
        if (!uploadingIds.add(item.id)) return
        retryButton.isEnabled = false
        retryButton.text = "上传中…"
        deleteButton.isEnabled = false
        Toast.makeText(this, "正在上传图片…", Toast.LENGTH_SHORT).show()
        thread {
            runCatching {
                AttachmentUploader.upload(this, PendingUploadStore.uri(this, item), item.source)
            }.onSuccess { attachment ->
                PendingUploadStore.remove(this, item)
                runOnUiThread {
                    startActivity(MainActivity.openWithAttachment(this, attachment))
                    finish()
                }
            }.onFailure { error ->
                runOnUiThread {
                    uploadingIds.remove(item.id)
                    retryButton.isEnabled = true
                    retryButton.text = "重试上传"
                    deleteButton.isEnabled = true
                    Toast.makeText(this, error.message ?: "上传失败，请稍后再试", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun confirmRemove(item: PendingUpload) {
        AlertDialog.Builder(this)
            .setTitle("删除待上传图片？")
            .setMessage("删除后无法恢复，也不会创建账单。")
            .setNegativeButton("取消", null)
            .setPositiveButton("删除") { _, _ ->
                PendingUploadStore.remove(this, item)
                renderItems()
            }
            .show()
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun formatSize(bytes: Long): String = when {
        bytes >= 1_048_576 -> String.format("%.1f MB", bytes / 1_048_576.0)
        bytes >= 1_024 -> String.format("%.1f KB", bytes / 1_024.0)
        else -> "$bytes B"
    }
}
