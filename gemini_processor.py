"""
Gemini processor for rewriting scraped descriptions using a prompt template file.
"""
from pathlib import Path


class GeminiDescriptionProcessor:
    """Rewrite descriptions with Gemini using the configured prompt template."""

    FALLBACK_MODELS = (
        'models/gemini-2.0-flash',
        'models/gemini-2.5-flash',
        'models/gemini-flash-latest',
    )

    def __init__(self, api_key, model_name, prompt_file='title_prompt.txt'):
        self.api_key = api_key
        self.model_name = self._normalize_model_name(model_name)
        self.prompt_file = prompt_file
        self.enabled = False
        self.error = None
        self.base_prompt = self._load_prompt(prompt_file)
        self._genai = None
        self._model = None

        if not self.api_key:
            self.error = 'Missing GEMINI_API_KEY'
            return

        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._genai = genai
            self._model = genai.GenerativeModel(self.model_name)
            self.enabled = True
        except Exception as exc:
            self.error = f'Gemini initialization failed: {exc}'

    def _load_prompt(self, prompt_file):
        prompt_path = Path(prompt_file)
        if not prompt_path.exists():
            print(f"Prompt file '{prompt_file}' not found. Using fallback prompt.")
            return 'Rewrite the following product description. Return only the final cleaned description.'

        content = prompt_path.read_text(encoding='utf-8').strip()
        if not content:
            return 'Rewrite the following product description. Return only the final cleaned description.'
        return content

    @staticmethod
    def _normalize_model_name(model_name):
        if not model_name:
            return 'models/gemini-2.0-flash'
        if model_name.startswith('models/'):
            return model_name
        return f'models/{model_name}'

    def _switch_to_fallback_model(self):
        for candidate in self.FALLBACK_MODELS:
            if candidate == self.model_name:
                continue
            try:
                self._model = self._genai.GenerativeModel(candidate)
                self.model_name = candidate
                print(f"Switched Gemini model fallback to: {candidate}")
                return True
            except Exception:
                continue
        return False

    def rewrite_description(self, description):
        """Rewrite a single description string using Gemini."""
        if not description:
            return description

        if not self.enabled:
            return description

        prompt = (
            f"{self.base_prompt}\n\n"
            "Product description:\n"
            f"{description}\n\n"
            "Return only the rewritten description text."
        )

        try:
            response = self._model.generate_content(prompt)
            rewritten = (getattr(response, 'text', None) or '').strip()
            return rewritten if rewritten else description
        except Exception as exc:
            error_message = str(exc)
            if 'not found' in error_message or 'not supported' in error_message:
                if self._switch_to_fallback_model():
                    try:
                        response = self._model.generate_content(prompt)
                        rewritten = (getattr(response, 'text', None) or '').strip()
                        return rewritten if rewritten else description
                    except Exception as retry_exc:
                        print(f"Gemini rewrite failed after fallback: {retry_exc}")
                        return description

            print(f"Gemini rewrite failed: {exc}")
            return description
