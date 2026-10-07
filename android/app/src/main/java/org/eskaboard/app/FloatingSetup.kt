package org.eskaboard.app

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts

/**
 * Turns the floating buttons on and off, from Settings or from the board's
 * top bar: "Display over other apps", the notification permission, then (for
 * the screenshot button) the screen-capture consent, then the service.
 *
 * Create it while [activity] is being constructed (it registers for results).
 * [changed] runs on the main thread once a button was turned on, refused, or off.
 */
class FloatingSetup(private val activity: ComponentActivity, private val changed: (Kind) -> Unit) {
    enum class Kind { SHOT, ENTER }

    private var enabling: Kind? = null // until the last permission answer

    private val overlayPermission = activity.registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        if (Settings.canDrawOverlays(activity)) askNotifications() else cancel(R.string.overlay_denied)
    }

    // The service's notification; the button works without it, so the answer doesn't matter
    private val notificationPermission = activity.registerForActivityResult(ActivityResultContracts.RequestPermission()) {
        afterNotifications()
    }

    private val capturePermission = activity.registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val data = result.data
        if (result.resultCode != Activity.RESULT_OK || data == null) {
            cancel(R.string.capture_denied)
            return@registerForActivityResult
        }
        enabling = null
        if (!ShotService.start(activity, result.resultCode, data)) {
            Toast.makeText(activity, R.string.capture_denied, Toast.LENGTH_LONG).show()
        }
        changed(Kind.SHOT)
    }

    val busy: Boolean get() = enabling != null

    fun running(kind: Kind) = when (kind) {
        Kind.SHOT -> ShotService.running
        Kind.ENTER -> EnterService.running
    }

    fun toggle(kind: Kind) = set(kind, !running(kind))

    fun set(kind: Kind, on: Boolean) {
        if (!on) {
            if (kind == Kind.SHOT) ShotService.stop(activity) else EnterService.stop(activity)
            changed(kind)
            return
        }
        if (running(kind)) return
        enabling?.takeIf { it != kind }?.let(changed) // one at a time: the other one shows its state again
        enabling = kind
        if (Settings.canDrawOverlays(activity)) {
            askNotifications()
        } else {
            Toast.makeText(activity, R.string.overlay_explain, Toast.LENGTH_LONG).show()
            overlayPermission.launch(
                Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:${activity.packageName}"))
            )
        }
    }

    private fun askNotifications() {
        if (Build.VERSION.SDK_INT >= 33 &&
            activity.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            afterNotifications()
        }
    }

    private fun afterNotifications() {
        when (enabling) {
            null -> Unit // the screen was recreated meanwhile
            Kind.SHOT -> {
                val manager = activity.getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
                capturePermission.launch(manager.createScreenCaptureIntent())
            }
            Kind.ENTER -> {
                enabling = null
                if (!EnterService.start(activity)) {
                    Toast.makeText(activity, R.string.floating_failed, Toast.LENGTH_LONG).show()
                }
                changed(Kind.ENTER)
            }
        }
    }

    private fun cancel(message: Int) {
        val kind = enabling ?: return
        enabling = null
        Toast.makeText(activity, message, Toast.LENGTH_LONG).show()
        changed(kind)
    }
}
