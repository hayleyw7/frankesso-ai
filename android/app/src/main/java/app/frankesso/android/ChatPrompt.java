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
    private static final String IDENTITY = "I’m Frankesso, an offline chat assistant.";
    private final Deque<String> turns = new ArrayDeque<>();

    static String capabilityReply(String input) {
        return switch (normalize(input)) {
            case "who are you", "what are you", "what is your name", "what's your name",
                    "who is frankesso" -> IDENTITY;
            case "are you able to access files on my phone", "can you access files on my phone",
                    "can you read files on my phone", "can you access my files" ->
                    "I don’t have access to your personal files.";
            default -> null;
        };
    }

    static final String COUNTRY_CLARIFICATION = "Which country do you mean?";
    private static final String CANNOT_VERIFY_PRESIDENT =
            "I can’t verify who currently holds that office offline.";
    private static final Pattern CURRENT_PRESIDENT = Pattern.compile(
            "who (?:is the |'s the |is |'s )(?:current )?president(?: of (?:the )?([\\p{L}\\p{M} .’-]+?))?(?: now| today)?[?!.]*",
            Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE);
    private static final Pattern DATED_PRESIDENT = Pattern.compile(
            "(.{1,120}?) dated ([a-z]+ [0-9]{1,2}, [0-9]{4}) lists ([\\p{L}\\p{M} .’-]{1,65}) as president\\.\\s*(.+)",
            Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE);

    String clarificationReply(String input) {
        String question = normalize(input).replaceFirst("^who's ", "who is ");
        var dated = DATED_PRESIDENT.matcher(input.trim());
        if (dated.matches()) {
            var query = CURRENT_PRESIDENT.matcher(normalize(dated.group(4)).replaceFirst("^who's ", "who is "));
            // Quote the user's statement only when it names the same jurisdiction in both clauses.
            if (query.matches() && query.group(1) != null
                    && (" " + dated.group(1).toLowerCase(Locale.ROOT) + " ").contains(" " + query.group(1) + " ")) {
                try {
                    var date = java.time.LocalDate.parse(dated.group(2), LONG_DATE.withResolverStyle(java.time.format.ResolverStyle.STRICT));
                    return "The source you supplied lists " + dated.group(3) + " as president as of "
                            + LONG_DATE.format(date) + ". " + CANNOT_VERIFY_PRESIDENT;
                } catch (java.time.format.DateTimeParseException ignored) {
                    return CANNOT_VERIFY_PRESIDENT;
                }
            }
        }
        var current = CURRENT_PRESIDENT.matcher(question);
        if (!current.matches() || question.matches(".*\\b(?:in|during|after|before|under|when|was|were)\\b.*")) return null;
        if (current.group(1) != null || !turns.isEmpty()) return CANNOT_VERIFY_PRESIDENT;
        return COUNTRY_CLARIFICATION;
    }

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

    private static String normalize(String input) {
        return input.trim().toLowerCase(Locale.ROOT).replace('’', (char) 39)
                .replaceAll("\\s+", " ").replaceFirst("[?!.]+$", "")
                .replaceFirst("^whats ", "what's ").replaceFirst("^whos ", "who's ")
                .replaceFirst(" (?:right now|currently)$", "");
    }

    static String deviceClockReply(String input, LocalDateTime local, boolean use24Hour) {
        String question = normalize(input);
        return switch (question) {
            case "what is today's date", "what's today's date", "what is the date", "what's the date",
                    "what is the date today", "what's the date today", "what day is it",
                    "what day is it today", "today's date", "what is today" ->
                    "Today is " + LONG_DATE.format(local) + ".";
            case "what year is it", "what is the current year", "what's the current year", "current year" ->
                    "The current year is " + local.getYear() + ".";
            case "what time is it", "what is the time", "what's the time", "what time exactly",
                    "what time is it exactly", "what is the current time", "what's the current time",
                    "current time", "what time is it now", "tell me the time", "tell me the current time",
                    "what is my local time", "what's my local time", "can you tell me the time",
                    "can you tell me what time it is", "i want the literal exact time",
                    "tell me the exact time", "i want the exact time", "what is the exact time" ->
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
        String system = "Answer directly and briefly. If unsure, say so. Do not invent facts. "
                + "You are offline and have no tools or location access. "
                + "The device's local date is " + LONG_DATE.format(local)
                + ". Its local time is " + clockTime(local, use24Hour) + ". "
                + "For current facts, use only a reliable dated source supplied in chat. Say what the source says as of its date and that you cannot verify whether it is still current. If there is no source, say you cannot verify. "
                + "Device date is not a source date. Never invent source dates or last updates. A scheduled term date does not prove who serves now. "
                + "For “what does X feel like?”, summarize what people report, not firsthand experience. "
                + "Use the shown clock format without rounding. Spell dates Month D, YYYY. Default to US customary first with metric in parentheses, e.g. 6 ft (1.83 m), 68°F (20°C). Preserve requested or safety-critical source units.";
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
