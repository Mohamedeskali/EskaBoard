package org.eskaboard.app

import android.view.View
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

/** Keeps [view]'s content clear of the status bar, navigation bar, notch and keyboard. */
fun padForSystemBars(view: View) {
    ViewCompat.setOnApplyWindowInsetsListener(view) { v, insets ->
        val i = insets.getInsets(
            WindowInsetsCompat.Type.systemBars() or
                WindowInsetsCompat.Type.displayCutout() or
                WindowInsetsCompat.Type.ime()
        )
        v.setPadding(i.left, i.top, i.right, i.bottom)
        WindowInsetsCompat.CONSUMED
    }
}
