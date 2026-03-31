package com.malte_hinrichs.learn_ai

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.atomic.AtomicInteger

/**
 * Foreground service that subscribes to ntfy topics via SSE and shows Android notifications.
 *
 * Topics subscribed:
 *  - Learn-AI-Notifications (global channel, always)
 *  - Learn-AI-<user_id_prefix> (personal channel, set via EXTRA_USER_TOPIC after login)
 */
class NtfyListenerService : Service() {

    companion object {
        const val EXTRA_USER_TOPIC = "user_topic"
        private const val NTFY_SERVER = "https://ntfy.malte-hinrichs.de"
        private const val GLOBAL_TOPIC = "Learn-AI-Notifications"
        private const val SERVICE_CHANNEL_ID = "LearnAI_ServiceChannel"
        private const val NOTIF_CHANNEL_ID = "LearnAI_Notifications"
        private val notifCounter = AtomicInteger(2000)
        private val TAG = "NtfyListenerService"
    }

    private val threads = mutableListOf<Thread>()
    private val subscribedTopics = mutableSetOf<String>()
    private val shownMessageIds = mutableSetOf<String>()

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Start as foreground service with a silent persistent notification
        startForeground(1, buildServiceNotification())

        // Always subscribe to the global channel
        subscribeIfNew(GLOBAL_TOPIC)

        // If a personal user topic was provided, subscribe to it too
        intent?.getStringExtra(EXTRA_USER_TOPIC)?.takeIf { it.isNotEmpty() }?.let {
            subscribeIfNew(it)
        }

        return START_STICKY
    }

    private fun subscribeIfNew(topic: String) {
        if (subscribedTopics.contains(topic)) return
        subscribedTopics.add(topic)
        Log.d(TAG, "Subscribing to topic: $topic")

        val thread = Thread {
            while (!Thread.currentThread().isInterrupted) {
                try {
                    val url = URL("$NTFY_SERVER/$topic/json?since=10m")
                    val conn = url.openConnection() as HttpURLConnection
                    conn.apply {
                        requestMethod = "GET"
                        setRequestProperty("Accept", "application/x-ndjson")
                        connectTimeout = 30_000
                        readTimeout = 0  // keep-alive for SSE / NDJSON stream
                        connect()
                    }

                    BufferedReader(InputStreamReader(conn.inputStream)).use { reader ->
                        var line: String?
                        while (reader.readLine().also { line = it } != null
                            && !Thread.currentThread().isInterrupted
                        ) {
                            line?.takeIf { it.isNotBlank() }?.let { handleMessage(it) }
                        }
                    }
                    conn.disconnect()
                } catch (e: InterruptedException) {
                    Thread.currentThread().interrupt()
                    break
                } catch (e: Exception) {
                    Log.w(TAG, "Stream error for $topic, retrying in 10s: ${e.message}")
                    try { Thread.sleep(10_000) } catch (_: InterruptedException) { break }
                }
            }
            Log.d(TAG, "Thread for $topic stopped")
        }
        thread.isDaemon = true
        thread.start()
        threads.add(thread)
    }

    private fun handleMessage(raw: String) {
        try {
            val json = JSONObject(raw)
            // ntfy sends "open", "keepalive" and "message" events
            if (json.optString("event") != "message") return

            val msgId = json.optString("id")
            if (msgId.isNotEmpty()) {
                if (shownMessageIds.contains(msgId)) return
                shownMessageIds.add(msgId)
                if (shownMessageIds.size > 100) {
                    shownMessageIds.iterator().also { it.next(); it.remove() }
                }
            }

            val title = json.optString("title").ifEmpty { "Learn AI" }
            val body = json.optString("message").takeIf { it.isNotEmpty() } ?: return

            showNotification(title, body)
        } catch (e: Exception) {
            // silently ignore JSON parse errors (e.g. keepalive lines)
        }
    }

    private fun showNotification(title: String, body: String) {
        val id = notifCounter.getAndIncrement()
        val notif = NotificationCompat.Builder(this, NOTIF_CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .build()

        try {
            NotificationManagerCompat.from(this).notify(id, notif)
        } catch (e: SecurityException) {
            Log.w(TAG, "POST_NOTIFICATIONS permission not granted")
        }
    }

    private fun buildServiceNotification(): Notification =
        NotificationCompat.Builder(this, SERVICE_CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("Learn AI")
            .setContentText("Benachrichtigungen aktiv")
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .setOngoing(true)
            .build()

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val mgr = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

            // Low-importance channel for the persistent service notification
            mgr.createNotificationChannel(
                NotificationChannel(SERVICE_CHANNEL_ID, "Dienst (Learn AI)", NotificationManager.IMPORTANCE_MIN)
            )

            // High-importance channel for actual alerts
            mgr.createNotificationChannel(
                NotificationChannel(NOTIF_CHANNEL_ID, "Learn AI Benachrichtigungen", NotificationManager.IMPORTANCE_HIGH).apply {
                    description = "Arbeitsblätter, Hausaufgaben-Erinnerungen und neue Aufgaben"
                }
            )
        }
    }

    override fun onDestroy() {
        threads.forEach { it.interrupt() }
        threads.clear()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
