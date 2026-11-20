package com.hdt.diettracker;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.SocketTimeoutException;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Supplier;

/**
 * Native bridge for OpenAI-compatible vision requests.
 *
 * <p>Calling the provider from Java avoids WebView CORS restrictions and keeps large base64
 * images out of fetch/XHR. The JS side registers {@code window.__hdtNativeAiResult(id, ok, payload)}.
 */
public class AiBridge {

    /** Hard cap so a hostile or misconfigured endpoint cannot exhaust the heap. */
    private static final int MAX_RESPONSE_BYTES = 5 * 1024 * 1024;

    private final Activity activity;
    private final WebView webView;
    private final Supplier<String> pageUrlSupplier;
    private final String allowedOrigin;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean closed = new AtomicBoolean(false);

    public AiBridge(Activity activity, WebView webView,
                    Supplier<String> pageUrlSupplier, String allowedOrigin) {
        this.activity = activity;
        this.webView = webView;
        this.pageUrlSupplier = pageUrlSupplier;
        this.allowedOrigin = allowedOrigin;
    }

    /**
     * The JS interface is injected into every frame. Only the app's own main document may
     * call it; remote/embedded documents must not be able to use the native HTTP proxy.
     */
    private boolean isTrustedCall() {
        String url = pageUrlSupplier == null ? null : pageUrlSupplier.get();
        return url != null
                && (url.equals(allowedOrigin) || url.startsWith(allowedOrigin + "/"));
    }

    @JavascriptInterface
    public void chat(String requestId, String endpoint, String apiKey, String model,
                     String imageDataUrl, String prompt, String timeoutMs) {
        if (!isTrustedCall()) {
            return;
        }
        submit(requestId, endpoint, apiKey, model, imageDataUrl, prompt, timeoutMs, false);
    }

    @JavascriptInterface
    public void test(String requestId, String endpoint, String apiKey, String model, String timeoutMs) {
        if (!isTrustedCall()) {
            return;
        }
        submit(requestId, endpoint, apiKey, model, null,
                "Reply with the single word OK.", timeoutMs, true);
    }

    /**
     * Search USDA FoodData Central from the native layer (avoids WebView CORS).
     * Results are delivered to {@code window.__hdtUsdaResult(id, ok, payload)}.
     */
    @JavascriptInterface
    public void usdaSearch(String requestId, String query, String apiKey, String pageSize) {
        if (!isTrustedCall() || closed.get()) {
            return;
        }
        final String safeQuery = query == null ? "" : query.trim();
        final String key = (apiKey == null || apiKey.trim().isEmpty()) ? "DEMO_KEY" : apiKey.trim();
        int size = 8;
        try {
            size = Integer.parseInt(pageSize == null ? "" : pageSize.trim());
        } catch (Exception ignored) {
            // keep default
        }
        size = Math.max(1, Math.min(25, size));
        final int page = size;
        executor.execute(() -> {
            boolean ok = false;
            String payload;
            try {
                String url = "https://api.nal.usda.gov/fdc/v1/foods/search?api_key="
                        + URLEncoder.encode(key, "UTF-8")
                        + "&query=" + URLEncoder.encode(safeQuery, "UTF-8")
                        + "&pageSize=" + page
                        + "&dataType=" + URLEncoder.encode("Foundation,SR Legacy,Survey (FNDDS)", "UTF-8");
                HttpResult result = get(url, 15000);
                if (result.status >= 200 && result.status < 300) {
                    ok = true;
                    payload = result.body;
                } else if (result.status == 429) {
                    payload = errorPayload("rate_limited", result.status,
                            "USDA 请求过于频繁，请稍后再试或换用自定义 API Key。", result.body);
                } else if (result.status == 401 || result.status == 403) {
                    payload = errorPayload("auth", result.status,
                            "USDA API Key 无效，请检查设置。", result.body);
                } else {
                    payload = errorPayload(reasonFor(result.status), result.status,
                            "USDA 检索失败（HTTP " + result.status + "）。", result.body);
                }
            } catch (SocketTimeoutException error) {
                payload = errorPayload("timeout", 0, "USDA 检索超时，请检查网络。", "");
            } catch (Exception error) {
                payload = errorPayload("network", 0,
                        "USDA 检索网络失败：" + safeMessage(error), "");
            }
            dispatchTo("__hdtUsdaResult", requestId, ok, payload);
        });
    }

    /**
     * Encrypted secret storage (Android Keystore, AES/GCM). Used for the AI and USDA API keys
     * so they never live in WebView localStorage as plaintext.
     */
    @JavascriptInterface
    public boolean setSecret(String name, String value) {
        return isTrustedCall() && SecureStore.put(activity, name, value);
    }

