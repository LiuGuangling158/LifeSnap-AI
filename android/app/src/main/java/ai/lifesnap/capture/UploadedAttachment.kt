package ai.lifesnap.capture

data class UploadedAttachment(
    val id: String,
    val filename: String,
    val contentType: String,
    val fileSize: Long,
    val source: String,
)
