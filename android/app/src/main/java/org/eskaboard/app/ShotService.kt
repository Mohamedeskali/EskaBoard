package org.eskaboard.app

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.graphics.drawable.Icon
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.Looper
import android.util.Base64
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.WindowManager
import android.widget.ImageView
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.core.content.edit
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.abs

/**
 * The floating screenshot button: a round button over every app. A tap takes
 * a screenshot of the phone (without the button), puts it on the phone's
 * clipboard and, when the board page is connected, sends it to the PC's
 * clipboard through the page's encrypted session.
 *
 * Runs as a foreground service (type mediaProjection) with a notification.
 * The screen-capture consent is given once when the service starts; Android
 * 14+ allows one virtual display per consent, so it stays open while the
 * service runs and a tap reads its latest frame.
 */
class ShotService : Service() {
    private val main = Handler(Looper.getMainLooper())
    private lateinit var captureThread: HandlerThread
    private lateinit var capture: Handler // ImageReader callbacks and PNG encoding

    private var projection: MediaProjection? = null
    private var display: VirtualDisplay? = null
    private var reader: ImageReader? = null
    private var latest: Image? = null // capture thread only
    private var width = 0
    private var height = 0

    private lateinit var windows: WindowManager
    private var button: ImageView? = null
    private var params: WindowManager.LayoutParams? = null
    private var busy = false

