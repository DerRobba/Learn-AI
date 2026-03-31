package com.malte_hinrichs.learn_ai

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import java.util.concurrent.atomic.AtomicInteger

class LearnAIFirebaseMessagingService : FirebaseMessagingService() {

    companion object {
        private const val NOTIF_CHANNEL_ID = "LearnAI_Notifications"
        private val notifCounter = AtomicInteger(3000)
        private const val TAG = "FCMService"
    }

    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        val title = remoteMessage.notification?.title
            ?: remoteMessage.data["title"]
            ?: "Learn AI"
        val body = remoteMessage.notification?.body
            ?: remoteMessage.data["message"]
            ?: return

        Log.d(TAG, "FCM message received: $title")
        createNotificationChannel()
        showNotification(title, body)
    }

    override fun onNewToken(token: String) {
        Log.d(TAG, "FCM token refreshed")
        getSharedPreferences("fcm", MODE_PRIVATE).edit()
            .putString("token", token)
            .putBoolean("needs_upload", true)
            .apply()
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

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val mgr = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            if (mgr.getNotificationChannel(NOTIF_CHANNEL_ID) == null) {
                mgr.createNotificationChannel(
                    NotificationChannel(
                        NOTIF_CHANNEL_ID,
                        "Learn AI Benachrichtigungen",
                        NotificationManager.IMPORTANCE_HIGH
                    ).apply {
                        description = "Arbeitsblätter, Hausaufgaben-Erinnerungen und neue Aufgaben"
                    }
                )
            }
        }
    }
}
