"""Gemini LLM metadata enrichment client.

Generates Netflix-style metadata:
- Catchphrase: Dramatic, movie-style teaser
- Synopsis: ~100 Japanese characters summarizing the tension without heavy spoilers
- Mood tags: Array of 2-5 thematic tags (e.g. ['#極限の心理戦', '#過酷', '#逃亡劇'])

Enforces strict error handling and graceful fallbacks when the LLM is unavailable.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EnrichmentResult(BaseModel):
    """Pydantic schema for structured Gemini LLM output."""

    catchphrase: str = Field(
        ...,
        description="High-impact Netflix-style Japanese catchphrase (max 40 characters)",
    )
    synopsis: str = Field(
        ...,
        description="Concise Japanese synopsis of around 100 characters emphasizing tension",
    )
    mood_tags: List[str] = Field(
        ...,
        description="2 to 5 thematic hashtags e.g. ['#極限の心理戦', '#過酷']",
    )


class MetadataEnricher:
    """Client for generating video metadata using Google Gemini API."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        if not api_key or api_key.startswith("your_"):
            raise ValueError("Invalid Gemini API key provided.")
        self._api_key = api_key
        self.model_name = model_name
        self._client = None

    def _get_client(self):
        """Lazy-initialize Google GenAI client."""
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except Exception as e:
                logger.error("Failed to initialize Google GenAI Client: %s", e)
                raise
        return self._client

    def enrich_video_metadata(
        self,
        title: str,
        description: str,
    ) -> EnrichmentResult:
        """Call Gemini to extract catchphrase, synopsis, and mood tags.

        Falls back gracefully if the API fails, ensuring batch pipeline never crashes.
        """
        # Trim description to 1500 chars to avoid prompt bloat and unnecessary token cost
        clean_desc = (description or "").strip()[:1500]

        prompt = (
            "あなたはNetflixのクリエイティブ・ディレクターです。"
            "YouTubeクリエイター「だいにぐるーぷ」の大型企画動画のタイトルと概要欄から、"
            "視聴者を強烈に惹きつけるNetflix風の番組メタデータを生成してください。\n\n"
            f"【動画タイトル】:\n{title}\n\n"
            f"【動画概要】:\n{clean_desc}\n\n"
            "以下のJSONスキーマに従って厳密にJSON形式のみで出力してください:\n"
            "{\n"
            '  "catchphrase": "劇的で緊迫感のあるキャッチコピー（40文字以内）",\n'
            '  "synopsis": "緊張感とストーリー展開を伝えるあらすじ（100文字前後、ネタバレ厳禁）",\n'
            '  "mood_tags": ["#極限の心理戦", "#過酷", "#逃走劇 など2〜4個のハッシュタグ"]\n'
            "}"
        )

        try:
            client = self._get_client()
            # Call using standard SDK
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": EnrichmentResult,
                    "temperature": 0.7,
                },
            )

            response_text = response.text.strip()
            # Clean possible markdown block
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            parsed = json.loads(response_text.strip())
            return EnrichmentResult(**parsed)

        except Exception as e:
            logger.warning(
                "Gemini metadata enrichment failed for title '%s': %s. Using heuristic fallback.",
                title[:30],
                e,
            )
            return self.generate_fallback_enrichment(title, description)

    @staticmethod
    def generate_fallback_enrichment(title: str, description: str) -> EnrichmentResult:
        """Heuristic fallback generation when LLM is unavailable or encounters an error."""
        # Simple tag heuristic
        tags = ["#大型企画"]
        lowered = (title + " " + (description or "")).lower()

        if any(w in lowered for w in ("心理戦", "騙", "嘘", "人狼", "詐欺")):
            tags.append("#極限の心理戦")
        if any(w in lowered for w in ("逃亡", "鬼ごっこ", "追跡", "逮捕", "警察")):
            tags.append("#逃亡劇")
        if any(w in lowered for w in ("1週間", "無人島", "樹海", "過酷", "生活", "サバイバル")):
            tags.append("#過酷サバイバル")
        if any(w in lowered for w in ("検証", "実験", "潜入", "調査")):
            tags.append("#潜入ドキュメンタリー")

        if len(tags) == 1:
            tags.append("#だいにぐるーぷ")

        # Catchphrase fallback
        catchphrase = f"だいにぐるーぷが仕掛ける、本気の大型エンターテインメント。"
        if "【" in title and "】" in title:
            # Extract bracket title
            series_name = title.split("【")[1].split("】")[0]
            catchphrase = f"究極のリアルが交錯する、『{series_name}』の記録。"

        # Synopsis fallback
        synopsis_snippet = (description or "").strip().replace("\n", " ")[:90]
        if not synopsis_snippet:
            synopsis_snippet = f"だいにぐるーぷによる傑作企画「{title}」。緊迫の展開と予測不能な結末が待ち受ける。"
        else:
            synopsis_snippet = synopsis_snippet + "…"

        return EnrichmentResult(
            catchphrase=catchphrase[:40],
            synopsis=synopsis_snippet[:120],
            mood_tags=tags[:4],
        )
