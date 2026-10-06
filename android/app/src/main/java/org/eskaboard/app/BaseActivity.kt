package org.eskaboard.app

import android.content.Context
import androidx.activity.ComponentActivity

/** Shows the app in the language chosen in Settings, and follows a change at once. */
abstract class BaseActivity : ComponentActivity() {
    private var shownLanguage: String? = null

    override fun attachBaseContext(newBase: Context) {
        shownLanguage = AppSettings.language(newBase)
        super.attachBaseContext(AppSettings.wrap(newBase))
    }

    override fun onResume() {
        super.onResume()
        if (AppSettings.language(this) != shownLanguage) onLanguageChanged()
    }

    /** The language was changed in Settings while this screen was behind it. */
    protected open fun onLanguageChanged() {
        recreate()
    }
}
