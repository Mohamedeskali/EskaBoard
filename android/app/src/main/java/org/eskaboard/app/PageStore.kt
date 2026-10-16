package org.eskaboard.app

import android.content.Context
import androidx.core.content.edit

/** What the page keeps on the phone through the app (EskaBoardApp.storeGet / storeSet). */
object PageStore {
    /** Only these names: the saved texts and the unsent box. */
    val NAMES = setOf("history", "draft")

    /** More than the page ever writes (50 texts of 20 000 characters, as JSON). */
    const val MAX_LENGTH = 2_000_000

    private const val FILE = "page_store"

    private fun prefs(context: Context) = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    fun get(context: Context, name: String): String? =
        if (name in NAMES) prefs(context).getString(name, null) else null

    fun set(context: Context, name: String, value: String) {
        if (!accepts(name, value)) return
        prefs(context).edit { putString(name, value) }
    }

    fun accepts(name: String, value: String): Boolean = name in NAMES && value.length <= MAX_LENGTH
}
