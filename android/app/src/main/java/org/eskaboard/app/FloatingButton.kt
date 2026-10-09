package org.eskaboard.app

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.PixelFormat
import android.os.Build
import android.view.Gravity
import android.view.MotionEvent
import android.view.ViewConfiguration
import android.view.WindowManager
import android.widget.ImageView
import androidx.core.content.edit
import kotlin.math.abs

/**
 * A round button over every app (needs "Display over other apps"). Drag it
 * anywhere; its place is remembered under [prefsName]. A tap calls [onTap].
 */
class FloatingButton(
    private val context: Context,
    icon: Int,
    description: String,
    private val prefsName: String,
    /** Where it first appears, as a fraction of the screen height. */
    private val startY: Float,
    private val onTap: () -> Unit,
) {
    private val windows = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    private val size = (BUTTON_DP * context.resources.displayMetrics.density).toInt()
    val view: ImageView = ImageView(context).apply {
        setImageResource(icon)
        setBackgroundResource(R.drawable.float_button)
        val pad = size / 4
        setPadding(pad, pad, pad, pad)
        contentDescription = description
        elevation = 6 * context.resources.displayMetrics.density
    }
    private val params: WindowManager.LayoutParams
    private var shown = false

    init {
        @Suppress("DEPRECATION")
        val type = if (Build.VERSION.SDK_INT >= 26) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            WindowManager.LayoutParams.TYPE_PHONE
        }
        params = WindowManager.LayoutParams(
            size, size, type,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        ).apply { gravity = Gravity.TOP or Gravity.START }
        listenForTouches()
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun listenForTouches() {
        val prefs = context.getSharedPreferences(prefsName, Context.MODE_PRIVATE)
        val slop = ViewConfiguration.get(context).scaledTouchSlop
        var downX = 0f
        var downY = 0f
        var startX = 0
        var startY = 0
        var dragging = false
        view.setOnTouchListener { _, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downX = e.rawX
                    downY = e.rawY
                    startX = params.x
                    startY = params.y
                    dragging = false
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = e.rawX - downX
                    val dy = e.rawY - downY
                    if (dragging || abs(dx) > slop || abs(dy) > slop) {
                        dragging = true
                        place(startX + dx.toInt(), startY + dy.toInt())
                    }
                }
                MotionEvent.ACTION_UP -> {
                    if (dragging) {
                        prefs.edit { putInt("x", params.x).putInt("y", params.y) }
                    } else {
                        view.performClick()
                        onTap()
                    }
                }
            }
            true
        }
    }

    fun show() {
        if (shown) return
        val prefs = context.getSharedPreferences(prefsName, Context.MODE_PRIVATE)
        val (w, h) = screenSize()
        windows.addView(view, params)
        shown = true
        place(prefs.getInt("x", w - size - size / 3), prefs.getInt("y", (h * startY).toInt()))
    }

    fun remove() {
        if (!shown) return
        shown = false
        runCatching { windows.removeView(view) }
    }

    /** After a rotation: keep it on screen. */
    fun keepOnScreen() = place(params.x, params.y)

    /** Moves the button, kept fully on screen. */
    private fun place(x: Int, y: Int) {
        if (!shown) return
        val (w, h) = screenSize()
        params.x = x.coerceIn(0, (w - params.width).coerceAtLeast(0))
        params.y = y.coerceIn(0, (h - params.height).coerceAtLeast(0))
        runCatching { windows.updateViewLayout(view, params) }
    }

    private fun screenSize(): Pair<Int, Int> =
        if (Build.VERSION.SDK_INT >= 30) {
            val bounds = windows.maximumWindowMetrics.bounds
            bounds.width() to bounds.height()
        } else {
            val metrics = android.util.DisplayMetrics()
            @Suppress("DEPRECATION")
            windows.defaultDisplay.getRealMetrics(metrics)
            metrics.widthPixels to metrics.heightPixels
        }

    companion object {
        private const val BUTTON_DP = 56
    }
}
