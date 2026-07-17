#!/usr/bin/env python3
"""Test configured OpenAI-compatible LLM API key validity.

Usage:
    conda activate reachy_mini_env
    cd /path/to/clawbody-minimax
    python test_minimax_key.py

Reads MINIMAX_* variables from .env for historical compatibility.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def test_key(api_key: str, base_url: str, model: str, label: str) -> bool:
    """Test a specific key + base_url + model combination."""
    logger.info("Testing %s...", label)
    logger.info("  Key: configured (length: %d)", len(api_key))
    logger.info("  URL: %s", base_url)
    logger.info("  Model: %s", model)

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10,
        )
        text = response.choices[0].message.content
        logger.info("  SUCCESS! Response: %s", text)
        return True

    except Exception as e:
        logger.error("  FAILED: %s", e)
        return False


async def main():
    """Run configured LLM key diagnostics."""
    logger.info("=" * 60)
    logger.info("OpenAI-Compatible LLM API Key Diagnostic Tool")
    logger.info("=" * 60)
    logger.info("")

    api_key = os.getenv("MINIMAX_API_KEY", "")
    base_url = os.getenv("MINIMAX_BASE_URL", "")
    model = os.getenv("MINIMAX_MODEL", "")
    if not api_key:
        logger.error("MINIMAX_API_KEY not found in .env")
        return
    if not base_url:
        logger.error("MINIMAX_BASE_URL not found in .env")
        return
    if not model:
        logger.error("MINIMAX_MODEL not found in .env")
        return

    logger.info("Key from .env: configured (length: %d)", len(api_key))
    logger.info("")

    success = await test_key(api_key, base_url, model, ".env configuration")

    logger.info("=" * 60)
    logger.info("Result Summary")
    logger.info("=" * 60)
    logger.info("%s: .env configuration", "PASS" if success else "FAIL")

    if not success:
        logger.info("")
        logger.info("The configured LLM request failed. Possible causes:")
        logger.info("1. API key is invalid or expired")
        logger.info("2. BASE_URL does not match the provider's OpenAI-compatible endpoint")
        logger.info("3. MODEL is unavailable in the provider account or region")
        logger.info("4. Account doesn't have model service access enabled")


if __name__ == "__main__":
    asyncio.run(main())
