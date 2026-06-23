package com.flipperboards.display

import android.annotation.SuppressLint
import android.content.Context
import android.content.SharedPreferences
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.WindowInsetsController
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.*
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONArray
import java.net.URL
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var configButton: ImageButton
    private lateinit var prefs: SharedPreferences
    private val hideHandler = Handler(Looper.getMainLooper())
    private val hideRunnable = Runnable { hideConfigButton() }
    private val HIDE_DELAY_MS = 3000L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences("flipper_prefs", Context.MODE_PRIVATE)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webView)
        configButton = findViewById(R.id.configButton)

        setupWebView()
        setupImmersiveMode()
        setupConfigButton()

        val savedUrl = prefs.getString("server_url", "") ?: ""
        val savedScreen = prefs.getString("screen_id", "") ?: ""

        if (savedUrl.isBlank()) {
            showConfigDialog()
        } else {
            loadDisplay(savedUrl, savedScreen)
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            loadWithOverviewMode = true
            useWideViewPort = true
            cacheMode = WebSettings.LOAD_DEFAULT
        }
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest) = false
        }
        webView.setOnClickListener { showConfigButtonTemporarily() }
    }

    private fun setupImmersiveMode() {
        window.decorView.windowInsetsController?.let { controller ->
            controller.hide(
                android.view.WindowInsets.Type.statusBars() or
                android.view.WindowInsets.Type.navigationBars()
            )
            controller.systemBarsBehavior =
                WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
    }

    private fun setupConfigButton() {
        configButton.alpha = 0f
        configButton.setOnClickListener { showConfigDialog() }
        webView.setOnTouchListener { _, _ ->
            showConfigButtonTemporarily()
            false
        }
    }

    private fun showConfigButtonTemporarily() {
        hideHandler.removeCallbacks(hideRunnable)
        configButton.animate().alpha(1f).setDuration(200).start()
        hideHandler.postDelayed(hideRunnable, HIDE_DELAY_MS)
    }

    private fun hideConfigButton() {
        configButton.animate().alpha(0f).setDuration(500).start()
    }

    private fun loadDisplay(serverUrl: String, screenId: String) {
        val base = serverUrl.trimEnd('/')
        val soundParam = if (prefs.getBoolean("sound_enabled", true)) "1" else "0"
        val url = buildString {
            append("$base/display?kiosk=1")
            if (screenId.isNotBlank()) append("&screen=$screenId")
            append("&sound=$soundParam")
        }
        webView.loadUrl(url)
    }

    private fun showConfigDialog() {
        showConfigButtonTemporarily()

        val dialogView = layoutInflater.inflate(R.layout.dialog_config, null)
        val urlInput = dialogView.findViewById<EditText>(R.id.urlInput)
        val screenSpinner = dialogView.findViewById<Spinner>(R.id.screenSpinner)
        val fetchButton = dialogView.findViewById<Button>(R.id.fetchScreensButton)
        val statusText = dialogView.findViewById<TextView>(R.id.statusText)
        val soundSwitch = dialogView.findViewById<Switch>(R.id.soundSwitch)

        val currentUrl = prefs.getString("server_url", "") ?: ""
        val currentScreen = prefs.getString("screen_id", "") ?: ""
        urlInput.setText(currentUrl)
        soundSwitch.isChecked = prefs.getBoolean("sound_enabled", true)

        val screenOptions = mutableListOf("Default (no screen)")
        val screenIds = mutableListOf("")
        var selectedIndex = 0

        val spinnerAdapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, screenOptions)
        spinnerAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        screenSpinner.adapter = spinnerAdapter

        screenSpinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>, view: View?, pos: Int, id: Long) {
                selectedIndex = pos
            }
            override fun onNothingSelected(parent: AdapterView<*>) {}
        }

        fetchButton.setOnClickListener {
            val url = urlInput.text.toString().trimEnd('/')
            if (url.isBlank()) {
                statusText.text = "Enter a server URL first"
                return@setOnClickListener
            }
            statusText.text = "Fetching screens..."
            thread {
                try {
                    val response = URL("$url/api/screens").readText()
                    val json = JSONArray(response)
                    val names = mutableListOf("Default (no screen)")
                    val ids = mutableListOf("")
                    for (i in 0 until json.length()) {
                        val obj = json.getJSONObject(i)
                        names.add(obj.optString("name", "Screen ${obj.optInt("id")}"))
                        ids.add(obj.optString("id", obj.optInt("id").toString()))
                    }
                    runOnUiThread {
                        screenOptions.clear(); screenOptions.addAll(names)
                        screenIds.clear(); screenIds.addAll(ids)
                        spinnerAdapter.notifyDataSetChanged()
                        val savedIdx = ids.indexOf(currentScreen)
                        if (savedIdx >= 0) screenSpinner.setSelection(savedIdx)
                        statusText.text = "Found ${json.length()} screen(s)"
                    }
                } catch (e: Exception) {
                    runOnUiThread { statusText.text = "Error: ${e.message}" }
                }
            }
        }

        AlertDialog.Builder(this)
            .setTitle("FlipperBoards Config")
            .setView(dialogView)
            .setPositiveButton("Save") { _, _ ->
                val newUrl = urlInput.text.toString().trim()
                val newScreen = if (selectedIndex < screenIds.size) screenIds[selectedIndex] else ""
                prefs.edit()
                    .putString("server_url", newUrl)
                    .putString("screen_id", newScreen)
                    .putBoolean("sound_enabled", soundSwitch.isChecked)
                    .apply()
                if (newUrl.isNotBlank()) loadDisplay(newUrl, newScreen)
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) setupImmersiveMode()
    }
}
