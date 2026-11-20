package com.hdt.diettracker;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.security.Key;
import java.security.KeyStore;
import java.util.regex.Pattern;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * Minimal secret store backed by a non-exportable Android Keystore AES key.
 *
 * <p>Only the ciphertext (IV + GCM output, Base64) is written to SharedPreferences, so a
 * backup, adb pull of the data directory, or a plaintext-localStorage leak cannot reveal the
 * API keys. The key itself never leaves the Keystore (hardware-backed where available).
 */
final class SecureStore {

    private static final String PREFS = "hdt_secure";
    private static final String KEY_ALIAS = "hdt_secrets_v1";
    private static final String TRANSFORMATION = "AES/GCM/NoPadding";
    private static final int GCM_TAG_BITS = 128;
    private static final int GCM_IV_BYTES = 12;
    private static final int MAX_VALUE_CHARS = 4096;
    private static final Pattern NAME = Pattern.compile("[A-Za-z0-9._-]{1,64}");

    private SecureStore() {
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    /** Keep preference keys predictable so JS cannot inject arbitrary names. */
    static boolean isValidName(String name) {
        return name != null && NAME.matcher(name).matches();
    }

    /** Empty value deletes the entry. Returns true when the store accepted the write. */
    static boolean put(Context context, String name, String value) {
        if (context == null || !isValidName(name)) {
            return false;
        }
        try {
            if (value == null || value.isEmpty()) {
                return prefs(context).edit().remove(name).commit();
            }
            if (value.length() > MAX_VALUE_CHARS) {
                return false;
            }
            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey());
            byte[] iv = cipher.getIV();
            if (iv == null || iv.length != GCM_IV_BYTES) {
                return false;
            }
            byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
            String payload = Base64.encodeToString(iv, Base64.NO_WRAP)
                    + ":" + Base64.encodeToString(encrypted, Base64.NO_WRAP);
            return prefs(context).edit().putString(name, payload).commit();
        } catch (Exception error) {
            return false;
        }
    }

    /** Returns "" when the entry is missing, the Keystore key was lost, or decryption fails. */
    static String get(Context context, String name) {
        if (context == null || !isValidName(name)) {
            return "";
        }
        String payload = prefs(context).getString(name, null);
        if (payload == null || payload.isEmpty()) {
            return "";
        }
        int split = payload.indexOf(':');
        if (split <= 0 || split == payload.length() - 1) {
            return "";
        }
        try {
            byte[] iv = Base64.decode(payload.substring(0, split), Base64.NO_WRAP);
            byte[] encrypted = Base64.decode(payload.substring(split + 1), Base64.NO_WRAP);
            if (iv.length != GCM_IV_BYTES) {
                return "";
            }
            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(),
                    new GCMParameterSpec(GCM_TAG_BITS, iv));
            return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
        } catch (Exception error) {
            return "";
        }
    }

    static void remove(Context context, String name) {
        if (context == null || !isValidName(name)) {
            return;
        }
        prefs(context).edit().remove(name).commit();
    }

    private static SecretKey getOrCreateKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
        keyStore.load(null);
        Key existing = keyStore.getKey(KEY_ALIAS, null);
        if (existing instanceof SecretKey) {
            return (SecretKey) existing;
        }
        KeyGenerator generator = KeyGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .setRandomizedEncryptionRequired(true)
                .build());
        return generator.generateKey();
    }
}
