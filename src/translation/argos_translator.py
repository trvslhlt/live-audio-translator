"""Argos Translate module for offline translation."""

try:
    import argostranslate.package
    import argostranslate.translate
except ImportError:
    argostranslate = None


class ArgosTranslator:
    """Translates text between English and French using Argos Translate."""

    LANGUAGE_PAIRS = [
        ("en", "fr"),
        ("fr", "en"),
    ]

    def __init__(self):
        """Initialize the translator."""
        if argostranslate is None:
            raise ImportError(
                "argostranslate is required. Install with: pip install argostranslate"
            )

        self._installed_languages = None

    def ensure_packages_installed(self) -> bool:
        """
        Ensure required language packages are installed.

        Returns:
            True if all packages are available, False otherwise.
        """
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()

        for from_lang, to_lang in self.LANGUAGE_PAIRS:
            if not self._is_package_installed(from_lang, to_lang):
                # Find and install the package
                package = next(
                    (
                        p
                        for p in available_packages
                        if p.from_code == from_lang and p.to_code == to_lang
                    ),
                    None,
                )
                if package:
                    argostranslate.package.install_from_path(package.download())
                else:
                    return False

        # Refresh installed languages cache
        self._installed_languages = None
        return True

    def _is_package_installed(self, from_lang: str, to_lang: str) -> bool:
        """Check if a language package is installed."""
        installed = argostranslate.package.get_installed_packages()
        return any(p.from_code == from_lang and p.to_code == to_lang for p in installed)

    def get_installed_languages(self) -> list[tuple[str, str]]:
        """Get list of installed language pairs."""
        if self._installed_languages is None:
            installed = argostranslate.package.get_installed_packages()
            self._installed_languages = [(p.from_code, p.to_code) for p in installed]
        return self._installed_languages

    def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        """
        Translate text from one language to another.

        Args:
            text: Text to translate.
            from_lang: Source language code ('en' or 'fr').
            to_lang: Target language code ('en' or 'fr').

        Returns:
            Translated text.

        Raises:
            ValueError: If the language pair is not supported or installed.
        """
        if not text.strip():
            return ""

        if (from_lang, to_lang) not in self.LANGUAGE_PAIRS:
            raise ValueError(f"Unsupported language pair: {from_lang} -> {to_lang}")

        if not self._is_package_installed(from_lang, to_lang):
            raise ValueError(
                f"Language package not installed: {from_lang} -> {to_lang}. "
                "Run ensure_packages_installed() first."
            )

        translated = argostranslate.translate.translate(text, from_lang, to_lang)
        return translated

    def translate_auto(
        self, text: str, detected_lang: str, target_lang: str | None = None
    ) -> tuple[str, str]:
        """
        Translate text with automatic target language selection.

        If source is English, translates to French and vice versa.

        Args:
            text: Text to translate.
            detected_lang: Detected source language code.
            target_lang: Optional target language. If None, auto-selects opposite language.

        Returns:
            Tuple of (translated_text, target_language_code).
        """
        if not text.strip():
            return "", detected_lang

        # Normalize language codes
        source = (
            "en"
            if detected_lang.startswith("en")
            else "fr"
            if detected_lang.startswith("fr")
            else None
        )

        if source is None:
            # Unsupported language, return original
            return text, detected_lang

        if target_lang:
            target = (
                "en"
                if target_lang.startswith("en")
                else "fr"
                if target_lang.startswith("fr")
                else None
            )
        else:
            # Auto-select: translate to the other language
            target = "fr" if source == "en" else "en"

        if source == target:
            return text, target

        translated = self.translate(text, source, target)
        return translated, target
