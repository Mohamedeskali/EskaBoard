package org.eskaboard.app

import java.lang.ref.WeakReference

/**
 * Lets the floating screenshot button reach the open board page, whose
 * encrypted session is the only way to the PC (one phone at a time: a second
 * connection would push the page out).
 */
object BoardBridge {
    private var board = WeakReference<BoardActivity>(null)

    fun attach(activity: BoardActivity) {
        board = WeakReference(activity)
    }

    fun detach(activity: BoardActivity) {
        if (board.get() === activity) board.clear()
    }

    /** Main thread. [done] gets true once the page sent the image to the PC. */
    fun sendImage(base64Png: String, done: (Boolean) -> Unit) {
        val activity = board.get()
        if (activity == null || activity.isFinishing || activity.isDestroyed) {
            done(false)
            return
        }
        activity.sendImage(base64Png, done)
    }
}
