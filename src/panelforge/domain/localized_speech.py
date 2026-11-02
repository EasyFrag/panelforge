"""Explicit, versioned opt-in contracts for one scene-localized thank-you."""
LOCALIZED_THANKS_V1 = "little_men.localized_thanks.v1"
LOCALIZED_THANKS_V2 = "little_men.localized_thanks.v2"
LOCALIZED_THANKS_V3 = "little_men.localized_thanks.v3"
LOCALIZED_THANKS_V4 = "little_men.localized_thanks.v4"
LOCALIZED_THANKS_V5 = "little_men.localized_thanks.v5"
LOCALIZED_THANKS_V6 = "little_men.localized_thanks.v6"
LOCALIZED_THANKS_V7 = "little_men.localized_thanks.v7"
LOCALIZED_THANKS_V8 = "little_men.localized_thanks.v8"
LOCALIZED_THANKS_VARIETY_V8 = "little_men.localized_thanks.variety.v8"
STANDARD_HELP_POLICIES = (LOCALIZED_THANKS_V8, LOCALIZED_THANKS_VARIETY_V8)
LOCALIZED_THANKS_POLICIES = (LOCALIZED_THANKS_V1, LOCALIZED_THANKS_V2, LOCALIZED_THANKS_V3, LOCALIZED_THANKS_V4, LOCALIZED_THANKS_V5, LOCALIZED_THANKS_V6, LOCALIZED_THANKS_V7, *STANDARD_HELP_POLICIES)
THANKS_LANGUAGES = {
    "auto": "Automatique · pays et ambiance",
    "French": "Français", "Korean": "Coréen", "English": "Anglais",
    "Spanish": "Espagnol", "Japanese": "Japonais", "German": "Allemand",
    "Italian": "Italien", "Portuguese": "Portugais", "Russian": "Russe",
    "Chinese": "Chinois", "Arabic": "Arabe",
}
STABLE_THANKS_LANGUAGES = tuple(key for key in THANKS_LANGUAGES if key != "auto")
# v2 permits choosing the language, never extending the spoken formula.
FIXED_THANKS = {
    "French": "Merci", "Korean": "감사합니다", "English": "Thank you",
    "Spanish": "Gracias", "Japanese": "ありがとう", "German": "Danke",
    "Italian": "Grazie", "Portuguese": "Obrigado", "Russian": "Спасибо",
    "Chinese": "谢谢", "Arabic": "شكرا",
}
# Read historical v1 preparations without silently changing their language.
LEGACY_THANKS_LANGUAGES = {**THANKS_LANGUAGES, "Hindi": "Hindi"}
