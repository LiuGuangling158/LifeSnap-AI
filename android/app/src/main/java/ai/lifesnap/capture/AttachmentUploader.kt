package ai.lifesnap.capture

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import org.json.JSONObject
import java.io.BufferedOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

object AttachmentUploader {
    fun upload(
        context: Context,
        contentUri: Uri,
        source: String,
    ): UploadedAttachment {
        val boundary = "LifeSnap-${UUID.randomUUID()}"
        val connection = (URL("${WorkspaceConfig.baseUrl(context)}/attachments/upload").openConnection() as HttpURLConnection)
        return try {
            connection.requestMethod = "POST"
            connection.connectTimeout = 20_000
            connection.readTimeout = 60_000
            connection.doOutput = true
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")

            val mimeType = context.contentResolver.getType(contentUri) ?: "image/png"
            val filename = displayName(context, contentUri)
            BufferedOutputStream(connection.outputStream).use { output ->
                writeField(output, boundary, "source", source)
                writeField(output, boundary, "save_original", "true")
                output.write("--$boundary\r\n".toByteArray())
                output.write(
                    "Content-Disposition: form-data; name=\"file\"; filename=\"${filename.replace("\"", "_")}\"\r\n"
                        .toByteArray(),
                )
                output.write("Content-Type: $mimeType\r\n\r\n".toByteArray())
                context.contentResolver.openInputStream(contentUri)?.use { input ->
                    input.copyTo(output)
                } ?: error("Unable to read selected image")
                output.write("\r\n--$boundary--\r\n".toByteArray())
            }

            val status = connection.responseCode
            val body = (if (status in 200..299) connection.inputStream else connection.errorStream)
                ?.bufferedReader()
                ?.use { it.readText() }
                .orEmpty()
            if (status !in 200..299) {
                val detail = runCatching { JSONObject(body).optString("detail") }.getOrDefault("")
                error(detail.ifBlank { "Image upload failed ($status)" })
            }
            val payload = JSONObject(body)
            UploadedAttachment(
                id = payload.getString("id"),
                filename = payload.optString("filename", filename),
                contentType = payload.optString("content_type", mimeType),
                fileSize = payload.optLong("file_size", 0L),
                source = source,
            )
        } finally {
            connection.disconnect()
        }
    }

    private fun writeField(output: BufferedOutputStream, boundary: String, name: String, value: String) {
        output.write("--$boundary\r\n".toByteArray())
        output.write("Content-Disposition: form-data; name=\"$name\"\r\n\r\n".toByteArray())
        output.write(value.toByteArray())
        output.write("\r\n".toByteArray())
    }

    private fun displayName(context: Context, uri: Uri): String {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) {
                val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (index >= 0) return cursor.getString(index)
            }
        }
        return "lifesnap-capture.png"
    }
}