    override fun attachBaseContext(newBase: Context) {
        super.attachBaseContext(AppSettings.wrap(newBase))
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        windows = getSystemService(WINDOW_SERVICE) as WindowManager
        captureThread = HandlerThread("eskaboard-shot").also { it.start() }
        capture = Handler(captureThread.looper)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (projection != null) return START_NOT_STICKY // already running

        val code = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
        val data: Intent? = if (Build.VERSION.SDK_INT >= 33) {
            intent?.getParcelableExtra(EXTRA_RESULT_DATA, Intent::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent?.getParcelableExtra(EXTRA_RESULT_DATA)
        }
        // Foreground first: Android 14+ refuses the projection otherwise
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFICATION_ID, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else {
            startForeground(NOTIFICATION_ID, notification())
        }
        val manager = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        val mp = if (data != null && code != 0) {
            try {
                manager.getMediaProjection(code, data)
            } catch (e: Exception) {
                null
            }
        } else {
            null
        }
        if (mp == null || !android.provider.Settings.canDrawOverlays(this)) {
            stopSelf()
            return START_NOT_STICKY
        }
        projection = mp
        // Ended from the system (the "stop sharing" chip, screen lock on some phones)
        mp.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() {
                main.post { stopSelf() }
            }
        }, main)
        startCapture()
        showButton()
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        running = false
        button?.let { runCatching { windows.removeView(it) } }
        button = null
        display?.release()
        display = null
        projection?.stop()
        projection = null
        capture.post {
            latest?.close()
            latest = null
            reader?.close()
            reader = null
        }
        captureThread.quitSafely()
        super.onDestroy()
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        // Rotation: capture at the new size, and keep the button on screen
        val (w, h, dpi) = screenSize()
        if (w != width || h != height) {
            width = w
            height = h
            capture.post {
                val old = reader
                val next = newReader(w, h)
                display?.resize(w, h, dpi)
                display?.surface = next.surface
                latest?.close()
                latest = null
                old?.close()
                reader = next
            }
        }
        params?.let { placeButton(it.x, it.y) }
    }

    // ---- capture ----

    private fun screenSize(): Triple<Int, Int, Int> {
        val dpi = resources.displayMetrics.densityDpi
        return if (Build.VERSION.SDK_INT >= 30) {
            val bounds = windows.maximumWindowMetrics.bounds
            Triple(bounds.width(), bounds.height(), dpi)
        } else {
            val metrics = android.util.DisplayMetrics()
            @Suppress("DEPRECATION")
            windows.defaultDisplay.getRealMetrics(metrics)
            Triple(metrics.widthPixels, metrics.heightPixels, dpi)
        }
    }

    private fun startCapture() {
        val (w, h, dpi) = screenSize()
        width = w
        height = h
        val first = newReader(w, h)
        reader = first
        display = projection?.createVirtualDisplay(
            "EskaBoard screenshot", w, h, dpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            first.surface, null, capture,
        )
    }

    /** Keeps only the newest frame; frames come when the screen changes. */
    private fun newReader(w: Int, h: Int): ImageReader =
        ImageReader.newInstance(w, h, PixelFormat.RGBA_8888, 3).apply {
            setOnImageAvailableListener({ r ->
                if (r !== reader) return@setOnImageAvailableListener
                val image = try {
                    r.acquireLatestImage()
                } catch (e: IllegalStateException) {
                    null
                } ?: return@setOnImageAvailableListener
                latest?.close()
                latest = image
            }, capture)
        }

    private fun takeScreenshot() {
        if (busy) return
        busy = true
        // Hidden while the frame is taken: hiding it changes the screen, so
        // the newest frame after the delay is the screen without the button
        button?.visibility = View.INVISIBLE
        capture.postDelayed({
            val bitmap = latest?.let(::toBitmap)
            main.post { button?.visibility = View.VISIBLE }
            if (bitmap == null) {
                main.post { done(getString(R.string.shot_failed)) }
                return@postDelayed
            }
            val file = try {
                save(bitmap)
            } catch (e: Exception) {
                null
            } finally {
                bitmap.recycle()
            }
            if (file == null) {
                main.post { done(getString(R.string.shot_failed)) }
                return@postDelayed
            }
            val base64 = if (file.length() <= MAX_SEND_BYTES) {
                Base64.encodeToString(file.readBytes(), Base64.NO_WRAP)
            } else {
                null
            }
            main.post { deliver(file, base64) }
        }, HIDE_MS)
    }

    private fun toBitmap(image: Image): Bitmap {
        val plane = image.planes[0]
        val buffer = plane.buffer.apply { rewind() }
        val rowPixels = plane.rowStride / plane.pixelStride // rows may be padded
        val padded = Bitmap.createBitmap(rowPixels, image.height, Bitmap.Config.ARGB_8888)
        padded.copyPixelsFromBuffer(buffer)
        if (rowPixels == image.width) return padded
        val exact = Bitmap.createBitmap(padded, 0, 0, image.width, image.height)
        padded.recycle()
        return exact
    }

    /** cache/shots/Screenshot_….png; only the last few are kept. */
    private fun save(bitmap: Bitmap): File {
        val dir = File(cacheDir, "shots").apply { mkdirs() }
        dir.listFiles()?.sortedByDescending { it.lastModified() }?.drop(KEEP_SHOTS - 1)?.forEach { it.delete() }
        val name = "Screenshot_${SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())}.png"
        val file = File(dir, name)
        file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        return file
    }

    /** Main thread: phone clipboard, then the PC if the board page is connected. */
    private fun deliver(file: File, base64: String?) {
        val uri = FileProvider.getUriForFile(this, "$packageName.shots", file)
        val clipboard = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newUri(contentResolver, getString(R.string.shot_clip_label), uri))
        if (base64 == null) {
            done(getString(R.string.shot_copied_too_big))
            return
        }
        BoardBridge.sendImage(base64) { sent ->
            done(getString(if (sent) R.string.shot_copied_sent else R.string.shot_copied_only))
        }
    }

    private fun done(message: String) {
        busy = false
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }

    // ---- floating button ----

    @SuppressLint("ClickableViewAccessibility")
    private fun showButton() {
        val size = (BUTTON_DP * resources.displayMetrics.density).toInt()
        val view = ImageView(this).apply {
            setImageResource(R.drawable.ic_camera)
            setBackgroundResource(R.drawable.float_button)
            val pad = size / 4
            setPadding(pad, pad, pad, pad)
            contentDescription = getString(R.string.shot_button)
            elevation = 6 * resources.displayMetrics.density
        }
        @Suppress("DEPRECATION")
        val type = if (Build.VERSION.SDK_INT >= 26) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            WindowManager.LayoutParams.TYPE_PHONE
        }
        val lp = WindowManager.LayoutParams(
            size, size, type,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        ).apply { gravity = Gravity.TOP or Gravity.START }
        params = lp

        val prefs = getSharedPreferences("floating", MODE_PRIVATE)
        val slop = ViewConfiguration.get(this).scaledTouchSlop
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
                    startX = lp.x
                    startY = lp.y
                    dragging = false
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = e.rawX - downX
                    val dy = e.rawY - downY
                    if (dragging || abs(dx) > slop || abs(dy) > slop) {
                        dragging = true
                        placeButton(startX + dx.toInt(), startY + dy.toInt())
                    }
                }
                MotionEvent.ACTION_UP -> {
                    if (dragging) {
                        prefs.edit { putInt("x", lp.x).putInt("y", lp.y) }
                    } else {
                        view.performClick()
                        takeScreenshot()
                    }
                }
            }
            true
        }
        button = view
        val (w, h, _) = screenSize()
        windows.addView(view, lp)
        placeButton(prefs.getInt("x", w - size - size / 3), prefs.getInt("y", h / 3))
    }

    /** Moves the button, kept fully on screen. */
    private fun placeButton(x: Int, y: Int) {
        val view = button ?: return
        val lp = params ?: return
        val (w, h, _) = screenSize()
        lp.x = x.coerceIn(0, (w - lp.width).coerceAtLeast(0))
        lp.y = y.coerceIn(0, (h - lp.height).coerceAtLeast(0))
        runCatching { windows.updateViewLayout(view, lp) }
    }

    // ---- notification ----

    private fun notification(): Notification {
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL, getString(R.string.shot_channel), NotificationManager.IMPORTANCE_LOW)
            )
        }
        val flags = PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        val open = PendingIntent.getActivity(this, 0, Intent(this, SettingsActivity::class.java), flags)
        val stop = PendingIntent.getService(this, 1, Intent(this, ShotService::class.java).setAction(ACTION_STOP), flags)
        val builder = if (Build.VERSION.SDK_INT >= 26) {
            Notification.Builder(this, CHANNEL)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }
        return builder
            .setSmallIcon(R.drawable.ic_camera)
            .setContentTitle(getString(R.string.shot_notification_title))
            .setContentText(getString(R.string.shot_notification_text))
            .setContentIntent(open)
            .setOngoing(true)
            .addAction(Notification.Action.Builder(Icon.createWithResource(this, R.drawable.ic_camera), getString(R.string.shot_stop), stop).build())
            .build()
    }

    companion object {
        /** True from start() until the service ends (the Settings switch follows it). */
        @Volatile
        var running = false
            private set

        /** Starts the service with the screen-capture consent; false if Android refused. */
        fun start(context: Context, resultCode: Int, data: Intent): Boolean {
            running = true
            return try {
                ContextCompat.startForegroundService(
                    context,
                    Intent(context, ShotService::class.java)
                        .putExtra(EXTRA_RESULT_CODE, resultCode)
                        .putExtra(EXTRA_RESULT_DATA, data),
                )
                true
            } catch (e: Exception) {
                running = false
                false
            }
        }

        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"
        const val ACTION_STOP = "org.eskaboard.app.STOP_SHOT"
        private const val CHANNEL = "floating_shot"
        private const val NOTIFICATION_ID = 1
        private const val BUTTON_DP = 56
        private const val HIDE_MS = 300L
        private const val KEEP_SHOTS = 5
        // The PC accepts PNGs up to 16 MB (phonekb/screenshot.py); a screenshot is a few MB
        private const val MAX_SEND_BYTES = 12L shl 20
    }
}