    @JavascriptInterface
    public String getSecret(String name) {
        return isTrustedCall() ? SecureStore.get(activity, name) : "";
    }

    @JavascriptInterface
    public boolean removeSecret(String name) {
        if (!isTrustedCall()) {
            return false;
        }
        SecureStore.remove(activity, name);
        return true;
    }

    @JavascriptInterface
    public String getVersion() {
        return isTrustedCall() ? "1.0.0" : "";
    }

    @JavascriptInterface
    public void openExternal(String url) {
        if (!isTrustedCall() || url == null) {
            return;
        }
        String lower = url.toLowerCase(Locale.ROOT);
        if (!lower.startsWith("https://")) {
            return;
        }
        activity.runOnUiThread(() -> {
            try {
                Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                activity.startActivity(intent);
            } catch (Exception error) {
                Toast.makeText(activity, "无法打开链接", Toast.LENGTH_SHORT).show();
            }
        });
    }

    @JavascriptInterface
    public void toast(String message) {
        if (!isTrustedCall() || message == null) {
            return;
        }
        activity.runOnUiThread(() ->
                Toast.makeText(activity, message, Toast.LENGTH_SHORT).show());
    }

    private void submit(String requestId, String endpoint, String apiKey, String model,
                        String imageDataUrl, String prompt, String timeoutMs, boolean testOnly) {
        if (closed.get()) {
            return;
        }
        int parsedTimeout = 60_000;
        try {
            parsedTimeout = Math.max(10_000, Math.min(180_000, Integer.parseInt(timeoutMs.trim())));
        } catch (Exception ignored) {
            // keep the default
        }
        final int timeout = parsedTimeout;
        executor.execute(() -> {
            String payload;
            boolean ok;
            try {
                String body = buildRequestBody(model, prompt, imageDataUrl,
                        testOnly ? 16 : 2048, !testOnly);
                HttpResult result = post(endpoint, apiKey, body, timeout);
                // Some OpenAI-compatible providers reject response_format; retry once without it.
                if (!testOnly && result.status == 400 && result.body != null
                        && result.body.contains("response_format")) {
                    body = buildRequestBody(model, prompt, imageDataUrl, 2048, false);
                    result = post(endpoint, apiKey, body, timeout);
                }
                if (result.status >= 200 && result.status < 300) {
                    ok = true;
                    payload = result.body;
                } else {
                    ok = false;
                    payload = errorPayload(reasonFor(result.status), result.status,
                            messageFor(result.status), result.body);
                }
            } catch (SocketTimeoutException error) {
                ok = false;
                payload = errorPayload("timeout", 0, "请求超时，请检查网络或稍后重试。", "");
            } catch (Exception error) {
                ok = false;
                payload = errorPayload("network", 0,
                        "网络请求失败：" + safeMessage(error), "");
            }
            dispatch(requestId, ok, payload, testOnly);
        });
    }

    private String buildRequestBody(String model, String prompt, String imageDataUrl,
                                    int maxTokens, boolean jsonFormat) throws Exception {
        JSONObject body = new JSONObject();
        body.put("model", model == null ? "" : model.trim());

        JSONArray content = new JSONArray();
        JSONObject textPart = new JSONObject();
        textPart.put("type", "text");
        textPart.put("text", prompt == null ? "" : prompt);
        content.put(textPart);

        if (imageDataUrl != null && !imageDataUrl.isEmpty()) {
            JSONObject imageUrl = new JSONObject();
            imageUrl.put("url", imageDataUrl);
            JSONObject imagePart = new JSONObject();
            imagePart.put("type", "image_url");
            imagePart.put("image_url", imageUrl);
            content.put(imagePart);
        }

        JSONObject message = new JSONObject();
        message.put("role", "user");
        message.put("content", content);

        JSONArray messages = new JSONArray();
        messages.put(message);

        body.put("messages", messages);
        body.put("temperature", 0);
        body.put("max_tokens", maxTokens);
        if (jsonFormat) {
            JSONObject format = new JSONObject();
            format.put("type", "json_object");
            body.put("response_format", format);
        }
        return body.toString();
    }

    private static final class HttpResult {
        final int status;
        final String body;

        HttpResult(int status, String body) {
            this.status = status;
            this.body = body;
        }
    }

