# Keep WebView JavaScript interface (not used here, but safe to have)
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
# Keep AppCompat and WebKit
-keep class androidx.webkit.** { *; }
