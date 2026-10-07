package org.eskaboard.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.content.res.Configuration
import android.graphics.drawable.Icon
import android.os.Build
import android.os.IBinder
import android.view.HapticFeedbackConstants
import android.widget.Toast
import androidx.core.content.ContextCompat

/**
 * The floating Enter button: a round button over every app that presses Enter
 * on the PC through the app's own encrypted connection (PcSender). Runs as a
 * foreground service with a notification, which also keeps the board
 * connected behind other apps (BoardActivity.applyKeepAlive).
 */
class EnterService : Service() {
    private var button: FloatingButton? = null
    private var pending = 0 // taps not answered yet

    override fun attachBaseContext(newBase: Context) {
        super.attachBaseContext(AppSettings.wrap(newBase))
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (button != null) return START_NOT_STICKY // already running
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIFICATION_ID, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(NOTIFICATION_ID, notification())
        }
        if (!android.provider.Settings.canDrawOverlays(this)) {
            stopSelf()
            return START_NOT_STICKY
        }
        button = FloatingButton(this, R.drawable.ic_enter, getString(R.string.enter_button), "floating_enter", 0.5f) {
            pressEnter()
        }.also { it.show() }
        BoardBridge.floatingChanged() // keep the board connected behind other apps
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        running = false
        BoardBridge.floatingChanged()
        button?.remove()
        button = null
        super.onDestroy()
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        button?.keepOnScreen()
    }

    private fun pressEnter() {
        val view = button?.view ?: return
        view.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
        pending++
        view.alpha = 0.6f // waiting for the PC
        PcSender.send(this, listOf(mapOf("type" to "key", "key" to "enter"))) { sent ->
            pending--
            if (pending == 0) button?.view?.alpha = 1f
            if (sent) {
                BoardBridge.keySent() // live mode: the page's text is the PC's now
            } else {
                Toast.makeText(this, R.string.enter_not_sent, Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun notification(): Notification {
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL, getString(R.string.enter_channel), NotificationManager.IMPORTANCE_LOW)
            )
        }
        val flags = PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        val open = PendingIntent.getActivity(this, 0, Intent(this, SettingsActivity::class.java), flags)
        val stop = PendingIntent.getService(this, 1, Intent(this, EnterService::class.java).setAction(ACTION_STOP), flags)
        val builder = if (Build.VERSION.SDK_INT >= 26) {
            Notification.Builder(this, CHANNEL)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }
        return builder
            .setSmallIcon(R.drawable.ic_enter)
            .setContentTitle(getString(R.string.enter_channel))
            .setContentText(getString(R.string.enter_notification_text))
            .setContentIntent(open)
            .setOngoing(true)
            .addAction(Notification.Action.Builder(Icon.createWithResource(this, R.drawable.ic_enter), getString(R.string.shot_stop), stop).build())
            .build()
    }

    companion object {
        /** True from start() until the service ends (the Settings switch follows it). */
        @Volatile
        var running = false
            private set

        /** Stops the service; [running] is false at once (Settings and the board show it). */
        fun stop(context: Context) {
            running = false
            context.stopService(Intent(context, EnterService::class.java))
        }

        /** False if Android refused to start it. */
        fun start(context: Context): Boolean {
            running = true
            return try {
                ContextCompat.startForegroundService(context, Intent(context, EnterService::class.java))
                true
            } catch (e: Exception) {
                running = false
                false
            }
        }

        const val ACTION_STOP = "org.eskaboard.app.STOP_ENTER"
        private const val CHANNEL = "floating_enter"
        private const val NOTIFICATION_ID = 2
    }
}
