package org.eskaboard.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.Switch
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts

/** Language, the board's tool buttons, and the floating screenshot button. */
@Suppress("UseSwitchCompatOrMaterialCode") // no AppCompat in this app
class SettingsActivity : BaseActivity() {
    private lateinit var floating: Switch
    private var updating = false
    private var enabling = false // between the switch and the last permission answer

    private val overlayPermission = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        if (Settings.canDrawOverlays(this)) askNotifications() else cancelFloating(R.string.overlay_denied)
    }

    // The service's notification; the button works without it, so the answer doesn't matter
    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) {
        askCapture()
    }

    private val capturePermission = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val data = result.data
        if (result.resultCode != RESULT_OK || data == null) {
            cancelFloating(R.string.capture_denied)
            return@registerForActivityResult
        }
        enabling = false
        if (!ShotService.start(this, result.resultCode, data)) cancelFloating(R.string.capture_denied)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)
        padForSystemBars(findViewById(R.id.root))

        setUpLanguage()
        setUpTools()

        floating = findViewById(R.id.floating)
        floating.setOnCheckedChangeListener { _, on ->
            if (updating) return@setOnCheckedChangeListener
            if (on) enableFloating() else stopService(Intent(this, ShotService::class.java))
        }
    }

    override fun onResume() {
        super.onResume()
        // The service may have stopped meanwhile (notification's Stop, "stop sharing")
        if (!enabling) setFloating(ShotService.running)
    }

    private fun setUpLanguage() {
        val group = findViewById<RadioGroup>(R.id.language)
        val ids = mapOf("" to R.id.lang_auto, "ar" to R.id.lang_ar, "fr" to R.id.lang_fr, "en" to R.id.lang_en)
        group.check(ids.getValue(AppSettings.language(this)))
        group.setOnCheckedChangeListener { _, checkedId ->
            val tag = ids.entries.first { it.value == checkedId }.key
            if (tag == AppSettings.language(this)) return@setOnCheckedChangeListener
            AppSettings.setLanguage(this, tag)
            recreate() // at once; the screens behind follow when shown again
        }
    }

    private fun setUpTools() {
        val labels = mapOf(
            "enter" to R.string.tool_enter,
            "esc" to R.string.tool_esc,
            "erase" to R.string.tool_erase,
            "copy" to R.string.tool_copy,
            "paste" to R.string.tool_paste,
            "shots" to R.string.tool_shots,
        )
        val container = findViewById<LinearLayout>(R.id.tools)
        val hidden = AppSettings.hiddenTools(this)
        for (tool in AppSettings.TOOLS) {
            val row = layoutInflater.inflate(R.layout.setting_switch, container, false) as Switch
            row.setText(labels.getValue(tool))
            row.isChecked = tool !in hidden
            row.setOnCheckedChangeListener { _, shown -> AppSettings.setToolShown(this, tool, shown) }
            container.addView(row)
        }
    }

    // ---- floating screenshot button: overlay, notifications, then screen capture ----

    private fun enableFloating() {
        enabling = true
        if (Settings.canDrawOverlays(this)) {
            askNotifications()
        } else {
            Toast.makeText(this, R.string.overlay_explain, Toast.LENGTH_LONG).show()
            overlayPermission.launch(
                Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName"))
            )
        }
    }

    private fun askNotifications() {
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            askCapture()
        }
    }

    private fun askCapture() {
        val manager = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        capturePermission.launch(manager.createScreenCaptureIntent())
    }

    private fun cancelFloating(message: Int) {
        enabling = false
        setFloating(false)
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    }

    private fun setFloating(on: Boolean) {
        updating = true
        floating.isChecked = on
        updating = false
    }
}