    private HttpResult post(String endpoint, String apiKey, String body, int timeout)
            throws Exception {
        String url = chatUrl(endpoint);
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        connection.setRequestMethod("POST");
        connection.setConnectTimeout(Math.min(timeout, 20_000));
        connection.setReadTimeout(timeout);
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("User-Agent", "HealthyDietTracker-Android/1.0");
        if (apiKey != null && !apiKey.isEmpty()) {
            connection.setRequestProperty("Authorization", "Bearer " + apiKey.trim());
        }
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(bytes.length);
        try (OutputStream output = connection.getOutputStream()) {
            output.write(bytes);
        }

        int status = connection.getResponseCode();
        InputStream input = status >= 200 && status < 300
                ? connection.getInputStream()
                : connection.getErrorStream();
        String text = readAll(input);
        connection.disconnect();
        return new HttpResult(status, text);
    }

    private HttpResult get(String url, int timeout) throws Exception {
        if (url == null || !url.toLowerCase(Locale.ROOT).startsWith("https://")) {
            throw new IllegalArgumentException("url must use https");
        }
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        connection.setRequestMethod("GET");
        connection.setConnectTimeout(Math.min(timeout, 20_000));
        connection.setReadTimeout(timeout);
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("User-Agent", "HealthyDietTracker-Android/1.0");
        int status = connection.getResponseCode();
        InputStream input = status >= 200 && status < 300
                ? connection.getInputStream()
                : connection.getErrorStream();
        String text = readAll(input);
        connection.disconnect();
        return new HttpResult(status, text);
    }

    private static String readAll(InputStream input) throws Exception {
        if (input == null) {
            return "";
        }
        try (InputStream stream = input;
             ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
            byte[] chunk = new byte[8192];
            int read;
            int total = 0;
            while ((read = stream.read(chunk)) != -1) {
                total += read;
                if (total > MAX_RESPONSE_BYTES) {
                    throw new IOException("response exceeds size limit");
                }
                buffer.write(chunk, 0, read);
            }
            return buffer.toString("UTF-8");
        }
    }

    private static String chatUrl(String endpoint) {
        String base = endpoint == null ? "" : endpoint.trim();
        if (!base.toLowerCase(Locale.ROOT).startsWith("https://")) {
            throw new IllegalArgumentException("endpoint must use https");
        }
        if (base.endsWith("/chat/completions")) {
            return base;
        }
        while (base.endsWith("/")) {
            base = base.substring(0, base.length() - 1);
        }
        return base + "/chat/completions";
    }

    private static String reasonFor(int status) {
        if (status == 401 || status == 403) return "auth";
        if (status == 402) return "insufficient_balance";
        if (status == 404) return "not_found";
        if (status == 429) return "rate_limited";
        if (status >= 500) return "provider_5xx";
        return "provider_4xx";
    }

    private static String messageFor(int status) {
        if (status == 401 || status == 403) return "API Key 无效或没有权限。";
        if (status == 402) return "账户余额不足。";
        if (status == 404) return "API 地址或模型不存在，请检查设置。";
        if (status == 429) return "请求过于频繁，请稍后重试。";
        if (status >= 500) return "AI 服务暂时不可用，请稍后重试。";
        return "AI 服务拒绝了请求，请检查 API 地址与模型。";
    }

    private static String errorPayload(String reason, int status, String message, String body) {
        try {
            JSONObject error = new JSONObject();
            error.put("reason", reason);
            error.put("status", status);
            error.put("message", message);
            if (body != null && !body.isEmpty()) {
                error.put("body", body.length() > 600 ? body.substring(0, 600) : body);
            }
            return error.toString();
        } catch (Exception ignored) {
            return "{\"reason\":\"unknown\",\"message\":\"请求失败\"}";
        }
    }

    private static String safeMessage(Exception error) {
        String message = error.getMessage();
        if (message == null || message.isEmpty()) {
            return error.getClass().getSimpleName();
        }
        return message.length() > 200 ? message.substring(0, 200) : message;
    }

    private void dispatch(String requestId, boolean ok, String payload, boolean testOnly) {
        dispatchTo(testOnly ? "__hdtNativeAiTest" : "__hdtNativeAiResult", requestId, ok, payload);
    }

    private void dispatchTo(String callback, String requestId, boolean ok, String payload) {
        if (closed.get() || webView == null) {
            return;
        }
        String script = "window." + callback + "(" + JSONObject.quote(requestId) + ","
                + (ok ? "true" : "false") + "," + JSONObject.quote(payload) + ");";
        activity.runOnUiThread(() -> {
            if (webView != null) {
                webView.evaluateJavascript(script, null);
            }
        });
    }

    public void shutdown() {
        closed.set(true);
        executor.shutdownNow();
    }
}
