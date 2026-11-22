package app.frankesso.android;

import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.function.BooleanSupplier;
import java.util.function.LongConsumer;

final class ModelImport {
    static final long MODEL_BYTES = 491_400_032L;
    static final String MODEL_SHA256 = "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db";

    private ModelImport() { }

    static void copyVerified(InputStream source, Path destination, long size, String sha256,
            BooleanSupplier canceled, LongConsumer progress) throws IOException {
        Path temporary = Files.createTempFile(destination.getParent(), "import-", ".part");
        try {
            MessageDigest sha = sha256();
            long total = 0;
            byte[] data = new byte[256 * 1024];
            try (FileOutputStream output = new FileOutputStream(temporary.toFile())) {
                while (true) {
                    if (canceled.getAsBoolean()) throw new IOException("Model setup canceled.");
                    int n = source.read(data);
                    if (n < 0) break;
                    if (n > size - total) throw invalidModel();
                    sha.update(data, 0, n);
                    output.write(data, 0, n);
                    total += n;
                    progress.accept(total);
                }
                if (total != size || !hex(sha.digest()).equals(sha256)) throw invalidModel();
                output.getFD().sync();
            }
            if (canceled.getAsBoolean()) throw new IOException("Model setup canceled.");
            Files.move(temporary, destination, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } finally {
            Files.deleteIfExists(temporary);
        }
    }

    static void removeInterruptedCopies(Path directory) throws IOException {
        try (var stale = Files.newDirectoryStream(directory, "import-*.part")) {
            for (Path file : stale) Files.deleteIfExists(file);
        }
    }

    static boolean isVerified(Path file, BooleanSupplier canceled) throws IOException {
        if (!Files.isRegularFile(file) || Files.size(file) != MODEL_BYTES) return false;
        MessageDigest sha = sha256();
        byte[] bytes = new byte[256 * 1024];
        try (InputStream input = Files.newInputStream(file)) {
            int n;
            while ((n = input.read(bytes)) >= 0) {
                if (canceled.getAsBoolean()) return false;
                sha.update(bytes, 0, n);
            }
        }
        return hex(sha.digest()).equals(MODEL_SHA256);
    }

    private static IOException invalidModel() {
        return new IOException("The bundled Qwen2.5 Instruct model did not pass its integrity check.");
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is unavailable.", e);
        }
    }

    private static String hex(byte[] bytes) {
        char[] chars = new char[2 * bytes.length];
        String digits = "0123456789abcdef";
        for (int i = 0; i < bytes.length; i++) {
            chars[2 * i] = digits.charAt((bytes[i] & 255) >>> 4);
            chars[2 * i + 1] = digits.charAt(bytes[i] & 15);
        }
        return new String(chars);
    }
}
