package ai.lifesnap.capture

import android.content.Context
import android.net.Uri
import androidx.core.content.FileProvider
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

data class PendingUpload(
    val id: String,
    val filename: String,
    val source: String,
    val createdAt: Long,
)

object PendingUploadStore {
    private const val PREFS = "lifesnap_pending_uploads"
    private const val KEY_ITEMS = "items"
    private const val DIRECTORY = "pending_uploads"

    fun all(context: Context): List<PendingUpload> = read(context).sortedByDescending { it.createdAt }

    fun count(context: Context): Int = read(context).size

    fun enqueue(context: Context, sourceUri: Uri, source: String): PendingUpload {
        val id = UUID.randomUUID().toString()
        val filename = "capture-$id.png"
        val directory = File(context.filesDir, DIRECTORY).apply { mkdirs() }
        val target = File(directory, filename)
        context.contentResolver.openInputStream(sourceUri)?.use { input ->
            target.outputStream().use(input::copyTo)
        } ?: error("Unable to preserve the selected image")
        val item = PendingUpload(id, filename, source, System.currentTimeMillis())
        write(context, read(context) + item)
        return item
    }

    fun uri(context: Context, item: PendingUpload): Uri {
        val file = File(File(context.filesDir, DIRECTORY), item.filename)
        check(file.exists()) { "Pending image is no longer available" }
        return FileProvider.getUriForFile(context, "${context.packageName}.files", file)
    }

    fun remove(context: Context, item: PendingUpload) {
        File(File(context.filesDir, DIRECTORY), item.filename).delete()
        write(context, read(context).filterNot { it.id == item.id })
    }

    private fun read(context: Context): List<PendingUpload> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_ITEMS, "[]") ?: "[]"
        return runCatching {
            val array = JSONArray(raw)
            buildList {
                for (index in 0 until array.length()) {
                    val value = array.getJSONObject(index)
                    val item = PendingUpload(
                        id = value.getString("id"),
                        filename = value.getString("filename"),
                        source = value.optString("source", "screenshot"),
                        createdAt = value.optLong("created_at", 0L),
                    )
                    if (File(File(context.filesDir, DIRECTORY), item.filename).exists()) add(item)
                }
            }
        }.getOrDefault(emptyList())
    }

    private fun write(context: Context, items: List<PendingUpload>) {
        val payload = JSONArray()
        items.forEach { item ->
            payload.put(JSONObject()
                .put("id", item.id)
                .put("filename", item.filename)
                .put("source", item.source)
                .put("created_at", item.createdAt))
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_ITEMS, payload.toString())
            .apply()
    }
}
