package ai.lifesnap.capture

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class FloatingCaptureActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == ACTION_STOP) {
            context.stopService(Intent(context, FloatingCaptureService::class.java))
        }
    }

    companion object {
        const val ACTION_STOP = "ai.lifesnap.capture.action.STOP_FLOATING_CAPTURE"
    }
}
