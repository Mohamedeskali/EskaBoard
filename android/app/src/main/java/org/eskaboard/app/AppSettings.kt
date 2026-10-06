package org.eskaboard.app

import android.content.Context
import android.content.res.Configuration
import androidx.core.content.edit
import java.util.Locale

/** The app's own settings (Settings screen). */
object AppSettings {
    /** "" follows the phone's language. */
    val LANGUAGES = listOf("", "ar", "fr", "en")

    /** The page's tool buttons that can be hidden (data-tool in phonekb/static/index.html). */
    val TOOLS = listOf("enter", "esc", "erase", "copy", "paste", "files", "shots")

    private const val FILE = "settings"
    private const val KEY_LANGUAGE = "language"
    private const val KEY_HIDDEN = "hidden_tools"
    private const val KEY_AUTO_PASTE = "auto_paste"

    private fun prefs(context: Context) = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    fun language(context: Context): String =
        prefs(context).getString(KEY_LANGUAGE, "").orEmpty().takeIf { it in LANGUAGES }.orEmpty()

    fun setLanguage(context: Context, tag: String) {
        require(tag in LANGUAGES)
        prefs(context).edit { putString(KEY_LANGUAGE, tag) }
    }

    fun hiddenTools(context: Context): Set<String> =
        prefs(context).getStringSet(KEY_HIDDEN, emptySet()).orEmpty().filterTo(mutableSetOf()) { it in TOOLS }

    fun setToolShown(context: Context, tool: String, shown: Boolean) {
        require(tool in TOOLS)
        val hidden = hiddenTools(context).toMutableSet()
        if (shown) hidden.remove(tool) else hidden.add(tool)
        prefs(context).edit { putStringSet(KEY_HIDDEN, hidden) }
    }

    /** A screenshot or photo that reaches the PC's clipboard is pasted there too (Ctrl+V). */
    fun autoPaste(context: Context): Boolean = prefs(context).getBoolean(KEY_AUTO_PASTE, false)

    fun setAutoPaste(context: Context, on: Boolean) {
        prefs(context).edit { putBoolean(KEY_AUTO_PASTE, on) }
    }

    /** What the page reads through EskaBoardApp.settings(). */
    fun pageJson(context: Context): String = pageJson(language(context), hiddenTools(context), autoPaste(context))

    /** Only known values go in, so no escaping is needed. */
    fun pageJson(language: String, hidden: Set<String>, autoPaste: Boolean = false): String {
        val lang = language.takeIf { it in LANGUAGES }.orEmpty()
        val tools = TOOLS.filter { it in hidden }.joinToString(",") { "\"$it\"" }
        return """{"lang":"$lang","hidden":[$tools],"autoPaste":$autoPaste}"""
    }

    /** [base] with the chosen language (unchanged when it follows the phone). */
    fun wrap(base: Context): Context {
        val tag = language(base)
        if (tag.isEmpty()) return base
        val locale = Locale.forLanguageTag(tag)
        val config = Configuration(base.resources.configuration)
        config.setLocale(locale)
        config.setLayoutDirection(locale)
        return base.createConfigurationContext(config)
    }
}
