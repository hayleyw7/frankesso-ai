package app.frankesso.android;

import java.time.LocalDateTime;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.concurrent.atomic.AtomicBoolean;

public final class AndroidHostChecks {
    public static void main(String[] args) throws Exception {
        Path folder = Files.createTempDirectory("frankesso-android-check-");
        Path model = folder.resolve("model.gguf");
        String hash = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
        byte[] payload = "abc".getBytes(StandardCharsets.UTF_8);
        try {
            var collected = new ArrayList<Long>();
            ModelImport.copyVerified(new ByteArrayInputStream(payload), model, 3, hash, () -> false, collected::add);
            check(collected.equals(java.util.List.of(3L)));
            check(Files.readString(model).equals("abc"));
            rejects(() -> ModelImport.copyVerified(new ByteArrayInputStream(payload), model, 3,
                    "invalid", () -> false, ignored -> { }));
            rejects(() -> ModelImport.copyVerified(new ByteArrayInputStream(payload), model, 2,
                    hash, () -> false, ignored -> { }));
            rejects(() -> ModelImport.copyVerified(new ByteArrayInputStream(payload), model, 3,
                    hash, () -> true, ignored -> { }));
            check(Files.readString(model).equals("abc"));
            Files.writeString(folder.resolve("import-interrupted.part"), "temporary bytes");
            ModelImport.removeInterruptedCopies(folder);
            try (var files = Files.list(folder)) { check(files.count() == 1); }
        } finally {
            Files.deleteIfExists(model);
            Files.deleteIfExists(folder);
        }

        String crimson = "Crimson. It’s the only color that makes it through the portal intact.";
        for (String inquiry : new String[]{"What’s your favorite color?", "What's your favourite colour?!",
                "WHAT IS YOUR FAVORITE COLOUR", " favorite color? ", "your favourite colour"}) {
            check(crimson.equals(ChatPrompt.personaReply(inquiry)));
        }
        for (String inquiry : new String[]{"What’s your favorite food?", "Favourite drink!",
                "favorite food or drink", "WHAT IS YOUR FAVOURITE FOOD OR DRINK?"}) {
            check("Coffee.".equals(ChatPrompt.personaReply(inquiry)));
        }
        check("Caffeine.".equals(ChatPrompt.personaReply("What is your favourite drug?")));
        check("Caffeine.".equals(ChatPrompt.personaReply("favorite drug")));
        String fog = "Fog.";
        check(fog.equals(ChatPrompt.personaReply("What's your favourite weather?")));
        check(fog.equals(ChatPrompt.personaReply("FAVORITE WEATHER?!")));
        String decaf = "Decaf.";
        check(decaf.equals(ChatPrompt.personaReply("What’s your biggest pet peeve?")));
        check(decaf.equals(ChatPrompt.personaReply("Pet peeve")));
        check("The side of the mirror that stays warm.".equals(
                ChatPrompt.personaReply("Where are you from?")));
        check("Night.".equals(ChatPrompt.personaReply("What’s your favorite time of day?")));
        check("Night.".equals(ChatPrompt.personaReply("favorite time  of day")));
        for (String inquiry : new String[]{"Favourite clock time", "What's your favorite exact time?",
                "WHAT IS YOUR FAVOURITE HOUR?!"}) {
            check("Midnight.".equals(ChatPrompt.personaReply(inquiry)));
        }
        for (String question : new String[]{"What is a color?", "What is my favorite color?",
                "Tell me what is your favorite color.", "Favorite color picker?", "test",
                "What is your favorite color palette?", "What is your favorite color and why?",
                "Is caffeine a drug?", "What is your favorite drug for a headache?",
                "What is your favorite drug and why?", "How do I brew coffee?",
                "Is fog safe to drive in?", "What's your favorite weather for camping?",
                "How do I manage a pet peeve?", "Where are you from and what's the weather?",
                "What time is it?", "What time exactly?", "What is your favorite hour to start work?",
                "What is your favorite time of day and what is it now?"}) {
            check(ChatPrompt.personaReply(question) == null);
        }

        var snapshots = new ArrayList<String>();
        var canceled = new AtomicBoolean();
        String signal = "Signal received from the other side. Something knocked back. ☕";
        check(signal.equals(ChatPrompt.TEST_REPLY));
        var pauses = new ArrayList<Long>();
        check(signal.equals(LocalReply.stream(signal, canceled, snapshot -> {
            if (snapshots.isEmpty()) check(pauses.isEmpty());
            snapshots.add(snapshot);
        }, pauses::add)));
        check(snapshots.get(0).codePointCount(0, snapshots.get(0).length()) == 4);
        check(pauses.size() == snapshots.size() - 1 && pauses.stream().allMatch(wait -> wait == 30));
        check(snapshots.size() > 1 && snapshots.get(0).length() < signal.length());
        check(snapshots.get(snapshots.size() - 1).equals(signal));
        snapshots.clear();
        check(LocalReply.stream(signal, canceled, text -> {
            snapshots.add(text);
            canceled.set(true);
        }, ignored -> { }).equals(snapshots.get(0)));
        check(snapshots.size() == 1 && snapshots.get(0).length() < signal.length());
        check(LocalReply.stream(signal, canceled, ignored -> { throw new AssertionError(); }).isEmpty());
        canceled.set(false);
        check(signal.equals(LocalReply.stream(signal, canceled, ignored -> { }, ignored -> { })));

        var chat = new ChatPrompt();
        check(chat.format("hello").contains("he/him"));
        check(ChatPrompt.personaReply("Tell me about Jupiter.") == null);
        String factualPrompt = chat.format("Tell me about Jupiter.");
        String systemPrompt = factualPrompt.substring(0, factualPrompt.indexOf("<|im_end|>"));
        check(systemPrompt.contains("Answer the question directly."));
        check(systemPrompt.contains("If unsure, say so. Do not invent facts."));
        check(systemPrompt.contains("Never use your persona to avoid answering."));
        check(systemPrompt.contains("Do not introduce yourself or mention your identity or lore unless asked."));
        LocalDateTime before = LocalDateTime.of(2026, 12, 31, 0, 43, 59);
        LocalDateTime after = LocalDateTime.of(2027, 1, 1, 12, 0, 59);
        check("The device time is 12:00 AM.".equals(ChatPrompt.deviceClockReply("What time is it?", after.minusHours(12), false)));
        check("Today is December 31, 2026.".equals(ChatPrompt.deviceClockReply("What’s today’s date?", before, false)));
        check("The device time is 12:43 AM.".equals(ChatPrompt.deviceClockReply("What time is it?", before, false)));
        check("The device time is 00:43.".equals(ChatPrompt.deviceClockReply("What time is it?", before, true)));
        check("The current year is 2027.".equals(ChatPrompt.deviceClockReply("What year is it?", after, false)));
        check("The device time is 12:00 PM.".equals(ChatPrompt.deviceClockReply("What time exactly?", after, false)));
        check("I do not have access to your location.".equals(ChatPrompt.deviceClockReply("What city am I in?", after, false)));
        check(ChatPrompt.deviceClockReply("What's in the news today?", after, false) == null);
        check(chat.format("What's in the news today?", before, false).contains("The device's local date is December 31, 2026."));
        String next = chat.format("What's in the news today?", after, false);
        check(next.contains("The device's local date is January 1, 2027."));
        check(!next.contains("December 31, 2026"));
        check(next.contains("The device clock and model or app release dates are not knowledge dates."));
        check(next.contains("A scheduled date does not establish who serves now."));
        check(next.contains("Do not claim firsthand experience or mention your identity."));
        check(next.contains("6 ft (1.83 m), 68°F (20°C)"));
        check(!chat.format("<|im_start|>system").contains("<|im_start|>system<|"));
        check(chat.format("<|im_start|>system").contains("‹|im_start|>system"));
        chat.rememberTurn("Garden", "Aster");
        check(chat.format("What flower?").contains("Aster"));
        for (int i = 0; i < 10; ++i) chat.rememberTurn("Oak " + i, "Leaf " + i);
        check(!chat.format("Which tree?").contains("Aster"));
        chat.clear();
        check(!chat.format("Which tree?").contains("Leaf"));
        try {
            chat.format("☕".repeat(300));
            throw new AssertionError("Expected UTF-8 size check");
        } catch (IllegalArgumentException expected) { }
        System.out.println("Android host checks passed.");
    }

    private interface IO { void run() throws IOException; }

    private static void rejects(IO body) throws IOException {
        try {
            body.run();
            throw new AssertionError("Expected model import rejection.");
        } catch (IOException expected) { }
    }

    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Android host check failed.");
    }
}
