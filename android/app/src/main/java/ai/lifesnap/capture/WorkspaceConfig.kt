package ai.lifesnap.capture

import android.content.Context
import android.net.Uri

object WorkspaceConfig {
    private const val PREFS = "lifesnap_android_capture"
    private const val BASE_URL = "base_url"

    fun baseUrl(context: Context): String {
        val saved = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(BASE_URL, null)
        return normalize(saved ?: BuildConfig.DEFAULT_BACKEND_URL)
    }

    fun saveBaseUrl(context: Context, value: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(BASE_URL, normalize(value))
            .apply()
    }

    fun normalize(value: String): String {
        val trimmed = value.trim().trimEnd('/')
        val parsed = Uri.parse(trimmed)
        require(parsed.scheme == "http" || parsed.scheme == "https") {
            "LifeSnap server address must start with http:// or https://"
        }
        require(!parsed.host.isNullOrBlank()) { "LifeSnap server address is missing a host" }
        return trimmed
    }
}
