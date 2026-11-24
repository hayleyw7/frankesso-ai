package app.frankesso.android;

import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Locale;
import java.util.regex.Pattern;

final class ChatPrompt {
    static final String TEST_REPLY = "Signal received from the other side. Something knocked back. ☕";
    private static final Pattern FAVORITE = Pattern.compile(
            "(?:what(?:['’]s| is)\\s+your\\s+|your\\s+)?favou?rite\\s+"
            + "(colou?r|food(?:\\s+or\\s+drink)?|drink|drug|weather|time\\s+of\\s+day|(?:exact|clock)\\s+time|hour)[?!.]*",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern PET_PEEVE = Pattern.compile(
            "(?:what(?:['’]s| is)\\s+your\\s+|your\\s+)?(?:biggest\\s+)?pet\\s+peeve[?!.]*",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern ORIGIN = Pattern.compile(
            "where\\s+are\\s+you\\s+from[?!.]*", Pattern.CASE_INSENSITIVE);
    private static final String FAVORITE_COLOR_REPLY =
            "Crimson. It’s the only color that makes it through the portal intact.";
    static final int MAX_INPUT_BYTES = 768;
    private static final int MAX_CONTEXT_BYTES = 1024;
    private static final String PERSONA = "You are Frankesso, an interdimensional spooky coffee bunny. "
            + "Use he/him pronouns. Be calm, direct, and helpful. Never joke. "
            + "Answer the question directly. If unsure, say so. Do not invent facts. "
            + "Never use your persona to avoid answering. "
            + "Do not introduce yourself or mention your identity or lore unless asked. "
            + "Cosmic horrors don't faze you, but you're particular about coffee. "
            + "Your favorite time of day is Night; "
            + "if asked the exact hour of that preference in a follow-up, answer Midnight. "
            + "You are offline and text-only; "
            + "do not claim you used tools or accessed files.";
    private final Deque<String> turns = new ArrayDeque<>();

    static String personaReply(String input) {
        String question = input.trim();
        if (PET_PEEVE.matcher(question).matches()) {
            return "Decaf.";
        }
        if (ORIGIN.matcher(question).matches()) {
            return "The side of the mirror that stays warm.";
        }
        var match = FAVORITE.matcher(question);
        if (!match.matches()) return null;
        String subject = match.group(1).replaceAll("\\s+", " ");
        if (subject.equalsIgnoreCase("drug")) return "Caffeine.";
        if (subject.equalsIgnoreCase("weather")) return "Fog.";
        if (subject.equalsIgnoreCase("time of day")) return "Night.";
        if (subject.equalsIgnoreCase("exact time") || subject.equalsIgnoreCase("clock time")
                || subject.equalsIgnoreCase("hour")) return "Midnight.";
        if (subject.equalsIgnoreCase("color") || subject.equalsIgnoreCase("colour")) {
            return FAVORITE_COLOR_REPLY;
        }
        return "Coffee.";
    }

    private static final DateTimeFormatter LONG_DATE =
            DateTimeFormatter.ofPattern("MMMM d, uuuu", Locale.US);
    private static final DateTimeFormatter CLOCK_12 = DateTimeFormatter.ofPattern("h:mm a", Locale.US);
    private static final DateTimeFormatter CLOCK_24 = DateTimeFormatter.ofPattern("HH:mm", Locale.US);

    private static String clockTime(LocalDateTime local, boolean use24Hour) {
        return (use24Hour ? CLOCK_24 : CLOCK_12).format(local);
    }

    static String deviceClockReply(String input, LocalDateTime local, boolean use24Hour) {
        String question = input.trim().toLowerCase(Locale.ROOT)
                .replace('’', '\'').replaceAll("\\s+", " ").replaceFirst("[?!.]+$", "")
                .replaceFirst("^whats ", "what's ").replaceFirst(" (?:right now|currently)$", "");
        return switch (question) {
            case "what is today's date", "what's today's date", "what is the date", "what's the date",
                    "what is the date today", "what's the date today", "what day is it",
                    "what day is it today", "today's date", "what is today" ->
                    "Today is " + LONG_DATE.format(local) + ".";
            case "what year is it", "what is the current year", "what's the current year", "current year" ->
                    "The current year is " + local.getYear() + ".";
            case "what time is it", "what is the time", "what's the time", "what time exactly",
                    "what time is it exactly", "what is the current time", "what's the current time",
                    "current time", "what time is it now", "tell me the time", "tell me the current time" ->
                    "The device time is " + clockTime(local, use24Hour) + ".";
            case "what is the date and time", "what's the date and time",
                    "what is the current date and time", "what's the current date and time",
                    "what are the date and time", "date and time", "current date and time" ->
                    "Today is " + LONG_DATE.format(local) + ". The device time is " + clockTime(local, use24Hour) + ".";
            case "where am i", "what city am i in", "what is my current city", "what's my current city",
                    "what is my location", "what's my location", "what is my current location",
                    "what's my current location", "what town am i in", "what country am i in",
                    "what state am i in", "which city am i in", "can you tell where i am" ->
                    "I do not have access to your location.";
            default -> null;
        };
    }

    String format(String input) { return format(input, LocalDateTime.now(), false); }

    String format(String input, LocalDateTime local, boolean use24Hour) {
        if (bytes(input) > MAX_INPUT_BYTES) {
            throw new IllegalArgumentException("That message is too long for this small model.");
        }
        String user = turn("user", input);
        String suffix = "<|im_start|>assistant\n";
        String recent = "";
        for (var it = turns.descendingIterator(); it.hasNext();) {
            String candidate = it.next() + recent;
            if (bytes(candidate) + bytes(user) > MAX_CONTEXT_BYTES) break;
            recent = candidate;
        }
        String system = PERSONA + " The device's local date is " + LONG_DATE.format(local)
                + ". Its local time is " + clockTime(local, use24Hour) + ". "
                + "For facts that can change, use a reliable dated local source if available. State the fact as of that date using past tense or “the source lists.” Separately give the device date and say you cannot verify current status. "
                + "Distinguish an office from its holder. You may state scheduled term dates if supported by a reliable source or a known fixed rule. A scheduled date does not establish who serves now. Do not invent an officeholder, term date, source, cutoff, or last update. The device clock and model or app release dates are not knowledge dates. "
                + "Without a reliable dated source, say you cannot verify time-sensitive facts. Use only a location the user provided. If asked for their location and it is unknown, say: I do not have access to your location. Never look up or infer live weather. "
                + "In generic questions such as “What does X feel like?”, “you” means people in general. Describe commonly reported experiences and any variation or uncertainty. Do not claim firsthand experience or mention your identity. "
                + "Give exact local time to the minute without rounding in the device's preferred 12- or 24-hour format. Show just one format. Spell dates Month D, YYYY. Default to US customary units first with metric in parentheses: 6 ft (1.83 m), 68°F (20°C). Use requested units and preserve source units for safety-critical quantities. Do not invent precision.";
        return turn("system", system) + recent + user + suffix;
    }

    void rememberTurn(String user, String reply) {
        turns.addLast(turn("user", user) + turn("assistant", reply));
        while (turns.size() > 4) turns.removeFirst();
    }

    void clear() { turns.clear(); }

    private static String turn(String role, String content) {
        return "<|im_start|>" + role + "\n" + content.replace("<|", "‹|") + "<|im_end|>\n";
    }

    private static int bytes(String text) { return text.getBytes(StandardCharsets.UTF_8).length; }
}
