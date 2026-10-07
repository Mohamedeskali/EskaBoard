package org.eskaboard.app

import java.lang.ref.WeakReference

/** Lets the floating buttons reach the open board page. */
object BoardBridge {
    private var board = WeakReference<BoardActivity>(null)

    fun attach(activity: BoardActivity) {
        board = WeakReference(activity)
    }

    fun detach(activity: BoardActivity) {
        if (board.get() === activity) board.clear()
    }

    /** A floating button (screenshot or Enter) runs: the board stays connected behind other apps. */
    val keepAlive: Boolean
        get() = ShotService.running || EnterService.running

    /** Main thread: a floating button was turned on or off. */
    fun floatingChanged() {
        board.get()?.floatingChanged()
    }

    /** Main thread: a floating button pressed a key on the PC (the page resets its live text). */
    fun keySent() {
        board.get()?.keySent()
    }
}
