package org.eskaboard.app

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.edit
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions

/** Start screen: scan the QR code, paste the link, or reopen the last PC. */
class MainActivity : BaseActivity() {
    private lateinit var linkInput: EditText
    private lateinit var lastButton: Button
    private lateinit var message: TextView

    private val prefs by lazy { getSharedPreferences(PREFS, Context.MODE_PRIVATE) }

    private val scan = registerForActivityResult(ScanContract()) { result ->
        result.contents?.let { open(it, R.string.not_a_code) } // null: the user went back
    }

    private val board = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val label = lastLink()?.label.orEmpty()
        when (result.resultCode) {
            BoardActivity.RESULT_EXPIRED -> {
                forgetLast()
                showMessage(getString(R.string.expired))
            }
            BoardActivity.RESULT_BLOCKED -> showMessage(getString(R.string.blocked))
            BoardActivity.RESULT_UNREACHABLE -> showMessage(getString(R.string.unreachable, label))
        }
        showLast()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        padForSystemBars(findViewById(R.id.root))

        linkInput = findViewById(R.id.link)
        lastButton = findViewById(R.id.last)
        message = findViewById(R.id.message)

        findViewById<View>(R.id.settings).setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }
        findViewById<Button>(R.id.scan).setOnClickListener { startScan() }
        findViewById<Button>(R.id.connect).setOnClickListener { connectTyped() }
        linkInput.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_GO) {
                connectTyped()
                true
            } else {
                false
            }
        }
        lastButton.setOnClickListener { lastLink()?.let { launch(it) } }

        showLast()
        if (savedInstanceState == null) handleShare(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleShare(intent)
    }

    /** A link shared from another app (a chat, an e-mail…). */
    private fun handleShare(intent: Intent?) {
        if (intent?.action != Intent.ACTION_SEND) return
        val text = intent.getStringExtra(Intent.EXTRA_TEXT) ?: return
        linkInput.setText(text)
        open(text, R.string.not_a_link)
    }

    private fun startScan() {
        hideMessage()
        scan.launch(
            ScanOptions()
                .setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                .setPrompt(getString(R.string.scan_prompt))
                .setBeepEnabled(false)
                .setOrientationLocked(false)
        )
    }

    private fun connectTyped() {
        val text = linkInput.text.toString()
        if (text.isBlank()) {
            showMessage(getString(R.string.empty_link))
            return
        }
        open(text, R.string.not_a_link)
    }

    private fun open(text: String, errorRes: Int) {
        val link = BoardLink.parse(text)
        if (link == null) {
            showMessage(getString(errorRes))
            return
        }
        launch(link)
    }

    private fun launch(link: BoardLink) {
        hideMessage()
        // Kept so the app can reopen this PC while EskaBoard keeps running there
        prefs.edit { putString(KEY_LAST, link.url) }
        showLast()
        board.launch(Intent(this, BoardActivity::class.java).putExtra(BoardActivity.EXTRA_URL, link.url))
    }

    private fun lastLink(): BoardLink? = lastLink(this)

    private fun forgetLast() {
        prefs.edit { remove(KEY_LAST) }
    }

    private fun showLast() {
        val link = lastLink()
        lastButton.visibility = if (link == null) View.GONE else View.VISIBLE
        if (link != null) lastButton.text = getString(R.string.reconnect, link.label)
    }

    private fun showMessage(text: String) {
        message.text = text
        message.visibility = View.VISIBLE
    }

    private fun hideMessage() {
        message.visibility = View.GONE
    }

    private companion object {
        const val KEY_LAST = "last_link"
        private const val PREFS = "eskaboard"

        /** The PC last opened in the app (the floating buttons send there too). */
        fun lastLink(context: Context): BoardLink? =
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_LAST, null)?.let(BoardLink::parse)
    }
}
