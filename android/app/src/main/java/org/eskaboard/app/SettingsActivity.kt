package org.eskaboard.app

import android.os.Bundle
import android.view.View
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.RadioGroup
import android.widget.Switch
import android.widget.TextView
import androidx.activity.enableEdgeToEdge

/** The floating buttons, auto-paste, the board's tool buttons, and the language. */
@Suppress("UseSwitchCompatOrMaterialCode") // no AppCompat in this app
class SettingsActivity : BaseActivity() {
    private lateinit var shot: Switch
    private lateinit var enter: Switch
    private var updating = false

    private val floating = FloatingSetup(this) { showFloating() }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)
        padForSystemBars(findViewById(R.id.root))

        shot = row(R.id.row_shot, R.drawable.ic_camera, R.string.shot_row_title, R.string.shot_row_subtitle) { on ->
            floating.set(FloatingSetup.Kind.SHOT, on)
        }
        enter = row(R.id.row_enter, R.drawable.ic_enter, R.string.enter_row_title, R.string.enter_row_subtitle) { on ->
            floating.set(FloatingSetup.Kind.ENTER, on)
        }
        row(R.id.row_auto_paste, R.drawable.ic_auto_paste, R.string.auto_paste_switch, R.string.auto_paste_subtitle) { on ->
            AppSettings.setAutoPaste(this, on)
        }.isChecked = AppSettings.autoPaste(this)

        setUpTools()
        setUpLanguage()
    }

    override fun onResume() {
        super.onResume()
        // A service may have stopped meanwhile (notification's Stop, "stop sharing")
        showFloating()
    }

    /** Fills an included setting_row; a tap anywhere on it flips its switch. */
    private fun row(id: Int, icon: Int, title: Int, subtitle: Int, onChange: (Boolean) -> Unit): Switch {
        val row = findViewById<View>(id)
        row.findViewById<ImageView>(R.id.row_icon).setImageResource(icon)
        row.findViewById<TextView>(R.id.row_title).setText(title)
        row.findViewById<TextView>(R.id.row_subtitle).setText(subtitle)
        val switch = row.findViewById<Switch>(R.id.row_switch)
        switch.setOnCheckedChangeListener { _, on -> if (!updating) onChange(on) }
        row.setOnClickListener { switch.toggle() }
        row.contentDescription = getString(title)
        return switch
    }

    private fun showFloating() {
        if (floating.busy) return // the switch stays on until the permissions are answered
        updating = true
        shot.isChecked = floating.running(FloatingSetup.Kind.SHOT)
        enter.isChecked = floating.running(FloatingSetup.Kind.ENTER)
        updating = false
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
            "files" to R.string.tool_files,
            "shots" to R.string.tool_shots,
            "float_shot" to R.string.tool_float_shot,
            "float_enter" to R.string.tool_float_enter,
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
}
