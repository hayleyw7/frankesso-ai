package app.frankesso.android;

import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

/** Model ownership stays on one worker; cancellation is safe from the UI thread. */
final class NativeModel {
    static { System.loadLibrary("frankesso"); }

    private static final int REPLY_TIMEOUT_MS = 60_000;
    private long handle;

    synchronized void open(String file) {
        if (handle == 0) handle = nativeOpen(file);
    }

    String reply(String prompt, AtomicBoolean canceled, Consumer<String> progress) throws TimeoutException {
        return reply(prompt, canceled, progress, REPLY_TIMEOUT_MS);
    }

    String reply(String prompt, AtomicBoolean canceled, Consumer<String> progress,
            int timeoutMillis) throws TimeoutException {
        final long session;
        synchronized (this) {
            if (handle == 0) throw new IllegalStateException("No model is loaded.");
            if (canceled.get()) return "";
            session = handle;
            nativeSetCanceled(session, false);
        }
        return new String(nativeReply(session, prompt.getBytes(StandardCharsets.UTF_8),
                new ReplySink(progress), timeoutMillis), StandardCharsets.UTF_8).trim();
    }

    synchronized void cancel() {
        if (handle != 0) nativeSetCanceled(handle, true);
    }

    synchronized void close() {
        if (handle != 0) {
            nativeClose(handle);
            handle = 0;
        }
    }

    private static final class ReplySink {
        private final Consumer<String> progress;

        ReplySink(Consumer<String> progress) { this.progress = progress; }

        @SuppressWarnings("unused") // Called by the native decoder.
        void onBytes(byte[] bytes) {
            // Tokens may split a multi-byte character. Ignore any incomplete ending until the
            // next cumulative snapshot rather than briefly drawing a replacement character.
            var decoder = StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPLACE)
                    .onUnmappableCharacter(CodingErrorAction.REPLACE);
            CharBuffer text = CharBuffer.allocate(bytes.length);
            decoder.decode(ByteBuffer.wrap(bytes), text, false);
            text.flip();
            String value = text.toString().trim();
            if (!value.isEmpty()) progress.accept(value);
        }
    }

    private static native long nativeOpen(String path);
    private static native byte[] nativeReply(long handle, byte[] prompt, ReplySink sink, int timeoutMillis)
            throws TimeoutException;
    private static native void nativeSetCanceled(long handle, boolean canceled);
    private static native void nativeClose(long handle);
}
